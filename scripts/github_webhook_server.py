#!/usr/bin/env python3
"""
GitHub Webhook 接收服务器

接收 GitHub 仓库的 push 事件，自动同步更新的文件到知识库

配置步骤：
1. 启动此服务器
2. 在 GitHub 仓库 Settings -> Webhooks 中添加 Webhook
3. Payload URL: http://your-server:9000/webhook
4. Content type: application/json
5. Secret: 设置与 GITHUB_WEBHOOK_SECRET 环境变量相同的值
6. 选择 "Just the push event"
"""

import os
import sys
import hmac
import hashlib
import logging
import threading
from pathlib import Path
from flask import Flask, request, jsonify

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.github_repo_watcher import GitHubRepoWatcher, DEFAULT_REPO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
TARGET_REPO = os.environ.get("KB_REPO", DEFAULT_REPO)
REPO_BRANCH = os.environ.get("KB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# 初始化 watcher
watcher = GitHubRepoWatcher(TARGET_REPO, REPO_BRANCH, GITHUB_TOKEN)


def verify_signature(payload: bytes, signature: str) -> bool:
    """验证 GitHub Webhook 签名"""
    if not WEBHOOK_SECRET:
        return True
    
    if not signature:
        return False
    
    expected = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def sync_in_background():
    """后台同步文件"""
    try:
        logger.info("🔄 后台同步开始...")
        files = watcher.get_repo_files()
        if files:
            converted = watcher.sync_files(files)
            logger.info(f"✅ 后台同步完成: {converted} 个文件")
            
            if converted > 0:
                logger.info("📢 请重启 KB Service 以加载新文档")
    except Exception as e:
        logger.error(f"❌ 后台同步失败: {e}")


@app.route("/webhook", methods=["POST"])
def github_webhook():
    """接收 GitHub Webhook"""
    # 验证签名
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = request.get_data()
    
    if not verify_signature(payload, signature):
        logger.warning("❌ Webhook 签名验证失败")
        return jsonify({"error": "Invalid signature"}), 401
    
    # 获取事件类型
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    
    if event_type != "push":
        logger.info(f"⏭️  忽略事件类型: {event_type}")
        return jsonify({"status": "ignored", "event": event_type})
    
    # 解析数据
    data = request.get_json()
    repo_name = data.get("repository", {}).get("full_name", "")
    ref = data.get("ref", "")
    
    logger.info(f"📥 收到 push 事件: {repo_name} @ {ref}")
    
    # 检查是否目标仓库和分支
    if repo_name != TARGET_REPO:
        return jsonify({"status": "ignored", "reason": "Not target repo"})
    
    if ref != f"refs/heads/{REPO_BRANCH}":
        return jsonify({"status": "ignored", "reason": "Not target branch"})
    
    # 检查文件变更
    commits = data.get("commits", [])
    added_files = set()
    modified_files = set()
    
    for commit in commits:
        added_files.update(commit.get("added", []))
        modified_files.update(commit.get("modified", []))
    
    all_files = added_files | modified_files
    
    if not all_files:
        return jsonify({"status": "no_files_changed"})
    
    logger.info(f"📁 变更文件: {len(all_files)} 个")
    for f in list(all_files)[:5]:
        logger.info(f"   - {f}")
    
    # 后台同步
    thread = threading.Thread(target=sync_in_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "status": "syncing",
        "files_changed": len(all_files)
    })


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "repo": TARGET_REPO,
        "branch": REPO_BRANCH
    })


@app.route("/sync", methods=["POST"])
def manual_sync():
    """手动触发同步"""
    thread = threading.Thread(target=sync_in_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "syncing"})


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Webhook 接收服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=9000, help="监听端口")
    
    args = parser.parse_args()
    
    logger.info(f"🚀 启动 GitHub Webhook 服务器")
    logger.info(f"   监听: {args.host}:{args.port}")
    logger.info(f"   目标仓库: {TARGET_REPO}")
    logger.info(f"   分支: {REPO_BRANCH}")
    
    if not WEBHOOK_SECRET:
        logger.warning("⚠️  未设置 WEBHOOK_SECRET，Webhook 签名验证已禁用")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
