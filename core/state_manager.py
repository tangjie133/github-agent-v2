"""
State Manager
Tracks issue processing state to avoid duplicates and enable conversation
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from core.models import IssueState, IntentType

logger = logging.getLogger(__name__)


class StateManager:
    """Manages issue processing state"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or "/tmp/github-agent-v2/state")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_state_file(self, repo: str, issue_number: int) -> Path:
        """Get state file path for an issue"""
        # Sanitize repo name for filesystem
        safe_repo = repo.replace("/", "-")
        return self.storage_dir / f"{safe_repo}-{issue_number}.json"
    
    def get_state(self, repo: str, issue_number: int) -> Optional[IssueState]:
        """Get processing state for an issue"""
        state_file = self._get_state_file(repo, issue_number)
        
        if not state_file.exists():
            return None
        
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
            
            return IssueState(
                issue_number=data.get("issue_number", issue_number),
                repo_full_name=data.get("repo_full_name", repo),
                processed_at=datetime.fromisoformat(data.get("processed_at", datetime.now().isoformat())),
                intent=IntentType(data.get("intent")) if data.get("intent") else None,
                pull_request_number=data.get("pull_request_number", 0),
                pull_request_url=data.get("pull_request_url", ""),
                branch_name=data.get("branch_name", ""),
                processing_count=data.get("processing_count", 0),
                last_action=data.get("last_action", "")
            )
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None
    
    def save_state(self, state: IssueState):
        """Save processing state for an issue"""
        state_file = self._get_state_file(state.repo_full_name, state.issue_number)
        
        data = {
            "issue_number": state.issue_number,
            "repo_full_name": state.repo_full_name,
            "processed_at": state.processed_at.isoformat(),
            "intent": state.intent.value if state.intent else None,
            "pull_request_number": state.pull_request_number,
            "pull_request_url": state.pull_request_url,
            "branch_name": state.branch_name,
            "processing_count": state.processing_count,
            "last_action": state.last_action
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved state for issue #{state.issue_number}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def record_action(self, repo: str, issue_number: int, action: str):
        """Record a processing action"""
        state = self.get_state(repo, issue_number)
        
        if state is None:
            state = IssueState(
                issue_number=issue_number,
                repo_full_name=repo
            )
        
        state.record_processing(action)
        self.save_state(state)
        
        logger.info(f"Recorded action '{action}' for issue #{issue_number} (count: {state.processing_count})")
    
    def update_pr_info(
        self,
        repo: str,
        issue_number: int,
        pr_number: int,
        pr_url: str,
        branch_name: str
    ):
        """Update PR information for an issue"""
        state = self.get_state(repo, issue_number)
        
        if state is None:
            state = IssueState(
                issue_number=issue_number,
                repo_full_name=repo
            )
        
        state.pull_request_number = pr_number
        state.pull_request_url = pr_url
        state.branch_name = branch_name
        
        self.save_state(state)
        logger.info(f"Updated PR info for issue #{issue_number}: PR #{pr_number}")
    
    def list_states(self, repo: str = None) -> Dict[str, Any]:
        """List all tracked states"""
        states = []
        
        for state_file in self.storage_dir.glob("*.json"):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                
                if repo is None or data.get("repo_full_name") == repo:
                    states.append(data)
            except Exception as e:
                logger.warning(f"Failed to read state file {state_file}: {e}")
        
        return {
            "total": len(states),
            "states": states
        }
