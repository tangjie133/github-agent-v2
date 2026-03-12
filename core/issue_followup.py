"""
Issue Follow-up Manager

Automatically tracks issue resolution status and sends follow-up comments
to ask users if their issue has been resolved.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import re

from core.state_manager import StateManager, IssueState

logger = logging.getLogger(__name__)


class ResolutionStatus(Enum):
    """Issue resolution status"""
    PENDING = "pending"
    WAITING_FOR_FEEDBACK = "waiting_for_feedback"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class FollowUpState:
    """State for tracking follow-up"""
    issue_number: int
    repo_full_name: str
    last_action_time: datetime
    follow_up_count: int = 0
    resolution_status: str = ResolutionStatus.PENDING.value
    follow_up_scheduled_at: Optional[datetime] = None


class IssueFollowupManager:
    """Manager for issue follow-up and resolution tracking"""
    
    # Keywords indicating issue is resolved
    RESOLUTION_KEYWORDS = [
        # Chinese
        "已解决", "有解决", "解决了", "解决", "搞定", "可以了", "ok了", "好了", 
        "完美", "没问题", "行的", "可行", "成功", 
        "谢谢", "感谢", "有用", "work了", "测试通过", "验证通过",
        # English
        "work", "fixed", "works", "working", "solved", "resolved",
        "thank", "thanks", "great", "perfect", "awesome", "ok", "good", "verified"
    ]
    
    # Keywords indicating issue is NOT resolved
    NOT_RESOLVED_KEYWORDS = [
        # Chinese
        "没解决", "还不行", "不行", "还是有问题", "仍然报错", 
        "还是报错", "还是不行", "没有解决", "不对", "错误", "异常",
        # English
        "not working", "still broken", "doesn't work", "still error",
        "not fixed", "problem persists", "still fails"
    ]
    
    FOLLOW_UP_DELAY_HOURS = 24  # First follow-up after 24 hours
    FOLLOW_UP_INTERVAL_HOURS = 48  # Subsequent follow-ups every 48 hours
    MAX_FOLLOW_UPS = 3  # Maximum number of follow-ups
    
    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()
    
    def check_resolution_keywords(self, text: str) -> Optional[bool]:
        """
        Check if text indicates issue resolution status
        
        Returns:
            True: Issue is resolved
            False: Issue is NOT resolved
            None: Unclear status
        """
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Priority 1: Check for explicit close/resolve keywords first
        # These should take precedence over new_request_keywords
        explicit_close_keywords = [
            "已解决", "解决了", "搞定", "可以关闭", "关闭吧", "没问题了",
            "可以了", "ok了", "fixed", "resolved", "solved", "close it",
            "测试通过", "验证通过", "完美", "works now", "it works"
        ]
        for kw in explicit_close_keywords:
            if kw in text_lower:
                logger.info(f"Detected explicit close keyword: '{kw}'")
                return True
        
        # Priority 2: Check for explicit NOT resolved keywords
        explicit_not_resolved = [
            "没解决", "还不行", "仍然报错", "还是报错", "还是不行",
            "没有解决", "not working", "still broken", "doesn't work",
            "still error", "not fixed", "problem persists"
        ]
        for kw in explicit_not_resolved:
            if kw in text_lower:
                logger.info(f"Detected explicit NOT resolved keyword: '{kw}'")
                return False
        
        # Priority 3: Check if this looks like a new feature request
        # These indicate user is asking for something new, not responding to previous fix
        new_request_keywords = [
            "请帮我", "请修改", "请添加", "请实现", "求助",
            "how to", "how do i", "can you", "could you", "would you",
            "帮我", "怎么", "如何"
        ]
        if any(kw in text_lower for kw in new_request_keywords):
            logger.debug(f"Text contains new request keywords, not a resolution reply")
            return None
        
        # Priority 4: Check general positive/negative keywords
        # Check positive keywords
        positive_matches = [kw for kw in self.RESOLUTION_KEYWORDS if kw in text_lower]
        # Check negative keywords
        negative_matches = [kw for kw in self.NOT_RESOLVED_KEYWORDS if kw in text_lower]
        
        # More weight to negative keywords (users often say "not working" when it fails)
        if negative_matches:
            logger.info(f"Detected NOT resolved keywords: {negative_matches}")
            return False
        
        if positive_matches:
            logger.info(f"Detected resolved keywords: {positive_matches}")
            return True
        
        return None
    
    def should_follow_up(self, state: IssueState) -> bool:
        """
        Check if we should send a follow-up comment
        
        Returns True if enough time has passed since last action
        """
        if not state or not state.last_action_time:
            return False
        
        # Don't follow up if already closed
        if state.last_action == "closed":
            return False
        
        # Don't follow up if already waiting for feedback (sent follow-up but no response)
        if state.last_action == "follow_up":
            return False
            
        # Don't follow up for clarification requests
        if state.last_action == "clarified":
            return False
        
        try:
            # last_action_time returns datetime object directly
            last_time = state.last_action_time
            if isinstance(last_time, str):
                last_time = datetime.fromisoformat(last_time)
            time_since_last = datetime.now() - last_time
            
            # First follow-up after 24 hours
            if state.processing_count == 1 and time_since_last >= timedelta(hours=self.FOLLOW_UP_DELAY_HOURS):
                logger.info(f"Issue #{state.issue_number}: Time for first follow-up ({time_since_last.total_seconds()/3600:.1f}h since last action)")
                return True
            
            # Subsequent follow-ups every 48 hours (up to MAX_FOLLOW_UPS)
            if state.processing_count > 1 and time_since_last >= timedelta(hours=self.FOLLOW_UP_INTERVAL_HOURS):
                follow_up_count = getattr(state, 'follow_up_count', 0)
                if follow_up_count < self.MAX_FOLLOW_UPS:
                    logger.info(f"Issue #{state.issue_number}: Time for follow-up #{follow_up_count + 1}")
                    return True
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse last_action_time: {e}")
            return False
        
        return False
    
    def get_follow_up_message(self, follow_up_count: int = 0) -> str:
        """Generate follow-up message based on count"""
        messages = [
            """⏰ 您好！距离我上次回复已经一段时间了。

请问您的问题是否已经解决？如果已解决，请回复"已解决"或"搞定"，我会关闭此 Issue。

如果仍有问题，请告诉我具体情况，我会继续协助您。""",
            
            """👋 跟进一下

请问问题是否已经解决了？如果还有疑问，欢迎继续讨论。""",
            
            """🔔 最后跟进

由于长时间没有收到回复，如果问题已解决请回复"已解决"，我会关闭此 Issue。
如果仍需要帮助，请尽快回复，我会继续协助您。"""
        ]
        
        return messages[min(follow_up_count, len(messages) - 1)]
    
    def schedule_follow_up(self, owner: str, repo: str, issue_number: int, 
                           github_client) -> bool:
        """
        Schedule a follow-up check for the issue
        
        Note: This is a simplified implementation. In production, you would use
        a background scheduler (like APScheduler or Celery) to handle the delays.
        
        For now, we mark the state to indicate follow-up is scheduled and let
        the state manager handle it.
        """
        try:
            state = self.state_manager.get_state(f"{owner}/{repo}", issue_number)
            if state:
                # Update state to track that follow-up is scheduled
                self.state_manager.record_action(
                    f"{owner}/{repo}", issue_number, "scheduled_follow_up"
                )
                logger.info(f"Follow-up scheduled for issue #{issue_number}")
                return True
        except Exception as e:
            logger.error(f"Failed to schedule follow-up: {e}")
        
        return False
    
    def send_follow_up(self, owner: str, repo: str, issue_number: int,
                       github_client) -> bool:
        """Send follow-up comment to issue"""
        try:
            repo_full_name = f"{owner}/{repo}"
            state = self.state_manager.get_state(repo_full_name, issue_number)
            
            if not state:
                logger.warning(f"No state found for issue #{issue_number}")
                return False
            
            follow_up_count = getattr(state, 'follow_up_count', 0)
            message = self.get_follow_up_message(follow_up_count)
            
            # Send comment
            github_client.create_issue_comment(owner, repo, issue_number, message)
            
            # Update state
            self.state_manager.record_action(repo_full_name, issue_number, "follow_up")
            
            # Update follow-up count in state
            state.follow_up_count = follow_up_count + 1
            self.state_manager.save_state(state)
            
            logger.info(f"Follow-up #{follow_up_count + 1} sent to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send follow-up: {e}")
            return False
    
    def close_if_resolved(self, owner: str, repo: str, issue_number: int,
                         github_client, resolution_confirmed: bool = True) -> bool:
        """
        Close issue with confirmation message
        
        Args:
            resolution_confirmed: If True, user explicitly confirmed resolution
        """
        try:
            if resolution_confirmed:
                message = """✅ 问题已确认解决！

感谢使用 GitHub Agent！如果还有其他问题，欢迎随时 @agent 提问。

祝您开发愉快！🎉"""
            else:
                message = """🤖 自动关闭

此 Issue 已被标记为已解决。如有后续问题，请重新打开或创建新 Issue。"""
            
            # Post closing comment
            github_client.create_issue_comment(owner, repo, issue_number, message)
            
            # Close the issue
            github_client.close_issue(owner, repo, issue_number)
            
            # Update state
            repo_full_name = f"{owner}/{repo}"
            self.state_manager.record_action(repo_full_name, issue_number, "closed")
            
            logger.info(f"Issue #{issue_number} closed as resolved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close resolved issue: {e}")
            return False
    
    def check_stale_issues(self, owner: str, repo: str, 
                          github_client, max_age_days: int = 7) -> int:
        """
        Check for stale issues and send follow-ups
        
        This method should be called periodically (e.g., by a scheduled job)
        to check all open issues in a repository and send follow-ups.
        
        Returns number of follow-ups sent.
        """
        sent_count = 0
        repo_full_name = f"{owner}/{repo}"
        
        try:
            # Get all open issues from GitHub
            # Note: This requires github_client to have a method to list issues
            # For now, we assume it exists or the state manager tracks active issues
            
            logger.info(f"Checking for stale issues in {repo_full_name}")
            
            # In a full implementation, you would:
            # 1. List all open issues
            # 2. For each issue, check if it should be followed up
            # 3. Send follow-up if needed
            
            # Simplified: just log for now
            logger.info("Stale issue check completed (implementation pending)")
            
        except Exception as e:
            logger.error(f"Failed to check stale issues: {e}")
        
        return sent_count
