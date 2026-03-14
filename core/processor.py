"""
Core Issue Processor for GitHub Agent V2
Coordinates all layers to process GitHub issues
"""

import os
import logging
from typing import Optional
from pathlib import Path

from core.models import (
    GitHubEvent, IssueContext, IntentResult, IntentType,
    ProcessingResult, ProcessingStatus, IssueState
)
from core.context_builder import ContextBuilder
from core.state_manager import StateManager
from core.issue_followup import IssueFollowupManager

# Import KB types for type hints
try:
    from knowledge_base import KBIntegrator
except ImportError:
    KBIntegrator = None

logger = logging.getLogger(__name__)


class IssueProcessor:
    """
    Main issue processor that coordinates all layers:
    1. Webhook -> Core (this class)
    2. Core -> Cloud Agent (intent recognition)
    3. Core -> Knowledge Base (query)
    4. Core -> Code Executor (modification)
    5. Core -> GitHub API (response)
    """
    
    def __init__(
        self,
        github_client=None,
        cloud_agent=None,
        knowledge_base=None,
        code_executor=None,
        auth_manager=None
    ):
        self.github = github_client
        self.auth_manager = auth_manager
        self.cloud_agent = cloud_agent
        self.knowledge_base = knowledge_base
        self.code_executor = code_executor
        
        self.context_builder = ContextBuilder(github_client)
        self.state_manager = StateManager()
        self.followup_manager = IssueFollowupManager()
        
        # Configuration
        self.issue_trigger_mode = os.environ.get(
            "GITHUB_AGENT_ISSUE_TRIGGER_MODE", "smart"
        )
        self.comment_trigger_mode = os.environ.get(
            "GITHUB_AGENT_COMMENT_TRIGGER_MODE", "smart"
        )
        self.confirm_mode = os.environ.get(
            "AGENT_CONFIRM_MODE", "auto"
        )
        self.auto_confirm_threshold = float(os.environ.get(
            "AGENT_AUTO_CONFIRM_THRESHOLD", "0.8"
        ))
        # Issue tracking feature switch
        self.issue_tracking_enabled = os.environ.get(
            "AGENT_ISSUE_TRACKING_ENABLED", "true"
        ).lower() in ("true", "1", "yes", "on")
    
    def _get_github_client(self, installation_id: str = None):
        """Get GitHub client for specific installation"""
        if self.github and hasattr(self.github, 'with_installation'):
            return self.github.with_installation(installation_id)
        elif self.auth_manager and installation_id:
            from github_api.github_client import GitHubClient
            return GitHubClient(self.auth_manager, installation_id)
        return self.github
    
    def process_event(self, event: GitHubEvent) -> ProcessingResult:
        """
        Main entry point for processing GitHub events
        
        Args:
            event: Parsed GitHub event
            
        Returns:
            Processing result
        """
        try:
            # Check if should process
            if not self._should_process(event):
                return ProcessingResult(
                    status=ProcessingStatus.SKIPPED,
                    issue_number=self._get_issue_number(event),
                    message="Event skipped based on trigger mode"
                )
            
            # Extract issue info
            owner, repo = self._parse_repo(event.repo_full_name)
            issue_number = self._get_issue_number(event)
            installation_id = event.installation_id
            
            if not all([owner, repo, issue_number, installation_id]):
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    issue_number=issue_number or 0,
                    error="Missing required fields"
                )
            
            logger.info(f"Processing issue #{issue_number} in {owner}/{repo}")
            
            # Build context
            context = self.context_builder.build(
                owner, repo, issue_number, installation_id, event
            )
            
            # Get state (check if processed before)
            repo_full_name = f"{owner}/{repo}"
            state = self.state_manager.get_state(repo_full_name, issue_number)
            processing_count = state.processing_count if state else 0
            
            if state:
                logger.info(f"Issue #{issue_number} has been processed {processing_count} times before")
            
            # ========== 防重复处理检查 ==========
            # 1. 检查评论 ID 是否已处理（防止 Webhook 重复发送）
            if event.event_type == "issue_comment":
                comment = event.comment or {}
                comment_id = comment.get("id")
                
                if comment_id and state and state.is_comment_processed(comment_id):
                    logger.warning(f"Comment {comment_id} already processed, skipping duplicate")
                    return ProcessingResult(
                        status=ProcessingStatus.SKIPPED,
                        issue_number=issue_number,
                        message=f"Comment {comment_id} already processed"
                    )
                
                # 记录评论 ID（如果后续处理成功会再次记录）
                if comment_id and state:
                    state.record_comment(comment_id)
                    self.state_manager.save_state(state)
            
            # 2. 检查是否在短时间内重复处理（5 秒保护窗口）
            if state and state.last_action:
                from datetime import datetime, timedelta
                time_since_last = datetime.now() - state.processed_at
                if time_since_last < timedelta(seconds=5):
                    logger.warning(f"Issue #{issue_number} processed {time_since_last.total_seconds():.1f}s ago, skipping")
                    return ProcessingResult(
                        status=ProcessingStatus.SKIPPED,
                        issue_number=issue_number,
                        message="Processing too frequent, skipped"
                    )
            
            # 3. 获取当前 Issue 状态（防止重复关闭已关闭的 Issue）
            github = self._get_github_client(installation_id)
            current_issue_state = None
            if github:
                try:
                    issue_info = github.get_issue(owner, repo, issue_number)
                    current_issue_state = issue_info.get("state", "unknown")
                    logger.info(f"Current issue #{issue_number} state: {current_issue_state}")
                    
                    # 更新状态中的 Issue 状态
                    if state:
                        state.issue_state = current_issue_state
                        self.state_manager.save_state(state)
                except Exception as e:
                    logger.warning(f"Failed to get issue state: {e}")
            
            # Check if this is a follow-up reply confirming resolution
            # This applies when:
            # 1. It's a comment event (not initial issue creation)
            # 2. User's reply contains resolution confirmation keywords
            # Note: We don't require processing_count > 0 here because:
            # - User might manually close without agent intervention
            # - Previous state might be lost
            if event.event_type == "issue_comment":
                followup_result = self._check_followup_reply(context)
                
                if followup_result is True:
                    # 检查 Issue 是否已经是关闭状态
                    if current_issue_state == "closed":
                        logger.info(f"Issue #{issue_number} is already closed, skipping")
                        # 记录评论已处理
                        if state and comment_id:
                            state.record_comment(comment_id)
                            self.state_manager.save_state(state)
                        return ProcessingResult(
                            status=ProcessingStatus.SKIPPED,
                            issue_number=issue_number,
                            message="Issue already closed"
                        )
                    
                    # Check if issue tracking is enabled
                    if not self.issue_tracking_enabled:
                        logger.info(f"Issue tracking disabled, not closing issue #{issue_number}")
                        # 仅回复确认消息，不关闭 Issue
                        if github:
                            github.create_issue_comment(
                                owner, repo, issue_number,
                                "✅ 收到您的反馈，很高兴问题已解决！\n\n（管理员已禁用自动关闭 Issue 功能，如需关闭请手动操作）"
                            )
                        # 记录评论已处理
                        if state and comment_id:
                            state.record_comment(comment_id)
                            self.state_manager.save_state(state)
                        return ProcessingResult(
                            status=ProcessingStatus.COMPLETED,
                            issue_number=issue_number,
                            message="Resolution acknowledged but auto-close is disabled"
                        )
                    
                    # User confirmed issue is resolved -> close it
                    if github:
                        self.followup_manager.close_if_resolved(owner, repo, issue_number, github)
                        self.state_manager.record_action(repo_full_name, issue_number, "closed")
                        # 记录评论已处理
                        if state and comment_id:
                            state.record_comment(comment_id)
                            self.state_manager.save_state(state)
                        return ProcessingResult(
                            status=ProcessingStatus.COMPLETED,
                            issue_number=issue_number,
                            message="Issue resolved and closed based on user confirmation"
                        )
                elif followup_result is False:
                    # User explicitly said issue is NOT resolved
                    # Reply with acknowledgment and continue normal processing
                    if github:
                        github.create_issue_comment(
                            owner, repo, issue_number,
                            "收到，我会继续跟进这个问题。请告诉我具体的错误信息或需要调整的地方。"
                        )
                    # 记录评论已处理
                    if state and comment_id:
                        state.record_comment(comment_id)
                        self.state_manager.save_state(state)
                    # Fall through to normal processing (don't return here)
                else:
                    # followup_result is None - check with fallback method
                    # This catches cases where user says "已解决" but _check_followup_reply
                    # returned None due to new_request_keywords filtering
                    if self._check_close_keywords(context.current_instruction or ""):
                        # 检查 Issue 是否已经是关闭状态
                        if current_issue_state == "closed":
                            logger.info(f"Issue #{issue_number} is already closed, skipping")
                            if state and comment_id:
                                state.record_comment(comment_id)
                                self.state_manager.save_state(state)
                            return ProcessingResult(
                                status=ProcessingStatus.SKIPPED,
                                issue_number=issue_number,
                                message="Issue already closed"
                            )
                        
                        # Check if issue tracking is enabled
                        if not self.issue_tracking_enabled:
                            logger.info(f"Issue tracking disabled, not closing issue #{issue_number}")
                            # 仅回复确认消息，不关闭 Issue
                            if github:
                                github.create_issue_comment(
                                    owner, repo, issue_number,
                                    "✅ 收到您的反馈，很高兴问题已解决！\n\n（管理员已禁用自动关闭 Issue 功能，如需关闭请手动操作）"
                                )
                            # 记录评论已处理
                            if state and comment_id:
                                state.record_comment(comment_id)
                                self.state_manager.save_state(state)
                            return ProcessingResult(
                                status=ProcessingStatus.COMPLETED,
                                issue_number=issue_number,
                                message="Resolution acknowledged but auto-close is disabled"
                            )
                        
                        logger.info("Fallback close keyword detection triggered")
                        if github:
                            self.followup_manager.close_if_resolved(owner, repo, issue_number, github)
                            self.state_manager.record_action(repo_full_name, issue_number, "closed")
                            # 记录评论已处理
                            if state and comment_id:
                                state.record_comment(comment_id)
                                self.state_manager.save_state(state)
                            return ProcessingResult(
                                status=ProcessingStatus.COMPLETED,
                                issue_number=issue_number,
                                message="Issue closed based on close keywords (fallback detection)"
                            )
            
            # Phase 2: Intent recognition (Cloud Agent)
            if self.cloud_agent:
                intent = self.cloud_agent.classify_with_history(
                    context,
                    state.intent if state else None,
                    processing_count
                )
                logger.info(f"Detected intent: {intent.intent.value} (confidence: {intent.confidence:.2f})")
                
                # Check for explicit user modification request
                if self._check_explicit_modify_request(context):
                    logger.info("User explicitly requested code modification, overriding intent to MODIFY")
                    intent = IntentResult(
                        intent=IntentType.MODIFY,
                        confidence=0.95,
                        reasoning="User explicitly requested code modification",
                        needs_research=False,
                        research_topics=[]
                    )
            else:
                # Fallback: assume modify intent
                intent = IntentResult(
                    intent=IntentType.MODIFY,
                    confidence=0.5,
                    reasoning="Cloud agent not available, defaulting to modify",
                    needs_research=False,
                    research_topics=[]
                )
            
            # Phase 2: Decision making
            if self.cloud_agent and hasattr(self.cloud_agent, 'decision_engine'):
                action_plan = self.cloud_agent.decision_engine.make_decision(
                    context.build_full_context(),
                    intent
                )
                logger.info(f"Action plan: {action_plan.action} (complexity: {action_plan.complexity})")
                
                # Check if should auto-execute
                if not self._should_auto_execute(action_plan, intent):
                    logger.info("Low confidence or manual mode, posting plan for confirmation")
                    return self._request_confirmation(
                        owner, repo, issue_number, action_plan, intent, installation_id
                    )
            else:
                # Fallback: create simple plan from intent
                from ..cloud_agent.decision_engine import ActionPlan
                action_plan = ActionPlan(
                    action="modify" if intent.intent == IntentType.MODIFY else "reply",
                    complexity="simple",
                    confidence=intent.confidence
                )
            
            # Execute based on intent and plan
            if intent.intent == IntentType.ANSWER:
                return self._handle_answer_intent(
                    owner, repo, issue_number, context, intent, state, action_plan, installation_id
                )
            elif intent.intent == IntentType.MODIFY:
                return self._handle_modify_intent(
                    owner, repo, issue_number, context, intent, state, action_plan, installation_id
                )
            elif intent.intent == IntentType.RESEARCH:
                return self._handle_research_intent(
                    owner, repo, issue_number, context, intent, state, action_plan, installation_id
                )
            elif intent.intent == IntentType.CLARIFY:
                return self._handle_clarify_intent(
                    owner, repo, issue_number, context, intent, action_plan, installation_id
                )
            else:
                return ProcessingResult(
                    status=ProcessingStatus.SKIPPED,
                    issue_number=issue_number,
                    message=f"Unknown intent: {intent.intent}"
                )
        
        except Exception as e:
            logger.exception("Failed to process issue")
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                issue_number=self._get_issue_number(event) if event else 0,
                error=str(e)
            )
    
    def _should_process(self, event: GitHubEvent) -> bool:
        """Check if event should be processed based on trigger mode"""
        # 对于评论事件，先检查是否是关闭/解决指令（这些不需要 @agent）
        if event.event_type == "issue_comment":
            comment = event.comment or {}
            body = comment.get("body", "")
            body_lower = body.lower()
            
            # 关闭/解决关键词 - 这些指令可以直接触发处理
            resolution_keywords = [
                "已解决", "解决了", "搞定", "可以关闭", "关闭吧", "没问题了",
                "可以了", "ok了", "ok", "fixed", "resolved", "close", "solved",
                "测试通过", "验证通过", "完美", "不用了", "works", "working"
            ]
            if any(kw in body_lower for kw in resolution_keywords):
                logger.info("Detected resolution keywords in comment, will process to close issue")
                return True
        
        if event.event_type == "issues":
            # Issue events
            if self.issue_trigger_mode == "auto":
                return True
            elif self.issue_trigger_mode == "smart":
                # Check if @agent in title or body
                issue = event.issue or {}
                title = issue.get("title", "")
                body = issue.get("body", "")
                return "@agent" in f"{title} {body}" or "@github-agent" in f"{title} {body}"
        
        elif event.event_type == "issue_comment":
            # Comment events
            if self.comment_trigger_mode == "all":
                return True
            elif self.comment_trigger_mode == "smart":
                # Check if @agent in comment
                comment = event.comment or {}
                body = comment.get("body", "")
                return "@agent" in body or "@github-agent" in body
        
        return False
    
    def _should_auto_execute(self, action_plan, intent: IntentResult) -> bool:
        """Determine if action should be executed automatically"""
        # Check manual mode
        if self.confirm_mode == "manual":
            return False
        
        # Check confidence threshold
        if intent.confidence < self.auto_confirm_threshold:
            return False
        
        # Check action plan confidence
        if action_plan.confidence < 0.6:
            return False
        
        # Check complexity
        if action_plan.complexity == "complex":
            return False
        
        return True
    
    def _request_confirmation(
        self, owner: str, repo: str, issue_number: int,
        action_plan, intent: IntentResult, installation_id: str
    ) -> ProcessingResult:
        """Request user confirmation before executing"""
        logger.info(f"Requesting confirmation for issue #{issue_number}")
        
        # Build confirmation message
        message = f"""🤖 我分析了这个 Issue，计划如下：

**意图识别**: {intent.intent.value}
**置信度**: {intent.confidence:.0%}
**处理方式**: {action_plan.action}
**复杂度**: {action_plan.complexity}

**计划说明**:
{action_plan.change_description or action_plan.response}

{'' if not action_plan.files_to_modify else f'**涉及文件**: {', '.join(action_plan.files_to_modify)}'}

---

请回复以下指令之一：
- `确认` 或 `执行` - 我将按此计划执行
- `修改方案` + 你的建议 - 我将调整方案
- `取消` - 不进行任何操作
        """
        
        github = self._get_github_client(installation_id)
        if github:
            github.create_issue_comment(owner, repo, issue_number, message)
        
        return ProcessingResult(
            status=ProcessingStatus.SKIPPED,
            issue_number=issue_number,
            intent=intent.intent,
            message="Waiting for user confirmation"
        )
    
    def _handle_answer_intent(
        self, owner: str, repo: str, issue_number: int,
        context: IssueContext, intent: IntentResult, state: Optional[IssueState],
        action_plan, installation_id: str
    ) -> ProcessingResult:
        """Handle answer intent - reply with explanation"""
        logger.info(f"Handling answer intent for issue #{issue_number}")
        
        # Use response from action plan if available
        if hasattr(action_plan, 'response') and action_plan.response:
            explanation = action_plan.response
        else:
            # Build explanation from previous processing if available
            explanation = "🤖 关于我的修改说明：\n\n"
            
            if state and state.pull_request_number:
                explanation += f"我之前创建了 PR #{state.pull_request_number} 来修复此问题。\n\n"
            
            explanation += f"**问题分析**: {intent.reasoning}\n\n"
            
            if state and state.files_modified:
                explanation += f"**修改的文件**: {', '.join(state.files_modified)}\n\n"
            
            explanation += "如果您认为需要调整，请告诉我具体问题（如'请使用方案B'），我会重新修改。"
        
        # Post comment
        github = self._get_github_client(installation_id)
        if github:
            github.create_issue_comment(owner, repo, issue_number, explanation)
        
        # Update state
        repo_full_name = f"{owner}/{repo}"
        self.state_manager.record_action(repo_full_name, issue_number, "answered")
        self.state_manager.save_state(IssueState(
            issue_number=issue_number,
            repo_full_name=repo_full_name,
            intent=intent.intent
        ))
        
        # Schedule follow-up check (if issue tracking is enabled)
        if self.issue_tracking_enabled:
            self.followup_manager.schedule_follow_up(owner, repo, issue_number, github)
        else:
            logger.debug(f"Issue tracking disabled, skipping follow-up scheduling for issue #{issue_number}")
        
        return ProcessingResult(
            status=ProcessingStatus.COMPLETED,
            issue_number=issue_number,
            intent=intent.intent,
            message="Replied with explanation"
        )
    
    def _handle_modify_intent(
        self, owner: str, repo: str, issue_number: int,
        context: IssueContext, intent: IntentResult, state: Optional[IssueState],
        action_plan, installation_id: str
    ) -> ProcessingResult:
        """Handle modify intent - execute code changes with KB enrichment"""
        logger.info(f"Handling modify intent for issue #{issue_number}")
        
        # Phase 3: Enrich context with knowledge base
        enriched_context = None
        if self.knowledge_base:
            logger.info("Enriching context with knowledge base...")
            try:
                enriched_context = self.knowledge_base.enrich_context(context)
                logger.info("Context enriched with KB data")
            except Exception as e:
                logger.warning(f"KB enrichment failed: {e}")
        
        # Phase 3: Query knowledge base for specific research topics
        kb_references = []
        if intent.needs_research and self.knowledge_base:
            logger.info(f"Querying knowledge base for topics: {intent.research_topics}")
            
            for topic in intent.research_topics:
                ref = self.knowledge_base.get_hardware_reference(
                    chip_name=self._extract_chip_name(topic),
                    topic=topic
                )
                if ref:
                    kb_references.append(ref)
        
        # Combine all context
        full_context = enriched_context or context.build_full_context()
        if kb_references:
            full_context += "\n\n=== 技术参考 ===\n"
            full_context += "\n".join(kb_references)
        
        # Phase 4: Execute code changes
        if not self.code_executor:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                issue_number=issue_number,
                error="Code executor not available"
            )
        
        try:
            # Get installation token
            github = self._get_github_client(installation_id)
            token = None
            if github and hasattr(github, 'get_installation_token'):
                try:
                    token = github.get_installation_token()
                    logger.info(f"✅ Got installation token for installation {str(installation_id)[:10]}...")
                except Exception as e:
                    logger.error(f"❌ Failed to get installation token: {e}")
            elif github and hasattr(github, 'auth') and github.auth:
                # Fallback to auth manager
                try:
                    token = github.auth.get_installation_token(installation_id)
                    logger.info(f"✅ Got installation token via auth manager")
                except Exception as e:
                    logger.error(f"❌ Failed to get installation token: {e}")
            else:
                logger.warning("⚠️  GitHub client not available or missing get_installation_token method")
            
            # Check if token was obtained
            if token:
                logger.info(f"✅ GitHub token obtained (length: {len(token)})")
            else:
                logger.error("❌ Failed to obtain GitHub token - code push will likely fail!")
            
            # Execute code changes
            logger.info("Executing code changes...")
            # 使用 OpenClaw 生成的详细修改描述，而不是原始 Issue 文本
            # 这样 AI 能更准确理解需要修改的位置和内容
            modification_instruction = action_plan.change_description or context.current_instruction or context.body
            logger.info(f"Using modification instruction: {modification_instruction[:100]}...")
            exec_result = self.code_executor.execute_task(
                task_type="fix_issue",
                instruction=modification_instruction,
                context=full_context,
                repo_full_name=f"{owner}/{repo}",
                issue_number=issue_number,
                github_token=token,
                files_to_modify=action_plan.files_to_modify if hasattr(action_plan, 'files_to_modify') else None
            )
            
            if exec_result.get("status") == "completed":
                # Code execution successful
                pr_number = exec_result.get("pr_number")
                pr_url = exec_result.get("pr_url")
                files_modified = exec_result.get("files_modified", [])
                branch = exec_result.get("branch", f"agent-fix-{issue_number}")
                exec_message = exec_result.get("message", "")
                
                logger.info(f"Code execution completed. PR: {pr_number}, Files: {files_modified}")
                
                # Update state - record action
                repo_full_name = f"{owner}/{repo}"
                self.state_manager.record_action(repo_full_name, issue_number, "modified")
                
                # Update PR info if available
                if pr_number and pr_url:
                    self.state_manager.update_pr_info(
                        repo_full_name, issue_number, 
                        pr_number=pr_number,
                        pr_url=pr_url,
                        branch_name=branch
                    )
                
                # Save state with files modified
                state = IssueState(
                    issue_number=issue_number,
                    repo_full_name=repo_full_name,
                    intent=intent.intent
                )
                if pr_number:
                    state.pull_request_number = pr_number
                if files_modified:
                    state.files_modified = files_modified
                self.state_manager.save_state(state)
                
                # Build reply message
                if pr_number and pr_url:
                    # PR created successfully
                    message = f"""🤖 代码修改完成

✅ 我已创建 PR #{pr_number} 来解决这个问题：
{pr_url}

**修改的文件**:
{chr(10).join([f'- `{f}`' for f in files_modified])}

请查看并确认修改是否符合预期。如果需要调整，请告诉我具体问题。"""
                else:
                    # Branch pushed but PR creation failed
                    message = f"""🤖 代码修改完成

⚠️ 我已推送代码到分支 `{branch}`，但 PR 创建失败。
{exec_message}

**修改的文件**:
{chr(10).join([f'- `{f}`' for f in files_modified])}

请手动创建 PR 或联系管理员检查 GitHub App 权限。"""
                
                # Send reply
                github = self._get_github_client(installation_id)
                if github:
                    try:
                        github.create_issue_comment(owner, repo, issue_number, message)
                        logger.info(f"✅ Reply sent to issue #{issue_number}")
                    except Exception as e:
                        logger.error(f"❌ Failed to send reply: {e}")
                else:
                    logger.error("❌ GitHub client not available, cannot send reply")
                
                # Schedule follow-up check if PR was created (and issue tracking is enabled)
                if pr_number and self.issue_tracking_enabled:
                    self.followup_manager.schedule_follow_up(owner, repo, issue_number, github)
                elif pr_number:
                    logger.debug(f"Issue tracking disabled, skipping follow-up scheduling for issue #{issue_number}")
                
                return ProcessingResult(
                    status=ProcessingStatus.COMPLETED,
                    issue_number=issue_number,
                    intent=intent.intent,
                    pr_number=pr_number,
                    message=f"PR created: #{pr_number}" if pr_number else f"Branch pushed: {branch}"
                )
            else:
                # Execution failed
                error = exec_result.get("error", "Unknown error")
                logger.error(f"Code execution failed: {error}")
                return ProcessingResult(
                    status=ProcessingStatus.FAILED,
                    issue_number=issue_number,
                    intent=intent.intent,
                    error=f"Code execution failed: {error}"
                )
        
        except Exception as e:
            logger.exception("Code execution failed")
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                issue_number=issue_number,
                error=f"Code execution failed: {e}"
            )
    
    def _extract_chip_name(self, text: str) -> str:
        """Extract chip name from text (simple heuristic)"""
        # Common chip patterns
        import re
        patterns = [
            r'(SD\d{4})',
            r'(DS\d{4})',
            r'(ESP\d{2})',
            r'(STM\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.upper())
            if match:
                return match.group(1)
        
        return "unknown"
    
    def _handle_research_intent(
        self, owner: str, repo: str, issue_number: int,
        context: IssueContext, intent: IntentResult, state: Optional[IssueState],
        action_plan, installation_id: str
    ) -> ProcessingResult:
        """Handle research intent - query knowledge base"""
        logger.info(f"Handling research intent for issue #{issue_number}")
        
        # Check if this might actually need code modification
        full_text = context.build_full_context().lower()
        code_indicators = [
            "can't", "not working", "error", "exception", "bug", "fix",
            "代码", "报错", "错误", "异常", "运行", "执行",
            "```", "def ", "class ", "import ", "function"
        ]
        has_code_context = any(indicator in full_text for indicator in code_indicators)
        
        if has_code_context:
            logger.info(f"Detected code context in research query, will provide modification guidance")
        
        # Query knowledge base directly
        kb_answer = None
        kb_source = ""
        kb_similarity = 0.0
        
        # Access KB client through knowledge_base (KBIntegrator)
        kb_client = None
        if self.knowledge_base and hasattr(self.knowledge_base, 'client'):
            kb_client = self.knowledge_base.client
        
        if kb_client:
            query = f"{context.title}\n{context.body}"
            logger.info(f"Querying KB: {query[:100]}...")
            
            try:
                kb_result = kb_client.query(query, top_k=3, generate_answer=True)
                
                if kb_result and kb_result.get('results'):
                    results = kb_result['results']
                    if results:
                        best_match = results[0]
                        kb_similarity = best_match.get('similarity', 0)
                        
                        # Use lower threshold for research queries (0.4 instead of 0.7)
                        if kb_similarity >= 0.4:
                            # Build answer from results
                            if kb_result.get('answer'):
                                kb_answer = kb_result['answer']
                            else:
                                # Build from best result text
                                kb_answer = best_match.get('text', '')[:1000]
                            
                            kb_source = best_match.get('metadata', {}).get('source', '')
                            logger.info(f"Found KB answer with similarity {kb_similarity:.2f}")
                        else:
                            logger.info(f"KB match similarity {kb_similarity:.2f} below threshold 0.4")
                else:
                    logger.info("No KB results found")
            except Exception as e:
                logger.error(f"KB query failed: {e}")
        else:
            logger.warning("KB client not available")
        
        # Build response
        if kb_answer:
            # KB found answer
            reply_parts = ["🤖 [知识库查询结果]", "", kb_answer, ""]
            
            # Add modification guidance if code context detected
            if has_code_context:
                reply_parts.extend([
                    "---",
                    "🔧 **代码修改建议**",
                    "",
                    "我注意到您的问题可能涉及代码实现。基于知识库信息，建议：",
                    "",
                    "1. 根据上述技术规格检查您的代码实现",
                    "2. 确认配置参数是否符合芯片要求",
                    "3. 如有需要，回复 `请帮我修改代码`，我可以协助生成修复代码",
                    ""
                ])
            
            reply_parts.extend([
                "---",
                f"📚 **参考文档**: {kb_source}",
                f"🎯 **匹配度**: {kb_similarity:.1%}",
                "",
                "如果以上信息未能解决您的问题，请：",
                "- 提供更多细节，我可以进一步分析",
            ])
            
            if has_code_context:
                reply_parts.append("- 或回复 `请帮我修改代码` 让我直接协助修复")
            
            reply = "\n".join(reply_parts)
        else:
            # No KB match
            if has_code_context:
                reply = """🤖 我理解您遇到了代码问题。

我尝试查询了相关知识库，但没有找到直接匹配的技术文档。

**建议**：
1. 请确认芯片/模块型号是否正确
2. 提供相关的代码片段，我可以尝试直接分析并修复
3. 或回复 `请帮我修改代码`，我将基于您的代码生成修复方案

**您的需求**：
"""
                if intent.research_topics:
                    reply += f"涉及: {', '.join(intent.research_topics)}\n"
            else:
                reply = "🤖 我需要进一步分析这个问题。\n\n"
                if intent.research_topics:
                    reply += f"**分析方向**: {', '.join(intent.research_topics)}\n\n"
                reply += "请稍候，我正在查询相关资料。"
        
        github = self._get_github_client(installation_id)
        if github:
            github.create_issue_comment(owner, repo, issue_number, reply)
        
        # Update state
        repo_full_name = f"{owner}/{repo}"
        self.state_manager.record_action(repo_full_name, issue_number, "researched")
        self.state_manager.save_state(IssueState(
            issue_number=issue_number,
            repo_full_name=repo_full_name,
            intent=intent.intent
        ))
        
        # Schedule follow-up check (if issue tracking is enabled)
        if self.issue_tracking_enabled:
            self.followup_manager.schedule_follow_up(owner, repo, issue_number, github)
        else:
            logger.debug(f"Issue tracking disabled, skipping follow-up scheduling for issue #{issue_number}")
        
        return ProcessingResult(
            status=ProcessingStatus.COMPLETED,
            issue_number=issue_number,
            intent=intent.intent,
            message="Knowledge base query completed" + (" (with answer)" if kb_answer else " (no match)") + (" [code context detected]" if has_code_context else "")
        )
    
    def _handle_clarify_intent(
        self, owner: str, repo: str, issue_number: int,
        context: IssueContext, intent: IntentResult, action_plan,
        installation_id: str
    ) -> ProcessingResult:
        """Handle clarify intent - need more information"""
        logger.info(f"Handling clarify intent for issue #{issue_number}")
        
        # Use response from action plan
        if hasattr(action_plan, 'response') and action_plan.response:
            reply = action_plan.response
        else:
            reply = """🤖 我需要更多信息来帮助您。

请提供：
1. 具体的错误信息或现象
2. 相关的代码片段或文件路径
3. 期望的行为和实际的行为

有了这些信息后，我可以更准确地分析和修复问题。"""
        
        github = self._get_github_client(installation_id)
        if github:
            github.create_issue_comment(owner, repo, issue_number, reply)
        
        # Update state (no follow-up for clarification requests)
        repo_full_name = f"{owner}/{repo}"
        self.state_manager.record_action(repo_full_name, issue_number, "clarified")
        
        return ProcessingResult(
            status=ProcessingStatus.SKIPPED,
            issue_number=issue_number,
            intent=intent.intent,
            message="Requested clarification"
        )
    
    def _parse_repo(self, full_name: str) -> tuple:
        """Parse owner/repo from full name"""
        parts = full_name.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", ""
    
    def _get_issue_number(self, event: GitHubEvent) -> int:
        """Extract issue number from event"""
        if event.issue:
            return event.issue.get("number", 0)
        return 0
    
    def _check_explicit_modify_request(self, context: IssueContext) -> bool:
        """
        Check if user explicitly requested code modification
        
        This overrides the AI intent classification when user clearly asks for code changes.
        """
        text = (context.current_instruction or "").lower()
        
        # Explicit modification request patterns
        modify_patterns = [
            "请帮我修改代码", "请修改代码", "帮我改代码",
            "请生成修复代码", "请帮我修复", "请修复代码",
            "请帮我实现", "请实现代码", "帮我写代码",
            "modify the code", "fix the code", "help me fix",
            "generate the fix", "provide the code", "write the code"
        ]
        
        for pattern in modify_patterns:
            if pattern in text:
                logger.info(f"Detected explicit modification request: '{pattern}'")
                return True
        
        return False
    
    def _check_followup_reply(self, context: IssueContext) -> Optional[bool]:
        """
        Check if this is a reply to our follow-up comment
        
        Returns:
            True: User confirms issue is resolved -> close issue
            False: User says issue is NOT resolved -> continue processing
            None: Not a follow-up reply -> proceed with normal intent classification
        """
        text = (context.current_instruction or "").lower()
        
        # Check for resolution keywords
        result = self.followup_manager.check_resolution_keywords(text)
        
        if result is True:
            logger.info("Detected follow-up reply confirming resolution")
            return True
        elif result is False:
            logger.info("Detected follow-up reply: issue NOT resolved, will continue processing")
            return False
        
        return None
    
    def _check_close_keywords(self, text: str) -> bool:
        """
        Direct check for close/resolve keywords
        This is used as a fallback when _check_followup_reply returns None
        
        Returns:
            True: Text contains close/resolve keywords
            False: No close keywords found
        """
        if not text:
            return False
            
        text_lower = text.lower()
        
        # Extended list of close/resolve keywords
        close_keywords = [
            # Chinese
            "已解决", "解决了", "搞定", "可以关闭", "关闭吧", "没问题了",
            "可以了", "ok了", "ok", "完美", "不用了", "取消",
            "测试通过", "验证通过", "没有问题", "完成", "结束",
            "谢谢", "感谢", "多谢",
            # English
            "fixed", "resolved", "solved", "close", "closing", "closed",
            "works", "working", "worked", "great", "perfect", "awesome",
            "thank", "thanks", "verified", "done", "completed", "it works"
        ]
        
        # Check for positive keywords
        for kw in close_keywords:
            if kw in text_lower:
                logger.info(f"Detected close keyword: '{kw}'")
                return True
        
        return False
