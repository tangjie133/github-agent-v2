#!/usr/bin/env python3
"""
GitHub Agent V2 - Main Entry Point

Coordinates all modules:
- Webhook receiver
- Cloud Agent (OpenClaw for intent recognition)
- Knowledge Base (RAG query)
- Code Executor (Ollama for code generation)
- GitHub API integration
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from github_api.auth_manager import GitHubAuthManager
from github_api.github_client import GitHubClient
from cloud_agent import OpenClawClient, IntentClassifier, DecisionEngine
from knowledge_base import KBClient, KBIntegrator
from code_executor import CodeGenerator, RepositoryManager, SafeCodeModifier, ChangeValidator
from core.processor import IssueProcessor
from webhook.webhook_server import run_server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_kb_service():
    """Ensure KB Service is running, start if not"""
    import requests
    import subprocess
    import time
    
    kb_url = os.environ.get("KB_SERVICE_URL", "http://localhost:8000")
    
    try:
        resp = requests.get(f"{kb_url}/health", timeout=2)
        if resp.status_code == 200:
            return True  # Already running
    except:
        pass
    
    # Try to start KB Service
    logger.info("KB Service not running, attempting to start...")
    try:
        # Start in background
        subprocess.Popen(
            [sys.executable, "-m", "knowledge_base.kb_service"],
            stdout=open("/tmp/kb_service.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Wait for it to start
        for i in range(10):
            time.sleep(1)
            try:
                resp = requests.get(f"{kb_url}/health", timeout=2)
                if resp.status_code == 200:
                    logger.info("✅ KB Service auto-started successfully")
                    return True
            except:
                pass
        
        logger.warning("⚠️  KB Service auto-start timed out")
        return False
    except Exception as e:
        logger.warning(f"⚠️  Failed to auto-start KB Service: {e}")
        return False


def create_processor() -> IssueProcessor:
    """Create and configure the issue processor with all components"""
    
    logger.info("Initializing GitHub Agent V2...")
    
    # Initialize GitHub auth
    auth_manager = GitHubAuthManager()
    
    # Cloud Agent components (Phase 2)
    logger.info("Initializing Cloud Agent (OpenClaw)...")
    openclaw_client = OpenClawClient()
    intent_classifier = IntentClassifier(openclaw_client)
    decision_engine = DecisionEngine(openclaw_client)
    
    # Attach decision engine to intent classifier for convenience
    intent_classifier.decision_engine = decision_engine
    
    # Check OpenClaw health
    if openclaw_client.health_check():
        logger.info("✅ OpenClaw is ready")
    else:
        logger.warning("⚠️  OpenClaw not available, intent recognition will use fallback")
    
    # Knowledge Base components (Phase 3)
    logger.info("Initializing Knowledge Base...")
    
    # Ensure KB Service is running
    ensure_kb_service()
    
    kb_client = KBClient()
    kb_integrator = KBIntegrator(kb_client)
    
    # Check KB Service health
    if kb_client.health_check():
        logger.info("✅ KB Service is ready")
        kb_stats = kb_client.get_stats()
        if kb_stats:
            logger.info(f"   Documents: {kb_stats.get('total_documents', 0)}")
    else:
        logger.warning("⚠️  KB Service not available, knowledge enrichment disabled")
    
    # Code Executor components (Phase 4)
    logger.info("Initializing Code Executor...")
    code_gen = CodeGenerator()
    repo_mgr = RepositoryManager()
    safe_mod = SafeCodeModifier(code_gen)
    validator = ChangeValidator(code_gen)
    
    # Check Ollama health
    if code_gen.health_check():
        logger.info(f"✅ Ollama is ready (model: {code_gen.model})")
    else:
        logger.warning("⚠️  Ollama not available, code generation disabled")
    
    # Create integrated code executor
    from code_executor.code_executor import CodeExecutor
    code_executor = CodeExecutor(
        code_generator=code_gen,
        repo_manager=repo_mgr,
        safe_modifier=safe_mod,
        validator=validator
    )
    
    # Create processor
    # GitHub client will be created per installation using auth_manager
    processor = IssueProcessor(
        github_client=None,
        cloud_agent=intent_classifier,
        knowledge_base=kb_integrator,
        code_executor=code_executor,
        auth_manager=auth_manager
    )
    
    logger.info("✅ Issue processor initialized")
    return processor


def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Agent V2")
    parser.add_argument("--host", default="0.0.0.0", help="Webhook server host")
    parser.add_argument("--port", type=int, default=8080, help="Webhook server port")
    parser.add_argument("--test-intent", action="store_true", help="Test intent classification")
    
    args = parser.parse_args()
    
    if args.test_intent:
        # Test intent classification
        logger.info("Testing intent classification...")
        
        from core.models import IssueContext
        
        client = OpenClawClient()
        classifier = IntentClassifier(client)
        
        # Test case 1: Question
        context1 = IssueContext(
            issue_number=1,
            title="Question about implementation",
            body="@agent Why did you use this approach?",
            author="testuser",
            current_instruction="@agent Why did you use this approach?"
        )
        
        result1 = classifier.classify(context1)
        print(f"\nTest 1 (Question):")
        print(f"  Input: {context1.current_instruction}")
        print(f"  Intent: {result1.intent.value}")
        print(f"  Confidence: {result1.confidence}")
        print(f"  Reasoning: {result1.reasoning}")
        
        # Test case 2: Modification request
        context2 = IssueContext(
            issue_number=2,
            title="Bug fix needed",
            body="@agent Please fix the null pointer exception in line 10",
            author="testuser",
            current_instruction="@agent Please fix the null pointer exception in line 10"
        )
        
        result2 = classifier.classify(context2)
        print(f"\nTest 2 (Modification):")
        print(f"  Input: {context2.current_instruction}")
        print(f"  Intent: {result2.intent.value}")
        print(f"  Confidence: {result2.confidence}")
        print(f"  Reasoning: {result2.reasoning}")
        
        return
    
    # Create processor
    processor = create_processor()
    
    # Run webhook server
    logger.info(f"Starting webhook server on {args.host}:{args.port}")
    run_server(host=args.host, port=args.port, processor=processor)


if __name__ == "__main__":
    main()
