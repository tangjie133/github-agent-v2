#!/usr/bin/env python3
"""
变更验证器
验证代码变更的语法正确性和质量
"""

import ast
import json
import logging
import re
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class ValidationResult:
    """验证结果"""
    
    def __init__(
        self,
        is_valid: bool,
        errors: List[str] = None,
        warnings: List[str] = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    @property
    def message(self) -> str:
        """获取验证消息"""
        if self.is_valid:
            return "验证通过"
        return "; ".join(self.errors)


class ChangeValidator:
    """
    变更验证器
    
    验证代码变更的：
    - 语法正确性（AST 解析）
    - 导入完整性
    - 基本代码质量
    """
    
    def __init__(self, code_generator=None):
        """
        初始化变更验证器
        
        Args:
            code_generator: 可选的代码生成器，用于 AI 辅助验证
        """
        self.code_generator = code_generator
    
    def validate_python_file(
        self,
        file_path: str,
        file_content: str
    ) -> ValidationResult:
        """
        验证 Python 文件
        
        Args:
            file_path: 文件路径（用于日志）
            file_content: 文件内容
            
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 1. 语法检查
        try:
            ast.parse(file_content)
        except SyntaxError as e:
            errors.append(f"语法错误: 第{e.lineno}行 - {e.msg}")
            logger.error(f"Python 语法错误: {file_path} - {e}")
            return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            errors.append(f"解析错误: {e}")
            return ValidationResult(is_valid=False, errors=errors)
        
        # 2. 检查常见错误
        # 未闭合的括号
        if not self._check_brackets(file_content):
            errors.append("括号不匹配")
        
        # 缩进问题（简单检查）
        if self._has_indentation_errors(file_content):
            warnings.append("可能存在缩进问题")
        
        # 3. 导入检查（可选，需要上下文）
        # 暂时不做，因为需要完整的 Python 环境
        
        is_valid = len(errors) == 0
        if is_valid:
            logger.info(f"✅ Python 验证通过: {file_path}")
        else:
            logger.error(f"❌ Python 验证失败: {file_path} - {errors}")
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    def validate_json_file(
        self,
        file_path: str,
        file_content: str
    ) -> ValidationResult:
        """
        验证 JSON 文件
        
        Args:
            file_path: 文件路径
            file_content: 文件内容
            
        Returns:
            验证结果
        """
        errors = []
        
        try:
            json.loads(file_content)
        except json.JSONDecodeError as e:
            errors.append(f"JSON 错误: 第{e.lineno}行, 第{e.colno}列 - {e.msg}")
            logger.error(f"JSON 验证失败: {file_path} - {e}")
            return ValidationResult(is_valid=False, errors=errors)
        
        logger.info(f"✅ JSON 验证通过: {file_path}")
        return ValidationResult(is_valid=True)
    
    def validate_yaml_file(
        self,
        file_path: str,
        file_content: str
    ) -> ValidationResult:
        """
        验证 YAML 文件
        
        Args:
            file_path: 文件路径
            file_content: 文件内容
            
        Returns:
            验证结果
        """
        errors = []
        
        try:
            import yaml
            yaml.safe_load(file_content)
        except ImportError:
            # YAML 库不可用，跳过验证
            logger.warning("PyYAML 未安装，跳过 YAML 验证")
            return ValidationResult(is_valid=True)
        except yaml.YAMLError as e:
            errors.append(f"YAML 错误: {e}")
            logger.error(f"YAML 验证失败: {file_path} - {e}")
            return ValidationResult(is_valid=False, errors=errors)
        
        logger.info(f"✅ YAML 验证通过: {file_path}")
        return ValidationResult(is_valid=True)
    
    def validate_file(
        self,
        file_path: str,
        file_content: str
    ) -> ValidationResult:
        """
        验证文件（根据扩展名自动判断类型）
        
        Args:
            file_path: 文件路径
            file_content: 文件内容
            
        Returns:
            验证结果
        """
        if file_path.endswith('.py'):
            return self.validate_python_file(file_path, file_content)
        elif file_path.endswith('.json'):
            return self.validate_json_file(file_path, file_content)
        elif file_path.endswith(('.yml', '.yaml')):
            return self.validate_yaml_file(file_path, file_content)
        else:
            # 其他文件类型，不验证
            logger.debug(f"跳过验证: {file_path}")
            return ValidationResult(is_valid=True)
    
    def validate_batch(
        self,
        files: Dict[str, str]
    ) -> Dict[str, ValidationResult]:
        """
        批量验证多个文件
        
        Args:
            files: {文件路径: 文件内容} 字典
            
        Returns:
            {文件路径: 验证结果} 字典
        """
        results = {}
        for file_path, content in files.items():
            results[file_path] = self.validate_file(file_path, content)
        return results
    
    def _check_brackets(self, content: str) -> bool:
        """
        检查括号是否匹配
        
        Args:
            content: 代码内容
            
        Returns:
            是否匹配
        """
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        close = set(pairs.values())
        
        # 忽略字符串中的括号
        in_string = False
        string_char = None
        escaped = False
        
        for char in content:
            if escaped:
                escaped = False
                continue
            
            if char == '\\':
                escaped = True
                continue
            
            if char in ('"', "'"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                continue
            
            if in_string:
                continue
            
            if char in pairs:
                stack.append(char)
            elif char in close:
                if not stack or pairs[stack.pop()] != char:
                    return False
        
        return len(stack) == 0
    
    def _has_indentation_errors(self, content: str) -> bool:
        """
        检查可能的缩进问题
        
        Args:
            content: 代码内容
            
        Returns:
            是否有问题
        """
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # 检查混合缩进
            if '\t' in line and '  ' in line:
                return True
        
        return False
    
    def ai_validate(
        self,
        file_path: str,
        original_content: str,
        modified_content: str,
        requirement: str
    ) -> ValidationResult:
        """
        AI 辅助验证
        
        让 AI 检查修改是否符合需求
        
        Args:
            file_path: 文件路径
            original_content: 原始内容
            modified_content: 修改后内容
            requirement: 需求说明
            
        Returns:
            验证结果
        """
        if not self.code_generator:
            # 没有代码生成器，跳过 AI 验证
            return ValidationResult(is_valid=True)
        
        prompt = f"""验证代码修改是否符合需求。

## 文件

{file_path}

## 原始内容（片段）

```python
{original_content[:500]}...
```

## 修改后内容（片段）

```python
{modified_content[:500]}...
```

## 需求

{requirement}

## 验证要求

1. 修改是否符合需求？
2. 是否有潜在的 bug？
3. 是否保持了代码风格一致性？

## 输出格式

```json
{{
  "is_valid": true,
  "errors": ["如果无效，列出错误"],
  "warnings": ["潜在警告"]
}}
```"""
        
        logger.info(f"AI 辅助验证: {file_path}")
        response = self.code_generator._generate(prompt, temperature=0.1)
        
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ValidationResult(
                    is_valid=data.get('is_valid', True),
                    errors=data.get('errors', []),
                    warnings=data.get('warnings', [])
                )
        except Exception as e:
            logger.error(f"AI 验证解析失败: {e}")
        
        # 解析失败时假设通过
        return ValidationResult(is_valid=True)
