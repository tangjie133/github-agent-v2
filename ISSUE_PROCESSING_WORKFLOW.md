# GitHub Agent V2 - Issue 处理流程文档

## 📋 目录
1. [整体架构](#整体架构)
2. [详细流程](#详细流程)
3. [关键修复点](#关键修复点)
4. [调试方法](#调试方法)
5. [验证清单](#验证清单)

---

## 整体架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub 平台                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ Issue 创建  │    │   评论      │    │  PR 事件    │         │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘         │
└─────────┼──────────────────┼────────────────────────────────────┘
          │                  │
          └────────┬─────────┘
                   ↓ HTTP POST
┌─────────────────────────────────────────────────────────────────┐
│                     ngrok 隧道 (公网暴露)                         │
│              https://xxx.ngrok-free.dev/webhook/github          │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Webhook Server (Port 8080)                   │
│                   webhook/webhook_server.py                     │
├─────────────────────────────────────────────────────────────────┤
│  1. 接收 POST /webhook/github                                   │
│  2. 验证签名 (X-Hub-Signature-256)                              │
│  3. 解析事件类型 (X-GitHub-Event)                               │
│  4. 保存到 /home/tj/state/webhooks/*.json                      │
│  5. 异步调用 IssueProcessor.process_event()                    │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓ 异步线程
┌─────────────────────────────────────────────────────────────────┐
│                   IssueProcessor.process_event()                │
│                      core/processor.py:83                       │
└──────────────────────────┬──────────────────────────────────────┘
                           ↓
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ↓                  ↓                  ↓
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  阶段 1-2     │  │   阶段 3-4    │  │   阶段 5-7    │
│  预处理       │  │  智能决策     │  │  执行处理     │
├───────────────┤  ├───────────────┤  ├───────────────┤
│ • 触发检查    │  │ • 意图识别    │  │ • KB 查询     │
│ • 状态检查    │  │ • 决策引擎    │  │ • 代码生成    │
│ • 防重复      │  │ • 确认模式    │  │ • PR 创建     │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub API 交互层                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ 回复 Issue  │    │  创建 PR    │    │  关闭 Issue │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 模块关系图

```
┌─────────────────────────────────────────────────────────────┐
│                      外部服务                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  GitHub  │  │ OpenClaw │  │  Ollama  │  │ ChromaDB │   │
│  │   API    │  │  (云端)  │  │  (本地)  │  │  (本地)  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
        ↓             ↓             ↓             ↓
┌─────────────────────────────────────────────────────────────┐
│                     Agent V2 核心                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              IssueProcessor (core/processor.py)       │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │  │ _should │→ │  Intent │→ │ Decision│→ │  Code   │ │  │
│  │  │process  │  │Classifier│  │ Engine  │  │Executor │ │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│                         ↓                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Webhook Server (webhook/webhook_server.py)  │  │
│  │         接收 → 验证 → 保存 → 异步分发                 │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│                     数据存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Webhook     │  │    日志      │  │   State      │       │
│  │  JSON 文件   │  │   .log       │  │  SQLite/JSON │       │
│  │  webhooks/   │  │   logs/      │  │  .state.json │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 详细流程图

### 完整处理流程图

```
┌────────────────────────────────────────────────────────────────────────┐
│                         GitHub Webhook 触发                             │
│              (issues / issue_comment / pull_request)                   │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 1: Webhook 接收与验证                           │
│                       webhook/webhook_server.py:98                      │
├────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│  │ 接收 POST   │ → │ 验证签名    │ → │ 解析 JSON   │               │
│  │ /webhook/   │    │ HMAC-SHA256 │    │ payload     │               │
│  │ github      │    │ (Webhook    │    │             │               │
│  │             │    │  Secret)    │    │             │               │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│         │                  │                  │                        │
│         └──────────────────┼──────────────────┘                        │
│                            ↓                                           │
│                   ┌─────────────────┐                                  │
│                   │ 保存到 webhooks/ │                                  │
│                   │ {event}.json    │                                  │
│                   └────────┬────────┘                                  │
│                            ↓                                           │
│                   ┌─────────────────┐                                  │
│                   │ 异步线程启动    │                                  │
│                   │ process_event() │                                  │
│                   └─────────────────┘                                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 2: 预处理与验证                                 │
│                      core/processor.py:83-178                           │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │ _should_process │ ← 检查触发条件                                    │
│  │     (event)     │    • smart 模式检查 @agent                        │
│  └────────┬────────┘    • auto 模式直接通过                            │
│           │                                                            │
│           ↓ 通过                                                       │
│  ┌─────────────────┐                                                   │
│  │  提取基本信息   │    owner, repo, issue_number, installation_id     │
│  └────────┬────────┘                                                   │
│           ↓                                                            │
│  ┌─────────────────┐                                                   │
│  │ 构建上下文      │ ← context_builder.build()                         │
│  │ IssueContext    │    获取 Issue 详情 + 评论历史                     │
│  └────────┬────────┘                                                   │
│           ↓                                                            │
│  ┌─────────────────┐                                                   │
│  │ 获取状态        │ ← state_manager.get_state()                       │
│  │ IssueState      │    检查处理历史 + 防重复                          │
│  └────────┬────────┘                                                   │
│           ↓                                                            │
│  ┌─────────────────┐     ┌───────────────┐     ┌───────────────┐      │
│  │ 防重复检查      │ →  │ 评论ID已处理? │ →  │ 5秒内处理过?  │      │
│  │                 │    │     SKIP      │    │     SKIP      │      │
│  └────────┬────────┘    └───────────────┘    └───────────────┘      │
│           ↓                                                            │
│  ┌─────────────────┐     ┌───────────────┐                            │
│  │ 跟进回复检查    │ →  │ 用户确认解决? │ → CLOSE & RETURN         │
│  │ _check_followup │    └───────────────┘                            │
│  └─────────────────┘                                                   │
│                                                                         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 3: 意图识别 (OpenClaw)                          │
│                     core/processor.py:295-322                           │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │           cloud_agent.classify_with_history(context)            │  │
│  │                                                                 │  │
│  │  输入: IssueContext (标题 + 正文 + 评论历史)                    │  │
│  │  ↓                                                              │  │
│  │  OpenClaw API 调用                                             │  │
│  │  ↓                                                              │  │
│  │  输出: IntentResult                                            │  │
│  │  {                                                             │  │
│  │    intent: "modify" | "answer" | "research" | "clarify",       │  │
│  │    confidence: 0.0-1.0,                                        │  │
│  │    reasoning: "用户要求修改代码...",                           │  │
│  │    needs_research: true/false                                  │  │
│  │  }                                                             │  │
│  └────────────────────────────────────┬────────────────────────────┘  │
│                                       ↓                                 │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  显式修改请求检查 _check_explicit_modify_request()              │  │
│  │  如果用户明确说"修改代码" → 覆盖 intent 为 MODIFY              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  日志输出:                                                              │
│  Detected intent: modify (confidence: 0.94)                            │
│                                                                         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 4: 决策引擎 (OpenClaw)                          │
│                     core/processor.py:324-346                           │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │            decision_engine.make_decision(context, intent)       │  │
│  │                                                                 │  │
│  │  输入: 完整上下文 + IntentResult                                │  │
│  │  ↓                                                              │  │
│  │  OpenClaw API 调用 (make_decision)                             │  │
│  │  ↓                                                              │  │
│  │  输出: ActionPlan ⭐ 关键输出                                  │  │
│  │  {                                                             │  │
│  │    action: "modify" | "reply" | "research" | "skip",           │  │
│  │    complexity: "simple" | "medium" | "complex",                │  │
│  │    files_to_modify: ["file1.cpp", "file2.h"],                 │  │
│  │    change_description: "详细修改说明...", ⭐ 关键              │  │
│  │    confidence: 0.0-1.0                                         │  │
│  │  }                                                             │  │
│  └────────────────────────────────────┬────────────────────────────┘  │
│                                       ↓                                 │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  自动执行检查 _should_auto_execute(action_plan, intent)         │  │
│  │                                                                 │  │
│  │  如果需要确认 → _request_confirmation() → 回复等待            │  │
│  │  如果自动执行 → 继续                                           │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  日志输出:                                                              │
│  Action plan: modify (complexity: medium)                              │
│  [如果手动确认] 请回复以下指令之一: 确认/修改方案/取消                 │
│                                                                         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 5: 知识库查询 (KB)                              │
│                    _handle_modify_intent() 内部                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  从 change_description 提取关键词                              │  │
│  │  例如: "SD3031 enableFrequency CTR2 寄存器"                     │  │
│  │                          ↓                                       │  │
│  │  knowledge_base.query()                                         │  │
│  │  ↓                                                               │  │
│  │  ChromaDB 向量搜索 (带 chip 过滤器)                             │  │
│  │  ↓                                                               │  │
│  │  返回相关文档片段                                               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  日志输出:                                                              │
│  Querying KB: SD3031 CTR2寄存器位定义                                  │
│  KB query returned 3 results                                           │
│                                                                         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 6: 代码执行 ⭐ 核心步骤                          │
│                    core/processor.py:602-616 ⭐ 关键修复                 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                        关键修复点 ⭐                             │  │
│  │                                                                 │  │
│  │  BEFORE (错误):                                                │  │
│  │    instruction = context.current_instruction or context.body   │  │
│  │    # 指令长度: 34 字符 (原始 Issue 文本)                        │  │
│  │                                                                 │  │
│  │  AFTER (修复):                                                 │  │
│  │    modification_instruction = action_plan.change_description   │  │
│  │                              or context.current_instruction   │  │
│  │                              or context.body                   │  │
│  │    # 指令长度: 94 字符 (详细修改说明)                           │  │
│  │                                                                 │  │
│  │  logger.info(f"Using modification instruction:                │  │
│  │              {modification_instruction[:100]}...")             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │           code_executor.execute_task()                          │  │
│  │                                                                 │  │
│  │  1. 克隆/更新仓库 → /tmp/github-agent/{owner}-{repo}           │  │
│  │  2. 创建分支 agent-fix-{issue_number}                          │  │
│  │  3. AI 分析并生成修改 (Ollama qwen3-coder)                     │  │
│  │  4. 安全修改验证 (SafeModifier)                                │  │
│  │  5. 提交并推送                                                 │  │
│  │  6. 创建 PR (GitHub API)                                       │  │
│  └────────────────────────────────────┬────────────────────────────┘  │
│                                         ↓                               │
│  日志输出:                                                              │
│  [CodeExecutor] 指令长度: 94 字符 ⭐ (不是 34)                         │
│  [CodeExecutor] 指定修改文件: ['DFRobot_SD3031.cpp']                   │
│  [CodeExecutor] Step 1: 准备仓库...                                    │
│  [CodeExecutor] Step 2: 创建分支...                                    │
│  [CodeExecutor] Step 3: 分析并生成修改...                              │
│                                                                         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    Step 7: 结果处理与回复                               │
│                    core/processor.py:618-677                            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  处理执行结果                                                   │  │
│  │  ├── status == "completed"                                     │  │
│  │  │   ├── 获取 PR 信息 (pr_number, pr_url)                     │  │
│  │  │   ├── 更新 state (记录 PR 编号、修改文件)                 │  │
│  │  │   ├── 在 Issue 中回复成功消息                              │  │
│  │  │   └── 返回 COMPLETED                                       │  │
│  │  │                                                             │  │
│  │  └── status == "failed"                                        │  │
│  │      └── 返回 FAILED                                          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  成功回复示例:                                                          │
│  🤖 代码修改完成                                                       │
│                                                                         │
│  ✅ 我已创建 PR #{number} 来解决这个问题：                             │
│  {pr_url}                                                              │
│                                                                         │
│  **修改的文件**:                                                        │
│  - `DFRobot_SD3031.cpp`                                                │
│                                                                         │
│  请查看并确认修改是否符合预期。                                         │
│                                                                         │
└────────────────────────────────────────┬───────────────────────────────┘
                                         ↓
┌────────────────────────────────────────────────────────────────────────┐
│                         处理完成                                        │
│              返回 ProcessingResult 到 Webhook Server                   │
│                    (不影响 GitHub 响应，已返回 200)                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 详细流程

**文件**: `webhook/webhook_server.py`

```python
1. 接收 GitHub POST /webhook/github
2. 验证签名 (GITHUB_WEBHOOK_SECRET)
3. 解析事件类型 (issues/issue_comment/pull_request)
4. 保存到 GITHUB_AGENT_STATEDIR/webhooks/
5. 异步调用 IssueProcessor.process_event()
```

**输出日志**:
```
Received issue_comment event
Saved webhook to: /home/tj/state/webhooks/issue_comment-{repo}-{number}-{timestamp}.json
Started async processing for issue_comment
```

**验证命令**:
```bash
ls -la /home/tj/state/webhooks/*.json | tail -5
```

---

### 阶段 2: 意图识别 (Intent Classification)

**文件**: `cloud_agent/intent_classifier.py`

```python
1. 构建上下文（Issue标题 + 正文 + 评论）
2. 调用 OpenClaw 进行意图识别
3. 返回: intent (modify/answer/research/clarify), confidence
```

**输出日志**:
```
[Intent Classification] Starting for issue #{number}
Context preview: 【当前指令】...
✅ [Intent Classification] SUCCESS via OpenClaw: {intent} (confidence: {confidence})
Reasoning: ...
```

**关键修复**: 
- 确保 `current_instruction` 正确提取（取最新评论）
- 如果用户说"重新修复"，需要重置处理计数

**验证命令**:
```bash
grep "Intent Classification" /home/tj/state/logs/agent.log | tail -5
```

---

### 阶段 3: 决策引擎 (Decision Engine)

**文件**: `cloud_agent/decision_engine.py`

```python
1. 根据意图类型生成 ActionPlan
2. modify 类型: 调用 OpenClaw.make_decision()
3. 返回: ActionPlan(action, files_to_modify, change_description, complexity)
```

**输出日志**:
```
[Decision Engine] Making decision for intent: modify
[Decision Engine] Trying OpenClaw for detailed planning...
✅ [Decision Engine] OpenClaw planning successful
Action plan: modify (complexity: medium)
```

**关键输出 - change_description**:
```
在 enableFrequency() 函数中，将 reg2 = reg2 | 0x21 精确替换为 reg2 = 0xEF
```

**验证命令**:
```bash
grep "Using modification instruction" /home/tj/state/logs/agent.log
```

---

### 阶段 4: 知识库查询 (KB Query)

**文件**: `knowledge_base/kb_client.py`

```python
1. 根据 change_description 提取关键词
2. 查询 ChromaDB（带 chip 过滤器）
3. 返回相关文档片段
```

**输出日志**:
```
Querying KB: {query}
KB query returned {n} results
Querying knowledge base for topics: [...]
```

**验证命令**:
```bash
curl -s http://localhost:8000/stats | python3 -m json.tool
grep "Querying KB" /home/tj/state/logs/agent.log | tail -5
```

---

### 阶段 5: 代码执行 (Code Execution)

**文件**: `code_executor/code_executor.py`

```python
1. 接收 instruction（应该是 change_description！）
2. 克隆/更新仓库到 /tmp/github-agent/
3. 创建分支 agent-fix-{issue_number}
4. 分析文件并生成修改
5. 提交并推送
6. 创建 PR
```

**关键修复**: 
- **必须使用 `action_plan.change_description` 作为 instruction**
- 不要直接使用 `context.body` 或 `current_instruction`

**代码位置**: `core/processor.py` 第 604-612 行

```python
# ✅ 正确做法
modification_instruction = action_plan.change_description or context.current_instruction or context.body
logger.info(f"Using modification instruction: {modification_instruction[:100]}...")
```

**输出日志**:
```
Using modification instruction: 在 enableFrequency() 函数中...
[CodeExecutor] 指令长度: 94 字符  ✅ (应该是 50+ 字符，不是 34 字符)
[CodeExecutor] 指定修改文件: ['DFRobot_SD3031.cpp']
[CodeExecutor] Step 1: 准备仓库
[CodeExecutor] Step 2: 创建分支
[CodeExecutor] Step 3: 分析并生成修改
```

---

### 阶段 6: PR 创建

**输出日志**:
```
✅ 代码执行成功，创建 PR #{number}: {url}
```

**验证命令**:
```bash
ls -lt /home/tj/state/webhooks/pull_request*.json | head -3
```

---

## 关键修复点

### 修复 1: Webhook 路径统一

**问题**: Webhook 文件保存到 `/tmp/github-webhooks`

**修复**:
```bash
# start.sh
export GITHUB_AGENT_STATEDIR="/home/tj/state"
export GITHUB_AGENT_WEBHOOK_DIR="/home/tj/state/webhooks"
```

**验证**:
```bash
curl http://localhost:8080/health | grep webhook_dir
# 应该返回: /home/tj/state/webhooks
```

---

### 修复 2: 代码修改指令源

**问题**: 使用原始 Issue 文本（34 字符），导致 AI 理解错误

**修复**:
```python
# core/processor.py 第 604-612 行
modification_instruction = action_plan.change_description or context.current_instruction or context.body
logger.info(f"Using modification instruction: {modification_instruction[:100]}...")
```

**验证**:
```bash
grep "Using modification instruction" /home/tj/state/logs/agent.log
# 应该显示详细的修改描述（50+ 字符）
grep "指令长度" /home/tj/state/logs/agent.log
# 应该是 50+ 字符，不是 34 字符
```

---

### 修复 3: 日志路径统一

**问题**: 日志分散在 `/tmp/` 和项目目录

**修复**:
```bash
# start.sh
LOG_DIR="${GITHUB_AGENT_STATEDIR}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/agent.log"
KB_LOG_FILE="${LOG_DIR}/kb_service.log"
```

**验证**:
```bash
ls -la /home/tj/state/logs/
# 应该看到: agent.log, kb_service.log
```

---

## 调试方法

### 实时监控

```bash
# 1. 监控日志
tail -f /home/tj/state/logs/agent.log | grep -E "(Using modification|指令长度|enableFrequency|change_description|Step 3)"

# 2. 监控 webhook 事件
watch -n 2 'ls -lt /home/tj/state/webhooks/*.json | head -5'

# 3. 检查服务状态
curl http://localhost:8080/health
curl http://localhost:8000/health
```

### 单步调试

```bash
# 1. 停止服务
pkill -f "main.py|kb_service"

# 2. 清除缓存
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# 3. 前台启动（带详细日志）
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
source venv/bin/activate
export LOG_LEVEL=DEBUG
export GITHUB_AGENT_STATEDIR=/home/tj/state
python3 -m knowledge_base.kb_service > /home/tj/state/logs/kb_service.log 2>&1 &
python3 main.py --host 0.0.0.0 --port 8080
```

---

## 验证清单

### 启动前检查

- [ ] `GITHUB_AGENT_STATEDIR` 已设置
- [ ] ngrok 正在运行
- [ ] GitHub Webhook URL 配置正确

### 启动后检查

- [ ] Agent: `curl http://localhost:8080/health`
- [ ] KB: `curl http://localhost:8000/health`
- [ ] 日志目录: `ls /home/tj/state/logs/`
- [ ] Webhook 目录: `ls /home/tj/state/webhooks/`

### Issue 处理后检查

- [ ] Webhook 文件已生成
- [ ] 日志显示 "Using modification instruction: ..."
- [ ] 指令长度 > 50 字符
- [ ] 修改了正确的函数（enableFrequency 而不是 setTime）
- [ ] PR 已创建

---

## 常见问题

### Q1: 指令长度仍然是 34 字符

**原因**: 使用了 `context.body` 而不是 `action_plan.change_description`

**解决**: 检查 `core/processor.py` 第 606 行

### Q2: AI 修改了错误的函数

**原因**: instruction 不够详细

**解决**: 确保使用 OpenClaw 生成的 `change_description`

### Q3: Webhook 文件不在 statedir

**原因**: `GITHUB_AGENT_WEBHOOK_DIR` 未设置

**解决**: 检查 `start.sh` 中的环境变量导出

---

*文档版本: 2024-03-14*
*最后更新: 修复指令源和日志路径*
