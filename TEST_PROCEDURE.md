# GitHub Agent V2 - 测试流程文档

## 📋 测试前准备

### 1. 确认服务状态

```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2

# 检查进程
ps aux | grep -E "main.py|kb_service|ngrok" | grep -v grep

# 检查端口
fuser 8080/tcp  # Agent
fuser 8000/tcp  # KB Service
```

### 2. 确认 ngrok 在线

```bash
# 检查 ngrok 状态
curl -s http://localhost:4040/api/tunnels | grep public_url

# 应该返回类似：
# https://chalazian-exasperatingly-vergie.ngrok-free.dev
```

### 3. 确认 GitHub Webhook 配置

访问：https://github.com/tangjie133/test/settings/hooks

确认 Payload URL 为：
```
https://chalazian-exasperatingly-vergie.ngrok-free.dev/webhook/github
```

---

## 🧪 测试步骤

### 步骤 1：创建测试 Issue

**访问**：https://github.com/tangjie133/test/issues/new

**标题**：`@agent 测试 SD3031 1Hz 输出配置`

**内容**：
```markdown
你好，我使用 SD3031 RTC 模块，想要配置 INT 引脚输出 1Hz 方波。

请问需要设置哪些寄存器？

根据数据手册，我尝试修改 enableFrequency 函数，将：
```cpp
reg2 = reg2 | 0x21;
```
改为：
```cpp
reg2 = 0xEF;
```
这样可以工作，但我不确定这是否是正确的做法。

请帮我确认正确的配置方法。
```

---

### 步骤 2：监控 Webhook 接收

**终端 1**：监控 webhook 文件
```bash
# 查看当前 webhook 文件数
ls /home/tj/state/webhooks/*.json | wc -l

# 监控新文件
watch -n 2 'ls -lt /home/tj/state/webhooks/*.json | head -5'
```

**预期结果**：
- 新文件生成：`issue_comment-test-{number}-{timestamp}.json`

---

### 步骤 3：监控处理日志

**终端 2**：监控 Agent 日志
```bash
# 实时监控关键日志
tail -f /home/tj/state/logs/agent.log | grep -E \
  "(Using modification|指令长度|enableFrequency|change_description|PR #|SUCCESS|FAILED)"
```

**关键检查点**：

1. **Intent Classification**
   ```
   [Intent Classification] SUCCESS via OpenClaw: modify (confidence: {0.8+})
   ```

2. **Decision Engine**
   ```
   [Decision Engine] OpenClaw planning successful
   Action plan: modify (complexity: medium)
   ```

3. **关键修复验证 - Using modification instruction**
   ```
   Using modification instruction: 在 enableFrequency() 函数中...
   ```
   ✅ 应该显示详细的修改描述，不是原始 Issue 文本

4. **指令长度验证**
   ```
   [CodeExecutor] 指令长度: 94 字符
   ```
   ✅ 应该 > 50 字符，不能是 34 字符（原始 Issue 长度）

5. **文件修改验证**
   ```
   [CodeExecutor] 指定修改文件: ['DFRobot_SD3031.cpp']
   [CodeExecutor] Step 3: 分析并生成修改...
   ```

6. **PR 创建成功**
   ```
   ✅ 代码执行成功，创建 PR #{number}: {url}
   ```

---

### 步骤 4：验证 PR 内容

**访问 GitHub PR**：https://github.com/tangjie133/test/pulls

**检查要点**：

1. **PR 标题**：应该包含 `enableFrequency` 或 `SD3031`
2. **修改的文件**：`DFRobot_SD3031.cpp`
3. **修改的函数**：应该是 `enableFrequency()`，不是 `setTime()` 或其他函数

**查看 diff**：
```bash
# 或在本地查看
cd /tmp/github-agent/tangjie133-test
git fetch origin
git diff origin/main..origin/agent-fix-{issue_number}
```

**预期修改**：
```cpp
// 原始代码
reg2 = reg2 | 0x21;

// 修改为
reg2 = 0xEF;
// 或者更优雅的位操作
```

---

### 步骤 5：验证知识库查询

检查日志中是否有 KB 查询：
```bash
grep "Querying KB" /home/tj/state/logs/agent.log
```

**预期输出**：
```
Querying KB: SD3031 CTR2寄存器位定义
Querying KB: SD3031 频率输出配置
```

---

## ✅ 验证清单

### 基础功能
- [ ] Webhook 文件生成在 `/home/tj/state/webhooks/`
- [ ] Agent 日志生成在 `/home/tj/state/logs/agent.log`
- [ ] KB Service 日志生成在 `/home/tj/state/logs/kb_service.log`
- [ ] Intent 识别为 `modify`
- [ ] 置信度 > 0.8

### 关键修复验证
- [ ] 日志显示 "Using modification instruction: ..."
- [ ] 指令长度 > 50 字符（不能是 34）
- [ ] 修改的函数是 `enableFrequency()`
- [ ] 不是修改 `setTime()` 或其他函数
- [ ] PR 成功创建
- [ ] 修改符合预期（`reg2 = 0xEF` 或类似）

### 知识库
- [ ] 查询了 SD3031 相关文档
- [ ] 返回了 CTR2 寄存器信息

---

## 🔧 故障排除

### 问题 1：Agent 没有响应
```bash
# 检查服务状态
curl http://localhost:8080/health
curl http://localhost:8000/health

# 检查 ngrok
curl http://localhost:4040/api/tunnels
```

### 问题 2：指令长度仍是 34 字符
说明 `core/processor.py` 修复未生效：
```bash
# 检查代码
grep "Using modification instruction" core/processor.py

# 如果没有，需要重新应用修复
```

### 问题 3：修改了错误的函数
检查日志中的 AI 分析：
```bash
grep "修改.*函数\|Step 3" /home/tj/state/logs/agent.log
```

如果显示 `setTime` 而不是 `enableFrequency`，说明指令源仍有问题。

### 问题 4：Webhook 文件不在 statedir
```bash
# 检查环境变量
echo $GITHUB_AGENT_STATEDIR

# 检查 Agent 配置
curl http://localhost:8080/health | grep webhook_dir
```

---

## 📝 测试报告模板

测试完成后，填写以下报告：

```markdown
## 测试结果

### 基本信息
- 测试时间: 2026-03-14
- Issue 编号: #?
- PR 编号: #?

### 关键指标
| 检查项 | 结果 | 备注 |
|--------|------|------|
| Webhook 接收 | ✅/❌ | 文件路径 |
| Intent 识别 | ✅/❌ | 置信度 |
| 指令源修复 | ✅/❌ | 指令长度 |
| 修改函数正确 | ✅/❌ | 函数名 |
| PR 创建 | ✅/❌ | PR 链接 |

### 详细日志
```
(粘贴关键日志)
```

### 问题记录
- 问题 1: ...
- 解决: ...
```

---

*文档版本: 2024-03-14*
