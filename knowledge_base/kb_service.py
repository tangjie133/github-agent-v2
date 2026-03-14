#!/usr/bin/env python3
"""
知识库服务 (KB Service)

处理流程：PDF → 结构化文本 → chunk → embedding → ChromaDB
"""

import os
import sys
import json
import logging
import hashlib
import requests
import requests.adapters
import urllib3
from pathlib import Path
from typing import List, Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("urllib3").setLevel(logging.WARNING)


class SimpleEmbedding:
    """Ollama 嵌入生成器"""
    
    MODEL_DIMENSIONS = {
        "nomic-embed-text": 768,
        "nomic-embed-text:latest": 768,
        "bge-m3": 1024,
        "bge-m3:latest": 1024,
        "all-minilm": 384,
        "all-minilm:latest": 384,
    }
    
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.model = model
        self.hosts = [h.strip() for h in host.split(',')] if ',' in host else [host]
        self._host_index = 0
        self._host_lock = threading.Lock()
        self._cache = {}
        
        if model in self.MODEL_DIMENSIONS:
            self._dimension = self.MODEL_DIMENSIONS[model]
        else:
            self._dimension = 768
        logger.info(f"使用维度: {self._dimension} (模型: {model})")
        
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=urllib3.util.Retry(total=3, backoff_factor=0.1)
        )
        self._session.mount('http://', adapter)
    
    def _get_host(self) -> str:
        with self._host_lock:
            host = self.hosts[self._host_index]
            self._host_index = (self._host_index + 1) % len(self.hosts)
            return host
    
    def get_dimension(self) -> int:
        return self._dimension
    
    def embed(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self._dimension
        
        text = text.strip()[:8000]
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        host = self._get_host()
        response = self._session.post(
            f"{host}/api/embed",
            json={"model": self.model, "input": text},
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        embedding = result.get("embeddings", [[]])[0] if "embeddings" in result else result.get("embedding", [])
        
        if len(embedding) != self._dimension:
            raise ValueError(f"维度不匹配: 期望 {self._dimension}, 实际 {len(embedding)}")
        
        self._cache[cache_key] = embedding
        return embedding


class ChromaVectorStore:
    """ChromaDB 向量存储"""
    
    def __init__(self, persist_dir: str, collection_name: str = "knowledge_base"):
        try:
            import chromadb
            self.chromadb = chromadb
        except ImportError:
            raise RuntimeError("chromadb 未安装: pip install chromadb")
        
        self.persist_dir = persist_dir
        self.client = self.chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB 已初始化: {persist_dir}")
    
    def add_with_embedding(self, text: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
        doc_id = hashlib.md5(f"{metadata.get('source', 'unknown')}_{text[:100]}".encode()).hexdigest()
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
        return doc_id
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, max(1, self.collection.count())),
                include=["documents", "metadatas", "distances"]
            )
            
            output = []
            for i in range(len(results['ids'][0])):
                distance = results['distances'][0][i]
                similarity = 1 - distance
                output.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "similarity": round(similarity, 4)
                })
            return output
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def delete_by_source(self, source: str):
        try:
            results = self.collection.get(where={"source": source}, include=[])
            if results['ids']:
                self.collection.delete(ids=results['ids'])
        except Exception as e:
            logger.error(f"删除失败: {e}")
    
    def get_document_hashes(self) -> Dict[str, str]:
        """获取已存储文件的哈希（用于增量检测）"""
        try:
            results = self.collection.get(include=["metadatas"])
            hashes = {}
            seen = set()
            for meta in results['metadatas']:
                source = meta.get('source', '')
                file_hash = meta.get('file_hash', '')
                if source and file_hash and source not in seen:
                    hashes[source] = file_hash
                    seen.add(source)
            return hashes
        except Exception as e:
            logger.error(f"获取哈希失败: {e}")
            return {}
    
    def count(self) -> int:
        try:
            return self.collection.count()
        except:
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_documents": self.count(),
            "persist_dir": self.persist_dir
        }


class KnowledgeBaseService:
    """知识库服务"""
    
    def __init__(self, data_dir: str = None, embedding_model: str = None, 
                 embedding_host: str = None, chroma_dir: str = None):
        
        # 从环境变量获取状态目录
        statedir = Path(os.environ.get("GITHUB_AGENT_STATEDIR", "/tmp/github-agent-state"))
        statedir.mkdir(parents=True, exist_ok=True)
        
        # 知识库目录（基于 STATEDIR）
        self.kb_chips_dir = statedir / "knowledge_base" / "chips"
        self.kb_practices_dir = statedir / "knowledge_base" / "best_practices"
        
        # 初始化嵌入模型
        self.embedding_model = embedding_model or "nomic-embed-text"
        self.embedding_host = embedding_host or "http://localhost:11434"
        self.embedder = SimpleEmbedding(model=self.embedding_model, host=self.embedding_host)
        
        # 初始化 ChromaDB（也在 STATEDIR 下）
        chroma_path = chroma_dir or str(statedir / "chroma_db")
        self.vector_store = ChromaVectorStore(persist_dir=chroma_path)
        
        # 初始化 PDF 处理器
        self._init_pdf_processor()
        
        # 确保知识库目录存在
        self.kb_chips_dir.mkdir(parents=True, exist_ok=True)
        self.kb_practices_dir.mkdir(parents=True, exist_ok=True)
        
        # 后台加载知识库（避免启动阻塞）
        threading.Thread(target=self._sync_knowledge, daemon=True).start()
    
    def _init_pdf_processor(self):
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from pdf_processor import PDFProcessor
            self.pdf_processor = PDFProcessor(
                embedder=self.embedder,
                chunk_size=500,
                overlap=80
            )
        except Exception as e:
            logger.warning(f"PDF 处理器初始化失败: {e}")
            self.pdf_processor = None
    
    def _get_kb_dirs(self) -> List[tuple]:
        """获取知识库目录"""
        return [(self.kb_chips_dir, "chip"), (self.kb_practices_dir, "practice")]
    
    def _calc_hash(self, file: Path) -> str:
        """计算文件哈希"""
        if file.suffix.lower() == '.pdf':
            stat = file.stat()
            return hashlib.md5(f"{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()
        else:
            return hashlib.md5(file.read_bytes()).hexdigest()
    
    def _process_file(self, file: Path, doc_type: str, stored_hashes: Dict[str, str]) -> tuple:
        """处理单个文件，返回 (status, hash)"""
        file_key = str(file)
        file_hash = self._calc_hash(file)
        
        # 检查是否已存在
        if file_key in stored_hashes and stored_hashes[file_key] == file_hash:
            return "unchanged", file_hash
        
        # 删除旧数据（如果存在）
        if file_key in stored_hashes:
            self.vector_store.delete_by_source(file_key)
        
        # 处理 Markdown
        if file.suffix.lower() == '.md':
            content = file.read_text(encoding='utf-8')
            embedding = self.embedder.embed(content[:1000])
            self.vector_store.add_with_embedding(
                content, embedding,
                {"source": file_key, "type": doc_type, "file_hash": file_hash}
            )
            logger.info(f"已加载 Markdown: {file.name}")
            return "added", file_hash
        
        # 处理 PDF
        if file.suffix.lower() == '.pdf' and self.pdf_processor:
            from pdf_processor import PDFMetadata
            metadata = self.pdf_processor.extract_metadata_from_filename(file.name)
            metadata.source = file_key
            
            result = self.pdf_processor.process_and_store(
                pdf_path=file,
                vector_store=self.vector_store,
                metadata=metadata
            )
            
            # 更新第一个 chunk 的 hash
            if result.get("chunks_stored", 0) > 0:
                try:
                    res = self.vector_store.collection.get(
                        where={"source": file_key}, limit=1, include=["metadatas"]
                    )
                    if res['ids']:
                        old_id = res['ids'][0]
                        old = self.vector_store.collection.get(
                            ids=[old_id], include=["documents", "embeddings"]
                        )
                        if old['documents']:
                            self.vector_store.collection.delete(ids=[old_id])
                            meta = res['metadatas'][0].copy()
                            meta['file_hash'] = file_hash
                            self.vector_store.add_with_embedding(
                                old['documents'][0], old['embeddings'][0], meta
                            )
                except:
                    pass
            
            logger.info(f"已加载 PDF: {file.name}")
            return "added", file_hash
        
        return "failed", ""
    
    def _sync_knowledge(self):
        """同步知识库（增量加载）"""
        stored_hashes = self.vector_store.get_document_hashes()
        stats = {"added": 0, "unchanged": 0, "failed": 0}
        
        for dir_path, doc_type in self._get_kb_dirs():
            if not dir_path.exists():
                continue
            
            for file in dir_path.glob("*"):
                if file.suffix.lower() not in ['.md', '.pdf']:
                    continue
                
                try:
                    status, _ = self._process_file(file, doc_type, stored_hashes)
                    stats[status] += 1
                except Exception as e:
                    stats["failed"] += 1
                    logger.warning(f"处理失败 {file}: {e}")
        
        if stats["added"] + stats["unchanged"] > 0:
            logger.info(f"加载完成: 新增 {stats['added']}, 未变更 {stats['unchanged']}, 失败 {stats['failed']}")
        else:
            logger.info("知识库为空")
    
    def reload(self) -> Dict[str, Any]:
        """重新加载（API 调用）"""
        logger.info("重新加载知识库...")
        self._sync_knowledge()
        return {"status": "success", "documents": self.vector_store.count()}
    
    def query(self, query_text: str, top_k: int = 3) -> Dict[str, Any]:
        """查询知识库"""
        import time
        start = time.time()
        
        query_embedding = self.embedder.embed(query_text)
        results = self.vector_store.search(query_embedding, top_k)
        
        return {
            "query": query_text,
            "results": results,
            "total_found": len(results),
            "elapsed_ms": round((time.time() - start) * 1000, 2)
        }
    
    def health_check(self) -> bool:
        try:
            return len(self.embedder.embed("test")) > 0
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "total_documents": self.vector_store.count()
        }


class KBRequestHandler(BaseHTTPRequestHandler):
    kb_service: KnowledgeBaseService = None
    
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")
    
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        if self.path == "/health":
            healthy = self.kb_service.health_check() if self.kb_service else False
            self._send_json({
                "status": "healthy" if healthy else "unhealthy",
                "documents": self.kb_service.get_stats()["total_documents"] if self.kb_service else 0
            })
        elif self.path == "/stats":
            self._send_json(self.kb_service.get_stats() if self.kb_service else {})
        elif self.path == "/reload":
            self._send_json(self.kb_service.reload() if self.kb_service else {})
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode()) if post_data else {}
        except:
            data = {}
        
        if self.path == "/query":
            query = data.get("query", "")
            top_k = data.get("top_k", 3)
            if not query:
                self._send_json({"error": "Missing query"}, 400)
                return
            self._send_json(self.kb_service.query(query, top_k))
        elif self.path == "/add":
            text = data.get("text", "")
            metadata = data.get("metadata", {})
            if not text:
                self._send_json({"error": "Missing text"}, 400)
                return
            embedding = self.kb_service.embedder.embed(text[:2000])
            self.kb_service.vector_store.add_with_embedding(text, embedding, metadata)
            self._send_json({"status": "success"})
        elif self.path == "/reload":
            self._send_json(self.kb_service.reload())
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()


def run_server(host: str = "0.0.0.0", port: int = 8000, data_dir: str = None,
               embedding_model: str = None, embedding_host: str = None, chroma_dir: str = None):
    logger.info(f"启动知识库服务 {host}:{port}")
    
    kb_service = KnowledgeBaseService(
        data_dir=data_dir,
        embedding_model=embedding_model,
        embedding_host=embedding_host,
        chroma_dir=chroma_dir
    )
    
    KBRequestHandler.kb_service = kb_service
    
    server = HTTPServer((host, port), KBRequestHandler)
    logger.info(f"知识库服务已启动 http://{host}:{port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("正在关闭服务...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--chroma-dir", default=None, help="ChromaDB 目录（默认使用 GITHUB_AGENT_STATEDIR/chroma_db）")
    parser.add_argument("--embedding-model", default="nomic-embed-text")
    parser.add_argument("--embedding-host", default="http://localhost:11434")
    args = parser.parse_args()
    
    run_server(
        host=args.host,
        port=args.port,
        chroma_dir=args.chroma_dir,
        embedding_model=args.embedding_model,
        embedding_host=args.embedding_host
    )
