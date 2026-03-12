#!/usr/bin/env python3
"""
知识库查询工具 - 查看量化后的知识库内容
"""

import sys
import requests
import json
import argparse
from pathlib import Path

KB_SERVICE_URL = "http://localhost:8000"

def check_stats():
    """查看知识库统计信息"""
    try:
        resp = requests.get(f"{KB_SERVICE_URL}/stats", timeout=5)
        data = resp.json()
        print("\n📊 知识库统计信息")
        print("=" * 50)
        print(f"文档总数: {data.get('total_documents', 0)}")
        print(f"嵌入模型: {data.get('embedding_model', 'unknown')}")
        print(f"数据目录: {data.get('data_dir', 'unknown')}")
        print("=" * 50)
        return data.get('total_documents', 0)
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return 0

def check_health():
    """检查服务健康状态"""
    try:
        resp = requests.get(f"{KB_SERVICE_URL}/health", timeout=5)
        data = resp.json()
        print(f"\n🏥 服务状态: {data.get('status', 'unknown')}")
        print(f"📄 文档数量: {data.get('documents', 0)}")
        return data.get('status') == 'healthy'
    except Exception as e:
        print(f"❌ 服务未启动: {e}")
        return False

def query_knowledge(query: str, top_k: int = 3):
    """查询知识库"""
    try:
        resp = requests.post(
            f"{KB_SERVICE_URL}/query",
            json={"query": query, "top_k": top_k, "generate_answer": True},
            timeout=10
        )
        data = resp.json()
        
        print(f"\n🔍 查询: {query}")
        print("=" * 60)
        
        if data.get('total_found', 0) == 0:
            print("❌ 未找到相关信息")
            return
        
        print(f"✅ 找到 {data.get('total_found', 0)} 条结果\n")
        
        for i, result in enumerate(data.get('results', []), 1):
            print(f"--- 结果 {i} (相似度: {result.get('similarity', 0):.3f}) ---")
            text = result.get('text', '')[:500]  # 限制显示长度
            print(text)
            print(f"来源: {result.get('metadata', {}).get('source', 'unknown')}")
            print()
        
        if 'answer' in data:
            print("🤖 自动生成的答案:")
            print(data['answer'])
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")

def reload_kb():
    """重新加载知识库"""
    try:
        print("🔄 正在重新加载知识库...")
        resp = requests.get(f"{KB_SERVICE_URL}/reload", timeout=30)
        data = resp.json()
        print(f"✅ 重新加载完成")
        print(f"📄 文档数量: {data.get('documents', 0)}")
    except Exception as e:
        print(f"❌ 重新加载失败: {e}")

def list_local_files():
    """列出本地知识库文件"""
    kb_base = Path(__file__).parent.parent / "knowledge_base"
    
    print("\n📁 本地知识库文件")
    print("=" * 60)
    
    chips_dir = kb_base / "chips"
    if chips_dir.exists():
        files = list(chips_dir.glob("*.md"))
        print(f"\n🔧 芯片文档 ({len(files)} 个):")
        for f in files:
            print(f"  - {f.name}")
    
    practices_dir = kb_base / "best_practices"
    if practices_dir.exists():
        files = list(practices_dir.glob("*.md"))
        print(f"\n📚 最佳实践 ({len(files)} 个):")
        for f in files:
            print(f"  - {f.name}")
    
    if not any(chips_dir.glob("*.md")) and not any(practices_dir.glob("*.md")):
        print("\n⚠️ 暂无本地文件，请先同步 GitHub 仓库")
        print(f"   仓库: https://github.com/tangjie133/knowledge-base")

def main():
    parser = argparse.ArgumentParser(description="知识库查询工具")
    parser.add_argument("query", nargs="?", help="查询内容")
    parser.add_argument("-k", "--top-k", type=int, default=3, help="返回结果数量")
    parser.add_argument("-s", "--stats", action="store_true", help="查看统计信息")
    parser.add_argument("-l", "--list", action="store_true", help="列出本地文件")
    parser.add_argument("-r", "--reload", action="store_true", help="重新加载知识库")
    parser.add_argument("--health", action="store_true", help="检查服务健康")
    
    args = parser.parse_args()
    
    if args.health:
        check_health()
    elif args.stats:
        check_stats()
    elif args.list:
        list_local_files()
    elif args.reload:
        reload_kb()
    elif args.query:
        query_knowledge(args.query, args.top_k)
    else:
        # 默认显示统计和文件列表
        check_health()
        check_stats()
        list_local_files()
        print("\n" + "=" * 60)
        print("使用示例:")
        print("  python scripts/kb_query.py 'SAMD21 芯片'    # 查询知识库")
        print("  python scripts/kb_query.py -s               # 查看统计")
        print("  python scripts/kb_query.py -l               # 列出文件")
        print("  python scripts/kb_query.py -r               # 重新加载")

if __name__ == "__main__":
    main()
