"""
Context Builder
Builds complete context for AI processing
"""

import logging
from typing import Optional

from core.models import GitHubEvent, IssueContext

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds complete issue context from GitHub event"""
    
    def __init__(self, github_client=None):
        self.github = github_client
    
    def build(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        installation_id: str,
        event: GitHubEvent
    ) -> IssueContext:
        """
        Build complete issue context
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            installation_id: GitHub App installation ID
            event: GitHub webhook event
            
        Returns:
            Complete issue context
        """
        # Get issue details
        issue = event.issue or {}
        
        # Get comments
        comments = []
        if self.github:
            try:
                comments = self.github.get_issue_comments(owner, repo, issue_number)
            except Exception as e:
                logger.warning(f"Failed to get comments: {e}")
        
        # Extract current instruction from triggering comment
        current_instruction = ""
        if event.event_type == "issue_comment" and event.comment:
            current_instruction = event.comment.get("body", "")
        elif event.event_type == "issues":
            current_instruction = issue.get("body", "")
        
        context = IssueContext(
            issue_number=issue_number,
            title=issue.get("title", ""),
            body=issue.get("body", ""),
            author=issue.get("user", {}).get("login", ""),
            labels=[label.get("name", "") for label in issue.get("labels", [])],
            comments=comments,
            current_instruction=current_instruction
        )
        
        logger.info(f"Built context for issue #{issue_number}: {context.title[:50]}")
        return context
