# GitHub Agent V2 - 系统架构设计

本文档详细描述 GitHub Agent V2 的系统架构、设计原则和关键技术决策。

## 📋 目录

1. [架构总览](#架构总览)
2. [设计原则](#设计原则)
3. [模块详解](#模块详解)
4. [知识库架构](#知识库架构)
5. [数据流](#数据流)
6. [关键技术决策](#关键技术决策)
7. [配置说明](#配置说明)

---

## 架构总览

GitHub Agent V2 采用**分层架构 + 管道模式**，将复杂的自动化流程拆分为多个独立的层次，每层只负责单一职责。

```
┌─────────────────────────────────────────────────────────────────┐
│                     External Systems                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    GitHub    │  │   OpenClaw   │  │   Ollama     │           │
│  │    API       │  │   (Cloud)    │  │   (Local)    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Agent V2                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 5: Presentation Layer (Webhook)                     │ │
│  │  - Webhook 接收与验证                                      │ │
│  │  - 事件路由                                                │ │
│  │  - HTTP API 接口                                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 4: Core Layer (Processor)                           │ │
│  │  - 业务流程编排                                            │ │
│  │  - 状态管理                                                │ │
│  │  - 错误处理                                                │ │
│  │  - Issue 生命周期跟踪                                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 3: Intelligence Layer                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │ │
│  │  │   Intent     │  │  Knowledge   │  │    Code      │      │ │
│  │  │ Classification│  │     Base     │  │  Execution   │      │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 2: Service Layer (GitHub API)                       │ │
│  │  - GitHub API 封装                                         │ │
│  │  - 认证管理                                                │ │
│  │  - PR/Comment 操作                                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 1: Infrastructure Layer                             │ │
│  │  - 配置管理 (Pydantic)                                     │ │
│  │  - 日志记录                                                │ │
│  │  - 工具函数                                                │ │
│  │  - 重试机制                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 设计原则

### 1. 单一职责原则 (SRP)

每个模块只负责一个明确的职责：

| 模块 | 职责 |
|------|------|
| `webhook/` | HTTP 请求处理和事件路由 |
| `core/` | 业务流程编排和状态管理 |
| `cloud_agent/` | 意图识别和决策 |
| `code_executor/` | 代码生成、修改和验证 |
| `knowledge_base/` | 文档存储、检索和向量化 |
| `github_api/` | GitHub API 交互 |

### 2. 依赖倒置原则 (DIP)

高层模块依赖抽象接口，而非具体实现：

```python
# 好的设计：依赖抽象
class IssueProcessor:
    def __init__(self, github_client: GitHubClientInterface, ...):
        self.github = github_client

# 避免：直接依赖具体实现
class IssueProcessor:
    def __init__(self):
        self.github = ConcreteGitHubClient()  # ❌
```

### 3. 统一存储架构

所有文档类型采用统一的存储架构：

```
GitHub 文件 (.pdf/.md/.txt/.docx)
       ↓
下载到临时目录 (WORKDIR)
       ↓
文本提取/解析
- PDF: PyMuPDF 按页解析 + 语义分块
- Markdown: 直接读取
- TXT: 包装为 Markdown
- DOCX: python-docx/pandoc 提取
       ↓
分段处理（长文档）
       ↓
并行生成 embedding (Ollama)
       ↓
ChromaDB 持久化存储
- 元数据: source, doc_type, page/chunk_index
- 向量维度: 768/1024/384 (根据模型)
```

### 4. 故障隔离

每个外部服务都有降级方案：

| 服务故障 | 降级方案 |
|---------|---------|
| OpenClaw 不可用 | 使用本地规则分类 |
| KB Service 不可用 | 跳过知识库查询 |
| Ollama 不可用 | 返回错误，不执行代码修改 |
| ChromaDB 损坏 | 重新同步 GitHub 仓库重建 |

---

## 模块详解

### 1. Webhook 层 (`webhook/`)

**职责：** 接收 GitHub Webhook 事件，进行初步验证和路由

**核心组件：**
- `webhook_server.py` - Flask HTTP 服务器
- 事件验证（Webhook Secret）
- 事件分发到 Processor

### 2. 核心层 (`core/`)

**职责：** 业务流程编排和状态管理

**核心组件：**
- `processor.py` - IssueProcessor，主处理器
- `context_builder.py` - 构建完整的 Issue 上下文
- `state_manager.py` - 跟踪 Issue 处理状态
- `issue_followup.py` - Issue 跟踪和自动关闭

**处理流程：**
```
Webhook Event
    ↓
Should Process? (触发模式检查)
    ↓
Build Context
    ↓
Classify Intent (OpenClaw/本地规则)
    ↓
Query Knowledge Base (如果需要)
    ↓
Execute Action (answer/modify/research)
    ↓
Send Response
```

### 3. 智能层 (`cloud_agent/` + `knowledge_base/` + `code_executor/`)

#### 3.1 意图识别 (`cloud_agent/`)

**组件：**
- `intent_classifier.py` - 意图分类器
- `openclaw_client.py` - OpenClaw API 客户端
- `decision_engine.py` - 决策引擎

**意图类型：**
```python
class IntentType:
    ANSWER = "answer"      # 回答技术问题
    MODIFY = "modify"      # 修改代码
    RESEARCH = "research"  # 查询知识库
    CLARIFY = "clarify"    # 需要澄清
```

**降级策略：**
- 优先使用 OpenClaw AI
- 失败时使用本地关键词规则

#### 3.2 知识库 (`knowledge_base/`)

**组件：**
- `kb_service.py` - ChromaDB 向量存储服务
- `pdf_processor.py` - PDF 解析、清理、分块
- `kb_client.py` - 客户端 API
- `kb_integrator.py` - 与 Issue 处理集成

**存储架构：**
```
ChromaDB (PersistentClient)
└── Collection: "knowledge_base"
    ├── Document: text content
    ├── Embedding: vector (768/1024 dim)
    └── Metadata:
        ├── source: file path
        ├── doc_type: "pdf" | "document"
        ├── page: page number (PDF)
        ├── chunk_index: segment index
        ├── total_chunks: total segments
        ├── category: "chip_doc" | "best_practice"
        └── vendor/chip: for chip docs
```

**PDF 处理流程：**
```
PDF File
    ↓
PyMuPDF 解析 (110 pages/s)
    ↓
文本清理 (移除页眉/页脚/版权)
    ↓
目录/版权页检测 (自动跳过)
    ↓
语义分块 (400 chars / chunk)
    ↓
结构化转换 (Markdown-like)
    ↓
Parallel Embedding Generation
    ↓
ChromaDB Storage
```

#### 3.3 代码执行 (`code_executor/`)

**组件：**
- `code_executor.py` - 主执行器
- `code_generator.py` - Ollama 代码生成
- `safe_modifier.py` - SEARCH/REPLACE 安全修改
- `repo_manager.py` - Git 仓库管理
- `change_validator.py` - 变更验证
- `code_analyzer.py` - 代码结构分析

**安全修改机制：**
```python
# SEARCH/REPLACE 格式
### file_path
<<<<<<< SEARCH
old_code
=======
new_code
>>>>>>> REPLACE
```

**验证步骤：**
1. 语法检查（Python AST）
2. 上下文匹配验证
3. 变更范围检查
4. 测试运行（可选）

### 4. 服务层 (`github_api/`)

**组件：**
- `auth_manager.py` - GitHub App 认证
- `github_client.py` - API 封装

**功能：**
- JWT 认证
- 安装令牌管理
- PR/Comment/Issue 操作

### 5. 基础设施层 (`config/` + `utils/`)

**组件：**
- `settings.py` - Pydantic 配置管理
- `logging_config.py` - 日志配置
- `retry.py` - 重试机制
- `errors.py` - 异常定义

---

## 知识库架构

### ChromaDB 存储设计

```python
# Collection 配置
{
    "name": "knowledge_base",
    "metadata": {"hnsw:space": "cosine"},
    "persist_directory": "/home/tj/chroma_db"
}

# Document 结构
{
    "id": "hash_id",
    "document": "text content",
    "embedding": [0.1, -0.2, ...],  # 1024 dim for bge-m3
    "metadata": {
        "source": "datasheet/bmi160.pdf",
        "doc_type": "pdf",
        "page": 42,
        "chunk_index": 3,
        "total_chunks": 15,
        "category": "chip_doc",
        "vendor": "bosch",
        "chip": "bmi160"
    }
}
```

### 文件类型处理策略

| 类型 | 解析器 | 分块策略 | 特殊处理 |
|------|--------|---------|---------|
| PDF | PyMuPDF | 语义分块 (400 chars) | 页眉/页脚清理 |
| Markdown | 直接读取 | 整篇或分段 | 保留格式 |
| TXT | 包装为 MD | 整篇或分段 | 代码块标记 |
| DOCX | python-docx | 整篇或分段 | 纯文本提取 |

### 同步机制

```
GitHub Repo (knowledge-base)
    │
    │ 1. 检测变更 (SHA comparison)
    ▼
github_repo_watcher.py
    │ 2. 下载到临时目录
    ▼
PDF Processor / Text Extractor
    │ 3. 解析 + 分块
    ▼
Embedding Generator (Ollama)
    │ 4. 批量生成向量
    ▼
KB Service API (/add)
    │ 5. 存入 ChromaDB
    ▼
ChromaDB (Persistent)
```

---

## 数据流

### 1. Issue 处理流程

```
GitHub Webhook
    ↓
[Webhook Layer]
    ↓
[Core Layer]
    ├─> Build Context
    ├─> Check Trigger Mode
    ├─> Classify Intent
    │       ↓
    │   [OpenClaw/Local]
    │       ↓
    ├─> Query KB (if research)
    │       ↓
    │   [ChromaDB]
    │       ↓
    ├─> Execute Action
    │       ↓
    │   [CodeExecutor]
    │       ↓
    └─> Send Response
            ↓
    [GitHub API]
```

### 2. 代码修改流程

```
User Request (fix bug)
    ↓
CodeExecutor
    ├─> 1. Analyze Code
    │       └─> CodeAnalyzer
    ├─> 2. Generate Plan
    ├─> 3. Generate SEARCH/REPLACE
    │       └─> Ollama
    ├─> 4. Apply Changes
    │       └─> SafeModifier
    ├─> 5. Validate
    │       └─> ChangeValidator
    └─> 6. Create PR
            └─> GitHubClient
```

### 3. 知识库查询流程

```
User Query: "BMI160 I2C 地址"
    ↓
KBIntegrator
    ├─> 1. Generate Embedding
    │       └─> Ollama (bge-m3)
    ├─> 2. ChromaDB Search
    │       └─> cosine similarity
    ├─> 3. Top-K Results
    └─> 4. Format Context
            ↓
    LLM Answer Generation
```

---

## 关键技术决策

### 1. 为什么使用 ChromaDB？

| 特性 | 优势 |
|------|------|
| 持久化 | 服务重启数据不丢失 |
| 内置 HNSW | 快速近似检索 |
| 简单 API | 无需复杂 SQL |
| 元数据过滤 | 支持按 source/category 查询 |

### 2. 为什么双模型架构？

| 组件 | 模型 | 原因 |
|------|------|------|
| 意图识别 | OpenClaw (云端) | 需要强大的理解能力 |
| 代码生成 | Ollama (本地) | 保护代码隐私，减少延迟 |

### 3. 为什么语义分块？

对比整页存储 vs 语义分块：

| 方式 | 问题 | 解决 |
|------|------|------|
| 整页存储 | 页眉/版权信息干扰 | 清理 + 分块 |
| 整页存储 | 内容过长，语义稀释 | 400 char 分块 |
| 语义分块 | 保持上下文连贯 | 段落优先切分 |

### 4. 为什么 SEARCH/REPLACE？

| 方案 | 问题 | SEARCH/REPLACE 优势 |
|------|------|-------------------|
| 全文替换 | 误删风险 | 精确匹配上下文 |
| 行号定位 | 行号变化失效 | 基于内容定位 |
| AST 修改 | 复杂，易出错 | 简单，可验证 |

---

## 配置说明

### 关键环境变量

```bash
# GitHub App (必需)
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY_PATH=
GITHUB_WEBHOOK_SECRET=

# 服务配置
GITHUB_AGENT_PORT=8080
GITHUB_AGENT_HOST=0.0.0.0

# Ollama (本地代码生成)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:30b

# OpenClaw (云端意图识别)
OPENCLAW_URL=http://localhost:3000
OPENCLAW_MODEL=kimi-k2.5

# 知识库
KB_SERVICE_URL=http://localhost:8000
KB_EMBEDDING_MODEL=bge-m3:latest
# 状态目录（知识库和 ChromaDB 统一存储在此目录下）
GITHUB_AGENT_STATEDIR=/home/tj/state

# 同步
KB_GITHUB_SYNC_ENABLED=true
KB_REPO=owner/knowledge-base
```

### 配置文件优先级

```
.env 文件 > 环境变量 > 默认值
```

---

## 扩展阅读

- [KNOWLEDGE_SYNC_DESIGN.md](KNOWLEDGE_SYNC_DESIGN.md) - 知识库同步详细设计
- [METADATA_FORMAT.md](METADATA_FORMAT.md) - 元数据字段规范
- [FEATURES.md](FEATURES.md) - 功能特性说明
