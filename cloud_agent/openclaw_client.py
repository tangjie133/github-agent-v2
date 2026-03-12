"""
OpenClaw Client for Cloud Agent
Wraps OpenClaw CLI for intent recognition and decision making
"""

import os
import json
import re
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenClawClient:
    """
    Client for OpenClaw AI service
    Used for intent classification and decision making
    """
    
    def __init__(
        self,
        api_url: str = None,
        agent: str = "main",
        timeout: int = 60
    ):
        self.api_url = api_url or os.environ.get(
            "OPENCLAW_API_URL", "http://localhost:3000/api/v1"
        )
        self.agent = agent
        self.timeout = timeout
    
    def classify_intent(self, context_text: str) -> Dict[str, Any]:
        """
        Classify user intent from issue/comment context
        
        Args:
            context_text: Full context (issue + comments)
            
        Returns:
            Intent classification result
        """
        prompt = self._build_intent_prompt(context_text)
        
        try:
            result = self._call_openclaw(prompt)
            return self._parse_intent_response(result)
        except Exception as e:
            logger.error(f"OpenClaw intent classification failed: {e}")
            return self._fallback_intent()
    
    def make_decision(self, context_text: str, intent: str) -> Dict[str, Any]:
        """
        Make decision on how to handle the issue
        
        Args:
            context_text: Full context
            intent: Detected intent
            
        Returns:
            Decision with action plan
        """
        prompt = self._build_decision_prompt(context_text, intent)
        
        try:
            result = self._call_openclaw(prompt)
            return self._parse_decision_response(result)
        except Exception as e:
            logger.error(f"OpenClaw decision making failed: {e}")
            return self._fallback_decision()
    
    def _build_intent_prompt(self, context_text: str) -> str:
        """Build prompt for intent classification"""
        return f"""你是一个专业的意图分类助手。分析用户的 GitHub Issue/评论，判断用户的真实意图。

## 分析步骤

1. **理解内容**：仔细阅读用户的描述
2. **判断类型**：
   - "answer": 询问、质疑、需要解释、讨论修改合理性
   - "modify": 明确的修改指令、修复请求、功能实现
   - "research": 问题复杂，需要先查询资料才能确定方案
   - "clarify": 信息不足，无法判断意图

3. **特殊判断**：
   - "为什么"、"依据"、"原理" → answer
   - "修复"、"修改"、"改成" → modify
   - "这样对吗"、"是否合理" → answer

## 用户内容

```
{context_text}
```

## 输出格式

返回严格的 JSON：
```json
{{
  "intent": "answer|modify|research|clarify",
  "confidence": 0.0-1.0,
  "reasoning": "简要说明判断理由",
  "needs_research": true|false,
  "research_topics": ["如果需要查询，列出查询主题"]
}}
```

要求：
- confidence > 0.8 表示高置信度
- needs_research=true 当需要查询芯片手册、技术文档等
- 只返回 JSON，不要其他内容"""
    
    def _build_decision_prompt(self, context_text: str, intent: str) -> str:
        """Build prompt for decision making"""
        return f"""你是一个决策助手。基于已识别的意图，制定具体的处理方案。

## 已识别的意图

{intent}

## 用户内容

```
{context_text}
```

## 任务

根据意图制定处理方案：

1. 如果 intent="answer":
   - 确定回复内容要点
   - 判断是否需要引用之前的修改

2. 如果 intent="modify":
   - 分析需要修改的文件
   - 确定修改策略
   - 评估复杂度 (simple/medium/complex)

3. 如果 intent="research":
   - 列出需要查询的知识点
   - 制定查询计划

## 输出格式

返回 JSON：
```json
{{
  "action": "reply|modify|research|skip",
  "complexity": "simple|medium|complex",
  "files_to_modify": ["file1.cpp", "file2.h"],
  "change_description": "修改说明",
  "confidence": 0.0-1.0,
  "response": "如果不修改，回复给用户的内容"
}}
```"""
    
    def _call_openclaw(self, prompt: str) -> Dict[str, Any]:
        """Call OpenClaw CLI"""
        cmd = [
            "openclaw", "agent",
            "--agent", self.agent,
            "--local",
            "--json",
            "--message", prompt
        ]
        
        logger.debug(f"Calling OpenClaw with prompt length: {len(prompt)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"OpenClaw failed: {result.stderr}")
        
        return json.loads(result.stdout)
    
    def _parse_intent_response(self, result: Dict) -> Dict[str, Any]:
        """Parse intent classification response"""
        text = ""
        for payload in result.get("payloads", []):
            text += payload.get("text", "") + "\n"
        
        logger.debug(f"OpenClaw response: {text[:200]}...")
        
        try:
            # Try JSON block
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(1))
            else:
                # Try raw JSON
                match = re.search(r'(\{[\s\S]*"intent"[\s\S]*\})', text)
                if match:
                    parsed = json.loads(match.group(1))
                else:
                    raise ValueError("No JSON found in response")
            
            return {
                "intent": parsed.get("intent", "clarify"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reasoning": parsed.get("reasoning", ""),
                "needs_research": parsed.get("needs_research", False),
                "research_topics": parsed.get("research_topics", [])
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse intent response: {e}")
            return self._fallback_intent()
    
    def _parse_decision_response(self, result: Dict) -> Dict[str, Any]:
        """Parse decision response"""
        text = ""
        for payload in result.get("payloads", []):
            text += payload.get("text", "") + "\n"
        
        try:
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            match = re.search(r'(\{[\s\S]*"action"[\s\S]*\})', text)
            if match:
                return json.loads(match.group(1))
        except:
            pass
        
        return self._fallback_decision()
    
    def _fallback_intent(self) -> Dict[str, Any]:
        """Fallback when AI fails"""
        return {
            "intent": "modify",  # Default to modify to be safe
            "confidence": 0.3,
            "reasoning": "OpenClaw failed, defaulting to modify",
            "needs_research": False,
            "research_topics": []
        }
    
    def _fallback_decision(self) -> Dict[str, Any]:
        """Fallback decision"""
        return {
            "action": "reply",
            "complexity": "simple",
            "files_to_modify": [],
            "change_description": "AI service unavailable",
            "confidence": 0.3,
            "response": "🤖 服务暂时不可用，请稍后再试。"
        }
    
    def health_check(self) -> bool:
        """Check if OpenClaw is available"""
        try:
            result = subprocess.run(
                ["openclaw", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
