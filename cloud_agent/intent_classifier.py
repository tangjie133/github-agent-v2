"""
Intent Classifier
Uses OpenClaw AI to classify user intent from issue/comment context
"""

import logging
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import IssueContext, IntentResult, IntentType
from .openclaw_client import OpenClawClient

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Classifies user intent using OpenClaw AI
    
    Determines whether user wants:
    - answer: explanation, discussion
    - modify: code changes
    - research: needs investigation
    - clarify: insufficient information
    """
    
    def __init__(self, openclaw_client: Optional[OpenClawClient] = None):
        self.client = openclaw_client or OpenClawClient()
    
    def classify(self, context: IssueContext) -> IntentResult:
        """
        Classify intent from issue context
        
        Args:
            context: Complete issue context
            
        Returns:
            Intent classification result
        """
        # Build full context text
        context_text = context.build_full_context()
        
        logger.info(f"Classifying intent for issue #{context.issue_number}")
        
        # Call OpenClaw for intent classification
        try:
            result = self.client.classify_intent(context_text)
            
            # Map to IntentType
            intent_map = {
                "answer": IntentType.ANSWER,
                "modify": IntentType.MODIFY,
                "research": IntentType.RESEARCH,
                "clarify": IntentType.CLARIFY
            }
            
            intent_type = intent_map.get(
                result.get("intent", "clarify"),
                IntentType.CLARIFY
            )
            
            intent_result = IntentResult(
                intent=intent_type,
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", ""),
                needs_research=result.get("needs_research", False),
                research_topics=result.get("research_topics", [])
            )
            
            logger.info(
                f"Intent classified: {intent_result.intent.value} "
                f"(confidence: {intent_result.confidence:.2f})"
            )
            
            return intent_result
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Fallback to modify to avoid missing action items
            return IntentResult(
                intent=IntentType.MODIFY,
                confidence=0.3,
                reasoning=f"Classification failed: {e}, defaulting to modify",
                needs_research=False,
                research_topics=[]
            )
    
    def classify_with_history(
        self,
        context: IssueContext,
        previous_intent: Optional[IntentType] = None,
        processing_count: int = 0
    ) -> IntentResult:
        """
        Classify intent with historical context
        
        This helps avoid duplicate processing and understand conversation flow
        
        Args:
            context: Current issue context
            previous_intent: Previous intent classification (if any)
            processing_count: How many times this issue has been processed
            
        Returns:
            Intent classification result
        """
        # Get base classification
        result = self.classify(context)
        
        # Adjust based on history
        if processing_count > 0:
            # Issue has been processed before
            logger.info(f"Issue has been processed {processing_count} times before")
            
            # If this looks like a duplicate modification request
            if result.intent == IntentType.MODIFY and processing_count >= 2:
                # Check if user is asking for modification again
                if "不对" in context.current_instruction or \
                   "重新" in context.current_instruction or \
                   "不行" in context.current_instruction:
                    logger.info("Detected modification retry")
                    # Keep modify intent but note it's a retry
                    result.reasoning += " (retry with modifications)"
                else:
                    # User might be asking about previous modification
                    logger.info("Possible question about previous modification")
                    # Don't change intent, but processor should handle accordingly
        
        return result
