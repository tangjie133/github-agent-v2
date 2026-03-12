#!/usr/bin/env python3
"""
安全代码修改器
使用 SEARCH/REPLACE 格式精确修改代码，避免误删
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SafeCodeModifier:
    """
    安全代码修改器
    
    使用 diff 风格的 SEARCH/REPLACE 格式：
    - 精确匹配原始代码
    - 只替换匹配的部分
    - 不匹配时拒绝修改（安全回退）
    """
    
    def __init__(self, code_generator=None):
        """
        初始化安全修改器
        
        Args:
            code_generator: 可选的代码生成器，用于 AI 辅助修改
        """
        self.code_generator = code_generator
    
    def modify_file(
        self,
        file_path: str,
        file_content: str,
        instruction: str
    ) -> str:
        """
        安全地修改文件
        
        Args:
            file_path: 文件路径（用于日志）
            file_content: 当前文件内容
            instruction: 修改指令
            
        Returns:
            修改后的文件内容
            
        Raises:
            ValueError: 如果无法安全修改
        """
        # 如果文件不大（<=100行），使用精确替换
        lines = file_content.split('\n')
        if len(lines) <= 100:
            return self._precise_replace(file_path, file_content, instruction)
        
        # 大文件：分段处理
        return self._chunked_modify(file_path, file_content, instruction)
    
    def _precise_replace(
        self,
        file_path: str,
        file_content: str,
        instruction: str
    ) -> str:
        """
        精确替换 - 适用于小文件
        
        让 AI 生成 SEARCH/REPLACE 块，然后精确替换
        """
        # 如果有代码生成器，使用 AI 辅助
        if self.code_generator:
            return self._ai_assisted_replace(file_path, file_content, instruction)
        
        # 否则返回原始内容（需要外部处理）
        logger.warning(f"没有代码生成器，无法修改: {file_path}")
        return file_content
    
    def _ai_assisted_replace(
        self,
        file_path: str,
        file_content: str,
        instruction: str
    ) -> str:
        """
        AI 辅助的精确替换
        
        让 AI 生成 SEARCH/REPLACE 格式，然后执行替换
        """
        # 构建提示词
        prompt = f"""提供代码修改的 SEARCH/REPLACE 格式。

## 文件

{file_path}

## 当前内容

```
{file_content}
```

## 修改指令

{instruction}

## 输出格式

必须严格使用以下格式：

SEARCH:
```
要查找的精确代码（包含足够的上下文，3-5行）
```
REPLACE:
```
替换后的新代码
```

要求：
1. SEARCH 块必须能在原代码中精确匹配
2. 包含足够的上下文确保匹配唯一性
3. 只修改需要修改的地方"""
        
        # 调用 AI 生成 SEARCH/REPLACE
        logger.info(f"请求 AI 生成精确替换: {file_path}")
        response = self.code_generator._generate(prompt, temperature=0.1)
        
        # 解析 SEARCH/REPLACE
        search_match = re.search(r'SEARCH:\s*```\s*\n?(.*?)\n?```', response, re.DOTALL)
        replace_match = re.search(r'REPLACE:\s*```\s*\n?(.*?)\n?```', response, re.DOTALL)
        
        if not search_match or not replace_match:
            logger.error("AI 没有提供有效的 SEARCH/REPLACE 格式")
            raise ValueError("AI 没有提供有效的 SEARCH/REPLACE 格式")
        
        search_text = search_match.group(1).strip()
        replace_text = replace_match.group(1).strip()
        
        # 执行替换
        if search_text in file_content:
            new_content = file_content.replace(search_text, replace_text, 1)
            logger.info(f"✅ 精确替换成功: {file_path}")
            return new_content
        else:
            logger.error(f"❌ SEARCH 文本未找到: {file_path}")
            logger.debug(f"SEARCH 文本: {search_text[:100]}...")
            raise ValueError(f"无法在文件中找到要替换的文本: {search_text[:50]}...")
    
    def _chunked_modify(
        self,
        file_path: str,
        file_content: str,
        instruction: str
    ) -> str:
        """
        分段修改 - 适用于大文件
        
        1. 让 AI 找出需要修改的行号范围
        2. 提取相关代码段
        3. 对代码段使用精确替换
        4. 合并回原始文件
        """
        lines = file_content.split('\n')
        total_lines = len(lines)
        
        logger.info(f"大文件 ({total_lines} 行)，使用分段处理: {file_path}")
        
        # 第一步：让 AI 找出需要修改的行号
        line_prompt = f"""分析大文件，找出需要修改的行号。

文件: {file_path}
总行数: {total_lines}

文件开头（前50行）：
```
{'\n'.join(lines[:50])}
```

修改指令: {instruction}

## 任务

找出需要修改的行号范围。

## 输出格式

返回 JSON：
```json
{{
  "modifications": [
    {{"start_line": 10, "end_line": 20, "description": "修改说明"}}
  ]
}}
```"""
        
        response = self.code_generator._generate(line_prompt, temperature=0.1)
        
        try:
            # 解析 JSON
            import json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                modifications = data.get("modifications", [])
                
                # 应用修改
                new_content = file_content
                for mod in modifications:
                    start = mod.get("start_line", 1) - 1
                    end = mod.get("end_line", total_lines)
                    desc = mod.get("description", "")
                    
                    # 提取上下文（前后各3行）
                    context_start = max(0, start - 3)
                    context_end = min(total_lines, end + 3)
                    chunk = '\n'.join(lines[context_start:context_end])
                    
                    # 修改这个 chunk
                    modified_chunk = self._ai_assisted_replace(
                        file_path,
                        chunk,
                        f"{instruction}\n具体: {desc}"
                    )
                    
                    # 替换回原内容
                    new_content = new_content.replace(chunk, modified_chunk, 1)
                
                return new_content
        except Exception as e:
            logger.error(f"分段修改失败: {e}")
        
        # 失败时返回原始内容（安全回退）
        logger.warning(f"⚠️  分段修改失败，返回原始内容: {file_path}")
        return file_content
    
    def create_new_file(
        self,
        file_path: str,
        instruction: str,
        context: str = None
    ) -> str:
        """
        创建新文件
        
        Args:
            file_path: 新文件路径
            instruction: 创建指令
            context: 可选上下文
            
        Returns:
            新文件内容
        """
        if not self.code_generator:
            raise ValueError("需要代码生成器才能创建文件")
        
        context_str = f"\n\n上下文:\n{context}" if context else ""
        
        prompt = f"""创建新文件。

文件路径: {file_path}
{context_str}

要求:
{instruction}

返回完整的文件内容，不要加 markdown 代码块。"""
        
        logger.info(f"创建新文件: {file_path}")
        content = self.code_generator._generate(prompt, temperature=0.3)
        
        # 清理代码块标记
        return self.code_generator._extract_code(content)
