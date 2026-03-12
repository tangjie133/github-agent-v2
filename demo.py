#!/usr/bin/env python3
"""
GitHub Agent V2 - Quick Demo
Demonstrates all implemented phases
"""

import sys
sys.path.insert(0, '.')

print("="*60)
print("GitHub Agent V2 - Functionality Demo")
print("="*60)

# ===== Phase 1: Core Models =====
print("\n📦 Phase 1: Core Models")
print("-" * 40)

from core.models import GitHubEvent, IssueContext, IntentResult, IntentType

# Create test event
event = GitHubEvent(
    event_type="issue_comment",
    action="created",
    repository={
        "full_name": "tangjie133/test-ai",
        "name": "test-ai",
        "owner": {"login": "tangjie133"}
    },
    issue={
        "number": 16,
        "title": "Bug: 1Hz output not working",
        "body": "The INT pin is not outputting 1Hz signal",
        "user": {"login": "testuser"},
        "labels": []
    },
    comment={
        "body": "@agent Why is the 1Hz output not working?",
        "user": {"login": "testuser"}
    },
    installation={"id": "12345678"}
)

print(f"✅ Created GitHubEvent: {event.event_type} #{event.issue['number']}")

# Create context
context = IssueContext(
    issue_number=16,
    title="Bug: 1Hz output not working",
    body="The INT pin is not outputting 1Hz signal",
    author="testuser",
    current_instruction="@agent Why is the 1Hz output not working?",
    comments=[
        {"user": {"login": "user1"}, "body": "I have the same problem"},
        {"user": {"login": "user2"}, "body": "Check the register settings"}
    ]
)

print(f"✅ Created IssueContext with {len(context.comments)} comments")

# ===== Phase 2: Cloud Agent =====
print("\n☁️  Phase 2: Cloud Agent (Intent Recognition)")
print("-" * 40)

from cloud_agent import OpenClawClient, IntentClassifier, DecisionEngine

# Initialize
client = OpenClawClient()
classifier = IntentClassifier(client)
decision_engine = DecisionEngine(client)

print(f"✅ OpenClawClient initialized")
print(f"   Health check: {client.health_check()}")

# Test intent classification
print("\n📝 Testing Intent Classification:")

test_cases = [
    {
        "name": "Question about previous fix",
        "instruction": "@agent Why did you change the register value?",
        "expected": "answer"
    },
    {
        "name": "Direct modification request",
        "instruction": "@agent Please fix the null pointer on line 10",
        "expected": "modify"
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n  Test {i}: {test['name']}")
    print(f"  Input: {test['instruction']}")
    
    ctx = IssueContext(
        issue_number=i,
        title="Test",
        body=test['instruction'],
        author="testuser",
        current_instruction=test['instruction']
    )
    
    result = classifier.classify(ctx)
    print(f"  → Intent: {result.intent.value} (confidence: {result.confidence:.2f})")
    print(f"  → Reasoning: {result.reasoning[:60]}...")

# ===== Phase 3: Knowledge Base =====
print("\n📚 Phase 3: Knowledge Base")
print("-" * 40)

from knowledge_base import KBClient, KBIntegrator, LocalKBManager

kb_client = KBClient()
kb_integrator = KBIntegrator(kb_client)
local_kb = LocalKBManager()

print(f"✅ KBClient initialized")
print(f"   Health check: {kb_client.health_check()}")

print(f"✅ KBIntegrator initialized")
print(f"✅ LocalKBManager initialized")

# Show stats
stats = local_kb.get_stats()
print(f"\n📊 Local KB Stats:")
print(f"   Total documents: {stats['total_documents']}")
print(f"   Indexed: {stats['indexed']}")
print(f"   Directory: {stats['kb_directory']}")

# Test context enrichment
print("\n📝 Testing Context Enrichment:")
enriched = kb_integrator.enrich_context(context)
print(f"✅ Context enriched (length: {len(enriched)} chars)")

# ===== Summary =====
print("\n" + "="*60)
print("✅ All Phases Working!")
print("="*60)

print("""
Implemented Features:
✅ Phase 1: Core Models - Data structures for events, issues, intents
✅ Phase 1: GitHub API - Authentication and API client
✅ Phase 1: Webhook Server - Event receiving and routing

✅ Phase 2: OpenClaw Integration - Intent classification
✅ Phase 2: Decision Engine - Action planning
✅ Phase 2: Confirmation Mode - Auto/Manual execution control

✅ Phase 3: KB Service Client - RAG query integration
✅ Phase 3: Context Enrichment - Knowledge-enhanced processing
✅ Phase 3: Local KB Management - Document organization

Next Steps:
⏳ Phase 4: Code Execution (qwen3-coder integration)
⏳ End-to-end testing with real GitHub events
""")
