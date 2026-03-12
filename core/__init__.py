"""
Core module for GitHub Agent V2
"""

from core.models import (
    IntentType, ProcessingStatus, IntentResult,
    GitHubEvent, IssueContext, KBResult, CodeChange,
    ProcessingResult, IssueState
)
from core.state_manager import StateManager
from core.context_builder import ContextBuilder
from core.issue_followup import IssueFollowupManager, ResolutionStatus, FollowUpState
from core.processor import IssueProcessor

__all__ = [
    # Enums
    'IntentType', 'ProcessingStatus', 'ResolutionStatus',
    # Data classes
    'IntentResult', 'GitHubEvent', 'IssueContext', 'KBResult', 'CodeChange',
    'ProcessingResult', 'IssueState', 'FollowUpState',
    # Managers
    'StateManager', 'ContextBuilder', 'IssueFollowupManager', 'IssueProcessor',
]
