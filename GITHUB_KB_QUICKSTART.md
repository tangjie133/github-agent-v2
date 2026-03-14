# GitHub 仓库知识库快速上手指南

将技术文档存入 GitHub 仓库，自动同步到 ChromaDB 向量知识库，支持智能检索。

---

## 🎯 方案对比

| 方式 | 实时性 | 适用场景 | 复杂度 |
|------|--------|---------|--------|
| **Webhook** | ⭐⭐⭐ 实时 | 团队协作，频繁更新 | 中等 |
| **定时同步** | ⭐⭐ 5分钟延迟 | 个人使用，更新不频繁 | 简单 |
| **手动同步** | ⭐ 按需 | 偶尔更新 | 最简单 |

---

## 🚀 快速开始（3 分钟）

### 步骤 1: 配置环境（1分钟）

```bash
cd /home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2

# 编辑 .env 文件
vim .env
```

**添加以下配置：**
```bash
# 知识库同步配置
KB_GITHUB_SYNC_ENABLED=true
KB_REPO=tangjie133/knowledge-base    # 你的知识库仓库
KB_BRANCH=main
KB_GITHUB_TOKEN=ghp_xxx               # GitHub Token（可选，用于私有仓库）

# 状态目录配置（所有数据统一存储）
GITHUB_AGENT_STATEDIR=/home/tj/state

# 嵌入模型配置
KB_EMBEDDING_MODEL=bge-m3:latest
KB_EMBEDDING_HOST=http://localhost:11434
```

**创建必要目录：**
```bash
mkdir -p /home/tj/state
mkdir -p /home/tj/state
```

---

### 步骤 2: 选择同步方式

#### 方式 A: Webhook 实时同步（推荐团队使用）

**1. 启动接收服务器：**
```bash
python scripts/github_webhook_server.py --port 9000
```

**2. 配置 GitHub Webhook：**
1. 打开 GitHub 仓库 → Settings → Webhooks
2. 点击 "Add webhook"
3. 填写配置：
   - **Payload URL**: `http://your-server-ip:9000/webhook`
   - **Content type**: `application/json`
   - **Secret**: （可选）
   - **Which events?**: "Just the push event"
4. 点击 "Add webhook"

**3. 测试同步：**
```bash
# 向仓库推送一个文件
git add esp32_datasheet.pdf
git commit -m "添加 ESP32 数据手册"
git push

# 观察服务器日志，自动同步
# 输出示例：
# 📄 直接处理 PDF: esp32_datasheet.pdf
# 🚀 开始并行处理: 110 页 | 4 线程
# ✅ PDF 新增完成: 110/110 页已存储
```

#### 方式 B: 定时同步（推荐个人使用）

```bash
# 后台运行，每 5 分钟检查一次
python scripts/github_repo_watcher.py --daemon --interval 300

# 或手动同步一次
python scripts/github_repo_watcher.py --sync
```

#### 方式 C: 使用启动脚本（推荐）

```bash
# 启动脚本会自动同步并启动 KB Service
./scripts/start.sh --port 8080
```

---

## 📁 仓库文件组织建议

```
knowledge-base/           # GitHub 仓库根目录
├── chips/               # 芯片数据手册
│   ├── esp32_datasheet.pdf
│   ├── bmi160_datasheet.pdf
│   └── stm32f103_ref.pdf
├── guides/              # 开发指南
│   ├── i2c_protocol.md
│   ├── sensor_driver_guide.txt
│   └── coding_standards.docx
└── README.md           # 仓库说明
```

**分类规则：**
- 文件名包含 `chip`, `芯片`, `hardware`, `datasheet` → 标记为芯片文档
- 其他文件 → 标记为最佳实践

---

## 📝 支持的文件格式

| 格式 | 处理方式 | 存储粒度 | 特点 |
|------|---------|---------|------|
| **PDF** | PyMuPDF 解析 | 按页存储 | 保留分页信息，可定位到具体页码 |
| **Markdown** | 直接读取 | 分段存储 | 保留格式，长文档自动分段 |
| **TXT** | 包装为 Markdown | 分段存储 | 纯文本支持 |
| **DOCX** | python-docx/pandoc | 分段存储 | Word 文档支持 |

**统一存储**：所有格式最终都存入 **ChromaDB**，不保留本地文件！

---

## 🔍 查询知识库

### 方式 1: 使用查询工具（推荐）

```bash
# 查看知识库状态
python scripts/kb_query.py status

# 输出示例：
# 📊 知识库状态
# 文档数量: 127
# 嵌入模型: bge-m3:latest
# 向量存储: ChromaDB

# 查询知识库
python scripts/kb_query.py query "ESP32 如何配置 WiFi？"

# 输出示例：
# 🔍 查询: ESP32 如何配置 WiFi？
# 
# 📄 结果 1 (相似度: 0.89)
# 来源: esp32_datasheet.pdf 第 45 页
# 内容: WiFi 配置需要先包含 <WiFi.h> 头文件...
```

### 方式 2: 在 Issue 中使用

在 GitHub Issue 中 `@agent` 并提问：

```markdown
@agent SD3031 温度传感器如何读取数据？
```

Agent 会自动：
1. 检索知识库中的 SD3031 文档
2. 找到相关的寄存器说明和代码示例
3. 生成完整的回复

---

## 📊 性能参考

### 同步性能

| 文件类型 | 文件大小 | 处理时间 | 存储数量 |
|---------|---------|---------|---------|
| PDF (110页) | 2.2MB | ~10s | 110 条向量 |
| Markdown | 50KB | ~1s | 1-3 条向量 |
| TXT | 20KB | ~1s | 1-2 条向量 |
| DOCX | 100KB | ~2s | 1-3 条向量 |

### 检索性能

- **延迟**: ~0.2ms/查询
- **支持规模**: 1万+ 文档
- **召回率**: 95%+

---

## 🔧 高级配置

### PDF 处理优化

```bash
# PDF 处理线程数（默认 CPU/4）
KB_PDF_WORKERS=6

# 启用并行的页数阈值（3页以上）
KB_PDF_PARALLEL_THRESHOLD=3
```

### 嵌入模型选择

```bash
# 高维度，高精度（1024维，推荐）
KB_EMBEDDING_MODEL=bge-m3:latest

# 中等维度，快速（768维）
KB_EMBEDDING_MODEL=nomic-embed-text:latest

# 低维度，最快（384维）
KB_EMBEDDING_MODEL=all-minilm:latest
```

### 多 Ollama 实例负载均衡

```bash
# 配置多个 Ollama 实例提高并发
KB_EMBEDDING_HOST=http://localhost:11434,http://localhost:11435,http://localhost:11436
```

---

## 🐛 故障排查

### 问题 1: 同步失败

```bash
# 检查日志
tail -f /tmp/github_kb_sync.log

# 常见原因：
# 1. GitHub Token 过期 → 重新生成 Token
# 2. 网络问题 → 检查代理设置 HTTP_PROXY
# 3. Ollama 未启动 → curl http://localhost:11434/api/tags
```

### 问题 2: 文档已同步但查询不到

```bash
# 检查 ChromaDB 中的文档
python scripts/kb_query.py status

# 如果数量不对，可能是维度不匹配，重建：
rm -rf /home/tj/chroma_db
python scripts/github_repo_watcher.py --sync
```

### 问题 3: PDF 处理慢

```bash
# 检查当前线程数配置
echo $KB_PDF_WORKERS

# 增加线程数（根据 CPU 核心数调整）
export KB_PDF_WORKERS=8

# 使用 PyMuPDF（已默认启用，比 pdfplumber 快 70 倍）
```

---

## 📖 目录说明

| 路径 | 用途 | 说明 |
|------|------|------|
| `/home/tj/chroma_db` | ChromaDB 存储 | 所有文档向量存储于此 |
| `/home/tj/github-agent-v2` | 工作目录 | 临时下载文件（自动清理） |
| `/home/tj/state` | 同步状态 | 记录已同步文件的 SHA |

**注意**：`knowledge_base/chips/` 和 `knowledge_base/best_practices/` 不再用于存储同步的文件！

---

## 🎉 完成！

现在你可以：
1. 向 GitHub 仓库推送文档，自动同步到知识库
2. 在 Issue 中 `@agent` 查询技术问题
3. 享受毫秒级的知识检索体验

**下一步**：查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解详细架构设计。
