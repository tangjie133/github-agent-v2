#!/usr/bin/env python3
"""
仓库管理器
处理本地 Git 操作：克隆、分支、提交、推送
"""

import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    仓库管理器
    
    管理本地 Git 仓库：
    - 克隆或更新仓库
    - 创建分支
    - 提交和推送修改
    - 获取文件内容
    """
    
    def __init__(self, work_dir: str = None):
        """
        初始化仓库管理器
        
        Args:
            work_dir: 工作目录，默认使用环境变量或 /tmp/github-agent-v2
        """
        self.work_dir = Path(work_dir or os.environ.get(
            "GITHUB_AGENT_WORKDIR", "/tmp/github-agent-v2"
        ))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"仓库管理器初始化: 工作目录={self.work_dir}")
    
    def get_repo_path(self, owner: str, repo: str) -> Path:
        """
        获取仓库本地路径
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            
        Returns:
            本地路径
        """
        return self.work_dir / f"{owner}-{repo}"
    
    def clone_or_update(
        self,
        clone_url: str,
        owner: str,
        repo: str
    ) -> Path:
        """
        克隆或更新仓库
        
        Args:
            clone_url: 带认证的克隆 URL
            owner: 仓库所有者
            repo: 仓库名
            
        Returns:
            本地仓库路径
        """
        repo_path = self.get_repo_path(owner, repo)
        
        if repo_path.exists():
            # 更新已有仓库
            logger.info(f"更新已有仓库: {repo_path}")
            try:
                # 获取最新代码
                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                # 重置到 main 分支最新状态
                subprocess.run(
                    ["git", "reset", "--hard", "origin/main"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"✅ 仓库更新成功: {repo_path}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"更新失败，重新克隆: {e}")
                shutil.rmtree(repo_path)
                return self.clone_or_update(clone_url, owner, repo)
        else:
            # 克隆新仓库
            logger.info(f"克隆仓库到: {repo_path}")
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                logger.info(f"✅ 仓库克隆成功: {repo_path}")
            except subprocess.TimeoutExpired:
                logger.error("克隆超时")
                raise RuntimeError("Git 克隆超时，请检查网络")
            except subprocess.CalledProcessError as e:
                logger.error(f"克隆失败: {e.stderr}")
                raise
        
        return repo_path
    
    def create_branch(
        self,
        repo_path: Path,
        branch_name: str,
        base_branch: str = "main"
    ) -> None:
        """
        创建并切换到新分支
        
        Args:
            repo_path: 仓库本地路径
            branch_name: 新分支名
            base_branch: 基础分支
        """
        # 确保在基础分支上
        subprocess.run(
            ["git", "checkout", base_branch],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 拉取最新代码
        subprocess.run(
            ["git", "pull", "origin", base_branch],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 创建新分支
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"✅ 创建分支: {branch_name}")
        except subprocess.CalledProcessError:
            # 分支可能已存在，直接切换
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"切换到已有分支: {branch_name}")
    
    def commit_and_push(
        self,
        repo_path: Path,
        message: str,
        branch: str,
        clone_url: str = None
    ) -> bool:
        """
        提交并推送修改
        
        Args:
            repo_path: 仓库本地路径
            message: 提交信息
            branch: 分支名
            clone_url: 带认证的克隆 URL（用于更新 remote）
            
        Returns:
            是否有实际变更并提交
        """
        # 配置 git 用户（如果未配置）
        try:
            subprocess.run(
                ["git", "config", "user.email"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError:
            # 未配置，设置默认值
            subprocess.run(
                ["git", "config", "user.email", "github-agent@openclaw.local"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            subprocess.run(
                ["git", "config", "user.name", "GitHub Agent"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
        
        # 如果需要，更新 remote URL（使用带 token 的 URL）
        if clone_url:
            logger.info("更新 remote URL")
            subprocess.run(
                ["git", "remote", "set-url", "origin", clone_url],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
        
        # 添加所有修改
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 检查是否有变更
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        if not status_result.stdout.strip():
            logger.info("没有变更需要提交")
            return False
        
        # 提交
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # 推送
        logger.info(f"推送到 origin/{branch}")
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"✅ 推送成功: {branch}")
        except subprocess.CalledProcessError as e:
            # 推送失败，可能是远程分支有新提交
            logger.warning(f"推送失败: {e}")
            logger.info("尝试删除远程分支后重推...")
            
            # 删除远程分支
            subprocess.run(
                ["git", "push", "origin", "--delete", branch],
                cwd=repo_path,
                check=False,  # 分支可能不存在
                capture_output=True,
                text=True
            )
            
            # 重新推送
            subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"✅ 重推成功: {branch}")
        
        return True
    
    def get_file_content(self, repo_path: Path, file_path: str) -> Optional[str]:
        """
        获取文件内容
        
        Args:
            repo_path: 仓库本地路径
            file_path: 文件相对路径
            
        Returns:
            文件内容，如果文件不存在返回 None
        """
        full_path = repo_path / file_path
        if not full_path.exists():
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return None
    
    def write_file(self, repo_path: Path, file_path: str, content: str) -> None:
        """
        写入文件
        
        Args:
            repo_path: 仓库本地路径
            file_path: 文件相对路径
            content: 文件内容
        """
        full_path = repo_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.debug(f"写入文件: {file_path}")
    
    def list_files(self, repo_path: Path, pattern: str = "*") -> List[str]:
        """
        列出文件
        
        Args:
            repo_path: 仓库本地路径
            pattern: 匹配模式，如 "*.py"
            
        Returns:
            文件路径列表
        """
        files = []
        for f in repo_path.rglob(pattern):
            if f.is_file() and '.git' not in str(f.relative_to(repo_path)):
                files.append(str(f.relative_to(repo_path)))
        return files
    
    def cleanup(self, owner: str, repo: str) -> None:
        """
        清理仓库目录
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
        """
        repo_path = self.get_repo_path(owner, repo)
        if repo_path.exists():
            logger.info(f"清理仓库: {repo_path}")
            shutil.rmtree(repo_path)
