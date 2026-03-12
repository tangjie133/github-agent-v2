# GitHub Agent V2

智能 GitHub 自动化助手 - 基于多模型协作的 Issue 自动处理系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 目录

- [项目简介](#-项目简介)
- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [GitHub 知识库同步](#-github-知识库同步推荐)
- [触发模式与确认模式](#️-触发模式与确认模式)
- [意图识别](#-意图识别)
- [代码修改流程](#-代码修改流程)
- [测试与部署](#-测试)
- [架构文档](#-架构文档)

---

## 🎯 项目简介

GitHub Agent V2 是一个智能化的 GitHub 自动化系统，能够自动接收和处理 GitHub Issue，根据用户意图执行相应的操作：

- **💬 智能问答** - 自动回答关于代码的问题
- **🔧 代码修复** - 自动分析并修复 Bug
- **📚 知识检索** - 基于 RAG 查询技术文档
- **✅ 代码审查** - 自动创建 PR 并等待确认

### 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **双模型架构** | OpenClaw (云端) 负责意图识别，Ollama (本地) 负责代码生成 |
| 🔒 **安全修改** | 使用 SEARCH/REPLACE 格式精确修改，避免误删 |
| ⚡ **智能触发** | 支持 `smart` 模式（需 `@agent` 触发），避免误操作 |
| 📖 **知识增强** | 集成 RAG 知识库，支持技术文档查询 |
| 🔄 **自动确认** | 支持自动/手动确认模式，低置信度时请求人工确认 |

### 系统架构

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
# 一键启动（推荐）
./scripts/start.sh --port 8080

# 或使用 Python 直接启动
python main.py --port 8080
```

启动脚本会自动：
1. 检查依赖
2. 检查环境变量
3. 同步 GitHub 知识库（如果启用）
4. 启动 KB Service
5. 启动后台监控（定时+Webhook）
6. 启动主服务

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

#### Webhook 配置

```bash
GITHUB_AGENT_HOST=0.0.0.0          # 监听地址
GITHUB_AGENT_PORT=8080             # 服务端口
```

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

#### OpenClaw 配置（可选）

```bash
OPENCLAW_URL=http://localhost:3000
OPENCLAW_MODEL=kimi-k2.5
OPENCLAW_TIMEOUT=60
```

#### Ollama 配置

```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_TIMEOUT=300
```

#### 知识库服务配置

```bash
KB_SERVICE_URL=http://localhost:8000
KB_TIMEOUT=30
```

#### 工作目录配置

```bash
GITHUB_AGENT_WORKDIR=/tmp/github-agent-v2
GITHUB_AGENT_STATEDIR=./state
```

#### 日志配置

```bash
LOG_LEVEL=INFO
# LOG_FILE=/var/log/github-agent-v2/app.log
```

#### 安全配置

```bash
MAX_FILE_SIZE=1048576              # 最大文件大小（字节）
MAX_FILES_PER_PR=10                # 单次 PR 最大修改文件数
```

#### 重试配置

```bash
MAX_RETRIES=3
RETRY_DELAY=1.0
RETRY_BACKOFF=2.0
```

---

## 📚 GitHub 知识库同步（推荐）

将数据手册存入 GitHub 仓库，系统自动同步到知识库。

### 快速配置

```bash
# 启用 GitHub 仓库同步
KB_GITHUB_SYNC_ENABLED=true
KB_REPO=tangjie133/knowledge-base
KB_BRANCH=main

# 定时同步间隔（秒），0 表示仅使用 Webhook
KB_SYNC_INTERVAL=300

# Webhook 实时同步（可选）
KB_WEBHOOK_ENABLED=true
KB_WEBHOOK_PORT=9000
KB_WEBHOOK_SECRET=your_webhook_secret
```

### Webhook 配置

如果使用 Webhook 同步，需要在 GitHub 仓库设置：

1. 进入仓库 Settings → Webhooks → Add webhook
2. Payload URL: `http://your-server:9000/webhook`
3. Secret: 与 `KB_WEBHOOK_SECRET` 一致
4. Events: `Just the push event`

### 支持格式

- `.md` - Markdown 文件（直接使用）
- `.txt` - 文本文件（自动转换）
- `.pdf` - PDF 文档（提取文本后转换）
- `.docx` - Word 文档（转换后使用）

**详细文档：** [GITHUB_KB_QUICKSTART.md](./GITHUB_KB_QUICKSTART.md)

---

## ⚡️ 触发模式与确认模式

### 触发模式

| 模式 | Issue 触发 | 评论触发 | 说明 |
|------|-----------|---------|------|
| `auto` | 所有 Issue | 所有评论 | 自动处理所有事件 |
| `smart` | 含 `@agent` | 含 `@agent` | 仅处理显式提及的事件 |
| `manual` | 手动 | 手动 | 需要人工触发 |

```bash
# 配置示例
GITHUB_AGENT_ISSUE_TRIGGER_MODE=smart
GITHUB_AGENT_COMMENT_TRIGGER_MODE=smart
```

**Smart 模式使用示例：**

```
@agent 请修复这个 bug
@agent 解释一下这段代码
```

### 确认模式

| 模式 | 说明 |
|------|------|
| `auto` | 高置信度时自动执行，低置信度时请求确认 |
| `manual` | 所有操作都需要用户确认 |

```bash
AGENT_CONFIRM_MODE=auto
AGENT_AUTO_CONFIRM_THRESHOLD=0.8  # 自动确认阈值
```

---

## 🧠 意图识别

系统自动识别用户意图，分为四类：

| 意图 | 触发词 | 处理方式 |
|------|--------|---------|
| **answer** | "为什么"、"依据"、"解释" | 直接回复解释 |
| **modify** | "修复"、"修改"、"改成" | 分析并修改代码，创建 PR |
| **research** | "如何"、"查询"、"资料" | 查询知识库后回复 |
| **clarify** | 信息不足、模糊不清 | 请求用户补充信息 |

### 处理流程

```
用户提问
    ↓
[OpenClaw] 意图识别
    ↓
┌────────────────────────────────────────┐
│  answer  │  modify  │  research  │ clarify  │
└────────────────────────────────────────┘
    ↓           ↓            ↓            ↓
 直接回复    代码修改      知识查询      请求澄清
  (Comment)   (Create PR)   (Comment)    (Comment)
```

---

## 🔧 代码修改流程

当意图为 `modify` 时，系统执行以下流程：

```
1. 克隆仓库
   git clone <repo>

2. 创建分支
   git checkout -b agent-fix-{issue-number}

3. AI 分析
   - 识别需要修改的文件
   - 生成 SEARCH/REPLACE 修改方案

4. 安全修改
   - 使用精确匹配替换
   - 验证语法正确性

5. 提交推送
   git add -A
   git commit -m "fix: ..."
   git push origin agent-fix-{issue-number}

6. 创建 PR
   - 自动填写 PR 描述
   - 关联原 Issue

7. 回复用户
   - 在 Issue 中回复 PR 链接
   - 说明修改内容
```

---

## 🧪 测试

```bash
# 运行端到端测试
python tests/test_e2e.py

# 模块导入测试
python -c "from core.models import GitHubEvent; print('OK')"

# 健康检查
curl http://localhost:8080/health
```

---

## 📡 API 接口

### Webhook 接收

```http
POST /webhook/github
X-GitHub-Event: issues
X-Hub-Signature-256: sha256=...

{
  "action": "opened",
  "issue": {...},
  "repository": {...}
}
```

### 健康检查

```http
GET /health

{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "ollama": true,
    "openclaw": false,
    "kb_service": false
  }
}
```

---

## 🚢 部署

### 使用 systemd (推荐)

```bash
# 运行部署脚本
sudo ./scripts/deploy.sh

# 管理服务
sudo systemctl start github-agent-v2
sudo systemctl status github-agent-v2
sudo journalctl -u github-agent-v2 -f
```

### 日志位置

```bash
# 查看实时日志
sudo journalctl -u github-agent-v2 -f

# 查看最近 100 行
sudo journalctl -u github-agent-v2 -n 100
```

---

## 📁 项目结构

```
github-agent-v2/
├── config/                    # 配置管理
│   ├── settings.py           # 统一配置 (Pydantic)
│   └── logging_config.py     # 结构化日志
├── core/                      # 核心层
│   ├── models.py             # 数据模型
│   ├── processor.py          # 主处理器
│   ├── context_builder.py    # 上下文构建
│   └── state_manager.py      # 状态管理
├── github_api/                # GitHub API 封装
│   ├── github_client.py      # API 客户端
│   └── auth_manager.py       # 认证管理 (JWT)
├── cloud_agent/               # 云端意图识别 (OpenClaw)
│   ├── openclaw_client.py    # OpenClaw 客户端
│   ├── intent_classifier.py  # 意图分类器
│   └── decision_engine.py    # 决策引擎
├── knowledge_base/            # 知识库 (RAG)
│   ├── kb_client.py          # KB Service 客户端
│   ├── kb_integrator.py      # 知识库集成器
│   ├── local_kb.py           # 本地知识库
│   └── kb_service.py         # 知识库服务
├── code_executor/             # 代码执行层 (Ollama)
│   ├── code_generator.py     # 代码生成器
│   ├── safe_modifier.py      # 安全代码修改
│   ├── repo_manager.py       # Git 仓库管理
│   ├── change_validator.py   # 变更验证
│   └── code_executor.py      # 执行器主类
├── utils/                     # 工具模块
│   ├── retry.py              # 重试机制
│   └── errors.py             # 错误定义
├── tests/                     # 测试框架
│   ├── test_e2e.py           # 端到端测试
│   ├── test_config.py        # 配置测试
│   └── test_utils.py         # 工具测试
├── scripts/                   # 部署脚本
│   ├── start.sh              # 启动脚本
│   ├── deploy.sh             # 部署脚本
│   ├── github_repo_watcher.py # GitHub 同步
│   ├── github_webhook_server.py # Webhook 接收
│   └── setup_github_kb.sh    # 配置向导
├── webhook/                   # Webhook 服务
│   └── webhook_server.py     # Flask 服务器
├── main.py                    # 主入口
├── requirements.txt           # 依赖
└── .env.example              # 环境变量模板
```

---

## 📖 架构文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 系统架构设计文档
- [GITHUB_KB_QUICKSTART.md](./GITHUB_KB_QUICKSTART.md) - 知识库快速上手
- [PROGRESS.md](./PROGRESS.md) - 开发进度记录

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [OpenClaw](https://github.com/moonshot-ai/openclaw) - 云端意图识别
- [Ollama](https://ollama.ai/) - 本地大模型运行
- [LangChain](https://python.langchain.com/) - RAG 知识库参考
