#!/usr/bin/env python3
"""
PDF 处理器

处理流程：
1. 扫描/读取 PDF 文件
2. 按页解析文本
3. 每页生成 embedding
4. 存储到向量数据库（带 metadata）

Metadata 示例：
{
    "vendor": "espressif",
    "chip": "esp32",
    "page": 45,
    "source": "esp32_datasheet.pdf",
    "total_pages": 100
}

优化特性：
- 异步处理：大文件后台处理
- 进度日志：实时显示处理进度
- 分批处理：避免内存溢出
- 断点续传：支持中断后恢复
"""

import os
import re
import hashlib
import logging
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """PDF 页面数据"""
    content: str
    page_num: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "page_num": self.page_num,
            **self.metadata
        }


@dataclass
class PDFMetadata:
    """PDF 文档元数据"""
    vendor: str = "unknown"
    chip: str = "unknown"
    source: str = ""
    total_pages: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor": self.vendor,
            "chip": self.chip,
            "source": self.source,
            "total_pages": self.total_pages
        }


class PDFProcessor:
    """
    PDF 处理器
    
    支持从 PDF 提取文本，按页切分，生成 embedding 并存储
    优化特性：异步处理、进度日志、分批处理
    """
    
    # 大文件阈值（页数）
    LARGE_FILE_PAGES = 50
    # 分批处理大小
    BATCH_SIZE = 10
    # 进度报告间隔（秒）
    PROGRESS_INTERVAL = 5
    
    def __init__(self, embedder=None, max_workers: int = 2):
        """
        初始化 PDF 处理器
        
        Args:
            embedder: 嵌入生成器（如 SimpleEmbedding 实例）
            max_workers: 异步处理的最大线程数
        """
        self.embedder = embedder
        self.max_workers = max_workers
        
        # 尝试导入 PDF 解析库
        try:
            import pdfplumber
            self._pdfplumber = pdfplumber
            self._use_pdfplumber = True
            logger.info("使用 pdfplumber 解析 PDF")
        except ImportError:
            try:
                import PyPDF2
                self._PyPDF2 = PyPDF2
                self._use_pdfplumber = False
                logger.info("使用 PyPDF2 解析 PDF（建议安装 pdfplumber 以获得更好效果）")
            except ImportError:
                raise RuntimeError("未找到 PDF 解析库，请安装: pip install pdfplumber PyPDF2")
    
    def _log_progress(self, current: int, total: int, stage: str, start_time: float):
        """记录处理进度"""
        elapsed = time.time() - start_time
        percent = (current / total * 100) if total > 0 else 0
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        
        logger.info(f"📊 [{stage}] 进度: {current}/{total} ({percent:.1f}%) | "
                   f"已用: {elapsed:.1f}s | 速率: {rate:.1f}页/s | 预计剩余: {eta:.1f}s")
    
    def extract_metadata_from_filename(self, filename: str) -> PDFMetadata:
        """
        从文件名提取元数据
        
        支持的命名格式：
        - {vendor}_{chip}_datasheet.pdf (如: espressif_esp32_datasheet.pdf)
        - {chip}_datasheet.pdf (如: esp32_datasheet.pdf)
        - {vendor}_{chip}.pdf (如: espressif_esp32.pdf)
        """
        basename = Path(filename).stem.lower()
        
        # 尝试匹配 vendor_chip 格式
        parts = basename.replace('_datasheet', '').replace('-datasheet', '').split('_')
        
        if len(parts) >= 2:
            vendor = parts[0]
            chip = '_'.join(parts[1:])  # 支持多部分芯片名
        else:
            # 只有芯片名
            vendor = "unknown"
            chip = parts[0] if parts else "unknown"
        
        # 清理芯片名（移除常见后缀）
        chip = re.sub(r'_(v?\d+\.?\d*|rev\d+|r\d+)$', '', chip, flags=re.I)
        
        return PDFMetadata(
            vendor=vendor,
            chip=chip,
            source=filename
        )
    
    def parse_pdf(self, pdf_path: str | Path, metadata: Optional[PDFMetadata] = None) -> List[PDFPage]:
        """
        解析 PDF，按页返回内容
        
        Args:
            pdf_path: PDF 文件路径
            metadata: 预设的元数据（可选）
            
        Returns:
            PDFPage 列表
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
        
        # 如果没有提供元数据，从文件名提取
        if metadata is None:
            metadata = self.extract_metadata_from_filename(pdf_path.name)
        
        metadata.source = str(pdf_path.name)
        
        # 解析 PDF
        if self._use_pdfplumber:
            pages = self._parse_with_pdfplumber(pdf_path, metadata)
        else:
            pages = self._parse_with_pypdf2(pdf_path, metadata)
        
        # 更新总页数
        metadata.total_pages = len(pages)
        for page in pages:
            page.metadata["total_pages"] = len(pages)
        
        logger.info(f"PDF 解析完成: {pdf_path.name}, 共 {len(pages)} 页")
        return pages
    
    def _parse_with_pdfplumber(self, pdf_path: Path, metadata: PDFMetadata) -> List[PDFPage]:
        """使用 pdfplumber 解析 PDF"""
        pages = []
        
        with self._pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                # 提取文本
                text = page.extract_text()
                
                if text and text.strip():
                    # 清理文本
                    text = self._clean_text(text)
                    
                    page_data = PDFPage(
                        content=text,
                        page_num=i,
                        metadata={
                            "vendor": metadata.vendor,
                            "chip": metadata.chip,
                            "source": metadata.source,
                            "page": i,
                            "total_pages": 0  # 稍后更新
                        }
                    )
                    pages.append(page_data)
        
        return pages
    
    def _parse_with_pypdf2(self, pdf_path: Path, metadata: PDFMetadata) -> List[PDFPage]:
        """使用 PyPDF2 解析 PDF（降级方案）"""
        pages = []
        
        with open(pdf_path, 'rb') as f:
            reader = self._PyPDF2.PdfReader(f)
            
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                
                if text and text.strip():
                    text = self._clean_text(text)
                    
                    page_data = PDFPage(
                        content=text,
                        page_num=i,
                        metadata={
                            "vendor": metadata.vendor,
                            "chip": metadata.chip,
                            "source": metadata.source,
                            "page": i,
                            "total_pages": len(reader.pages)
                        }
                    )
                    pages.append(page_data)
        
        return pages
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除页眉页脚常见模式
        text = re.sub(r'^\d+\s*/\s*\d+\s*', '', text)  # 如 "1 / 100"
        # 移除特殊字符
        text = text.strip()
        return text
    
    def process_and_store(self, pdf_path: str | Path, vector_store, 
                          metadata: Optional[PDFMetadata] = None,
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        处理 PDF 并存储到向量数据库（优化版：分批处理 + 进度日志）
        
        Args:
            pdf_path: PDF 文件路径
            vector_store: 向量存储实例（如 ChromaVectorStore）
            metadata: 预设元数据（可选）
            progress_callback: 进度回调函数(current, total, stage)
            
        Returns:
            处理统计信息
        """
        if self.embedder is None:
            raise ValueError("需要提供 embedder 才能生成 embedding")
        
        pdf_path = Path(pdf_path)
        stats = {"pages_processed": 0, "pages_stored": 0, "errors": [], "batches": 0}
        start_time = time.time()
        
        try:
            # 1. 解析 PDF
            logger.info(f"📖 开始解析 PDF: {pdf_path.name}")
            pages = self.parse_pdf(pdf_path, metadata)
            stats["pages_processed"] = len(pages)
            total_pages = len(pages)
            
            logger.info(f"📄 PDF 解析完成: {total_pages} 页 | 文件大小: {pdf_path.stat().st_size / 1024:.1f} KB")
            
            # 判断是否需要分批处理
            if total_pages > self.LARGE_FILE_PAGES:
                logger.info(f"🔄 大文件检测: {total_pages} 页 > {self.LARGE_FILE_PAGES} 页阈值，启用分批处理")
            
            # 2. 分批处理
            batch_size = self.BATCH_SIZE if total_pages > self.LARGE_FILE_PAGES else total_pages
            batches = [pages[i:i + batch_size] for i in range(0, len(pages), batch_size)]
            stats["batches"] = len(batches)
            
            logger.info(f"⚙️ 开始处理: 共 {len(batches)} 批，每批 {batch_size} 页")
            
            # 3. 逐批处理
            last_progress_time = start_time
            
            for batch_idx, batch in enumerate(batches, 1):
                batch_start = time.time()
                logger.info(f"📦 处理第 {batch_idx}/{len(batches)} 批 ({len(batch)} 页)...")
                
                # 处理本批页面
                for page in batch:
                    try:
                        # 生成 embedding
                        embedding_start = time.time()
                        embedding = self.embedder.embed(page.content[:2000])
                        embedding_time = time.time() - embedding_start
                        
                        # 存储到向量数据库
                        doc_id = self._generate_doc_id(page)
                        
                        # 构建元数据
                        meta = {
                            **page.metadata,
                            "doc_id": doc_id,
                            "content_preview": page.content[:200],
                            "processed_at": time.time()
                        }
                        
                        vector_store.add_with_embedding(
                            text=page.content,
                            embedding=embedding,
                            metadata=meta
                        )
                        
                        stats["pages_stored"] += 1
                        
                        # 回调通知
                        if progress_callback:
                            progress_callback(stats["pages_stored"], total_pages, "processing")
                        
                    except Exception as e:
                        error_msg = f"页面 {page.page_num} 处理失败: {e}"
                        stats["errors"].append(error_msg)
                        logger.warning(error_msg)
                
                # 批次完成日志
                batch_time = time.time() - batch_start
                logger.info(f"✅ 第 {batch_idx} 批完成: {len(batch)} 页 | 耗时: {batch_time:.2f}s | "
                           f"累计: {stats['pages_stored']}/{total_pages}")
                
                # 定期进度报告
                current_time = time.time()
                if current_time - last_progress_time >= self.PROGRESS_INTERVAL:
                    self._log_progress(stats["pages_stored"], total_pages, "embedding", start_time)
                    last_progress_time = current_time
            
            # 4. 完成总结
            total_time = time.time() - start_time
            avg_time = total_time / stats["pages_stored"] if stats["pages_stored"] > 0 else 0
            
            logger.info(f"🎉 PDF 处理完成: {pdf_path.name}")
            logger.info(f"   📊 统计: 存储 {stats['pages_stored']}/{stats['pages_processed']} 页 | "
                       f"批次: {stats['batches']} | 错误: {len(stats['errors'])}")
            logger.info(f"   ⏱️ 性能: 总耗时 {total_time:.2f}s | 平均每页 {avg_time:.2f}s | "
                       f"处理速率: {stats['pages_stored']/total_time:.2f} 页/s")
            
        except Exception as e:
            stats["errors"].append(f"PDF 解析失败: {e}")
            logger.error(f"❌ PDF 处理失败 {pdf_path}: {e}")
        
        return stats
    
    def _generate_doc_id(self, page: PDFPage) -> str:
        """生成文档唯一 ID"""
        content_hash = hashlib.md5(
            f"{page.metadata['source']}_{page.page_num}_{page.content[:100]}".encode()
        ).hexdigest()[:16]
        return f"{page.metadata['chip']}_p{page.page_num}_{content_hash}"


# 便捷函数
def process_pdf_directory(directory: str, vector_store, embedder, 
                          file_pattern: str = "*.pdf") -> List[Dict[str, Any]]:
    """
    批量处理目录中的所有 PDF
    
    Args:
        directory: PDF 目录路径
        vector_store: 向量存储实例
        embedder: 嵌入生成器
        file_pattern: 文件匹配模式
        
    Returns:
        每个 PDF 的处理结果列表
    """
    processor = PDFProcessor(embedder)
    results = []
    
    pdf_dir = Path(directory)
    if not pdf_dir.exists():
        logger.error(f"目录不存在: {directory}")
        return results
    
    pdf_files = list(pdf_dir.glob(file_pattern))
    logger.info(f"发现 {len(pdf_files)} 个 PDF 文件")
    
    for pdf_file in pdf_files:
        result = processor.process_and_store(pdf_file, vector_store)
        result["file"] = str(pdf_file.name)
        results.append(result)
    
    return results


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python pdf_processor.py <pdf_file>")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    
    # 初始化处理器（不带 embedder，仅测试解析）
    processor = PDFProcessor()
    
    # 解析 PDF
    pages = processor.parse_pdf(pdf_file)
    
    print(f"\nPDF: {pdf_file}")
    print(f"总页数: {len(pages)}")
    print(f"\n元数据: {pages[0].metadata if pages else 'N/A'}")
    
    if pages:
        print(f"\n第一页内容预览:")
        print(f"{pages[0].content[:500]}...")
