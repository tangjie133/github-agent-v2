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

# 日志配置（如果作为主程序运行）
if __name__ == "__main__":
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_REPO = "tangjie133/knowledge-base"
DEFAULT_BRANCH = "main"
KB_CHIPS_DIR = Path(__file__).parent.parent / "knowledge_base" / "chips"
KB_PRACTICES_DIR = Path(__file__).parent.parent / "knowledge_base" / "best_practices"

# 支持的文件格式
SUPPORTED_EXTS = {'.md', '.txt', '.pdf', '.docx'}

# 基础目录
KB_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"

# 同步状态文件路径（支持环境变量配置）
_state_dir = os.environ.get("GITHUB_AGENT_STATEDIR")
if _state_dir:
    SYNC_STATE_FILE = Path(_state_dir) / ".github_kb_sync_state.json"
else:
    SYNC_STATE_FILE = Path(__file__).parent.parent / ".github_kb_sync_state.json"


class ContentClassifier:
    """
    智能内容分类器
    
    支持多种分类策略：
    1. 配置文件规则（用户自定义）
    2. 文件内容启发式分析
    3. AI 辅助分类（使用 Ollama）
    """
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or os.environ.get("KB_CLASSIFIER_CONFIG")
        self.rules = self._load_rules()
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.environ.get("KB_CLASSIFIER_MODEL", "qwen2.5:7b")
        
    def _load_rules(self) -> Dict:
        """加载分类规则"""
        default_rules = {
            "categories": {
                "chips": {
                    "keywords": ["芯片", "datasheet", "数据手册", "specification", "规格书"],
                    "file_patterns": ["*chip*", "*datasheet*", "*硬件*", "*hardware*"],
                    "content_indicators": ["型号", "参数", "引脚", "电气特性"]
                },
                "best_practices": {
                    "keywords": ["指南", "教程", "最佳实践", "guide", "tutorial"],
                    "file_patterns": ["*guide*", "*tutorial*", "*practice*"],
                    "content_indicators": ["步骤", "方法", "建议", "示例"]
                }
            },
            "default_category": "best_practices",
            "use_ai": False  # 默认不使用AI，避免额外延迟
        }
        
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_rules = json.load(f)
                    default_rules.update(user_rules)
                    logger.info(f"已加载分类规则: {self.config_file}")
            except Exception as e:
                logger.warning(f"加载分类规则失败: {e}，使用默认规则")
        
        return default_rules
    
    def classify(self, file_path: str, content: str = None) -> str:
        """
        分类文件，返回类别目录名
        
        Args:
            file_path: 文件路径
            content: 文件内容（可选，用于内容分析）
            
        Returns:
            类别目录名（如 "chips", "best_practices"）
        """
        path_lower = file_path.lower()
        filename = Path(file_path).name.lower()
        
        # 策略1: 文件名匹配
        for category, rules in self.rules["categories"].items():
            # 检查文件模式
            for pattern in rules.get("file_patterns", []):
                pattern_lower = pattern.lower().replace("*", "")
                if pattern_lower in filename or pattern_lower in path_lower:
                    return category
            
            # 检查关键词
            for keyword in rules.get("keywords", []):
                if keyword.lower() in filename or keyword.lower() in path_lower:
                    return category
        
        # 策略2: 内容分析（如果有内容）
        if content:
            category = self._classify_by_content(content)
            if category:
                return category
        
        # 策略3: AI 分类（如果启用）
        if self.rules.get("use_ai", False) and content:
            category = self._classify_by_ai(file_path, content)
            if category:
                return category
        
        # 默认分类
        return self.rules.get("default_category", "best_practices")
    
    def _classify_by_content(self, content: str) -> str:
        """基于内容启发式分类"""
        content_lower = content[:2000].lower()  # 只检查前2000字符
        
        scores = {}
        for category, rules in self.rules["categories"].items():
            score = 0
            for indicator in rules.get("content_indicators", []):
                if indicator.lower() in content_lower:
                    score += 1
            scores[category] = score
        
        # 返回得分最高的类别（至少要有1分）
        if scores:
            best_category = max(scores, key=scores.get)
            if scores[best_category] > 0:
                return best_category
        
        return None
    
    def _classify_by_ai(self, file_path: str, content: str) -> str:
        """使用 Ollama AI 分类"""
        try:
            import requests
            
            # 准备提示词
            prompt = f"""请分析以下文档内容，判断它属于哪一类：

文件名: {file_path}
内容摘要: {content[:1000]}...

可选类别:
{json.dumps(list(self.rules["categories"].keys()), ensure_ascii=False, indent=2)}

请只返回类别名称，不要解释。"""

            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "").strip().lower()
                # 验证返回的类别是否有效
                for category in self.rules["categories"].keys():
                    if category.lower() in result:
                        return category
                        
        except Exception as e:
            logger.debug(f"AI 分类失败: {e}")
        
        return None
    
    def get_category_dir(self, category: str) -> Path:
        """获取类别的本地目录"""
        return KB_BASE_DIR / category
    
    def list_categories(self) -> List[str]:
        """列出所有可用类别"""
        return list(self.rules["categories"].keys())


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
    
    def sync_files(self, files: List[Dict], force: bool = False) -> dict:
        """同步文件到知识库
        
        Returns:
            dict: 同步统计信息 {
                'total': 总文件数,
                'skipped': 跳过数,
                'success': 成功数,
                'failed': 失败数,
                'details': []  # 每个文件的处理详情
            }
        """
        # 加载同步状态
        sync_state = self._load_sync_state()
        
        # 创建临时下载目录
        temp_dir = Path("/tmp/github_kb_sync")
        temp_dir.mkdir(exist_ok=True)
        
        # 统计信息
        stats = {
            'total': len(files),
            'skipped': 0,
            'success': 0,
            'failed': 0,
            'details': []
        }
        
        logger.info(f"\n📋 开始处理 {len(files)} 个文件...")
        
        for i, file_info in enumerate(files, 1):
            file_path = file_info["path"]
            file_sha = file_info["sha"]
            file_name = Path(file_path).name
            
            # 检查是否需要更新
            if not force and file_sha == sync_state.get(file_path):
                # SHA 匹配，检查本地文件是否真的存在
                target_name = Path(file_path).stem + ".md"
                if "chip" in file_path.lower() or "芯片" in file_path:
                    local_path = KB_CHIPS_DIR / target_name
                else:
                    local_path = KB_PRACTICES_DIR / target_name
                
                if local_path.exists():
                    logger.info(f"  [{i}/{len(files)}] ⏭️  跳过（已同步）: {file_path}")
                    stats['skipped'] += 1
                    stats['details'].append({'file': file_path, 'status': 'skipped'})
                    continue
                else:
                    # SHA 匹配但文件不存在，可能是被删除了，重新下载
                    logger.info(f"  [{i}/{len(files)}] 📝 重新下载（本地缺失）: {file_path}")
            
            status_icon = "🆕" if file_path not in sync_state else "📝"
            logger.info(f"  [{i}/{len(files)}] {status_icon} 处理中: {file_path}")
            
            # 确定目标目录
            path_lower = file_path.lower()
            if any(keyword in path_lower for keyword in ["chip", "芯片", "hardware", "datasheet"]):
                target_dir = KB_CHIPS_DIR
            else:
                target_dir = KB_PRACTICES_DIR
            
            # 下载文件
            temp_file = temp_dir / Path(file_path).name
            if not self.download_file(file_path, temp_file):
                logger.error(f"       ❌ 下载失败: {file_path}")
                stats['failed'] += 1
                stats['details'].append({'file': file_path, 'status': 'failed', 'reason': 'download'})
                continue
            
            # 转换为目标 Markdown
            target_name = Path(file_path).stem + ".md"
            target_path = target_dir / target_name
            
            if self.convert_to_markdown(temp_file, target_path):
                sync_state[file_path] = file_sha
                stats['success'] += 1
                stats['details'].append({'file': file_path, 'status': 'success'})
            else:
                logger.error(f"       ❌ 转换失败: {file_path}")
                stats['failed'] += 1
                stats['details'].append({'file': file_path, 'status': 'failed', 'reason': 'convert'})
            
            # 清理临时文件
            temp_file.unlink(missing_ok=True)
        
        # 保存同步状态
        self._save_sync_state(sync_state)
        
        # 打印统计摘要
        logger.info(f"\n📊 同步统计:")
        logger.info(f"   总计: {stats['total']} 个文件")
        logger.info(f"   ⏭️  跳过: {stats['skipped']} 个（已是最新）")
        logger.info(f"   ✅ 成功: {stats['success']} 个")
        if stats['failed'] > 0:
            logger.info(f"   ❌ 失败: {stats['failed']} 个")
        
        # 如果有新文件，通知 KB Service 重新加载
        if stats['success'] > 0:
            self._reload_kb_service()
        
        return stats
    
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
        SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
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
                    stats = self.sync_files(files)
                    if stats['success'] > 0:
                        logger.info(f"\n✅ 同步完成: {stats['success']} 个新文件")
                        logger.info("🔄 请重启 KB Service 以加载新文档")
                    elif stats['failed'] > 0:
                        logger.warning(f"\n⚠️  同步完成，但有 {stats['failed']} 个文件失败")
                    else:
                        logger.info("\n✓ 所有文件已是最新")
                
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
            stats = watcher.sync_files(files, args.force)
            # 最终摘要
            if stats['success'] > 0:
                logger.info(f"\n✅ 同步成功: {stats['success']} 个新文件")
                logger.info(f"💡 提示: 重启 KB Service 以加载新文档")
            elif stats['failed'] > 0:
                logger.error(f"\n❌ 同步失败: {stats['failed']} 个文件失败")
            else:
                logger.info(f"\n✓ 所有文件已是最新 ({stats['skipped']} 个)")
    
    elif args.daemon:
        # 后台模式
        watcher.run_daemon(args.interval)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
