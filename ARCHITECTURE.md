# GitHub Agent V2 - 系统架构设计

本文档详细描述 GitHub Agent V2 的系统架构、设计原则和关键技术决策。

## 📋 目录

1. [架构总览](#架构总览)
2. [设计原则](#设计原则)
3. [分层架构](#分层架构)
4. [数据流](#数据流)
5. [关键技术决策](#关键技术决策)
6. [安全设计](#安全设计)

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
OpenClaw 不可用 → 使用本地规则分类
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

**四种意图类型：**

| 意图 | 说明 | 置信度阈值 |
|------|------|-----------|
| `answer` | 用户询问解释 | > 0.7 |
| `modify` | 用户要求修改代码 | > 0.8 |
| `research` | 需要查询资料 | > 0.7 |
| `clarify` | 需要澄清 | 任意 |

#### 3.2 知识库 (Knowledge Base)

**职责：** RAG 检索增强

**GitHub 知识库同步架构：**

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────┐
│  GitHub Repo    │      │  KB Sync Tools   │      │ KB Svc  │
│                 │      │                  │      │         │
│  chips/         │─────▶│  Repo Watcher    │─────▶│ Vector  │
│  ├── SD3031.pdf │ pull │  (Poll/Webhook)  │      │ Store   │
│  └── DS3231.md  │      │                  │      │         │
│                 │      │  File Converter  │      │ Embed   │
│  best_practices/│─────▶│  (.pdf→.md)      │─────▶│ (Ollama)│
│  └── guide.md   │      │                  │      │         │
└─────────────────┘      └──────────────────┘      └─────────┘
```

**同步流程：**
1. 检测更新（轮询/Webhook）
2. 下载文件到本地
3. 格式转换（PDF/TXT/DOCX → Markdown）
4. 向量嵌入（nomic-embed-text）
5. 加载到内存向量库

#### 3.3 代码执行 (Code Executor)

**职责：** 安全地生成和执行代码修改

```python
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
class IssueProcessor:
    def process_event(self, event: GitHubEvent) -> ProcessingResult:
        # 1. 构建上下文
        context = self.context_builder.build(event)
        
        # 2. 意图识别
        intent = self.cloud_agent.classify(context)
        
        # 3. 检查关闭指令（如"已解决"）
        if self._is_close_request(context):
            return self._close_issue(...)
        
        # 4. 执行对应处理
        if intent == IntentType.MODIFY:
            return self._handle_modify(...)
        elif intent == IntentType.RESEARCH:
            return self._handle_research(...)
        # ...
```

### Layer 5: 表现层 (Presentation)

**职责：** 接收外部请求

```python
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
│             │ 3. 防重复检查
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Core        │ 4. 构建上下文
│ Processor   │ 5. 检查触发模式
│             │ 6. 检查关闭指令
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
│             │    - Issue 跟踪
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
              │             │    - Close issue
              └─────────────┘
```

---

## 关键技术决策

### 1. 双模型架构

| 任务 | 模型 | 部署位置 | 原因 |
|------|------|---------|------|
| 意图识别 | kimi-k2.5 (via OpenClaw) | 云端 | 需要强大的推理能力，不涉及敏感代码 |
| 代码生成 | qwen3-coder:30b (via Ollama) | 本地 | 代码不出境，保证安全 |

### 2. SEARCH/REPLACE 安全修改

**好处：**
- 精确修改，不误删
- 可验证，不匹配时拒绝执行
- 便于人工审查

### 3. 异步处理

**好处：**
- GitHub 不会超时重试
- 可以处理耗时操作（代码生成）
- 提高响应速度

### 4. 状态持久化

使用本地 JSON 文件保存 Issue 状态：
- 简单，无需外部数据库
- 易于调试和审计
- 可手动修改状态

### 5. Issue 跟踪功能

**设计要点：**
- 评论 ID 去重，防止 Webhook 重复处理
- 5 秒处理窗口，防止短时间内重复处理
- 检测关闭关键词（"已解决"、"fixed" 等）
- 可配置开关（`AGENT_ISSUE_TRACKING_ENABLED`）

---

## 代码修改设计详解

### 设计目标

1. **安全性**：代码修改必须精确、可验证、不会误删
2. **可审查性**：修改过程透明，便于人工审查
3. **容错性**：修改失败时有安全回退机制
4. **效率性**：支持大文件和复杂修改场景

### 整体流程

```
用户 Issue 指令
     ↓
[CodeExecutor.execute_task]
     ↓
1. 克隆/更新仓库 → 2. 创建分支
     ↓
3. 分析需要修改的文件（AI 分析或用户指定）
     ↓
4. 循环处理每个文件
     ↓
[SafeCodeModifier.modify_file]
     ↓
文件 <= 100 行? ──YES──→ _precise_replace (精确替换)
     │
    NO
     ↓
_chunked_modify (分段处理)
     ↓
5. 验证修改 → 6. 提交推送 → 7. 创建 PR
```

### 核心组件

#### 1. CodeGenerator（代码生成器）

**职责**：与本地 Ollama 模型交互，生成代码和修改建议

| 方法 | 用途 | 温度参数 | 说明 |
|------|------|----------|------|
| `generate_modification` | 单文件修改 | 0.3 | 生成完整文件内容 |
| `generate_multi_file_modification` | 多文件修改 | 0.2 | 返回 JSON 数组 |
| `analyze_issue_complexity` | 复杂度分析 | 0.1 | 评估修改难度和范围 |

**模型参数自适应**：
```python
if "30b" in model or "32b" in model:
    num_ctx = 131072  # 128K 上下文
    num_predict = 8000
elif "14b" in model:
    num_ctx = 32768   # 32K 上下文
    num_predict = 6000
else:
    num_ctx = 16384   # 16K 上下文
    num_predict = 4000
```

#### 2. SafeCodeModifier（安全修改器）

**核心设计：SEARCH/REPLACE 精确匹配**

与传统全文替换相比的优势：

```
传统方式（危险）:
AI 生成完整文件 → 直接覆盖原文件
→ 可能丢失 AI 未提及的代码
→ 无法验证修改范围

SEARCH/REPLACE 方式（安全）:
AI 生成 SEARCH/REPLACE 块 → 精确匹配替换
→ 只修改明确指定的部分
→ 不匹配时拒绝执行（安全回退）
→ 便于人工审查修改内容
```

**处理策略：**

##### 小文件处理（<=100行）：`_precise_replace`

```
构建 SEARCH/REPLACE 提示词
     ↓
AI 生成格式：
  SEARCH:
  ```
  要查找的代码（包含3-5行上下文）
  ```
  REPLACE:
  ```
  新代码
  ```
     ↓
验证：SEARCH 是否存在于原文件？
     ↓
YES → 执行替换 → 验证内容变化 → 返回
NO  → 抛出异常（安全回退）
```

##### 大文件处理（>100行）：`_chunked_modify`

```
第一步：AI 分析需要修改的行号范围
  ↓
第二步：对每个修改区域：
  - 提取上下文（前后各3行）
  - 调用 _ai_assisted_replace（精确替换）
  ↓
第三步：合并所有修改回原文件
  ↓
返回修改后的完整内容
```

**关键安全机制：**

1. **匹配验证**：SEARCH 必须在原文件中精确存在
2. **变化验证**：修改后内容必须与原始内容不同
3. **语法验证**：通过 ChangeValidator 检查代码语法
4. **失败回退**：任何步骤失败时返回原始内容

#### 3. CodeExecutor（执行器主类）

**执行流程：**

```python
execute_task():
  # Step 1: 准备环境
  1.1 克隆/更新仓库
  1.2 创建分支 agent-fix-{issue_number}
  
  # Step 2: 确定修改范围
  2.1 如果用户指定了 files_to_modify：直接使用
  2.2 否则：AI 分析仓库文件，选择需要修改的文件
  
  # Step 3: 执行修改
  3.1 遍历每个目标文件
  3.2 获取原始内容
  3.3 调用 SafeCodeModifier.modify_file()
  3.4 验证修改（语法 + 内容变化）
  3.5 写入文件
  
  # Step 4: 提交和 PR
  4.1 提交并推送分支
  4.2 创建 Pull Request
  4.3 返回执行结果
```

### 关键技术决策

#### 1. 为什么使用 SEARCH/REPLACE？

| 对比项 | 全文替换 | SEARCH/REPLACE |
|--------|----------|----------------|
| 安全性 | ❌ 可能误删 | ✅ 精确匹配 |
| 可验证性 | ❌ 无法验证 | ✅ 匹配失败拒绝 |
| 可审查性 | ❌ 需对比全文 | ✅ 明确修改点 |
| 失败恢复 | ❌ 难以恢复 | ✅ 安全回退 |

#### 2. 文件大小分层的考虑

- **小文件（<=100行）**：完整内容送入 AI，上下文充足，一次生成修改
- **大文件（>100行）**：分段处理，避免 AI 注意力分散，减少 token 消耗

#### 3. 温度参数选择

| 场景 | 温度 | 原因 |
|------|------|------|
| 分析类任务 | 0.1 | 确定性高，减少随机性 |
| 代码生成 | 0.2-0.3 | 适度创造性，保持稳定性 |

#### 4. 错误处理策略

```
修改失败时：
  1. 记录详细错误日志
  2. 返回原始内容（不破坏原有代码）
  3. 标记该文件修改失败
  4. 继续处理其他文件（部分成功优于全部失败）
```

### 当前局限性与优化方向

#### 已知局限

1. **SEARCH 匹配问题**
   - AI 生成的 SEARCH 可能与原文件不完全匹配
   - 常见原因：空白字符差异、换行符、AI 省略代码

2. **大文件 chunk 边界**
   - 分段修改时，多个 chunk 可能相互影响
   - 行号分析可能不够精确

3. **缺乏反馈循环**
   - 如果修改失败，没有自动重试或修正机制

#### 优化方向

1. **模糊匹配**：允许一定程度的空白字符差异
2. **反馈循环**：SEARCH 不匹配时，让 AI 重新生成
3. **AST 分析**：使用语法树确定修改范围，而非行号
4. **测试验证**：修改后自动运行相关测试用例
5. **多轮对话**：分析→生成→验证→修正，多轮迭代

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

---

## 总结

GitHub Agent V2 的架构设计遵循以下核心理念：

1. **分层清晰** - 每层职责单一，便于维护和测试
2. **松耦合** - 模块间通过接口交互，可独立演进
3. **容错性** - 每个外部依赖都有降级方案
4. **可扩展** - 易于添加新功能和新集成
5. **安全性** - 多层安全机制保护代码和数据
