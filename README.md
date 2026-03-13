# GitHub Agent V2

智能 GitHub 自动化助手 - 基于多模型协作的 Issue 自动处理系统

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 目录

- [项目简介](#-项目简介)
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
| 📖 **知识增强** | 集成 RAG 知识库，支持技术文档查询，HNSW 加速检索 750x |
| 💾 **学习进化** | 自动保存成功案例，同步到知识库仓库，持续学习优化 |
| 🔄 **Issue 跟踪** | 支持自动/手动确认模式，检测"已解决"后自动关闭 Issue |
| 🎯 **智能分析** | 自动分析代码结构、引脚使用、库依赖，精准定位修改点 |

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
# 方法 1: 一键启动（推荐用于调试，不支持参数）
./start_all.sh

# 方法 2: 使用完整启动脚本（支持自定义参数）
./scripts/start.sh --port 8080

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

启用时，系统会在用户回复"已解决"、"搞定"、"fixed" 等关键词后自动关闭 Issue。禁用时，系统仅回复确认消息，不执行关闭操作。

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
# 知识库服务连接地址（用于连接已有服务）
KB_SERVICE_URL=http://localhost:8000

# 知识库服务监听配置（用于启动服务）
# KB_SERVICE_HOST=0.0.0.0
# KB_SERVICE_PORT=8000

# 嵌入模型配置（通过 Ollama，可选）
# KB_EMBEDDING_MODEL=nomic-embed-text  # 可选: bge-m3, all-minilm 等
# KB_EMBEDDING_HOST=http://localhost:11434

# ChromaDB 向量数据库配置（自动持久化 + 内置 HNSW）
# KB_CHROMA_DIR=./knowledge_base/chroma_db  # 持久化目录（默认）

# PDF 处理配置（多线程并行）
# KB_PDF_WORKERS=8                       # 线程数（默认 CPU/3，24核→8线程）
# KB_PDF_PARALLEL_THRESHOLD=3            # 启用并行阈值（默认 3页）

KB_TIMEOUT=30
```

#### 工作目录配置

```bash
GITHUB_AGENT_WORKDIR=/tmp/github-agent-v2
GITHUB_AGENT_STATEDIR=./state
```

#### 日志配置

```bash
# 日志级别: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# 日志格式（可选，默认使用内置格式）
# LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# 日志文件路径（可选，默认输出到控制台）
# LOG_FILE=/var/log/github-agent-v2/app.log
```

**DEBUG 模式：**

```bash
# 启用详细调试输出
export LOG_LEVEL=DEBUG
./scripts/start.sh --port 8080
```

DEBUG 模式将显示：
- 详细的环境检查信息
- 所有配置变量的值
- 知识库同步的详细过程
- 各组件的初始化详情

#### 安全配置

```bash
MAX_FILE_SIZE=1048576              # 最大文件大小（字节）
MAX_FILES_PER_PR=10                # 单次 PR 最大修改文件数

# 允许修改的文件扩展名（可选，逗号分隔）
# ALLOWED_FILE_EXTENSIONS=.py,.js,.ts,.json,.md,.yml,.yaml,.txt
```

#### 知识库同步配置

```bash
# 启用 GitHub 知识库同步
KB_GITHUB_SYNC_ENABLED=true

# 知识库仓库地址
KB_REPO=tangjie133/knowledge-base
KB_BRANCH=main

# GitHub Token（用于 API 认证）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx

# 自动同步间隔（秒），0 表示不同步
KB_SYNC_INTERVAL=300

# 启用 Webhook 实时同步
KB_WEBHOOK_ENABLED=true
KB_WEBHOOK_PORT=9000
KB_WEBHOOK_SECRET=your_webhook_secret

# 本地知识库路径（可选，默认 ./knowledge_base/data/cases）
# KB_STORAGE_PATH=./knowledge_base/data/cases
```

---

## 🚀 启动指南

### 方法 1: 一键前台启动（推荐用于调试）

```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
./start_all.sh
```

**特点：**
- KB Service 后台运行，日志写入 `kb_service.log`
- 主服务前台运行，日志直接输出到终端
- 按 `Ctrl+C` 停止所有服务
- ⚠️ **注意：此脚本不支持 `--port` 等参数，如需自定义端口请使用方法 2**

### 方法 1.5: 完整功能启动（推荐用于生产）

```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
./scripts/start.sh --port 8080
```

**特点：**
- 完整的启动流程，包括环境检查、依赖安装
- 支持 GitHub 知识库自动同步
- 支持自定义参数：`--host`、`--port`、`--log-level`
- 美观的启动界面和状态摘要

### 方法 2: 分步启动（完全控制）

**终端 1 - 启动知识库服务：**
```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
source venv/bin/activate
python3 -m knowledge_base.kb_service --host 0.0.0.0 --port 8000
```

**终端 2 - 启动主服务：**
```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
source venv/bin/activate
python3 main.py --port 8080
```

### 方法 3: 后台启动 + 日志追踪

```bash
# 启动 KB Service
source venv/bin/activate
python3 -m knowledge_base.kb_service > kb_service.log 2>&1 &

# 等待就绪
sleep 3

# 启动主服务
python3 main.py --port 8080 > main.log 2>&1 &

# 查看进程
echo "服务已启动，PIDs:"
pgrep -f "kb_service\|main.py"
```

**实时查看日志：**
```bash
tail -f kb_service.log main.log
```

### 停止服务

```bash
# 停止所有相关进程
pkill -f "kb_service\|main.py"

# 或者精确停止
kill $(pgrep -f "kb_service")
kill $(pgrep -f "main.py")
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

### 成功案例自动学习

系统自动保存成功的代码修复案例，并同步到知识库仓库，实现持续学习和知识积累。

**自动流程：**
```
代码修改成功 + PR 创建
    ↓
自动保存案例到本地
    ↓
异步推送到知识库仓库
    ↓
案例可用于相似问题检索
```

**配置：**
```bash
# 使用与拉取相同的知识库仓库
KB_REPO=tangjie133/knowledge-base
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx

# 启用自动同步
KB_AUTO_SYNC=true
```

**案例存储结构：**
```
knowledge_base/data/cases/
├── index.json
└── 2026/
    └── 03/
        ├── case_20260312_xxx.json    # 成功案例
        └── case_20260312_yyy.json
```

每个案例包含：
- **Issue 信息** - 问题描述、关键词、语言
- **解决方案** - 修改描述、代码模式、引脚/库信息
- **结果** - PR 状态、用户反馈

**详细文档：** [knowledge_base/USAGE.md](./knowledge_base/USAGE.md)

### 本地知识库路径

同步后的知识库文件存储在以下位置：

```
knowledge_base/
├── chips/              # 芯片数据手册（从 GitHub 同步）
│   ├── SD3031.md
│   └── DS3231.md
├── best_practices/     # 最佳实践文档（从 GitHub 同步）
│   └── guide.md
└── data/               # 本地数据（自动创建）
    ├── cases/          # 成功案例
    └── index.json      # 案例索引
```

**注意：** 同步是单向的（GitHub → 本地），系统会根据文件 SHA 值判断是否需要更新。

### 知识库查询

```bash
# 查看完整状态
python scripts/kb_query.py

# 查询特定内容
python scripts/kb_query.py 'SD3031 芯片规格'

# 查看统计
python scripts/kb_query.py -s

# 直接 API 调用
curl http://localhost:8000/stats
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SD3031", "top_k": 3}'
```

---

## 🎯 触发模式与确认模式

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

## 🔧 代码修改优化

系统通过多项优化提升代码修改的准确性和安全性。

### 智能代码分析 (CodeAnalyzer)

修改前自动分析代码结构，精准定位修改点：

| 分析维度 | 说明 |
|---------|------|
| **关键词提取** | 从 Issue 中提取函数名、引脚、错误信息 |
| **函数依赖** | 分析函数调用关系，避免遗漏关联代码 |
| **Arduino 特定** | 提取引脚使用（A0、D13等）、库依赖、中断配置 |
| **文件选择** | 智能匹配需要修改的文件（准确率 > 90%） |

### 安全修改机制 (SafeCodeModifier)

使用三级匹配策略确保修改精确：

| 匹配级别 | 策略 | 成功率 |
|---------|------|--------|
| **精确匹配** | 完全相同的文本匹配 | 70% |
| **规范化匹配** | 忽略行尾空白差异 | 85% |
| **相似度匹配** | difflib 算法（阈值 0.85） | 90% |

### 修改验证 (ChangeValidator)

修改后多重验证确保代码质量：

- ✅ **语法验证** - Python AST / Arduino 括号匹配
- ✅ **结构验证** - 检查函数/类是否完整保留
- ✅ **Arduino 检查** - setup/loop 存在性、delay() 警告
- ✅ **变化验证** - 确保确实产生了修改

### 调试信息

详细日志帮助排查问题：

```bash
# 查看代码分析日志
grep "\[CodeAnalyzer\]" logs/agent.log

# 查看修改匹配日志
grep "\[SafeModifier\]" logs/agent.log

# 查看验证日志
grep "\[Validator\]" logs/agent.log
```

**详细文档：** [DEBUG_GUIDE.md](./DEBUG_GUIDE.md)

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

## 🔧 调试与日志

### 查看服务状态

```bash
# KB Service 状态
curl http://localhost:8000/health
curl http://localhost:8000/stats

# Ollama 状态
curl http://localhost:11434/api/tags

# 主服务健康检查
curl http://localhost:8080/health
```

### 日志级别

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| `INFO` | 正常流程信息 | `✓ OpenClaw 服务就绪` |
| `WARNING` | 非致命错误 | `! OpenClaw 不可用，使用回退` |
| `ERROR` | 严重错误 | `✗ KB 查询失败` |
| `DEBUG` | 详细调试信息 | 显示配置值、执行详情 |

### 启用 DEBUG 模式

**方式 1：环境变量**
```bash
export LOG_LEVEL=DEBUG
./scripts/start.sh --port 8080
```

**方式 2：命令行前缀**
```bash
LOG_LEVEL=DEBUG ./scripts/start.sh --port 8080
```

**DEBUG 模式输出示例：**
```
▶ 步骤 1/6: 检查环境依赖
[DEBUG] 项目目录: /home/user/github-agent-v2
[DEBUG] 虚拟环境: /home/user/github-agent-v2/venv
[DEBUG] Python 路径: /home/user/github-agent-v2/venv/bin/python3
[✓] Python 版本: 3.12.0
...
▶ 步骤 2/6: 检查配置
[DEBUG] GITHUB_APP_ID: 2994177
[DEBUG] GITHUB_PRIVATE_KEY_PATH: /path/to/key.pem
[DEBUG] LOG_LEVEL: DEBUG
```

### 彩色日志输出

系统支持彩色日志输出，便于快速识别信息类型：
- 🔵 **蓝色** - INFO 级别信息
- 🟡 **黄色** - WARNING 级别警告
- 🔴 **红色** - ERROR 级别错误
- 🟣 **紫色** - DEBUG 级别调试信息
- 🟢 **绿色** - 成功状态
- ⚪ **灰色** - 状态详情

### 常见日志模式

**意图分类成功：**
```
🎯 [Intent Classification] Starting for issue #21
✅ [Intent Classification] SUCCESS via OpenClaw: research (confidence: 0.95)
```

**意图分类失败（本地规则回退）：**
```
⚠️  [Intent Classification] OpenClaw FAILED: session file locked
🔄 [Intent Classification] Switching to LOCAL RULES fallback
✅ [Intent Classification] SUCCESS via LOCAL RULES: research (confidence: 0.70)
```

### 测试

```bash
# 运行端到端测试
python tests/test_e2e.py

# 模块导入测试
python -c "from core.models import GitHubEvent; print('OK')"

# 健康检查
curl http://localhost:8080/health
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
│   ├── state_manager.py      # 状态管理
│   └── issue_followup.py     # Issue 跟踪
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
│   ├── kb_service.py         # 知识库服务
│   ├── success_case_store.py # 成功案例存储
│   └── knowledge_sync.py     # 知识库同步
├── code_executor/             # 代码执行层 (Ollama)
│   ├── code_analyzer.py      # 代码分析器
│   ├── code_generator.py     # 代码生成器
│   ├── safe_modifier.py      # 安全代码修改
│   ├── repo_manager.py       # Git 仓库管理
│   ├── change_validator.py   # 变更验证
│   └── code_executor.py      # 执行器主类
├── utils/                     # 工具模块
│   ├── retry.py              # 重试机制
│   └── errors.py             # 错误定义
├── tests/                     # 测试框架
├── scripts/                   # 部署脚本
│   ├── start.sh              # 生产启动脚本（推荐）
│   ├── start_all.sh          # 快速调试启动
│   ├── deploy.sh             # 部署脚本
│   └── github_repo_watcher.py # GitHub 同步工具
├── webhook/                   # Webhook 服务
│   └── webhook_server.py     # Flask 服务器
├── knowledge_base/            # 本地知识库存储（运行时创建）
│   ├── chips/                # 芯片文档（从 GitHub 同步）
│   ├── best_practices/       # 最佳实践文档（从 GitHub 同步）
│   └── data/                 # 本地数据（成功案例等）
├── main.py                    # 主入口
├── requirements.txt           # 依赖
├── .env.example              # 环境变量模板
├── README.md                 # 项目文档
├── ARCHITECTURE.md           # 架构文档
├── FEATURES.md               # 功能汇总
├── DEBUG_GUIDE.md            # 调试指南
└── GITHUB_KB_QUICKSTART.md   # 知识库快速上手
```

---

## 📖 架构文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) - 系统架构设计文档
- [GITHUB_KB_QUICKSTART.md](./GITHUB_KB_QUICKSTART.md) - 知识库快速上手指南

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
