#!/usr/bin/env python3
"""
GitHub 仓库知识库同步工具

监听指定 GitHub 仓库，自动拉取新文件并转换为知识库格式

支持的文件格式：
- .md - Markdown 文件（直接使用）
- .txt - 文本文件（转换为 Markdown）
- .pdf - PDF 文档（提取文本后转换）
- .docx - Word 文档（转换为 Markdown）

用法：
    # 手动同步一次
    python github_repo_watcher.py --sync
    
    # 后台监控模式（定期检查更新）
    python github_repo_watcher.py --daemon --interval 300
    
    # 配置 Webhook 自动触发
    python github_repo_watcher.py --webhook --port 9000
"""

import os
import sys
import json
import time
import argparse
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Set, Dict
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_REPO = "tangjie133/knowledge-base"
DEFAULT_BRANCH = "main"
KB_CHIPS_DIR = Path(__file__).parent.parent / "knowledge_base" / "chips"
KB_PRACTICES_DIR = Path(__file__).parent.parent / "knowledge_base" / "best_practices"
SYNC_STATE_FILE = Path(__file__).parent.parent / ".github_kb_sync_state.json"

# 支持的文件格式
SUPPORTED_EXTS = {'.md', '.txt', '.pdf', '.docx'}


class GitHubRepoWatcher:
    """GitHub 仓库监听器"""
    
    def __init__(self, repo: str, branch: str = "main", token: str = None):
        self.repo = repo
        self.branch = branch
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.api_base = "https://api.github.com"
        self.raw_base = "https://raw.githubusercontent.com"
        
    def _get_headers(self) -> Dict[str, str]:
        """获取 API 请求头"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Agent-KB-Sync"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    def _get_proxies(self) -> Dict[str, str]:
        """获取代理配置"""
        proxies = {}
        
        # 从环境变量读取代理配置
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        all_proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")
        
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy
        if all_proxy and not proxies:
            proxies["http"] = all_proxy
            proxies["https"] = all_proxy
            
        return proxies
    
    def get_repo_files(self) -> List[Dict]:
        """获取仓库文件列表"""
        import requests
        
        url = f"{self.api_base}/repos/{self.repo}/git/trees/{self.branch}?recursive=1"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self._get_headers(), proxies=self._get_proxies(), timeout=30)
                
                # 处理速率限制
                if response.status_code == 403 and "rate limit" in response.text.lower():
                    if not self.token:
                        logger.error("❌ GitHub API 速率限制 exceeded")
                        logger.error("   原因: 未提供 GITHUB_TOKEN")
                        logger.error("   解决: 设置 GITHUB_TOKEN 环境变量")
                        logger.error("   获取: https://github.com/settings/tokens")
                        return []
                    else:
                        # 有 token 但仍然被限制，等待重试
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        if reset_time:
                            wait_sec = max(reset_time - int(time.time()), 60)
                            logger.warning(f"⚠️  API 速率限制，等待 {wait_sec} 秒后重试...")
                            time.sleep(min(wait_sec, 60))  # 最多等待60秒
                            continue
                
                response.raise_for_status()
                data = response.json()
                
                files = []
                for item in data.get("tree", []):
                    if item.get("type") == "blob":
                        ext = Path(item["path"]).suffix.lower()
                        if ext in SUPPORTED_EXTS:
                            files.append({
                                "path": item["path"],
                                "sha": item["sha"],
                                "size": item.get("size", 0),
                                "url": item["url"]
                            })
                
                logger.info(f"📁 发现 {len(files)} 个支持的文件")
                return files
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 指数退避
                    logger.warning(f"⚠️  请求失败，{wait}秒后重试... ({e})")
                    time.sleep(wait)
                else:
                    logger.error(f"❌ 获取文件列表失败: {e}")
                    return []
            except Exception as e:
                logger.error(f"❌ 获取文件列表失败: {e}")
                return []
        
        return []
    
    def download_file(self, file_path: str, output_path: Path) -> bool:
        """下载单个文件"""
        import requests
        
        url = f"{self.raw_base}/{self.repo}/{self.branch}/{file_path}"
        
        try:
            response = requests.get(url, headers=self._get_headers(), proxies=self._get_proxies(), timeout=60)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            logger.info(f"⬇️  下载: {file_path} ({len(response.content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 下载失败 {file_path}: {e}")
            return False
    
    def convert_to_markdown(self, input_path: Path, output_path: Path) -> bool:
        """将文件转换为 Markdown"""
        ext = input_path.suffix.lower()
        
        try:
            if ext == '.md':
                # 直接复制
                content = input_path.read_text(encoding='utf-8')
                output_path.write_text(content, encoding='utf-8')
                
            elif ext == '.txt':
                # 文本文件包装为 Markdown
                content = input_path.read_text(encoding='utf-8')
                md_content = f"# {input_path.stem}\n\n```\n{content}\n```\n"
                output_path.write_text(md_content, encoding='utf-8')
                
            elif ext == '.pdf':
                # PDF 提取文本
                result = subprocess.run(
                    ["pdftotext", "-layout", str(input_path), "-"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                content = result.stdout
                md_content = f"# {input_path.stem}\n\n## 内容\n\n{content}\n"
                output_path.write_text(md_content, encoding='utf-8')
                
            elif ext == '.docx':
                # Word 文档转换（如果安装了 pandoc）
                try:
                    result = subprocess.run(
                        ["pandoc", str(input_path), "-t", "markdown", "-o", str(output_path)],
                        capture_output=True,
                        timeout=30
                    )
                    if result.returncode != 0:
                        # 失败则简单提取文本
                        raise RuntimeError("pandoc failed")
                except FileNotFoundError:
                    # pandoc 未安装，使用 python-docx
                    from docx import Document
                    doc = Document(input_path)
                    content = "\n".join([para.text for para in doc.paragraphs])
                    md_content = f"# {input_path.stem}\n\n{content}\n"
                    output_path.write_text(md_content, encoding='utf-8')
            
            logger.info(f"✅ 转换: {input_path.name} -> {output_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 转换失败 {input_path}: {e}")
            return False
    
    def sync_files(self, files: List[Dict], force: bool = False) -> int:
        """同步文件到知识库"""
        # 加载同步状态
        sync_state = self._load_sync_state()
        
        # 创建临时下载目录
        temp_dir = Path("/tmp/github_kb_sync")
        temp_dir.mkdir(exist_ok=True)
        
        converted = 0
        for file_info in files:
            file_path = file_info["path"]
            file_sha = file_info["sha"]
            
            # 检查是否需要更新
            if not force and file_sha == sync_state.get(file_path):
                logger.debug(f"⏭️  跳过（未变化）: {file_path}")
                continue
            
            # 确定目标目录
            if "chip" in file_path.lower() or "芯片" in file_path:
                target_dir = KB_CHIPS_DIR
            else:
                target_dir = KB_PRACTICES_DIR
            
            # 下载文件
            temp_file = temp_dir / Path(file_path).name
            if not self.download_file(file_path, temp_file):
                continue
            
            # 转换为目标 Markdown
            target_name = Path(file_path).stem + ".md"
            target_path = target_dir / target_name
            
            if self.convert_to_markdown(temp_file, target_path):
                sync_state[file_path] = file_sha
                converted += 1
            
            # 清理临时文件
            temp_file.unlink(missing_ok=True)
        
        # 保存同步状态
        self._save_sync_state(sync_state)
        
        # 如果有新文件，通知 KB Service 重新加载
        if converted > 0:
            self._reload_kb_service()
        
        return converted
    
    def _reload_kb_service(self):
        """通知 KB Service 重新加载知识库"""
        import requests
        
        kb_url = os.environ.get("KB_SERVICE_URL", "http://localhost:8000")
        
        try:
            logger.info("🔄 通知 KB Service 重新加载...")
            response = requests.post(f"{kb_url}/reload", timeout=10)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ KB Service 重新加载完成: {result.get('documents', 0)} 个文档")
            else:
                logger.warning(f"⚠️  KB Service 重新加载失败: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  无法连接 KB Service: {e}")
            logger.info("💡 请手动重启服务以加载新文档")
    
    def _load_sync_state(self) -> Dict[str, str]:
        """加载同步状态"""
        if SYNC_STATE_FILE.exists():
            try:
                with open(SYNC_STATE_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_sync_state(self, state: Dict[str, str]):
        """保存同步状态"""
        SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))
    
    def run_daemon(self, interval: int = 300):
        """后台运行，定期检查更新"""
        logger.info(f"👁️  开始监控仓库: {self.repo}")
        logger.info(f"   检查间隔: {interval} 秒")
        logger.info(f"   按 Ctrl+C 停止")
        
        try:
            while True:
                logger.info(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 检查更新...")
                
                files = self.get_repo_files()
                if files:
                    converted = self.sync_files(files)
                    if converted > 0:
                        logger.info(f"✅ 同步完成: {converted} 个文件")
                        logger.info("🔄 请重启 KB Service 以加载新文档")
                    else:
                        logger.info("✓ 所有文件已是最新")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\n✅ 监控已停止")


def main():
    parser = argparse.ArgumentParser(
        description="GitHub 仓库知识库同步工具"
    )
    parser.add_argument(
        "--repo", "-r",
        default=DEFAULT_REPO,
        help=f"GitHub 仓库地址 (默认: {DEFAULT_REPO})"
    )
    parser.add_argument(
        "--branch", "-b",
        default=DEFAULT_BRANCH,
        help=f"分支名称 (默认: {DEFAULT_BRANCH})"
    )
    parser.add_argument(
        "--token", "-t",
        help="GitHub Personal Access Token (也可设置 GITHUB_TOKEN 环境变量)"
    )
    parser.add_argument(
        "--sync", "-s",
        action="store_true",
        help="立即同步一次"
    )
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="后台监控模式"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=300,
        help="检查间隔（秒），默认 300"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制重新同步所有文件"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="显示同步状态"
    )
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    KB_CHIPS_DIR.mkdir(parents=True, exist_ok=True)
    KB_PRACTICES_DIR.mkdir(parents=True, exist_ok=True)
    
    watcher = GitHubRepoWatcher(args.repo, args.branch, args.token)
    
    if args.status:
        # 显示状态
        state = watcher._load_sync_state()
        files = watcher.get_repo_files()
        
        print(f"📊 同步状态: {args.repo}")
        print(f"   远程文件: {len(files)}")
        print(f"   已同步: {len(state)}")
        
        new_files = [f for f in files if f["path"] not in state]
        if new_files:
            print(f"\n🆕 新文件 ({len(new_files)}):")
            for f in new_files[:10]:
                print(f"   - {f['path']}")
    
    elif args.sync:
        # 单次同步
        logger.info(f"🔄 开始同步: {args.repo}")
        files = watcher.get_repo_files()
        if files:
            converted = watcher.sync_files(files, args.force)
            logger.info(f"\n✅ 同步完成: {converted} 个文件")
            logger.info(f"\n🚀 重启服务以加载新文档:")
            logger.info(f"   ./scripts/start.sh --port 8080")
    
    elif args.daemon:
        # 后台模式
        watcher.run_daemon(args.interval)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
