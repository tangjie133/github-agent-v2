#!/usr/bin/env python3
"""
知识库自动加载器

监控指定目录，自动将新添加的 PDF 转换为 Markdown 并加载到知识库

用法:
    # 一次性批量处理
    python auto_kb_loader.py --scan /path/to/pdf/folder
    
    # 后台监控模式（自动处理新文件）
    python auto_kb_loader.py --watch /path/to/pdf/folder --daemon
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pdf_to_kb import convert_pdf, KB_CHIPS_DIR

# 监控状态文件
WATCH_STATE_FILE = Path(__file__).parent.parent / ".kb_watch_state"


def scan_and_convert(pdf_folder: Path, force: bool = False) -> int:
    """扫描文件夹并转换所有 PDF"""
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        return 0
    
    print(f"🔍 扫描到 {len(pdf_files)} 个 PDF 文件")
    
    converted = 0
    for pdf_file in pdf_files:
        result = convert_pdf(pdf_file, force)
        if result:
            converted += 1
    
    return converted


def get_file_hash(filepath: Path) -> str:
    """获取文件哈希（用于检测变化）"""
    import hashlib
    stat = filepath.stat()
    return f"{stat.st_size}-{stat.st_mtime}"


def load_watch_state() -> dict:
    """加载监控状态"""
    if not WATCH_STATE_FILE.exists():
        return {}
    
    state = {}
    try:
        with open(WATCH_STATE_FILE) as f:
            for line in f:
                if ':' in line:
                    filename, filehash = line.strip().split(':', 1)
                    state[filename] = filehash
    except Exception:
        pass
    return state


def save_watch_state(state: dict):
    """保存监控状态"""
    with open(WATCH_STATE_FILE, 'w') as f:
        for filename, filehash in state.items():
            f.write(f"{filename}:{filehash}\n")


def watch_folder(pdf_folder: Path, interval: int = 60):
    """监控文件夹，自动处理新文件"""
    print(f"👁️  开始监控: {pdf_folder}")
    print(f"   检查间隔: {interval} 秒")
    print(f"   按 Ctrl+C 停止")
    print("=" * 50)
    
    # 加载之前的状态
    state = load_watch_state()
    
    try:
        while True:
            current_files = list(pdf_folder.glob("*.pdf"))
            new_files = []
            
            for pdf_file in current_files:
                filehash = get_file_hash(pdf_file)
                filename = pdf_file.name
                
                # 检查是否是新文件或已修改
                if filename not in state or state[filename] != filehash:
                    new_files.append(pdf_file)
                    state[filename] = filehash
            
            if new_files:
                print(f"\n📥 检测到 {len(new_files)} 个新文件:")
                for pdf_file in new_files:
                    print(f"   - {pdf_file.name}")
                    convert_pdf(pdf_file)
                
                save_watch_state(state)
                print(f"\n📝 知识库文档数: {len(list(KB_CHIPS_DIR.glob('*.md')))}")
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 等待中...")
            else:
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 无新文件", end='\r')
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n✅ 监控已停止")
        save_watch_state(state)


def list_kb_documents():
    """列出当前知识库中的所有文档"""
    md_files = list(KB_CHIPS_DIR.glob("*.md"))
    
    print(f"📚 当前知识库文档 ({len(md_files)} 个):")
    print("=" * 50)
    
    for i, md_file in enumerate(sorted(md_files), 1):
        size = md_file.stat().st_size
        print(f"{i:2}. {md_file.name:<30} ({size:>6} bytes)")
    
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="知识库自动加载器"
    )
    parser.add_argument(
        "--scan", "-s",
        type=Path,
        help="扫描指定文件夹中的所有 PDF"
    )
    parser.add_argument(
        "--watch", "-w",
        type=Path,
        help="监控文件夹，自动处理新文件"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="监控检查间隔（秒），默认 60"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出当前知识库文档"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制重新转换所有文件"
    )
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    KB_CHIPS_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.list:
        list_kb_documents()
    
    elif args.scan:
        folder = args.scan.expanduser().resolve()
        if not folder.exists():
            print(f"❌ 文件夹不存在: {folder}")
            return
        
        count = scan_and_convert(folder, args.force)
        if count > 0:
            print(f"\n🚀 重启服务后生效:")
            print(f"   ./scripts/start.sh --port 8080")
    
    elif args.watch:
        folder = args.watch.expanduser().resolve()
        if not folder.exists():
            print(f"❌ 文件夹不存在: {folder}")
            return
        
        watch_folder(folder, args.interval)
    
    else:
        # 默认行为：列出文档并显示帮助
        list_kb_documents()
        print()
        parser.print_help()


if __name__ == "__main__":
    main()
