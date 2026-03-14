# GitHub Agent V2

智能 GitHub 自动化助手 - 基于多模型协作的 Issue 自动处理系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 目录

- [项目简介](#-项目简介)
- [系统架构](#-系统架构)
- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [启动指南](#-启动指南)
- [GitHub 知识库同步](#-github-知识库同步)
- [触发模式与确认模式](#-触发模式与确认模式)
- [代码修改优化](#-代码修改优化)
- [意图识别](#-意图识别)
- [调试与日志](#-调试与日志)
- [架构文档](#-架构文档)

---

## 🎯 项目简介

GitHub Agent V2 是一个智能化的 GitHub 自动化系统，能够自动接收和处理 GitHub Issue，根据用户意图执行相应的操作：

- **💬 智能问答** - 自动回答关于代码的问题
- **🔧 代码修复** - 自动分析并修复 Bug
- **📚 知识检索** - 基于 RAG 查询技术文档
- **✅ Issue 跟踪** - 自动关闭已解决的 Issue

### 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **双模型架构** | OpenClaw (云端) 负责意图识别，Ollama (本地) 负责代码生成 |
| 🔒 **安全修改** | 使用 SEARCH/REPLACE 格式精确修改，避免误删 |
| ⚡ **智能触发** | 支持 `smart` 模式（需 `@agent` 触发），避免误操作 |
| 📖 **知识增强** | 集成 RAG 知识库，ChromaDB 持久化存储，支持技术文档查询 |
| 💾 **学习进化** | 自动保存成功案例，同步到知识库仓库，持续学习优化 |
| 🔄 **Issue 跟踪** | 支持自动/手动确认模式，检测"已解决"后自动关闭 Issue |
| 🎯 **智能分析** | 自动分析代码结构、引脚使用、库依赖，精准定位修改点 |
| 📄 **PDF 处理** | 支持 PDF 技术文档自动解析、语义分块、向量化存储 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Agent V2                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │
│  │   GitHub     │────▶│   Webhook    │────▶│    Core      │         │
│  │   Webhook    │     │    Server    │     │  Processor   │         │
│  └──────────────┘     └──────────────┘     └──────┬───────┘         │
│                                                    │                 │
│                           ┌────────────────────────┼────────────────┐│
│                           ▼                        ▼                ││
│  ┌──────────────────────────────────────────────────────────────┐  ││
│  │                      Processing Pipeline                      │  ││
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │  ││
│  │  │   Context    │──▶│   Intent     │──▶│   Decision   │      │  ││
│  │  │   Builder    │   │ Classification│   │   Engine     │      │  ││
│  │  └──────────────┘   └──────────────┘   └──────┬───────┘      │  ││
│  │                                                │              │  ││
│  │                           ┌────────────────────┼────────────┐ │  ││
│  │                           ▼                    ▼            │ │  ││
│  │  ┌────────────────────────────────────────────────────────┐ │ │  ││
│  │  │                    Action Execution                     │ │ │  ││
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │ │ │  ││
│  │  │  │  answer    │  │  modify    │  │  research  │        │ │ │  ││
│  │  │  │  (reply)   │  │  (PR)      │  │  (search)  │        │ │ │  ││
│  │  │  └────────────┘  └────────────┘  └────────────┘        │ │ │  ││
│  │  └────────────────────────────────────────────────────────┘ │ │  ││
│  └──────────────────────────────────────────────────────────────┘  ││
│                           │                                         ││
│                           ▼                                         ││
│  ┌──────────────────────────────────────────────────────────────┐  ││
│  │                     External Services                         │  ││
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │  ││
│  │  │   OpenClaw   │   │   Ollama     │   │  KB Service  │      │  ││
│  │  │  (Intent)    │   │   (Code)     │   │  (Knowledge) │      │  ││
│  │  └──────────────┘   └──────────────┘   └──────────────┘      │  ││
│  └──────────────────────────────────────────────────────────────┘  ││
│                           │                                         ││
│                           ▼                                         ││
│  ┌──────────────────────────────────────────────────────────────┐  ││
│  │                        GitHub API                             │  ││
│  │              (Create Comment / PR / Review)                   │  ││
│  └──────────────────────────────────────────────────────────────┘  ││
│                                                                      ││
└─────────────────────────────────────────────────────────────────────┘│
```

### 模块结构

```
github-agent-v2/
├── webhook/              # Webhook 接收与事件路由
│   └── webhook_server.py
├── core/                 # 核心业务逻辑
│   ├── processor.py      # Issue 处理器
│   ├── context_builder.py
│   ├── state_manager.py
│   └── issue_followup.py
├── cloud_agent/          # 云端意图识别
│   ├── intent_classifier.py
│   ├── openclaw_client.py
│   └── decision_engine.py
├── code_executor/        # 代码生成与执行
│   ├── code_executor.py
│   ├── code_generator.py
│   ├── safe_modifier.py
│   ├── repo_manager.py
│   ├── change_validator.py
│   └── code_analyzer.py
├── knowledge_base/       # 知识库服务
│   ├── kb_service.py     # ChromaDB 向量存储
│   ├── pdf_processor.py  # PDF 解析与分块
│   ├── kb_client.py
│   └── kb_integrator.py
├── github_api/           # GitHub API 封装
│   ├── auth_manager.py
│   └── github_client.py
├── config/               # 配置管理
│   └── settings.py
└── scripts/              # 工具脚本
    ├── start.sh
    ├── kb_query.py
    └── github_repo_watcher.py
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.12+
- Git
- [Ollama](https://ollama.ai/) (本地代码生成)
- [OpenClaw](https://github.com/moonshot-ai/openclaw) (可选，云端意图识别)
- GitHub App (需要配置 Webhook)

### 2. 安装

```bash
# 克隆项目
git clone <repository-url>
cd github-agent-v2

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制模板配置文件
cp .env.example .env
# 编辑配置
nano .env
```

**最少必要配置：**

```bash
# ========== GitHub App 配置（必需） ==========
GITHUB_APP_ID=2994177
GITHUB_PRIVATE_KEY_PATH=/home/tj/.keys/github-app-private-key.pem
GITHUB_WEBHOOK_SECRET=dfrobot

# ========== 服务端口 ==========
GITHUB_AGENT_PORT=8080

# ========== Ollama 配置 ==========
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:30b
```

### 4. 启动服务

```bash
# 方法 1: 使用完整启动脚本（推荐，支持自定义参数）
./scripts/start.sh --port 8080

# 方法 2: 一键启动所有服务
./start_all.sh

# 方法 3: 使用 Python 直接启动
python main.py --port 8080
```

### 5. 配置 GitHub App Webhook

1. 在 GitHub App 设置中，设置 Webhook URL 为 `http://your-server:8080/webhook/github`
2. 设置 Webhook Secret 与 `.env` 中的 `GITHUB_WEBHOOK_SECRET` 一致
3. 订阅事件：`Issues`、`Issue comment`

---

## ⚙️ 配置说明

### 完整环境变量参考

#### 必需配置

| 变量 | 说明 | 获取方式 |
|------|------|---------|
| `GITHUB_APP_ID` | GitHub App ID | GitHub App 设置页面 URL 中的数字 |
| `GITHUB_PRIVATE_KEY_PATH` | 私钥文件路径 | 下载 GitHub App 私钥后保存的路径 |
| `GITHUB_WEBHOOK_SECRET` | Webhook Secret | 创建 GitHub App 时设置的 Webhook Secret |

#### GitHub App 权限要求

| 权限 | 级别 | 用途 |
|------|------|------|
| **Contents** | Read & Write | 推送代码、创建分支 |
| **Issues** | Read & Write | 读取 Issue、创建评论 |
| **Pull requests** | Read & Write | 创建 PR |
| **Metadata** | Read | 读取仓库基本信息 |

#### 触发模式配置

```bash
# Issue 触发模式: auto(所有), smart(需@agent), manual(手动)
GITHUB_AGENT_ISSUE_TRIGGER_MODE=smart

# 评论触发模式: all(所有), smart(需@agent), manual(手动)
GITHUB_AGENT_COMMENT_TRIGGER_MODE=smart
```

#### 确认模式配置

```bash
# 确认模式: auto(自动执行), manual(需用户确认)
AGENT_CONFIRM_MODE=auto

# 自动确认置信度阈值 (0-1)
AGENT_AUTO_CONFIRM_THRESHOLD=0.8
```

#### Issue 跟踪功能配置

```bash
# 是否启用 Issue 跟踪功能
# true:  启用 - 检测用户回复"已解决"等关键词后自动关闭 Issue
# false: 禁用 - 不自动关闭 Issue，仅回复确认消息
AGENT_ISSUE_TRACKING_ENABLED=true
```

#### 知识库服务配置

```bash
# 知识库服务连接地址
KB_SERVICE_URL=http://localhost:8000

# 嵌入模型配置（通过 Ollama）
# 推荐模型：bge-m3:latest (1024维，高精度)，nomic-embed-text:latest (768维，快速)
KB_EMBEDDING_MODEL=bge-m3:latest

# 状态目录配置（所有数据统一存储）
# 知识库存储: ${GITHUB_AGENT_STATEDIR}/knowledge_base/
# ChromaDB 存储: ${GITHUB_AGENT_STATEDIR}/chroma_db/
GITHUB_AGENT_STATEDIR=/home/tj/state

# PDF 处理配置
KB_PDF_WORKERS=6                       # PDF 处理线程数
KB_PDF_PARALLEL_THRESHOLD=3            # 启用多线程的页数阈值
```

---

## 📚 GitHub 知识库同步

### 启用知识库同步

```bash
# .env 配置
KB_GITHUB_SYNC_ENABLED=true
KB_REPO=tangjie133/knowledge-base
KB_BRANCH=main
```

### 手动同步

```bash
# 同步知识库
python scripts/github_repo_watcher.py --sync

# 强制重新同步（忽略 SHA 检查）
python scripts/github_repo_watcher.py --sync --force

# 查看同步状态
python scripts/github_repo_watcher.py --status
```

### 支持的文件格式

| 格式 | 处理方式 | 存储位置 |
|------|---------|---------|
| PDF | PyMuPDF 解析，语义分块 | ChromaDB |
| Markdown | 直接读取 | ChromaDB |
| TXT | 包装为 Markdown | ChromaDB |
| DOCX | python-docx/pandoc 提取 | ChromaDB |

### 查询知识库

```bash
# 查询知识库
python scripts/kb_query.py "BMI160 I2C 地址"

# 返回 5 条结果
python scripts/kb_query.py -k 5 "SD3031 温度读取"

# 查看知识库统计
python scripts/kb_query.py --stats
```

---

## 🎛️ 触发模式与确认模式

### 触发模式

| 模式 | 说明 | 使用场景 |
|------|------|---------|
| `auto` | 所有 Issue/评论都触发 | 私有仓库，完全自动化 |
| `smart` | 需包含 `@agent` 才触发 | 公开仓库，避免误触发 |
| `manual` | 仅手动触发 | 测试环境 |

### 确认模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `auto` | 自动执行代码修改 | 低风险修改，完全自动化 |
| `manual` | 需用户回复确认才执行 | 高风险修改，需人工审核 |

---

## 🔧 代码修改优化

### 安全修改机制

代码修改使用 **SEARCH/REPLACE** 格式，确保精确修改：

```python
### src/main.py
<<<<<<< SEARCH
    def old_function():
        return "old"
=======
    def old_function():
        return "new"
>>>>>>> REPLACE
```

### 代码分析器

自动分析代码结构，识别：
- 引脚定义和使用
- 库依赖关系
- 函数调用链
- 变量作用域

### 成功案例学习

自动保存修复案例到知识库，持续优化：

```bash
# 案例存储位置
knowledge_base/data/cases/
```

---

## 🎯 意图识别

### 意图类型

| 意图 | 说明 | 示例 |
|------|------|------|
| `answer` | 回答技术问题 | "什么是 BMI160?" |
| `modify` | 修改代码 | "修复这个 bug" |
| `research` | 查询知识库 | "查一下 SD3031 的手册" |
| `clarify` | 需要澄清 | "什么意思?" |

### 本地规则备用

当 OpenClaw 不可用时，使用本地关键词规则：

```python
# 修改意图关键词
MODIFY_KEYWORDS = [
    "修复", "修改", "改成", "fix", "change", "update",
    "解决", "报错", "错误", "exception", "error", "bug"
]

# 查询意图关键词
RESEARCH_KEYWORDS = [
    "查询", "查一下", "搜索", "手册", "规格", "datasheet"
]
```

---

## 🐛 调试与日志

### 启动 DEBUG 模式

```bash
export LOG_LEVEL=DEBUG
./scripts/start.sh --port 8080
```

### 查看日志

```bash
# 知识库服务日志
tail -f /tmp/kb_service.log

# 定时同步日志
tail -f /tmp/github_kb_sync.log

# Webhook 日志
tail -f /tmp/github_webhook.log
```

### 健康检查

```bash
# 检查主服务
curl http://localhost:8080/health

# 检查知识库服务
curl http://localhost:8000/health

# 查看知识库统计
curl http://localhost:8000/stats
```

---

## 📖 架构文档

详细架构设计请参见 [ARCHITECTURE.md](ARCHITECTURE.md)，包含：

- 系统分层架构
- 知识库设计
- 数据流图
- 关键技术决策

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件
