#!/usr/bin/env python3
"""
GitHub 仓库知识库同步工具

同步文件到 GITHUB_AGENT_STATEDIR/knowledge_base/ 目录
通知 KB Service 重新加载
"""

import os
import sys
import json
import time
import argparse
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging

# 首先加载 .env 文件（在设置任何路径之前）
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)  # override=True 确保 .env 中的值覆盖环境变量
except ImportError:
    pass

# 配置日志
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_REPO = "tangjie133/knowledge-base"
DEFAULT_BRANCH = "main"
KB_SERVICE_URL = os.environ.get("KB_SERVICE_URL", "http://localhost:8000")


def get_statedir() -> Path:
    """获取状态目录（从环境变量，默认 /tmp/github-agent-state）"""
    statedir = Path(os.environ.get("GITHUB_AGENT_STATEDIR", "/tmp/github-agent-state"))
    return statedir


def get_kb_dirs():
    """获取知识库目录路径"""
    statedir = get_statedir()
    kb_base = statedir / "knowledge_base"
    return {
        "base": kb_base,
        "chips": kb_base / "chips",
        "practices": kb_base / "best_practices",
        "sync_state": statedir / ".github_kb_sync_state.json"
    }


class GitHubKBWatcher:
    """GitHub 知识库同步器"""
    
    def __init__(self, repo: str = None, branch: str = None, token: str = None):
        self.repo = repo or os.environ.get("KB_REPO", DEFAULT_REPO)
        self.branch = branch or os.environ.get("KB_BRANCH", DEFAULT_BRANCH)
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        
        self.api_base = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-KB-Watcher"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        
        # 获取路径配置
        self.paths = get_kb_dirs()
        
        # 确保目录存在
        self.paths["chips"].mkdir(parents=True, exist_ok=True)
        self.paths["practices"].mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 知识库目录: {self.paths['base']}")
        logger.info(f"📁 同步状态: {self.paths['sync_state']}")
        logger.info(f"📁 状态根目录: {get_statedir()}")
    
    def _api_get(self, url: str, params: dict = None) -> dict:
        """调用 GitHub API"""
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise RuntimeError("GitHub API 速率限制，请设置 GITHUB_TOKEN")
        response.raise_for_status()
        return response.json()
    
    def get_repo_files(self) -> List[dict]:
        """获取仓库文件列表"""
        url = f"{self.api_base}/git/trees/{self.branch}"
        params = {"recursive": "1"}
        
        try:
            data = self._api_get(url, params)
            files = []
            for item in data.get("tree", []):
                if item["type"] == "blob":
                    ext = Path(item["path"]).suffix.lower()
                    if ext in {'.md', '.pdf'}:
                        files.append({
                            "path": item["path"],
                            "sha": item["sha"]
                        })
            logger.info(f"📋 发现 {len(files)} 个知识库文件")
            return files
        except Exception as e:
            logger.error(f"❌ 获取文件列表失败: {e}")
            return []
    
    def download_file(self, file_path: str, local_path: Path) -> bool:
        """下载单个文件"""
        try:
            url = f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{file_path}"
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()
            
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(response.content)
            return True
        except Exception as e:
            logger.error(f"❌ 下载失败 {file_path}: {e}")
            return False
    
    def _classify_file(self, file_path: str) -> Path:
        """根据文件路径分类到本地目录"""
        path_lower = file_path.lower()
        
        # 根据路径关键词分类
        if any(k in path_lower for k in ['chip', 'datasheet', 'sensor', 'mcu', 'cpu']):
            return self.paths["chips"]
        elif any(k in path_lower for k in ['practice', 'best', 'guide', 'tutorial', 'howto']):
            return self.paths["practices"]
        else:
            # 根据文件扩展名默认分类
            ext = Path(file_path).suffix.lower()
            if ext == '.pdf':
                return self.paths["chips"]
            return self.paths["practices"]
    
    def _load_sync_state(self) -> Dict[str, str]:
        """加载同步状态"""
        if self.paths["sync_state"].exists():
            try:
                return json.loads(self.paths["sync_state"].read_text())
            except:
                pass
        return {}
    
    def _save_sync_state(self, state: Dict[str, str]):
        """保存同步状态"""
        self.paths["sync_state"].write_text(json.dumps(state, indent=2))
    
    def sync_files(self, files: List[dict]) -> dict:
        """同步文件到本地"""
        sync_state = self._load_sync_state()
        stats = {'total': len(files), 'skipped': 0, 'success': 0, 'failed': 0}
        
        for file_info in files:
            file_path = file_info["path"]
            file_sha = file_info["sha"]
            
            # 检查是否需要更新
            if file_path in sync_state and sync_state[file_path] == file_sha:
                logger.debug(f"⏭️  跳过: {file_path}")
                stats['skipped'] += 1
                continue
            
            # 确定本地存储路径
            target_dir = self._classify_file(file_path)
            local_path = target_dir / Path(file_path).name
            
            is_update = file_path in sync_state
            action = "更新" if is_update else "新增"
            logger.info(f"🔄 {action}: {file_path}")
            
            # 下载文件
            if self.download_file(file_path, local_path):
                sync_state[file_path] = file_sha
                stats['success'] += 1
                logger.info(f"   ✅ 已保存到: {local_path}")
            else:
                stats['failed'] += 1
        
        self._save_sync_state(sync_state)
        
        # 打印统计
        logger.info(f"\n📊 同步统计:")
        logger.info(f"   总计: {stats['total']} 个")
        logger.info(f"   ⏭️  跳过: {stats['skipped']} 个")
        logger.info(f"   ✅ 成功: {stats['success']} 个")
        if stats['failed'] > 0:
            logger.info(f"   ❌ 失败: {stats['failed']} 个")
        
        # 通知 KB Service
        if stats['success'] > 0:
            self._notify_kb_reload()
        
        return stats
    
    def _notify_kb_reload(self):
        """通知 KB Service 重新加载"""
        try:
            # 检查服务状态
            resp = requests.get(f"{KB_SERVICE_URL}/health", timeout=5)
            if resp.status_code != 200:
                logger.warning("   KB Service 未运行")
                return
            
            logger.info("🔄 通知 KB Service 重新加载...")
            resp = requests.post(f"{KB_SERVICE_URL}/reload", timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"✅ 重新加载完成")
            else:
                logger.warning(f"⚠️  重新加载失败: {resp.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  通知 KB Service 失败: {e}")
            logger.info("   💡 请手动重启 KB Service")
    
    def run_sync(self) -> dict:
        """执行完整同步"""
        logger.info(f"🚀 开始同步仓库: {self.repo} ({self.branch})")
        logger.info(f"   状态目录: {get_statedir()}")
        
        files = self.get_repo_files()
        if not files:
            logger.warning("⚠️  没有需要同步的文件")
            return {'total': 0, 'skipped': 0, 'success': 0, 'failed': 0}
        
        return self.sync_files(files)
    
    def run_daemon(self, interval: int = 300):
        """后台监控模式"""
        logger.info(f"👁️  开始监控: {self.repo}")
        logger.info(f"   检查间隔: {interval} 秒")
        logger.info(f"   状态目录: {get_statedir()}")
        
        try:
            while True:
                logger.info(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 检查更新...")
                self.run_sync()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("\n✅ 监控已停止")


def main():
    parser = argparse.ArgumentParser(description="GitHub 知识库同步工具")
    parser.add_argument("--repo", "-r", default=DEFAULT_REPO, help="仓库地址")
    parser.add_argument("--branch", "-b", default=DEFAULT_BRANCH, help="分支")
    parser.add_argument("--token", "-t", help="GitHub Token")
    parser.add_argument("--sync", "-s", action="store_true", help="立即同步一次")
    parser.add_argument("--daemon", "-d", action="store_true", help="后台监控")
    parser.add_argument("--interval", "-i", type=int, default=300, help="检查间隔(秒)")
    args = parser.parse_args()
    
    watcher = GitHubKBWatcher(repo=args.repo, branch=args.branch, token=args.token)
    
    if args.sync:
        watcher.run_sync()
    elif args.daemon:
        watcher.run_daemon(interval=args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
