#!/usr/bin/env python3
"""
Test script for Issue tracking feature switch
"""

import sys
import os
sys.path.insert(0, '/home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2')


def test_switch_enabled():
    """Test with AGENT_ISSUE_TRACKING_ENABLED=true"""
    os.environ["AGENT_ISSUE_TRACKING_ENABLED"] = "true"
    
    # Reload to pick up new env var
    from core.processor import IssueProcessor
    processor = IssueProcessor()
    
    assert processor.issue_tracking_enabled == True, f"Expected True, got {processor.issue_tracking_enabled}"
    print("✅ AGENT_ISSUE_TRACKING_ENABLED=true works correctly")


def test_switch_disabled():
    """Test with AGENT_ISSUE_TRACKING_ENABLED=false"""
    os.environ["AGENT_ISSUE_TRACKING_ENABLED"] = "false"
    
    # Need to reimport to pick up new env var
    import importlib
    import core.processor
    importlib.reload(core.processor)
    from core.processor import IssueProcessor
    
    processor = IssueProcessor()
    
    assert processor.issue_tracking_enabled == False, f"Expected False, got {processor.issue_tracking_enabled}"
    print("✅ AGENT_ISSUE_TRACKING_ENABLED=false works correctly")


def test_switch_various_values():
    """Test various values for the switch"""
    import importlib
    import core.processor
    from core.processor import IssueProcessor
    
    test_cases = [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),  # Empty string should default to False
    ]
    
    for value, expected in test_cases:
        os.environ["AGENT_ISSUE_TRACKING_ENABLED"] = value
        importlib.reload(core.processor)
        from core.processor import IssueProcessor
        processor = IssueProcessor()
        
        assert processor.issue_tracking_enabled == expected, \
            f"Value '{value}': Expected {expected}, got {processor.issue_tracking_enabled}"
        print(f"✅ Value '{value}' -> {expected} (correct)")


def test_switch_default():
    """Test default value when env var is not set"""
    # Remove env var if exists
    if "AGENT_ISSUE_TRACKING_ENABLED" in os.environ:
        del os.environ["AGENT_ISSUE_TRACKING_ENABLED"]
    
    import importlib
    import core.processor
    importlib.reload(core.processor)
    from core.processor import IssueProcessor
    
    processor = IssueProcessor()
    
    # Default should be True (enabled by default)
    assert processor.issue_tracking_enabled == True, f"Expected True (default), got {processor.issue_tracking_enabled}"
    print("✅ Default value (unset) -> True (correct)")


if __name__ == "__main__":
    print("\n🧪 Testing Issue Tracking Feature Switch\n")
    
    try:
        test_switch_enabled()
        test_switch_disabled()
        print()
        test_switch_various_values()
        print()
        test_switch_default()
        
        print()
        print("=" * 60)
        print("🎉 All switch tests passed!")
        print("=" * 60)
        print()
        print("Summary:")
        print("  - Enabled values: true, True, TRUE, 1, yes, on")
        print("  - Disabled values: false, False, FALSE, 0, no, off, ''")
        print("  - Default: true (enabled by default)")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
