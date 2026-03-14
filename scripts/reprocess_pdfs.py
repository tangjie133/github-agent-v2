#!/usr/bin/env python3
"""
重新处理知识库中的 PDF 文件，应用新的清理和分块策略
通过 KB Service API 发送到 ChromaDB 持久化存储
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from knowledge_base.pdf_processor import PDFProcessor
from knowledge_base.kb_service import SimpleEmbedding
import requests

KB_SERVICE_URL = os.environ.get("KB_SERVICE_URL", "http://localhost:8000")

def add_document_via_api(text: str, metadata: dict) -> bool:
    """通过 HTTP API 将文档添加到 KB Service (ChromaDB)"""
    try:
        response = requests.post(
            f"{KB_SERVICE_URL}/add",
            json={"text": text, "metadata": metadata},
            timeout=30
        )
        return response.status_code == 200
    except Exception as e:
        print(f"   ⚠️ API 添加失败: {e}")
        return False

def reprocess_pdfs():
    """重新处理所有 PDF 文件"""
    
    # 配置
    PDF_DIR = Path("./knowledge_base/data/pdfs")
    
    # 初始化组件（不需要 vector_store，直接通过 API 发送）
    embedder = SimpleEmbedding()
    processor = PDFProcessor(embedder=None)  # 不需要 embedder，PDFProcessor 只负责解析
    
    print("🔧 重新处理 PDF 文件")
    print("=" * 60)
    print(f"PDF 目录: {PDF_DIR}")
    print(f"KB Service: {KB_SERVICE_URL}")
    print()
    
    # 检查 KB Service 是否运行
    try:
        resp = requests.get(f"{KB_SERVICE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"❌ KB Service 未正常运行")
            return
        print("✅ KB Service 连接正常")
        print()
    except Exception as e:
        print(f"❌ 无法连接 KB Service: {e}")
        print("   请先启动 KB Service:")
        print("   python -m knowledge_base.kb_service --host 0.0.0.0 --port 8000")
        return
    
    if not PDF_DIR.exists():
        print(f"❌ PDF 目录不存在: {PDF_DIR}")
        return
    
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    print(f"📁 发现 {len(pdf_files)} 个 PDF 文件")
    print()
    
    total_chunks = 0
    success_count = 0
    
    for pdf_file in pdf_files:
        print(f"📖 处理: {pdf_file.name}")
        try:
            # 解析并分块（不生成 embedding）
            pages = processor.parse_pdf(pdf_file, enable_chunking=True)
            
            print(f"   解析到 {len(pages)} 个语义块")
            
            # 通过 API 发送到 KB Service
            file_success = 0
            for i, page in enumerate(pages):
                try:
                    if add_document_via_api(page.content, page.metadata):
                        file_success += 1
                        success_count += 1
                    
                    # 进度显示
                    if (i + 1) % 50 == 0 or i == len(pages) - 1:
                        print(f"   ⏳ 已发送 {i+1}/{len(pages)} 个块")
                        
                except Exception as e:
                    print(f"   ⚠️  块处理失败: {e}")
            
            total_chunks += len(pages)
            print(f"   ✅ 完成: {file_success}/{len(pages)} 块已存储")
            
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
        
        print()
    
    print("=" * 60)
    print(f"✅ 处理完成！")
    print(f"📊 总块数: {total_chunks}")
    print(f"✅ 成功存储: {success_count}")
    print()
    
    # 显示最终统计
    try:
        resp = requests.get(f"{KB_SERVICE_URL}/stats", timeout=5)
        stats = resp.json()
        print(f"💾 KB Service 文档总数: {stats.get('total_documents', 0)}")
    except:
        pass

if __name__ == "__main__":
    reprocess_pdfs()
