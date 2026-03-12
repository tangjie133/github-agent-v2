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
            state = self.state_manager.get_state(repo, issue_number)
            processing_count = state.processing_count if state else 0
            
            if state:
                logger.info(f"Issue #{issue_number} has been processed {processing_count} times before")
            
            # Phase 2: Intent recognition (Cloud Agent)
            if self.cloud_agent:
                intent = self.cloud_agent.classify_with_history(
                    context,
                    state.intent if state else None,
                    processing_count
                )
                logger.info(f"Detected intent: {intent.intent.value} (confidence: {intent.confidence:.2f})")
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
        self.state_manager.record_action(repo, issue_number, "answered")
        self.state_manager.save_state(IssueState(
            issue_number=issue_number,
            repo_full_name=f"{owner}/{repo}",
            intent=intent.intent
        ))
        
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
            token = github.get_installation_token(installation_id) if github and hasattr(github, 'get_installation_token') else None
            
            # Execute code changes
            logger.info("Executing code changes...")
            exec_result = self.code_executor.execute_task(
                task_type="fix_issue",
                instruction=context.current_instruction or context.body,
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
                
                # Update state
                self.state_manager.record_action(
                    repo, issue_number, "modified",
                    pr_number=pr_number,
                    files=files_modified
                )
                self.state_manager.save_state(IssueState(
                    issue_number=issue_number,
                    repo_full_name=f"{owner}/{repo}",
                    intent=intent.intent,
                    pull_request_number=pr_number,
                    files_modified=files_modified
                ))
                
                # Reply to issue
                message = f"""🤖 代码修改完成

我创建了一个 PR #{pr_number} 来解决这个问题：{pr_url}

**修改的文件**:
{chr(10).join([f'- `{f}`' for f in files_modified])}

请查看并确认修改是否符合预期。如果需要调整，请告诉我具体问题。"""
                
                github = self._get_github_client(installation_id)
                if github:
                    github.create_issue_comment(owner, repo, issue_number, message)
                
                return ProcessingResult(
                    status=ProcessingStatus.COMPLETED,
                    issue_number=issue_number,
                    intent=intent.intent,
                    pr_number=pr_number,
                    message=f"PR created: #{pr_number}"
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
        
        # Query knowledge base
        kb_answer = None
        if self.knowledge_base:
            query = f"{context.title}\n{context.body}"
            
            # Try to get solution from KB
            suggestion = self.knowledge_base.get_solution_suggestion(query)
            
            if suggestion:
                kb_answer = suggestion['answer']
                logger.info(f"Found KB solution with similarity {suggestion['similarity']:.2f}")
        
        # Build response
        if kb_answer:
            # KB found answer
            reply = f"""🤖 [知识库自动回答]

{kb_answer}

---
📚 **参考文档**: {suggestion['source']}
🎯 **匹配度**: {suggestion['similarity']:.1%}

如果以上信息未能解决您的问题，请提供更多细节，我可以进一步分析。"""
        else:
            # No KB match
            if hasattr(action_plan, 'response') and action_plan.response:
                reply = action_plan.response
            else:
                reply = "🤖 我需要进一步分析这个问题。\n\n"
                if intent.research_topics:
                    reply += f"**分析方向**: {', '.join(intent.research_topics)}\n\n"
                reply += "请稍候，我正在查询相关资料。"
        
        github = self._get_github_client(installation_id)
        if github:
            github.create_issue_comment(owner, repo, issue_number, reply)
        
        # Update state
        self.state_manager.record_action(repo, issue_number, "researched")
        self.state_manager.save_state(IssueState(
            issue_number=issue_number,
            repo_full_name=f"{owner}/{repo}",
            intent=intent.intent
        ))
        
        return ProcessingResult(
            status=ProcessingStatus.COMPLETED,
            issue_number=issue_number,
            intent=intent.intent,
            message="Knowledge base query completed" + (" (with answer)" if kb_answer else " (no match)")
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
