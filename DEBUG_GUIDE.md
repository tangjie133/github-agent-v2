# 调试指南 - 代码修改优化

本文档说明如何使用增强的调试信息来诊断代码修改过程中的问题。

## 日志级别

代码使用标准 Python logging，支持以下级别：

| 级别 | 用途 |
|------|------|
| `INFO` | 关键流程节点（默认显示） |
| `DEBUG` | 详细执行过程（调试用） |
| `WARNING` | 警告信息 |
| `ERROR` | 错误信息 |

## 启用详细调试日志

### 方法1: 环境变量

```bash
# 设置调试级别
export LOG_LEVEL=DEBUG

# 运行程序
./scripts/start.sh
```

### 方法2: 配置文件

在 `config/logging.yaml` 中设置：

```yaml
loggers:
  code_executor.code_analyzer:
    level: DEBUG
  code_executor.safe_modifier:
    level: DEBUG
  code_executor.change_validator:
    level: DEBUG
  code_executor.code_executor:
    level: DEBUG
```

### 方法3: 代码中临时启用

```python
import logging

# 启用特定模块的调试日志
logging.getLogger('code_executor.code_analyzer').setLevel(logging.DEBUG)
logging.getLogger('code_executor.safe_modifier').setLevel(logging.DEBUG)
```

## 调试标签说明

所有调试日志使用统一标签前缀，便于过滤：

| 标签 | 模块 |
|------|------|
| `[CodeAnalyzer]` | 代码分析器 |
| `[SafeModifier]` | 安全修改器 |
| `[Validator]` | 变更验证器 |
| `[CodeExecutor]` | 代码执行器 |

## 典型调试场景

### 场景1: 文件选择不正确

**问题**: AI 选择了错误的文件进行修改

**查看日志**:
```bash
grep "\[CodeAnalyzer\]" logs/agent.log
```

**关键日志**:
```
[CodeAnalyzer] 提取关键词: {'functions': [...], 'arduino_pins': [...], ...}
[CodeAnalyzer] 发现 5 个代码文件
[CodeAnalyzer] 分析文件: sensor.ino
[CodeAnalyzer]   - 语言: arduino
[CodeAnalyzer]   - 引脚: {14: ..., 13: ...}
[CodeAnalyzer] 匹配到 2 个待修改文件: ['sensor.ino', 'main.py']
```

**诊断**:
- 检查关键词提取是否正确
- 检查文件分析结果是否符合预期
- 查看匹配分数计算过程（DEBUG 级别）

### 场景2: SEARCH/REPLACE 匹配失败

**问题**: AI 生成的 SEARCH 文本无法匹配原文件

**查看日志**:
```bash
grep "\[SafeModifier\]" logs/agent.log
```

**关键日志**:
```
[SafeModifier] 开始模糊匹配
[SafeModifier] SEARCH 文本 (156 字符, 5 行):
[SafeModifier]   void setup() {
[SafeModifier]     pinMode(A0, INPUT);
[SafeModifier] 尝试精确匹配...
[SafeModifier] 精确匹配失败，尝试规范化匹配...
[SafeModifier] 规范化匹配失败，尝试相似度匹配...
[SafeModifier] 相似度阈值: 0.85
[SafeModifier] ❌ 所有匹配方法都失败
```

**诊断**:
- 检查 SEARCH 文本和实际内容的差异
- 查看 MD5 指纹对比
- 考虑调整相似度阈值或手动修复格式

### 场景3: 修改验证失败

**问题**: 修改后的代码无法通过验证

**查看日志**:
```bash
grep "\[Validator\]" logs/agent.log
```

**关键日志**:
```
[Validator] 开始验证 Python 文件: main.py
[Validator]   文件大小: 1250 字符, 45 行
[Validator]   检查 Python 语法...
[Validator] ❌ Python 语法错误: main.py
[Validator]    语法错误: 第23行, 第15列 - invalid syntax
[Validator]    错误行:     def broken(
```

或 Arduino:
```
[Validator] 开始验证 Arduino C++ 文件: sensor.ino
[Validator]   检查括号匹配...
[Validator] ❌ 括号不匹配
[Validator]   检查大括号平衡...
[Validator]     { x12, } x11
```

**诊断**:
- 查看具体语法错误位置和描述
- 检查括号/引号匹配状态
- 查看代码结构统计信息

### 场景4: 完整流程追踪

**问题**: 需要了解整个修改流程的执行情况

**查看日志**:
```bash
grep "\[CodeExecutor\]" logs/agent.log
```

**关键日志**:
```
[CodeExecutor] ========================================
[CodeExecutor] 开始执行任务: fix_issue
[CodeExecutor] 仓库: owner/repo#123
[CodeExecutor] 指令长度: 256 字符
[CodeExecutor] Step 1: 准备仓库 owner/repo...
[CodeExecutor] Step 2: 创建分支 agent-fix-123...
[CodeExecutor] Step 3: 分析并生成修改...
[CodeExecutor] 修改文件: sensor.ino
[CodeExecutor]   原始内容: 890 字符, 32 行
[CodeExecutor]   调用 AI 修改器...
[CodeExecutor]   内容变化: +156 字符
[CodeExecutor]   验证修改...
[CodeExecutor] ✅ 文件修改成功: sensor.ino (890 → 1046 字符, +156)
```

## 日志示例分析

### 成功案例分析

```
[CodeAnalyzer] 开始分析 Issue: Fix temperature reading...
[CodeAnalyzer] 提取关键词: {'arduino_pins': ['A0'], 'libraries': ['Wire']}
[CodeAnalyzer] 发现 3 个代码文件
[CodeAnalyzer] 分析文件: sensor.ino
[CodeAnalyzer]   - 语言: arduino
[CodeAnalyzer]   - 引脚: {14: <Pin A0>}
[CodeAnalyzer]   - 库: ['Wire']
[CodeAnalyzer] 成功分析 1/3 个文件
[CodeAnalyzer] 匹配到 1 个待修改文件: ['sensor.ino']

[SafeModifier] 开始模糊匹配
[SafeModifier] SEARCH 文本 (45 字符, 2 行):
[SafeModifier]   int value = analogRead(A0);
[SafeModifier] 尝试精确匹配...
[SafeModifier] ✅ 精确匹配成功

[Validator] 开始验证 Arduino C++ 文件: sensor.ino
[Validator]   文件大小: 1046 字符, 38 行
[Validator]   检查括号匹配...
[Validator]     括号检查通过
[Validator]   检查 Arduino 基本结构...
[Validator]     发现 setup()
[Validator]     发现 loop()
[Validator] ✅ Arduino C++ 验证通过: sensor.ino

[CodeExecutor] ✅ 文件修改成功: sensor.ino (890 → 1046 字符, +156)
```

### 失败案例分析

```
[CodeAnalyzer] 开始分析 Issue: Fix error handling...
[CodeAnalyzer] 提取关键词: {'functions': []}  # 注意：没有提取到函数
[CodeAnalyzer] 发现 2 个代码文件
[CodeAnalyzer] 成功分析 2/2 个文件
[CodeAnalyzer] 匹配到 0 个待修改文件: []  # 问题：没有匹配到文件
```

**问题**: 关键词提取失败，无法匹配文件
**解决**: 在 Issue 中明确提及函数名或文件路径

```
[SafeModifier] 开始模糊匹配
[SafeModifier] SEARCH 文本 (120 字符, 4 行):
[SafeModifier]   void setup() {
[SafeModifier]     Serial.begin(9600);
[SafeModifier] 尝试精确匹配...
[SafeModifier] 精确匹配失败，尝试规范化匹配...
[SafeModifier] SEARCH MD5: 1234
[SafeModifier] 内容 MD5: 5678  # MD5 不同，说明内容有差异
[SafeModifier] 规范化匹配失败，尝试相似度匹配...
[SafeModifier] 相似度阈值: 0.85
[SafeModifier] ❌ 所有匹配方法都失败
```

**问题**: SEARCH 文本与实际内容不匹配
**解决**: 检查空白字符、换行符或代码内容的实际差异

## 调试技巧

### 1. 实时查看日志

```bash
# 实时查看最新日志
tail -f logs/agent.log | grep "\[CodeAnalyzer\]"

# 同时查看多个模块
tail -f logs/agent.log | grep -E "\[CodeAnalyzer\]|\[SafeModifier\]"
```

### 2. 提取特定 Issue 的日志

```bash
# 假设 Issue #42 的分支名为 agent-fix-42
grep "agent-fix-42" logs/agent.log > issue_42_debug.log
```

### 3. 统计日志信息

```bash
# 统计各模块日志数量
grep -c "\[CodeAnalyzer\]" logs/agent.log
grep -c "\[SafeModifier\]" logs/agent.log
grep -c "\[Validator\]" logs/agent.log

# 统计错误数量
grep -c "❌" logs/agent.log
```

### 4. 性能分析

```bash
# 查看各步骤耗时（如果有时间戳）
grep "Step" logs/agent.log

# 查看文件分析耗时
grep "成功分析" logs/agent.log
```

## 常见问题 FAQ

### Q: 日志太多，如何只查看关键信息？

**A**: 使用 INFO 级别，或过滤特定标签：
```bash
grep -E "INFO|ERROR|WARNING" logs/agent.log
grep "\[CodeExecutor\]" logs/agent.log
```

### Q: 如何保存调试日志供分析？

**A**: 
```bash
# 完整日志
cp logs/agent.log debug_$(date +%Y%m%d_%H%M%S).log

# 只保存特定模块
grep "\[CodeAnalyzer\]" logs/agent.log > analyzer_debug.log
```

### Q: 调试信息会影响性能吗？

**A**: DEBUG 级别会产生大量日志，建议：
- 生产环境使用 INFO 级别
- 调试时临时启用 DEBUG 级别
- 针对特定模块启用 DEBUG，而非全局

## 联系支持

如果调试信息不足以解决问题，请提供：
1. 完整的 DEBUG 级别日志
2. 相关的 Issue 描述
3. 涉及的代码文件（原始和修改后的）
4. 期望的行为 vs 实际行为
