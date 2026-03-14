#!/usr/bin/env python3
"""
PDF 处理器 - 优化版本

优化目标：
1. chunk_size = 500, overlap = 80（减少 embedding 调用次数）
2. 保留 section/标题信息
3. 跳过目录页、版权页等无用内容
4. 过滤过短文本（< 50）

处理流程：
PDF → 结构化文本 → chunk → embedding → Chroma
"""

import re
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PDFChunk:
    """PDF 分块数据结构"""
    content: str
    page: int
    section: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PDFMetadata:
    """PDF 文档元数据"""
    vendor: str = "unknown"
    chip: str = "unknown"
    source: str = ""
    total_pages: int = 0


class PDFProcessor:
    """
    PDF 处理器 - 优化版本
    
    参数：
    - chunk_size: 500（平衡语义完整性和 embedding 调用次数）
    - chunk_overlap: 80（保证上下文连贯）
    - min_chunk_length: 50（过滤无效内容）
    """
    
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_OVERLAP = 80
    MIN_CHUNK_LENGTH = 50
    
    # 需要跳过的页面模式（目录、版权、法律声明等）
    SKIP_PAGE_PATTERNS = [
        r'^\s*Contents\s*$',
        r'^\s*Table of Contents\s*$',
        r'^\s*Copyright\s',
        r'^\s*©\s*\d{4}',
        r'^\s*Legal Notice',
        r'^\s*Disclaimer',
        r'^\s*Revision History',
        r'^\s*Document History',
        r'^\s*Ordering Information',
        r'^\s*Contact Information',
    ]
    
    # 页眉页脚模式（需要过滤）
    HEADER_FOOTER_PATTERNS = [
        r'BST-\w+-DS\d+-\d+.*?Revision.*\d+\.\d+',
        r'Page\s+\d+\s+of\s+\d+',
        r'^BMI160 Data sheet.*$',
        r'^Bosch Sensortec',
        r'©\s*Bosch Sensortec.*?reserved',
        r'BOSCH and the symbol are registered trademarks',
    ]
    
    def __init__(self, embedder=None, chunk_size: int = None, overlap: int = None):
        self.embedder = embedder
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.overlap = overlap or self.DEFAULT_OVERLAP
        
        try:
            import fitz
            self.fitz = fitz
        except ImportError:
            raise RuntimeError("PyMuPDF (fitz) 未安装: pip install pymupdf")
        
        # 编译正则表达式
        self._skip_patterns = [re.compile(p, re.IGNORECASE) for p in self.SKIP_PAGE_PATTERNS]
        self._header_patterns = [re.compile(p, re.IGNORECASE) for p in self.HEADER_FOOTER_PATTERNS]
        
        logger.info(f"PDF 处理器初始化: chunk_size={self.chunk_size}, overlap={self.overlap}")
    
    def extract_metadata_from_filename(self, filename: str) -> PDFMetadata:
        """从文件名提取 vendor 和 chip"""
        basename = Path(filename).stem.lower()
        parts = basename.replace('_datasheet', '').replace('-datasheet', '').split('_')
        
        if len(parts) >= 2:
            vendor = parts[0]
            chip = '_'.join(parts[1:])
        else:
            vendor = "unknown"
            chip = parts[0] if parts else "unknown"
        
        # 清理版本号
        chip = re.sub(r'_(v?\d+\.?\d*|rev\d+|r\d+)$', '', chip, flags=re.I)
        
        return PDFMetadata(vendor=vendor, chip=chip, source=filename)
    
    def _is_skip_page(self, text: str) -> bool:
        """检测是否为需要跳过的页面（目录、版权等）"""
        lines = text.strip().split('\n')[:10]  # 只看前10行
        header_text = ' '.join(lines[:3])
        
        for pattern in self._skip_patterns:
            if pattern.search(header_text):
                return True
        return False
    
    def _clean_text(self, text: str) -> str:
        """清理页眉页脚等多余内容"""
        # 移除页眉页脚
        for pattern in self._header_patterns:
            text = pattern.sub('', text)
        
        # 清理多余空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text.strip()
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """将文本分割为句子列表（不使用 look-behind）"""
        # 使用简单的标点分割，保留标点
        sentences = []
        current = []
        
        for char in text:
            current.append(char)
            if char in '.!?。':
                # 检查后面是否是空白或结束
                sentences.append(''.join(current).strip())
                current = []
        
        # 添加最后一部分
        if current:
            remainder = ''.join(current).strip()
            if remainder:
                sentences.append(remainder)
        
        return sentences if sentences else [text]
    
    def extract_structure(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        提取 PDF 结构化内容
        
        Returns:
            页面结构化数据列表，每个页面包含：
            - page_num: 页码
            - text: 清理后的文本
            - section: 当前章节标题
            - is_content: 是否有实质内容（非目录/版权页）
        """
        pages = []
        current_section = "General"
        
        with self.fitz.open(pdf_path) as doc:
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 提取带格式的文本块
                blocks = page.get_text("dict").get("blocks", [])
                
                page_lines = []
                page_section = current_section
                has_title = False
                
                for block in blocks:
                    if "lines" not in block:
                        continue
                    
                    for line in block["lines"]:
                        if not line.get("spans"):
                            continue
                        
                        # 提取文本
                        text = "".join([s.get("text", "") for s in line["spans"]]).strip()
                        if not text or len(text) < 2:
                            continue
                        
                        # 分析格式（字体大小、是否粗体）
                        first_span = line["spans"][0]
                        font_size = first_span.get("size", 11)
                        flags = first_span.get("flags", 0)
                        is_bold = bool(flags & 2**4) or "bold" in first_span.get("font", "").lower()
                        
                        # 标题检测（大字体或粗体）
                        if font_size > 13 or (font_size > 11 and is_bold):
                            # 更新章节标题
                            page_section = text
                            current_section = text
                            has_title = True
                            # 标题前加标记便于后续处理
                            page_lines.append(f"##SECTION##{text}")
                        else:
                            page_lines.append(text)
                
                # 合并页面文本
                raw_text = '\n'.join(page_lines)
                cleaned_text = self._clean_text(raw_text)
                
                # 检测是否为内容页（非目录/版权页）
                is_content = not self._is_skip_page(cleaned_text) and len(cleaned_text) > 100
                
                pages.append({
                    "page_num": page_num + 1,
                    "text": cleaned_text,
                    "section": page_section,
                    "is_content": is_content,
                    "has_title": has_title
                })
        
        return pages
    
    def create_chunks(self, pages: List[Dict[str, Any]], metadata: PDFMetadata) -> List[PDFChunk]:
        """
        从结构化页面创建 chunks
        
        策略：
        1. 跳过非内容页（目录、版权）
        2. 按 section 分组，保持语义完整性
        3. chunk_size=500, overlap=80
        4. 过滤长度 < 50 的 chunk
        """
        chunks = []
        
        # 过滤内容页
        content_pages = [p for p in pages if p["is_content"]]
        
        if not content_pages:
            logger.warning("未检测到有效内容页")
            return chunks
        
        logger.info(f"处理 {len(content_pages)}/{len(pages)} 个内容页")
        
        # 按 section 分组处理
        current_section = "General"
        section_buffer = []
        section_start_page = 1
        
        def flush_section_buffer():
            """将当前 section buffer 分块并保存"""
            nonlocal section_buffer, section_start_page
            
            if not section_buffer:
                return
            
            # 合并 section 内文本
            full_text = '\n\n'.join(section_buffer)
            
            # 如果整个 section 很短，作为一个 chunk
            if len(full_text) <= self.chunk_size:
                if len(full_text) >= self.MIN_CHUNK_LENGTH:
                    chunks.append(PDFChunk(
                        content=full_text,
                        page=section_start_page,
                        section=current_section,
                        metadata={
                            "source": metadata.source,
                            "vendor": metadata.vendor,
                            "chip": metadata.chip,
                        }
                    ))
                section_buffer = []
                return
            
            # 长 section 需要分割
            # 按段落分割，段落过长再按句子分割
            paragraphs = full_text.split('\n\n')
            
            chunk_parts = []
            chunk_size = 0
            chunk_start_page = section_start_page
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # 如果段落本身超过 chunk_size，按句子分割
                if len(para) > self.chunk_size:
                    sentences = self._split_into_sentences(para)
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        
                        # 检查是否需要新建 chunk
                        if chunk_size + len(sent) > self.chunk_size and chunk_parts:
                            # 保存当前 chunk
                            content = ' '.join(chunk_parts).strip()
                            if len(content) >= self.MIN_CHUNK_LENGTH:
                                chunks.append(PDFChunk(
                                    content=content,
                                    page=chunk_start_page,
                                    section=current_section,
                                    metadata={
                                        "source": metadata.source,
                                        "vendor": metadata.vendor,
                                        "chip": metadata.chip,
                                    }
                                ))
                            
                            # 创建重叠
                            overlap_text = self._calc_overlap(chunk_parts)
                            chunk_parts = [overlap_text, sent] if overlap_text else [sent]
                            chunk_size = sum(len(p) for p in chunk_parts)
                        else:
                            chunk_parts.append(sent)
                            chunk_size += len(sent)
                else:
                    # 正常段落处理
                    if chunk_size + len(para) > self.chunk_size and chunk_parts:
                        # 保存当前 chunk
                        content = '\n\n'.join(chunk_parts).strip()
                        if len(content) >= self.MIN_CHUNK_LENGTH:
                            chunks.append(PDFChunk(
                                content=content,
                                page=chunk_start_page,
                                section=current_section,
                                metadata={
                                    "source": metadata.source,
                                    "vendor": metadata.vendor,
                                    "chip": metadata.chip,
                                }
                            ))
                        
                        # 创建重叠
                        overlap_text = self._calc_overlap(chunk_parts)
                        chunk_parts = [overlap_text, para] if overlap_text else [para]
                        chunk_size = sum(len(p) for p in chunk_parts)
                    else:
                        chunk_parts.append(para)
                        chunk_size += len(para)
            
            # 保存最后一个 chunk
            if chunk_parts:
                content = '\n\n'.join(chunk_parts).strip() if len(chunk_parts) > 1 else chunk_parts[0].strip()
                if len(content) >= self.MIN_CHUNK_LENGTH:
                    chunks.append(PDFChunk(
                        content=content,
                        page=chunk_start_page,
                        section=current_section,
                        metadata={
                            "source": metadata.source,
                            "vendor": metadata.vendor,
                            "chip": metadata.chip,
                        }
                    ))
            
            section_buffer = []
        
        # 遍历所有内容页
        for page in content_pages:
            page_section = page["section"]
            page_text = page["text"]
            page_num = page["page_num"]
            
            # section 变化时，先处理之前的 buffer
            if page_section != current_section and section_buffer:
                flush_section_buffer()
                current_section = page_section
                section_start_page = page_num
            
            # 提取正文（移除 section 标记）
            text_lines = []
            for line in page_text.split('\n'):
                if line.startswith("##SECTION##"):
                    # section 标题单独一行
                    section_name = line[11:]  # 移除标记
                    if section_name != current_section:
                        flush_section_buffer()
                        current_section = section_name
                        section_start_page = page_num
                    text_lines.append(section_name)
                else:
                    text_lines.append(line)
            
            paragraph = '\n'.join(text_lines).strip()
            if paragraph:
                section_buffer.append(paragraph)
        
        # 处理最后一个 section
        flush_section_buffer()
        
        return chunks
    
    def _calc_overlap(self, parts: List[str]) -> str:
        """计算重叠文本（约 80 字符）"""
        if not parts:
            return ""
        
        # 从后往前拼接，直到达到 overlap 大小
        overlap_parts = []
        total = 0
        
        for part in reversed(parts):
            part_len = len(part)
            if total + part_len > self.overlap:
                # 如果当前部分太长，截断
                if total == 0:
                    return part[-self.overlap:]
                break
            overlap_parts.insert(0, part)
            total += part_len
        
        if len(overlap_parts) == 1:
            return overlap_parts[0]
        return '\n\n'.join(overlap_parts) if '\n\n' in parts[0] else ' '.join(overlap_parts)
    
    def process_pdf(self, pdf_path: Path, metadata: Optional[PDFMetadata] = None) -> List[PDFChunk]:
        """
        处理 PDF 文件
        
        流程：
        1. 提取结构化内容（跳过目录/版权页）
        2. 按 section 分块（size=500, overlap=80）
        3. 过滤短文本（<50）
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 不存在: {pdf_path}")
        
        if metadata is None:
            metadata = self.extract_metadata_from_filename(pdf_path.name)
        metadata.source = pdf_path.name
        
        logger.info(f"📖 处理 PDF: {pdf_path.name}")
        
        # 1. 提取结构化内容
        pages = self.extract_structure(pdf_path)
        content_pages = [p for p in pages if p["is_content"]]
        
        # 2. 创建 chunks
        chunks = self.create_chunks(pages, metadata)
        
        # 统计
        if chunks:
            sizes = [len(c.content) for c in chunks]
            avg_size = sum(sizes) / len(sizes)
            logger.info(f"   内容页: {len(content_pages)}/{len(pages)}")
            logger.info(f"   Chunks: {len(chunks)} 个")
            logger.info(f"   平均大小: {avg_size:.0f} 字符")
            logger.info(f"   大小范围: [{min(sizes)}, {max(sizes)}]")
        
        return chunks
    
    def store_chunks(self, chunks: List[PDFChunk], vector_store) -> Dict[str, Any]:
        """存储 chunks 到向量库"""
        if not self.embedder:
            raise ValueError("需要提供 embedder")
        
        stats = {"chunks_processed": len(chunks), "chunks_stored": 0, "errors": []}
        
        for i, chunk in enumerate(chunks):
            try:
                # 生成 embedding（限制长度）
                text_for_embed = chunk.content[:2500]  # 留足余量
                embedding = self.embedder.embed(text_for_embed)
                
                # 验证 embedding
                if not self._is_valid(embedding):
                    logger.warning(f"Chunk {i}: embedding 无效，跳过")
                    continue
                
                # 存储
                vector_store.add_with_embedding(
                    text=chunk.content,
                    embedding=embedding,
                    metadata={
                        **chunk.metadata,
                        "page": chunk.page,
                        "section": chunk.section,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                )
                stats["chunks_stored"] += 1
                
            except Exception as e:
                logger.error(f"Chunk {i} 存储失败: {e}")
                stats["errors"].append(f"chunk {i}: {str(e)[:50]}")
        
        return stats
    
    def process_and_store(self, pdf_path: Path, vector_store,
                          metadata: Optional[PDFMetadata] = None) -> Dict[str, Any]:
        """
        完整流程：PDF → 结构化文本 → Chunks → Embedding → Chroma
        """
        start = time.time()
        
        chunks = self.process_pdf(pdf_path, metadata)
        stats = self.store_chunks(chunks, vector_store)
        
        elapsed = time.time() - start
        logger.info(f"✅ {pdf_path.name}: {stats['chunks_stored']}/{stats['chunks_processed']} chunks, {elapsed:.1f}s")
        
        return stats
    
    def _is_valid(self, embedding: List[float]) -> bool:
        """验证 embedding 有效性"""
        if not embedding:
            return False
        if any(x != x for x in embedding):  # NaN
            return False
        if any(abs(x) == float('inf') for x in embedding):  # Inf
            return False
        if all(x == 0 for x in embedding):  # 全零
            return False
        return True


# ============ 便捷函数 ============

def process_pdf_file(pdf_path: str, vector_store, embedder,
                     chunk_size: int = 500, overlap: int = 80) -> Dict[str, Any]:
    """处理单个 PDF 文件"""
    processor = PDFProcessor(embedder=embedder, chunk_size=chunk_size, overlap=overlap)
    return processor.process_and_store(Path(pdf_path), vector_store)


def process_pdf_directory(directory: str, vector_store, embedder,
                          chunk_size: int = 500, overlap: int = 80) -> List[Dict[str, Any]]:
    """批量处理目录中的所有 PDF"""
    processor = PDFProcessor(embedder=embedder, chunk_size=chunk_size, overlap=overlap)
    results = []
    
    pdf_dir = Path(directory)
    if not pdf_dir.exists():
        logger.error(f"目录不存在: {directory}")
        return results
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        result = processor.process_and_store(pdf_file, vector_store)
        result["file"] = pdf_file.name
        results.append(result)
    
    return results
