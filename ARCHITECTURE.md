# GitHub Agent V2 - 系统架构设计

本文档详细描述 GitHub Agent V2 的系统架构、设计原则和关键技术决策。

## 📋 目录

1. [架构总览](#架构总览)
2. [设计原则](#设计原则)
3. [分层架构](#分层架构)
4. [数据流](#数据流)
5. [关键技术决策](#关键技术决策)
6. [扩展性设计](#扩展性设计)
7. [安全设计](#安全设计)

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
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 4: Core Layer (Processor)                           │ │
│  │  - 业务流程编排                                            │ │
│  │  - 状态管理                                                │ │
│  │  - 错误处理                                                │ │
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
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Layer 1: Infrastructure Layer                             │ │
│  │  - 配置管理                                                │ │
│  │  - 日志记录                                                │ │
│  │  - 工具函数                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 设计原则

### 1. 单一职责原则 (SRP)

每个模块只负责一个明确的职责：

- `webhook/` - 只处理 HTTP 请求和事件路由
- `cloud_agent/` - 只负责意图识别
- `code_executor/` - 只负责代码生成和执行
- `github_api/` - 只负责与 GitHub API 交互

### 2. 依赖倒置原则 (DIP)

高层模块不依赖低层模块，两者都依赖抽象：

```python
# 好的设计：依赖抽象接口
class IssueProcessor:
    def __init__(self, github_client: GitHubClientInterface, ...):
        self.github = github_client

# 避免：直接依赖具体实现
class IssueProcessor:
    def __init__(self):
        self.github = ConcreteGitHubClient()  # ❌
```

### 3. 开闭原则 (OCP)

对扩展开放，对修改关闭：

- 新增意图类型只需扩展 `IntentType`，无需修改核心处理器
- 新增 LLM 提供商只需实现相应客户端，无需修改业务逻辑

### 4. 故障隔离

每个外部服务都可能故障，设计时考虑降级方案：

```
OpenClaw 不可用 → 使用默认意图 (modify)
KB Service 不可用 → 跳过知识库查询
Ollama 不可用 → 返回错误，不执行代码修改
```

---

## 分层架构

### Layer 1: 基础设施层 (Infrastructure)

**职责：** 提供基础服务，与业务逻辑无关

| 模块 | 职责 |
|------|------|
| `config/` | 配置管理、环境变量、配置验证 |
| `utils/` | 重试机制、错误定义、通用工具 |

**关键设计：**

```python
# config/settings.py - Pydantic 配置验证
class Settings(BaseSettings):
    github_agent_port: int = 8080
    agent_confirm_mode: str = "auto"
    
    @validator('agent_confirm_mode')
    def validate_mode(cls, v):
        if v not in ['auto', 'manual']:
            raise ValueError('Invalid mode')
        return v
```

### Layer 2: 服务层 (Service)

**职责：** 封装外部服务交互

| 模块 | 职责 | 设计要点 |
|------|------|---------|
| `github_api/github_client.py` | GitHub REST API 调用 | Token 自动刷新、错误处理 |
| `github_api/auth_manager.py` | JWT 认证 | 私钥缓存、Token 生命周期管理 |

**认证流程：**

```
Webhook 请求
    ↓
提取 Installation ID
    ↓
AuthManager.get_token(installation_id)
    ├─ 检查缓存的 Token
    ├─ 如果过期，使用私钥生成新 JWT
    └─ 使用 JWT 换取 Installation Token
    ↓
返回 Token 给 GitHubClient 使用
```

### Layer 3: 智能层 (Intelligence)

**职责：** AI/ML 相关功能

#### 3.1 意图识别 (Cloud Agent)

**职责：** 理解用户意图

```python
# cloud_agent/intent_classifier.py
class IntentClassifier:
    def classify(self, context: IssueContext) -> IntentResult:
        # 1. 构建分类提示词
        prompt = self._build_prompt(context)
        
        # 2. 调用 OpenClaw
        response = self.openclaw.generate(prompt)
        
        # 3. 解析响应
        return IntentResult(
            intent=IntentType(response["intent"]),
            confidence=response["confidence"],
            reasoning=response["reasoning"]
        )
```

**四种意图类型：**

| 意图 | 说明 | 置信度阈值 |
|------|------|-----------|
| `answer` | 用户询问解释 | > 0.7 |
| `modify` | 用户要求修改代码 | > 0.8 |
| `research` | 需要查询资料 | > 0.7 |
| `clarify` | 需要澄清 | 任意 |

#### 3.2 知识库 (Knowledge Base)

**职责：** RAG 检索增强

```python
# knowledge_base/kb_integrator.py
class KBIntegrator:
    def enrich_context(self, context: IssueContext) -> str:
        # 1. 从 Issue 提取关键词
        keywords = self._extract_keywords(context)
        
        # 2. 查询知识库
        results = self.kb_client.query(keywords)
        
        # 3. 整合到上下文
        return self._merge_context(context, results)
```

##### 3.2.1 GitHub 知识库同步

**职责：** 从 GitHub 仓库自动同步数据手册到本地知识库

**架构设计：**

```
┌─────────────────────────────────────────────────────────────────┐
│                  GitHub KB Sync Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐      ┌──────────────────┐      ┌─────────┐│
│  │  GitHub Repo    │      │  KB Sync Tools   │      │ KB Svc  ││
│  │                 │      │                  │      │         ││
│  │  chips/         │─────▶│  Repo Watcher    │─────▶│ Vector  ││
│  │  ├── SD3031.pdf │ pull │  (Poll/Webhook)  │      │ Store   ││
│  │  └── DS3231.md  │      │                  │      │         ││
│  │                 │      │  File Converter  │      │ Embed   ││
│  │  best_practices/│─────▶│  (.pdf→.md)      │─────▶│ (Ollama)││
│  │  └── guide.md   │      │                  │      │         ││
│  └─────────────────┘      └──────────────────┘      └─────────┘│
│           │                                               ▲     │
│           │                    ┌──────────────┐          │     │
│           └────────────────────│  /reload API │──────────┘     │
│              (Push webhook)    │  (Hot reload)│                │
│                                └──────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

**组件说明：**

| 组件 | 文件 | 职责 |
|------|------|------|
| Repo Watcher | `github_repo_watcher.py` | 轮询 GitHub API 检查更新 |
| Webhook Server | `github_webhook_server.py` | 接收 GitHub Push 事件 |
| File Converter | `github_repo_watcher.py` | PDF/TXT/DOCX → Markdown |
| KB Service | `kb_service.py` | 向量嵌入与检索 |

**同步流程：**

```
1. 检测更新 (两种方式)
   ├── 定时轮询: 每 5 分钟检查一次
   └── Webhook: 实时接收 Push 事件

2. 下载文件
   └── 从 GitHub Raw 下载到 /tmp/

3. 格式转换
   ├── .md  → 直接使用
   ├── .txt → 包装为 Markdown
   ├── .pdf → pdftotext 提取
   └── .docx → pandoc 转换

4. 保存到本地
   └── knowledge_base/chips/ or best_practices/

5. 向量嵌入 (KB Service)
   ├── 分割文本
   ├── nomic-embed-text 生成向量
   └── 存入 SimpleVectorStore

6. 热更新 (可选)
   └── POST /reload 重新加载向量库
```

**启动顺序：**

```python
# scripts/start.sh
def startup():
    # 步骤1: 同步 GitHub 文件到本地（阻塞）
    sync_github_kb_if_enabled()
    
    # 步骤2: 启动 KB Service（加载向量库）
    start_kb_service()
    
    # 步骤3: 启动后台监控（非阻塞）
    start_github_kb_daemon_if_enabled()
    # - 定时同步（轮询）
    # - Webhook 服务器（实时）
```

**配置项：**

```bash
KB_GITHUB_SYNC_ENABLED=true      # 启用同步
KB_REPO=owner/knowledge-base     # 仓库地址
KB_BRANCH=main                   # 分支
KB_SYNC_INTERVAL=300             # 轮询间隔(秒)
KB_WEBHOOK_ENABLED=true          # 启用 Webhook
KB_WEBHOOK_PORT=9000             # Webhook 端口
```

#### 3.3 代码执行 (Code Executor)

**职责：** 安全地生成和执行代码修改

```python
# code_executor/code_executor.py
class CodeExecutor:
    def execute_task(self, task) -> ExecutionResult:
        # 1. 克隆仓库
        repo_path = self.repo_manager.clone(url)
        
        # 2. 创建分支
        self.repo_manager.create_branch(branch_name)
        
        # 3. 生成修改
        changes = self.code_generator.generate(instruction)
        
        # 4. 安全应用
        self.safe_modifier.apply(changes)
        
        # 5. 验证
        self.validator.validate(changes)
        
        # 6. 提交推送
        self.repo_manager.commit_and_push(message)
```

**安全修改机制：**

```
传统方式 (危险):
AI 生成完整文件 → 直接覆盖原文件 → 可能丢失未提及的代码

安全方式 (SEARCH/REPLACE):
AI 生成 SEARCH/REPLACE 块 → 精确匹配替换 → 只修改指定部分
```

### Layer 4: 核心层 (Core)

**职责：** 业务流程编排

```python
# core/processor.py
class IssueProcessor:
    def process_event(self, event: GitHubEvent) -> ProcessingResult:
        # 1. 构建上下文
        context = self.context_builder.build(event)
        
        # 2. 意图识别
        intent = self.cloud_agent.classify(context)
        
        # 3. 决策制定
        plan = self.decision_engine.make_plan(context, intent)
        
        # 4. 执行动作
        if plan.requires_confirmation:
            return self._request_confirmation(context, plan)
        
        return self._execute_plan(context, plan)
```

### Layer 5: 表现层 (Presentation)

**职责：** 接收外部请求

```python
# webhook/webhook_server.py
@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    # 1. 验证签名
    if not verify_signature(request):
        return "Invalid signature", 401
    
    # 2. 解析事件
    event = parse_event(request)
    
    # 3. 异步处理
    threading.Thread(target=processor.process_event, args=(event,)).start()
    
    return "OK", 200
```

---

## 数据流

### 完整处理流程

```
┌─────────────┐
│ GitHub      │ Issue/Comment 事件
│ Webhook     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Webhook     │ 1. 验证签名
│ Server      │ 2. 解析事件
│             │ 3. 保存到文件
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Core        │ 4. 构建上下文
│ Processor   │ 5. 检查触发模式
│             │ 6. 调用意图识别
└──────┬──────┘
       │
       ├───────────────────────────────────────────┐
       │                                           │
       ▼                                           ▼
┌─────────────┐                           ┌─────────────┐
│ Cloud Agent │                           │ Knowledge   │
│ (OpenClaw)  │                           │ Base        │
│             │                           │ (Optional)  │
│ Intent      │                           │             │
│ Classification│                         │ Query       │
└──────┬──────┘                           └─────────────┘
       │
       ▼
┌─────────────┐
│ Decision    │ 7. 制定行动计划
│ Engine      │    - 确认模式
│             │    - 复杂度评估
└──────┬──────┘
       │
       ├──────────┬──────────┬──────────┐
       │          │          │          │
       ▼          ▼          ▼          ▼
   ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
   │answer │ │modify │ │research│ │clarify│
   │       │ │       │ │       │ │       │
   │Reply  │ │Create │ │Search │ │Ask    │
   │Comment│ │PR     │ │KB     │ │Question│
   └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
       │         │         │         │
       └─────────┴────┬────┴─────────┘
                      │
                      ▼
              ┌─────────────┐
              │ GitHub API  │ 8. 发送响应
              │             │    - Create comment
              │             │    - Create PR
              └─────────────┘
```

---

## 关键技术决策

### 1. 双模型架构

**决策：** 使用两个不同的模型分别处理意图识别和代码生成

| 任务 | 模型 | 部署位置 | 原因 |
|------|------|---------|------|
| 意图识别 | kimi-k2.5 (via OpenClaw) | 云端 | 需要强大的推理能力，不涉及敏感代码 |
| 代码生成 | qwen3-coder:30b (via Ollama) | 本地 | 代码不出境，保证安全 |

**好处：**
- 云端模型可快速迭代更新
- 本地代码生成保证隐私
- 可独立扩展和优化

### 2. SEARCH/REPLACE 安全修改

**决策：** 不使用完整文件替换，而是使用 SEARCH/REPLACE 格式

```python
# AI 生成
SEARCH:
```
def old_function():
    return 1
```
REPLACE:
```
def old_function():
    return 2
```

# 系统执行
if SEARCH in original_content:
    new_content = original_content.replace(SEARCH, REPLACE, 1)
else:
    raise Error("无法找到匹配文本，拒绝修改")
```

**好处：**
- 精确修改，不误删
- 可验证，不匹配时拒绝执行
- 便于人工审查

### 3. 异步处理

**决策：** Webhook 接收后立即返回，后台异步处理

```python
@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    event = parse_event(request)
    # 后台处理，不阻塞响应
    threading.Thread(target=process_async, args=(event,)).start()
    return "OK", 200  # 立即返回
```

**好处：**
- GitHub 不会超时重试
- 可以处理耗时操作（代码生成）
- 提高响应速度

### 4. 状态持久化

**决策：** 使用本地 JSON 文件保存 Issue 状态

```python
# core/state_manager.py
class StateManager:
    def save_state(self, state: IssueState):
        file_path = self.state_dir / f"{state.issue_number}.json"
        with open(file_path, 'w') as f:
            json.dump(state.to_dict(), f)
```

**好处：**
- 简单，无需外部数据库
- 易于调试和审计
- 可手动修改状态

---

## 扩展性设计

### 1. 新增意图类型

```python
# 1. 在 IntentType 中添加新类型
class IntentType(Enum):
    ANSWER = "answer"
    MODIFY = "modify"
    RESEARCH = "research"
    CLARIFY = "clarify"
    NEW_TYPE = "new_type"  # 新增

# 2. 在 Processor 中添加处理器
def _handle_new_type_intent(self, ...):
    # 实现处理逻辑
    pass

# 3. 更新决策引擎
# 无需修改，自动支持
```

### 2. 新增 LLM 提供商

```python
# 实现新的客户端
class NewLLMClient:
    def generate(self, prompt: str) -> str:
        # 调用新 LLM API
        pass
    
    def health_check(self) -> bool:
        # 健康检查
        pass

# 在配置中切换
LLM_PROVIDER=new_llm
```

### 3. 新增触发模式

```python
# 在 TriggerMode 中添加
class TriggerMode(Enum):
    AUTO = "auto"
    SMART = "smart"
    MANUAL = "manual"
    CUSTOM = "custom"  # 新增

# 实现自定义逻辑
def _should_process_custom(self, event):
    # 自定义触发逻辑
    pass
```

### 4. 新增知识库数据源

```python
# 1. 实现新的数据源同步器
class NewKBSource:
    def sync(self) -> List[Document]:
        # 从新的数据源拉取文档
        pass
    
    def watch(self, callback):
        # 监控变更
        pass

# 2. 注册到启动流程
# scripts/start.sh
start_kb_sync() {
    # 现有的 GitHub 同步
    sync_github_kb_if_enabled
    
    # 新增数据源
    sync_new_source_kb_if_enabled
}
```

**内置数据源：**
- GitHub 仓库同步（`github_repo_watcher.py`）
- 本地文件夹监控（`auto_kb_loader.py`）

**可扩展：**
- GitLab 仓库
- S3 存储桶
- 企业内部 Wiki
- Confluence

---

## 安全设计

### 1. Webhook 签名验证

```python
def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 2. 代码修改安全

| 安全措施 | 说明 |
|---------|------|
| SEARCH/REPLACE | 精确匹配，不匹配时拒绝 |
| 语法验证 | 修改后验证 Python/JSON 语法 |
| 文件大小限制 | 超过限制拒绝处理 |
| 扩展名白名单 | 只允许修改指定类型文件 |
| 最大文件数 | 单个 PR 限制修改文件数量 |

### 3. 权限控制

- 使用 GitHub App 最小权限原则
- 只请求必要的权限 (Issues, Pull requests)
- Token 短期有效（1小时）

### 4. 敏感信息保护

```python
# 日志中隐藏敏感信息
def mask_sensitive(data: dict) -> dict:
    masked = data.copy()
    for key in ['token', 'secret', 'key']:
        if key in masked:
            masked[key] = '***'
    return masked
```

---

## 性能考虑

### 1. 连接池

```python
# github_api/github_client.py
class GitHubClient:
    def __init__(self):
        self.session = requests.Session()  # 复用连接
```

### 2. 缓存

```python
# github_api/auth_manager.py
class GitHubAuthManager:
    def __init__(self):
        self._token_cache = {}  # Token 缓存
        self._jwt_cache = None  # JWT 缓存
```

### 3. 异步处理

- Webhook 接收后立即返回
- 耗时操作（代码生成）在后台执行
- 支持并发处理多个 Issue

---

## 监控与可观测性

### 1. 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 开发调试，详细流程信息 |
| INFO | 正常流程，关键节点信息 |
| WARNING | 降级处理，非致命错误 |
| ERROR | 处理失败，需要人工介入 |

### 2. 关键指标

```python
# 可收集的指标
- webhook_received_total      # Webhook 接收总数
- intent_classification_duration_seconds  # 意图识别耗时
- code_generation_duration_seconds        # 代码生成耗时
- pr_created_total            # PR 创建数
- execution_failed_total      # 执行失败数
```

---

## 总结

GitHub Agent V2 的架构设计遵循以下核心理念：

1. **分层清晰** - 每层职责单一，便于维护和测试
2. **松耦合** - 模块间通过接口交互，可独立演进
3. **容错性** - 每个外部依赖都有降级方案
4. **可扩展** - 易于添加新功能和新集成
5. **安全性** - 多层安全机制保护代码和数据
