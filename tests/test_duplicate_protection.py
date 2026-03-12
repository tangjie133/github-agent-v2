#!/usr/bin/env python3
"""
Test script for duplicate processing protection
"""

import sys
import tempfile
import os
sys.path.insert(0, '/home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2')

from core.models import IssueState
from core.state_manager import StateManager
from datetime import datetime, timedelta


def test_comment_id_tracking():
    """Test that comment IDs are tracked properly"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = StateManager(storage_dir=tmpdir)
        
        # Create a state
        state = IssueState(
            issue_number=1,
            repo_full_name="test/repo"
        )
        
        # Initially no comments processed
        assert not state.is_comment_processed(12345), "New state should not have processed any comments"
        
        # Record a comment
        state.record_comment(12345)
        assert state.is_comment_processed(12345), "Should detect processed comment"
        assert not state.is_comment_processed(99999), "Should not detect unprocessed comment"
        
        # Save and reload
        manager.save_state(state)
        loaded_state = manager.get_state("test/repo", 1)
        
        assert loaded_state.is_comment_processed(12345), "Loaded state should remember processed comment"
        
        print("✅ Comment ID tracking test passed")


def test_comment_id_limit():
    """Test that only last 100 comment IDs are kept"""
    state = IssueState(
        issue_number=1,
        repo_full_name="test/repo"
    )
    
    # Add 150 comment IDs
    for i in range(150):
        state.record_comment(i)
    
    # Should only keep last 100
    assert len(state.processed_comment_ids) == 100, f"Should keep only 100 comments, got {len(state.processed_comment_ids)}"
    
    # First 50 should be removed
    assert not state.is_comment_processed(0), "Old comments should be removed"
    assert not state.is_comment_processed(49), "Old comments should be removed"
    
    # Last 100 should be kept
    assert state.is_comment_processed(50), "Recent comments should be kept"
    assert state.is_comment_processed(149), "Most recent comment should be kept"
    
    print("✅ Comment ID limit test passed")


def test_state_fields():
    """Test that new fields are properly saved and loaded"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = StateManager(storage_dir=tmpdir)
        
        # Create a state with new fields
        state = IssueState(
            issue_number=1,
            repo_full_name="test/repo",
            issue_state="closed",
            processed_comment_ids=[100, 200, 300]
        )
        
        # Save and reload
        manager.save_state(state)
        loaded = manager.get_state("test/repo", 1)
        
        assert loaded.issue_state == "closed", f"Expected 'closed', got '{loaded.issue_state}'"
        assert loaded.processed_comment_ids == [100, 200, 300], f"Comment IDs mismatch: {loaded.processed_comment_ids}"
        
        print("✅ State fields test passed")


def test_issue_state_methods():
    """Test IssueState helper methods"""
    state = IssueState(
        issue_number=1,
        repo_full_name="test/repo"
    )
    
    # Test record_processing updates count
    initial_count = state.processing_count
    state.record_processing("test_action")
    assert state.processing_count == initial_count + 1, "Processing count should increment"
    assert state.last_action == "test_action", "Last action should be recorded"
    
    # Test record_comment
    state.record_comment(999)
    assert state.is_comment_processed(999), "Should detect recorded comment"
    
    print("✅ IssueState methods test passed")


if __name__ == "__main__":
    print("\n🧪 Testing Duplicate Protection Features\n")
    
    try:
        test_comment_id_tracking()
        test_comment_id_limit()
        test_state_fields()
        test_issue_state_methods()
        
        print()
        print("=" * 60)
        print("🎉 All duplicate protection tests passed!")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
