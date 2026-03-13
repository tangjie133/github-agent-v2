#!/usr/bin/env python3
"""
知识库服务 (KB Service)

提供本地 RAG 知识库服务，使用 Ollama 的 nomic-embed-text 模型进行文本嵌入
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入必要的库
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy 未安装，知识库功能受限")


class SimpleEmbedding:
    """简化版嵌入生成器（使用 Ollama）"""
    
    # 常用模型的向量维度
    MODEL_DIMENSIONS = {
        "nomic-embed-text": 768,
        "nomic-embed-text:latest": 768,
        "bge-m3": 1024,
        "bge-m3:latest": 1024,
        "bge-large": 1024,
        "all-minilm": 384,
        "all-minilm:latest": 384,
        "mxbai-embed-large": 1024,
    }
    
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self._cache = {}  # 简单缓存
        self._dimension = None  # 动态获取的维度
        
    def _get_dimension(self) -> int:
        """获取向量维度（优先从已知模型获取，否则动态检测）"""
        if self._dimension is not None:
            return self._dimension
        
        # 从已知模型列表查找
        if self.model in self.MODEL_DIMENSIONS:
            self._dimension = self.MODEL_DIMENSIONS[self.model]
            return self._dimension
        
        # 尝试动态检测（调用一次嵌入服务）
        try:
            test_embedding = self.embed("test", use_cache=False)
            self._dimension = len(test_embedding)
            logger.info(f"检测到模型 '{self.model}' 的向量维度: {self._dimension}")
            return self._dimension
        except Exception:
            # 默认使用768
            logger.warning(f"无法检测模型 '{self.model}' 的维度，使用默认值 768")
            self._dimension = 768
            return 768
        
    def embed(self, text: str, use_cache: bool = True) -> List[float]:
        """生成文本嵌入向量"""
        # 检查缓存
        if use_cache and text in self._cache:
            return self._cache[text]
        
        try:
            import requests
            response = requests.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            embedding = response.json()["embedding"]
            
            # 缓存结果
            if use_cache:
                self._cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error(f"嵌入生成失败: {e}")
            # 返回零向量作为降级（使用正确的维度）
            return [0.0] * self._get_dimension()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入"""
        return [self.embed(t) for t in texts]


class SimpleVectorStore:
    """简化版向量存储"""
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        
    def add(self, text: str, metadata: Dict[str, Any] = None):
        """添加文档"""
        self.documents.append({
            "text": text,
            "metadata": metadata or {}
        })
    
    def add_with_embedding(self, text: str, embedding: List[float], metadata: Dict[str, Any] = None):
        """添加带嵌入的文档"""
        self.documents.append({
            "text": text,
            "metadata": metadata or {}
        })
        self.embeddings.append(embedding)
    
    def search(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """相似度搜索"""
        if not self.embeddings or not HAS_NUMPY:
            return []
        
        # 计算余弦相似度
        query_vec = np.array(query_embedding)
        doc_vecs = np.array(self.embeddings)
        
        # 归一化
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-8)
        doc_vecs = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-8)
        
        # 计算相似度
        similarities = np.dot(doc_vecs, query_vec)
        
        # 获取 top_k
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                "text": self.documents[idx]["text"],
                "metadata": self.documents[idx]["metadata"],
                "similarity": float(similarities[idx])
            })
        
        return results


class KnowledgeBaseService:
    """知识库服务"""
    
    def __init__(self, data_dir: str = None, embedding_model: str = None, embedding_host: str = None):
        self.data_dir = Path(data_dir or os.environ.get("KB_DATA_DIR", "./knowledge_base/data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 从环境变量或参数获取嵌入模型配置
        self.embedding_model = embedding_model or os.environ.get("KB_EMBEDDING_MODEL", "nomic-embed-text")
        self.embedding_host = embedding_host or os.environ.get("KB_EMBEDDING_HOST", "http://localhost:11434")
        
        # 初始化组件
        self.embedder = SimpleEmbedding(model=self.embedding_model, host=self.embedding_host)
        self.vector_store = SimpleVectorStore()
        
        logger.info(f"使用嵌入模型: {self.embedding_model} @ {self.embedding_host}")
        
        # DEBUG 模式下输出详细配置
        if logger.isEnabledFor(logging.DEBUG):
            # 获取实际的向量维度
            actual_dimension = self.embedder._get_dimension()
            logger.debug(f"嵌入模型配置详情:")
            logger.debug(f"  模型名称: {self.embedding_model}")
            logger.debug(f"  服务地址: {self.embedding_host}")
            logger.debug(f"  向量维度: {actual_dimension}")
            logger.debug(f"  数据目录: {self.data_dir}")
            # 测试嵌入服务是否可用
            try:
                test_embedding = self.embedder.embed("test")
                logger.debug(f"  服务状态: 正常 (向量长度: {len(test_embedding)})")
            except Exception as e:
                logger.debug(f"  服务状态: 异常 ({e})")
        
        # 加载本地知识
        self._load_local_knowledge()
        
        logger.info(f"知识库服务初始化完成，数据目录: {self.data_dir}")
    
    def _load_local_knowledge(self):
        """加载本地知识库"""
        kb_base = Path(__file__).parent
        
        # 加载芯片文档
        chips_dir = kb_base / "chips"
        if chips_dir.exists():
            for file in chips_dir.glob("*.md"):
                try:
                    content = file.read_text(encoding='utf-8')
                    embedding = self.embedder.embed(content[:1000])  # 限制长度
                    self.vector_store.add_with_embedding(
                        content,
                        embedding,
                        {"source": str(file), "type": "chip_doc"}
                    )
                    logger.info(f"加载芯片文档: {file.name}")
                except Exception as e:
                    logger.warning(f"加载文档失败 {file}: {e}")
        
        # 加载最佳实践
        practices_dir = kb_base / "best_practices"
        if practices_dir.exists():
            for file in practices_dir.glob("*.md"):
                try:
                    content = file.read_text(encoding='utf-8')
                    embedding = self.embedder.embed(content[:1000])
                    self.vector_store.add_with_embedding(
                        content,
                        embedding,
                        {"source": str(file), "type": "best_practice"}
                    )
                    logger.info(f"加载最佳实践: {file.name}")
                except Exception as e:
                    logger.warning(f"加载文档失败 {file}: {e}")
        
        logger.info(f"共加载 {len(self.vector_store.documents)} 个文档")
    
    def reload(self):
        """重新加载知识库（用于更新后刷新）"""
        logger.info("重新加载知识库...")
        
        # 清空现有数据
        self.vector_store = SimpleVectorStore()
        
        # 重新加载
        self._load_local_knowledge()
        
        return {
            "status": "success",
            "documents": len(self.vector_store.documents)
        }
    
    def query(self, query_text: str, top_k: int = 3, generate_answer: bool = False) -> Dict[str, Any]:
        """查询知识库"""
        # 生成查询向量
        query_embedding = self.embedder.embed(query_text)
        
        # 搜索相似文档
        results = self.vector_store.search(query_embedding, top_k)
        
        # 构建响应
        response = {
            "query": query_text,
            "results": results,
            "total_found": len(results)
        }
        
        if generate_answer and results:
            # 简单答案生成（实际项目中可以使用 LLM）
            answer = self._generate_simple_answer(query_text, results)
            response["answer"] = answer
        
        return response
    
    def _generate_simple_answer(self, query: str, results: List[Dict]) -> str:
        """生成简单答案"""
        if not results:
            return "未找到相关信息。"
        
        # 使用最相似的结果
        best = results[0]
        text = best["text"][:500]  # 限制长度
        
        return f"根据知识库，相关信息如下：\n\n{text}...\n\n来源: {best['metadata'].get('source', 'unknown')}"
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            # 测试嵌入功能
            test_embedding = self.embedder.embed("test")
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_documents": len(self.vector_store.documents),
            "embedding_model": self.embedder.model,
            "data_dir": str(self.data_dir)
        }


class KBRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    kb_service: KnowledgeBaseService = None
    
    def log_message(self, format, *args):
        """自定义日志"""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def _send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == "/health":
            healthy = self.kb_service.health_check() if self.kb_service else False
            self._send_json({
                "status": "healthy" if healthy else "unhealthy",
                "documents": self.kb_service.get_stats()["total_documents"] if self.kb_service else 0
            })
        
        elif self.path == "/stats":
            if self.kb_service:
                self._send_json(self.kb_service.get_stats())
            else:
                self._send_json({"error": "Service not initialized"}, 500)
        
        elif self.path == "/reload":
            # 重新加载知识库
            if self.kb_service:
                result = self.kb_service.reload()
                self._send_json(result)
            else:
                self._send_json({"error": "Service not initialized"}, 500)
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """处理 POST 请求"""
        if self.path == "/query":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                query_text = data.get("query", "")
                top_k = data.get("top_k", 3)
                generate_answer = data.get("generate_answer", False)
                
                if not query_text:
                    self._send_json({"error": "Missing query"}, 400)
                    return
                
                result = self.kb_service.query(query_text, top_k, generate_answer)
                self._send_json(result)
                
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
            except Exception as e:
                logger.exception("Query failed")
                self._send_json({"error": str(e)}, 500)
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        """处理 OPTIONS 请求（CORS 预检）"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(host: str = "0.0.0.0", port: int = 8000, data_dir: str = None):
    """运行知识库服务"""
    logger.info(f"启动知识库服务 {host}:{port}")
    
    # 初始化知识库服务
    kb_service = KnowledgeBaseService(data_dir)
    KBRequestHandler.kb_service = kb_service
    
    # 启动 HTTP 服务器
    server = HTTPServer((host, port), KBRequestHandler)
    logger.info(f"知识库服务已启动 http://{host}:{port}")
    logger.info(f"健康检查: http://{host}:{port}/health")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("正在关闭服务...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Base Service")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--data-dir", help="数据目录")
    
    args = parser.parse_args()
    
    run_server(args.host, args.port, args.data_dir)
