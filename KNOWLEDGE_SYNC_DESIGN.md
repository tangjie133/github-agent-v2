# 知识库同步设计 - 统一存储架构

## 设计目标

1. **单一数据源**: GitHub 仓库作为唯一数据源，ChromaDB 作为唯一存储
2. **无本地文件依赖**: 所有文档直接处理存入向量库，不保留本地文件
3. **高性能**: 利用多线程和优化解析器提升处理速度
4. **可移植性**: ChromaDB 目录可直接复制迁移
5. **版本控制**: 源文件版本由 GitHub 管理，同步状态独立追踪

---

## 架构设计

### 统一存储架构

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub 仓库                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  datasheet/  │  │   guides/    │  │  examples/   │       │
│  │  *.pdf       │  │   *.md       │  │   *.txt      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Webhook / 定时拉取
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 github_repo_watcher.py                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  1. 检测文件变更                                       │  │
│  │     - 对比 SHA（同步状态文件）                          │  │
│  │     - 检查 ChromaDB 中是否已存在                        │  │
│  └───────────────────────────────────────────────────────┘  │
                              │
                              │ 下载到临时目录
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 文档解析（根据文件类型）                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  PDF         │  │  Markdown    │  │  TXT/DOCX    │       │
│  │  PyMuPDF     │  │  直接读取    │  │  文本提取    │       │
│  │  ~70页/s     │  │  即时        │  │  <1s         │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 分段处理（长文档）
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. 并行生成 Embedding                                       │
│     - 批量请求 Ollama API                                    │
│     - 4-8 线程并发（可配置）                                  │
│     - 连接池优化 HTTP 请求                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. ChromaDB 存储                                            │
│     /home/tj/chroma_db/                                      │
│     - 向量数据                                               │
│     - 元数据索引                                             │
│     - 自动持久化                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 清理临时文件
                              ▼
                        [完成]
```

---

## 同步流程详解

### 1. 变更检测

```python
# 同步状态文件: /home/tj/state/.github_kb_sync_state.json
{
  "datasheet/esp32.pdf": "abc123...",
  "guides/i2c.md": "def456..."
}

# 检测逻辑:
1. 获取 GitHub 文件列表和 SHA
2. 对比本地同步状态
3. 如果 SHA 匹配，检查 ChromaDB 中是否存在
4. 如果不存在或 SHA 不匹配，需要重新处理
```

### 2. 文档解析

#### PDF 解析流程
```python
import fitz  # PyMuPDF

with fitz.open(pdf_path) as pdf:
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        text = page.get_text()
        # 每页独立处理
        embedding = embedder.embed(text)
        store.add(text, embedding, metadata={
            "source": "esp32.pdf",
            "page": page_num + 1,
            "doc_type": "pdf"
        })
```

#### Markdown/TXT/DOCX 解析流程
```python
# 1. 提取文本
if ext == '.md':
    content = file.read_text()
elif ext == '.txt':
    content = f"# {filename}\n\n```\n{file.read_text()}\n```"
elif ext == '.docx':
    content = extract_from_docx(file)

# 2. 长文档分段
if len(content) > 2000:
    chunks = split_into_chunks(content, chunk_size=2000)
else:
    chunks = [content]

# 3. 每段生成 embedding
for idx, chunk in enumerate(chunks, 1):
    embedding = embedder.embed(chunk)
    store.add(chunk, embedding, metadata={
        "source": filename,
        "chunk_index": idx,
        "total_chunks": len(chunks),
        "doc_type": "document"
    })
```

### 3. 并行 Embedding 生成

```python
from concurrent.futures import ThreadPoolExecutor

def embed_batch(texts):
    with ThreadPoolExecutor(max_workers=4) as executor:
        embeddings = list(executor.map(embedder.embed, texts))
    return embeddings

# 批量处理（50-100页/批）
for batch in chunks(pages, batch_size=50):
    embeddings = embed_batch([p.content for p in batch])
    for page, embedding in zip(batch, embeddings):
        store.add(page.content, embedding, page.metadata)
```

### 4. ChromaDB 存储

```python
# 集合名称: knowledge_base
# 持久化目录: /home/tj/chroma_db

vector_store.add_with_embedding(
    text=content,
    embedding=embedding,
    metadata={
        "source": "datasheet/esp32.pdf",
        "doc_type": "pdf",  # 或 "document"
        "page": 42,
        "chunk_index": 1,
        "total_chunks": 5,
        "category": "chip_doc",  # 或 "best_practice"
        "file_ext": ".pdf",
        "vendor": "espressif",
        "chip": "esp32",
        "processed_at": timestamp
    }
)
```

---

## 元数据设计

### 统一元数据格式

```json
{
  "source": "datasheet/esp32.pdf",
  "doc_type": "pdf|document",
  "file_ext": ".pdf|.md|.txt|.docx",
  "category": "chip_doc|best_practice",
  
  "// PDF 特有": "",
  "page": 42,
  "total_pages": 110,
  "vendor": "espressif",
  "chip": "esp32",
  
  "// 分段文档特有": "",
  "chunk_index": 1,
  "total_chunks": 5,
  
  "// 通用": "",
  "content_preview": "前200字符预览",
  "processed_at": 1773452624.022
}
```

### 分类规则

| 规则 | 分类 | 示例 |
|------|------|------|
| 文件名含 `chip/芯片/hardware/datasheet` | `chip_doc` | `bmi160_datasheet.pdf` |
| 其他文件 | `best_practice` | `coding_guide.md` |

---

## 存储对比

### 旧架构（混合存储）

```
PDF: GitHub → 本地临时 → 解析 → ChromaDB ✅
MD:  GitHub → 本地文件 → KB Service加载 → ChromaDB ❌
TXT: GitHub → 本地文件 → KB Service加载 → ChromaDB ❌
DOCX: GitHub → 本地文件 → KB Service加载 → ChromaDB ❌
```

**问题：**
1. 本地文件和 ChromaDB 可能不一致
2. 启动时需要加载本地文件，增加启动时间
3. 路径管理复杂

### 新架构（统一存储）

```
所有类型: GitHub → 本地临时 → 解析 → ChromaDB ✅
               ↓
         清理临时文件
```

**优势：**
1. 单一数据源（GitHub）+ 单一存储（ChromaDB）
2. 启动时直接读取 ChromaDB，无需加载本地文件
3. 简化架构，易于维护

---

## 性能设计

### 解析性能

| 文件类型 | 解析器 | 速度 | 备注 |
|---------|--------|------|------|
| PDF | PyMuPDF | ~70页/s | 比 pdfplumber 快 70 倍 |
| Markdown | 原生 | 即时 | 直接读取 |
| TXT | 原生 | 即时 | 包装为 Markdown |
| DOCX | python-docx | <1s | 纯文本提取 |

### 并发设计

```
文档解析（单线程）
    ↓
分批（50-100页/批）
    ↓
并行 Embedding（4-8线程）
    ↓
批量写入 ChromaDB
```

### 性能指标

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 110页 PDF | ~60s | ~10s | 6x |
| 启动时间 | ~30s | ~3s | 10x |
| 检索延迟 | ~161ms | ~0.2ms | 750x |

---

## 配置参数

### 环境变量

```bash
# 状态目录（所有数据统一存储在此目录下）
# 知识库存储: ${GITHUB_AGENT_STATEDIR}/knowledge_base/
# ChromaDB 存储: ${GITHUB_AGENT_STATEDIR}/chroma_db/
# 同步状态: ${GITHUB_AGENT_STATEDIR}/.github_kb_sync_state.json
GITHUB_AGENT_STATEDIR=/home/tj/state

# PDF 处理
KB_PDF_WORKERS=4                    # 并行线程数（默认 CPU/4）
KB_PDF_PARALLEL_THRESHOLD=3         # 启用并行阈值（页数）

# 嵌入模型
KB_EMBEDDING_MODEL=bge-m3:latest
KB_EMBEDDING_HOST=http://localhost:11434

# 文档分段
KB_CHUNK_SIZE=2000                  # 每段最大字符数（可选）
```

### 目录结构

```
/home/tj/
├── chroma_db/                    # ChromaDB 向量存储（持久化）
│   ├── chroma.sqlite3
│   └── ...
├── github-agent-v2/              # 工作目录（临时文件，可清理）
│   └── github_kb_sync/
│       └── temp_xxx.pdf
└── state/                        # 同步状态（持久化）
    └── .github_kb_sync_state.json
```

---

## 故障恢复

### 场景 1: ChromaDB 数据损坏

```bash
# 1. 停止服务
pkill -f kb_service

# 2. 删除损坏的 ChromaDB
rm -rf /home/tj/chroma_db

# 3. 重新同步（从 GitHub 重建）
python scripts/github_repo_watcher.py --sync

# 4. 启动服务
python -m knowledge_base.kb_service
```

### 场景 2: 同步状态丢失

```bash
# 删除同步状态文件
rm /home/tj/state/.github_kb_sync_state.json

# 重新同步（会重新处理所有文件）
python scripts/github_repo_watcher.py --sync
```

### 场景 3: 临时文件堆积

```bash
# 清理工作目录
rm -rf /home/tj/github-agent-v2/github_kb_sync/*

# 注意：正常流程会自动清理临时文件，堆积可能是异常中断导致
```

---

## 注意事项

### 1. 不再使用的目录

以下目录**不再写入文件**，仅保留代码兼容性：

```bash
knowledge_base/chips/          # 原芯片文档存储
knowledge_base/best_practices/ # 原最佳实践存储
```

**清理命令**（可选）：
```bash
rm -rf knowledge_base/chips/* knowledge_base/best_practices/*
```

### 2. 向量维度一致性

切换嵌入模型时需要重建 ChromaDB：

```bash
# 查看当前模型
curl http://localhost:11434/api/tags

# 切换模型前清理
cp -r /home/tj/chroma_db /home/tj/chroma_db.backup
rm -rf /home/tj/chroma_db

# 修改 .env 中的 KB_EMBEDDING_MODEL
# 重新同步
python scripts/github_repo_watcher.py --sync
```

### 3. 大文件处理

超过 100MB 的 PDF 可能需要：
- 增加 `KB_PDF_WORKERS` 以提升并发
- 或者拆分为多个小文件

---

## 附录

### A. 同步状态文件格式

```json
{
  "datasheet/esp32.pdf": {
    "sha": "abc123...",
    "synced_at": "2026-03-14T09:30:00Z"
  },
  "guides/i2c.md": {
    "sha": "def456...",
    "synced_at": "2026-03-14T09:30:00Z"
  }
}
```

### B. ChromaDB 集合结构

```python
Collection: knowledge_base
- embedding_function: 默认（使用预计算向量）
- metadata: 见上文统一元数据格式
- distance: cosine
```

### C. 监控指标

```bash
# 查看文档数量
curl http://localhost:8000/stats | jq '.total_documents'

# 查看 ChromaDB 大小
du -sh /home/tj/chroma_db

# 查看同步日志
tail -f /tmp/github_kb_sync.log
```
