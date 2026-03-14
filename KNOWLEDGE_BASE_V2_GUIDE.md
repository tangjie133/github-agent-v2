# 知识库系统 V2 使用指南

## 概述

知识库系统 V2 是一个统一文档处理平台，支持 Markdown、PDF 等多种格式，使用 ChromaDB 向量数据库存储，通过 Ollama 进行文本嵌入。

**核心特性：**
- 统一文档处理接口（所有文档类型使用相同流程）
- 增量同步（自动检测变更，避免重复量化）
- 芯片型号过滤查询（避免不同芯片文档混淆）
- 统一的 Metadata 结构（支持 source/type/chip/tags 等字段）

## 系统架构

```
PDF/Markdown → document_processor → Chunks → Embedding → ChromaDB
                    ↓                    ↓         ↓
              章节分割             Metadata  Ollama
              自动提取              统一结构   BGE-M3/nomic
```

**数据目录结构：**
```
${GITHUB_AGENT_STATEDIR}  (默认: /home/tj/state)
├── knowledge_base/
│   ├── chips/              # 芯片文档 (PDF)
│   └── best_practices/     # 最佳实践 (Markdown)
├── chroma_db/              # ChromaDB 向量数据库
│   └── chroma.sqlite3
└── .github_kb_sync_state.json   # 同步状态
```

## 快速开始

### 1. 配置环境变量

编辑 `.env` 文件：

```bash
# GitHub Agent 基础配置
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
GITHUB_WEBHOOK_SECRET=your_secret

# 知识库状态目录（所有数据存储在此）
GITHUB_AGENT_STATEDIR=/home/tj/state

# 嵌入模型配置
KB_EMBEDDING_MODEL=nomic-embed-text:latest
KB_EMBEDDING_HOST=http://localhost:11434

# GitHub 同步配置
KB_GITHUB_SYNC_ENABLED=true
KB_REPO=owner/knowledge-base
KB_BRANCH=main
GITHUB_TOKEN=ghp_xxx
```

### 2. 启动服务

**方式一：一键启动所有服务**
```bash
./scripts/start.sh --port 8080
```

**方式二：单独启动 KB Service**
```bash
export GITHUB_AGENT_STATEDIR=/home/tj/state
python knowledge_base/kb_service.py
```

### 3. 手动同步知识库

```bash
python scripts/github_repo_watcher.py --sync
```

### 4. 测试查询

```bash
# 健康检查
curl http://localhost:8000/health

# 统计信息
curl http://localhost:8000/stats

# 查询（限定芯片型号）
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "温度寄存器地址",
    "top_k": 3,
    "filters": {"chip": "bmi161"}
  }'
```

## API 文档

### 查询接口

**POST /query**

请求体：
```json
{
  "query": "查询文本",
  "top_k": 3,
  "filters": {
    "chip": "bmi161",      // 芯片型号过滤
    "doc_type": "chip",    // 文档类型过滤
    "vendor": "bosch"      // 厂商过滤
  }
}
```

响应：
```json
{
  "query": "温度寄存器地址",
  "results": [
    {
      "content": "Register (0x20-0x21) TEMPERATURE...",
      "metadata": {
        "source": "/home/tj/state/knowledge_base/chips/bmi161_datasheet.pdf",
        "doc_type": "chip",
        "content_type": "text",
        "chip": "bmi161",
        "vendor": "bosch",
        "page": 53,
        "section": "Temperature",
        "tags": "text,温度",
        "similarity": 0.8234
      }
    }
  ],
  "total_found": 3,
  "elapsed_ms": 125.5
}
```

### 其他接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/stats` | GET | 统计信息 |
| `/reload` | POST | 重新加载知识库 |

## 使用最佳实践

### 1. 始终指定芯片型号过滤

**❌ 错误用法（结果可能来自错误芯片）**
```bash
curl -d '{"query": "温度寄存器"}' http://localhost:8000/query
# 可能返回 BMI161 的，但你需要的是 SD3031 的
```

**✅ 正确用法**
```bash
curl -d '{
  "query": "温度寄存器",
  "filters": {"chip": "bmi161"}
}' http://localhost:8000/query
```

### 2. 查询技巧

| 场景 | 查询示例 |
|------|---------|
| 查找寄存器地址 | `"I2C 地址 0x68"` |
| 查找温度相关 | `"温度传感器 0x20"` |
| 查找电气参数 | `"工作电压 2.7V"` |
| 查找时序 | `"I2C 时序 SCL"` |

### 3. 理解 Metadata 字段

```json
{
  "source": "文件路径",
  "doc_type": "chip/practice/guide",
  "content_type": "text/table/register/code",
  "chip": "bmi161",           // 芯片型号
  "vendor": "bosch",          // 厂商
  "page": 53,                 // PDF 页码
  "section": "章节标题",
  "tags": "温度,寄存器,I2C"   // 自动提取的标签
}
```

## 故障排查

### 问题 1：KB Service 启动失败

**现象：**
```
ImportError: attempted relative import with no known parent package
```

**解决：**
```bash
# 使用正确的工作目录
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2
export GITHUB_AGENT_STATEDIR=/home/tj/state
python knowledge_base/kb_service.py
```

### 问题 2：查询结果来自错误芯片

**现象：** 查询 SD3031 返回 BMI161 的内容

**解决：**
```bash
# 添加芯片型号过滤
curl -d '{
  "query": "你的查询",
  "filters": {"chip": "sd3031"}
}' http://localhost:8000/query
```

### 问题 3：文档数为 0

**现象：** `/stats` 返回 `"total_documents": 0`

**排查：**
```bash
# 1. 检查文件是否下载
ls -la /home/tj/state/knowledge_base/chips/

# 2. 检查 ChromaDB 路径
ls -la /home/tj/state/chroma_db/

# 3. 手动触发加载
curl -X POST http://localhost:8000/reload
```

### 问题 4：同步失败

**现象：** `github_repo_watcher.py` 无法下载文件

**排查：**
```bash
# 检查 GitHub Token
echo $GITHUB_TOKEN

# 检查网络
curl -I https://api.github.com

# 手动测试同步
python scripts/github_repo_watcher.py --sync
```

## 文件参考

| 文件 | 说明 |
|------|------|
| `knowledge_base/kb_service.py` | 知识库服务主程序 |
| `knowledge_base/document_processor.py` | 统一文档处理器 |
| `knowledge_base/schema.py` | 数据模型定义 |
| `scripts/github_repo_watcher.py` | GitHub 同步工具 |
| `scripts/start.sh` | 一键启动脚本 |

## 更新日志

### V2.0 主要变更

1. **统一接口**：所有文档类型使用相同的处理流程
2. **统一 Metadata**：标准化的 chunk metadata 结构
3. **增量检测**：基于 file_hash 避免重复量化
4. **芯片过滤**：支持按 chip/vendor/doc_type 过滤查询
5. **自动标签**：从内容自动提取关键词标签
6. **路径统一**：所有数据统一到 `GITHUB_AGENT_STATEDIR`

---

**问题反馈：** 如遇问题请检查日志 `/tmp/kb_service.log`
