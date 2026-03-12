#!/usr/bin/env python3
"""
代码执行器主类

整合所有代码执行组件，提供统一的执行接口：
- CodeGenerator: 代码生成
- SafeCodeModifier: 安全修改
- RepositoryManager: 仓库管理
- ChangeValidator: 变更验证
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .code_generator import CodeGenerator
from .safe_modifier import SafeCodeModifier
from .repo_manager import RepositoryManager
from .change_validator import ChangeValidator

logger = logging.getLogger(__name__)


class CodeExecutor:
    """
    代码执行器
    
    整合代码生成、修改、版本控制的完整工作流：
    1. 分析需求
    2. 获取仓库上下文
    3. 生成代码修改
    4. 安全应用修改
    5. 验证变更
    6. 创建 PR
    """
    
    def __init__(
        self,
        code_generator: CodeGenerator,
        repo_manager: RepositoryManager,
        safe_modifier: SafeCodeModifier,
        validator: ChangeValidator
    ):
        """
        初始化代码执行器
        
        Args:
            code_generator: 代码生成器
            repo_manager: 仓库管理器
            safe_modifier: 安全修改器
            validator: 变更验证器
        """
        self.code_gen = code_generator
        self.repo_mgr = repo_manager
        self.modifier = safe_modifier
        self.validator = validator
        
        logger.info("代码执行器初始化完成")
    
    def execute_task(
        self,
        task_type: str,
        instruction: str,
        context: str,
        repo_full_name: str,
        issue_number: int,
        github_token: str = None,
        files_to_modify: List[str] = None
    ) -> Dict[str, Any]:
        """
        执行代码任务
        
        Args:
            task_type: 任务类型 (fix_issue, implement_feature, etc.)
            instruction: 用户指令
            context: 完整上下文（Issue 信息 + 知识库参考）
            repo_full_name: 仓库全名 (owner/repo)
            issue_number: Issue 编号
            github_token: GitHub 安装令牌
            files_to_modify: 指定要修改的文件列表
            
        Returns:
            执行结果，包含状态、PR 信息、错误等
        """
        logger.info(f"执行任务: {task_type} for {repo_full_name}#{issue_number}")
        
        # 解析仓库信息
        owner, repo = repo_full_name.split('/')
        
        # 构造分支名
        branch_name = f"agent-fix-{issue_number}"
        
        # 构造认证克隆 URL
        clone_url = None
        if github_token:
            clone_url = f"https://x-access-token:{github_token}@github.com/{repo_full_name}.git"
        
        try:
            # Step 1: 克隆/更新仓库
            logger.info(f"准备仓库: {repo_full_name}")
            repo_path = self.repo_mgr.clone_or_update(clone_url, owner, repo)
            
            # Step 2: 创建分支
            logger.info(f"创建分支: {branch_name}")
            self.repo_mgr.create_branch(repo_path, branch_name)
            
            # Step 3: 分析需求并生成修改
            files_modified = []
            
            if files_to_modify:
                # 修改指定文件
                for file_path in files_to_modify:
                    success = self._modify_file(
                        repo_path, file_path, instruction, context
                    )
                    if success:
                        files_modified.append(file_path)
            else:
                # AI 分析并选择文件
                files_to_edit = self._analyze_files_to_edit(
                    repo_path, instruction, context
                )
                for file_path in files_to_edit:
                    success = self._modify_file(
                        repo_path, file_path, instruction, context
                    )
                    if success:
                        files_modified.append(file_path)
            
            if not files_modified:
                return {
                    "status": "failed",
                    "error": "没有成功修改任何文件"
                }
            
            # Step 4: 提交并推送
            commit_message = f"fix: {instruction[:50]}... (fixes #{issue_number})"
            has_changes = self.repo_mgr.commit_and_push(
                repo_path, commit_message, branch_name, clone_url
            )
            
            if not has_changes:
                return {
                    "status": "failed",
                    "error": "没有可提交的变更"
                }
            
            # Step 5: 创建 PR
            if github_token:
                from core.github_client import GitHubClient
                github = GitHubClient(github_token)
                
                pr_title = f"[Agent] {instruction[:80]}"
                pr_body = f"""🤖 此 PR 由 GitHub Agent 自动创建

## 修改说明

{instruction}

## 修改的文件

{chr(10).join([f'- `{f}`' for f in files_modified])}

---
fixes #{issue_number}
"""
                pr = github.create_pull_request(
                    owner, repo,
                    title=pr_title,
                    head=branch_name,
                    base="main",
                    body=pr_body
                )
                
                if pr:
                    return {
                        "status": "completed",
                        "pr_number": pr["number"],
                        "pr_url": pr["html_url"],
                        "files_modified": files_modified,
                        "branch": branch_name
                    }
            
            # 没有 GitHub token，只能返回分支信息
            return {
                "status": "completed",
                "branch": branch_name,
                "files_modified": files_modified,
                "message": "分支已推送，请手动创建 PR"
            }
        
        except Exception as e:
            logger.exception("代码执行失败")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _analyze_files_to_edit(
        self,
        repo_path: Path,
        instruction: str,
        context: str
    ) -> List[str]:
        """
        分析需要修改的文件
        
        让 AI 根据指令分析哪些文件需要修改
        
        Args:
            repo_path: 仓库本地路径
            instruction: 用户指令
            context: 完整上下文
            
        Returns:
            需要修改的文件列表
        """
        # 获取仓库文件列表（仅关键文件）
        all_files = []
        for pattern in ["*.py", "*.js", "*.ts", "*.json", "*.md"]:
            files = self.repo_mgr.list_files(repo_path, pattern)
            all_files.extend(files[:20])  # 限制数量
        
        # 构建分析提示
        prompt = f"""分析以下 Issue 指令，判断需要修改哪些文件。

## 指令

{instruction}

## 上下文

{context[:500]}

## 仓库文件列表

{chr(10).join(all_files[:30])}

## 输出格式

只返回 JSON 数组：
```json
["src/main.py", "src/utils.py"]
```

最多选择 3 个最相关的文件。如果没有合适的文件，返回空数组 []。"""
        
        response = self.code_gen._generate(prompt, temperature=0.1)
        
        try:
            import json
            import re
            
            # 提取 JSON
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                files = json.loads(json_match.group())
                logger.info(f"AI 选择修改文件: {files}")
                return files
        except Exception as e:
            logger.warning(f"解析文件列表失败: {e}")
        
        # 失败时返回空列表
        return []
    
    def _modify_file(
        self,
        repo_path: Path,
        file_path: str,
        instruction: str,
        context: str
    ) -> bool:
        """
        修改单个文件
        
        Args:
            repo_path: 仓库本地路径
            file_path: 文件相对路径
            instruction: 修改指令
            context: 完整上下文
            
        Returns:
            是否成功
        """
        logger.info(f"修改文件: {file_path}")
        
        # 获取当前内容
        original_content = self.repo_mgr.get_file_content(repo_path, file_path)
        
        if original_content is None:
            # 文件不存在，可能是创建新文件
            if self._should_create_new_file(file_path, instruction):
                logger.info(f"创建新文件: {file_path}")
                new_content = self.modifier.create_new_file(
                    file_path, instruction, context
                )
                self.repo_mgr.write_file(repo_path, file_path, new_content)
                
                # 验证
                val_result = self.validator.validate_file(file_path, new_content)
                if not val_result.is_valid:
                    logger.error(f"新文件验证失败: {val_result.message}")
                    return False
                
                return True
            else:
                logger.warning(f"文件不存在: {file_path}")
                return False
        
        # 修改现有文件
        try:
            new_content = self.modifier.modify_file(
                file_path, original_content, instruction
            )
            
            # 验证修改
            val_result = self.validator.validate_file(file_path, new_content)
            if not val_result.is_valid:
                logger.error(f"修改验证失败: {val_result.message}")
                return False
            
            # 写入修改
            self.repo_mgr.write_file(repo_path, file_path, new_content)
            logger.info(f"✅ 文件修改成功: {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"修改文件失败 {file_path}: {e}")
            return False
    
    def _should_create_new_file(self, file_path: str, instruction: str) -> bool:
        """
        判断是否应该创建新文件
        
        根据指令内容判断用户的意图
        
        Args:
            file_path: 文件路径
            instruction: 指令
            
        Returns:
            是否应该创建
        """
        # 简单的启发式判断
        create_keywords = [
            "创建", "新建", "添加", "create", "new", "add",
            "增加", "implement", "添加文件", "create file"
        ]
        
        instruction_lower = instruction.lower()
        for keyword in create_keywords:
            if keyword.lower() in instruction_lower:
                return True
        
        # 检查是否提到特定的新文件
        if file_path.split('/')[-1].lower() in instruction_lower:
            return True
        
        return False
