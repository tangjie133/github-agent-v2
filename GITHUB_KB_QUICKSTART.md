# GitHub 仓库知识库快速上手指南

将你的数据手册存入 GitHub 仓库，自动同步到知识库。

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

# 运行配置向导
./scripts/setup_github_kb.sh

# 按提示输入：
# - GitHub 仓库: tangjie133/knowledge-base
# - 分支: main
# - GitHub Token: （可选，用于私有仓库）
# - Webhook Secret: （可选，用于安全验证）
```

### 步骤 2: 选择同步方式

#### 方式 A: Webhook 实时同步（推荐团队使用）

**启动接收服务器：**
```bash
python scripts/github_webhook_server.py --port 9000
```

**配置 GitHub Webhook：**
1. 打开 GitHub 仓库 → Settings → Webhooks
2. 点击 "Add webhook"
3. 填写配置：
   - **Payload URL**: `http://your-server-ip:9000/webhook`
   - **Content type**: `application/json`
   - **Secret**: （如果你在步骤1设置了）
   - **Which events?**: "Just the push event"
4. 点击 "Add webhook"

**测试：**
```bash
# 向仓库推送一个文件
git add SD3031.pdf
git commit -m "添加 SD3031 数据手册"
git push

# 观察服务器日志，自动同步
```

#### 方式 B: 定时同步（推荐个人使用）

```bash
# 后台运行，每 5 分钟检查一次
python scripts/github_repo_watcher.py --daemon --interval 300

# 或手动同步一次
python scripts/github_repo_watcher.py --sync
```

---

## 📁 仓库文件组织建议

```
knowledge-base/           # GitHub 仓库根目录
├── chips/               # 芯片数据手册
│   ├── SD3031.pdf
│   ├── DS3231.md
│   └── STM32F103.txt
├── guides/              # 开发指南
│   ├── python_driver_guide.md
│   └── i2c_protocol.docx
└── README.md           # 仓库说明
```

**规则：**
- 文件名包含 "chip" 或 "芯片" → 存入 `knowledge_base/chips/`
- 其他文件 → 存入 `knowledge_base/best_practices/`

---

## 📝 支持的文件格式

| 格式 | 处理方式 | 建议 |
|------|---------|------|
| `.md` | 直接使用 | ⭐ 推荐，效果最佳 |
| `.txt` | 转为 Markdown | 适用于纯文本文档 |
| `.pdf` | 提取文本后转换 | 数据手册常用格式 |
| `.docx` | 转为 Markdown | Word 文档 |

---

## 🔍 查询知识库

### 方式 1: 使用查询工具（推荐）

```bash
# 查看完整状态
python scripts/kb_query.py

# 查询特定内容
python scripts/kb_query.py 'SAMD21 芯片规格'

# 查看统计
python scripts/kb_query.py -s

# 列出本地文件
python scripts/kb_query.py -l

# 重新加载知识库（同步后使用）
python scripts/kb_query.py -r
```

### 方式 2: 直接 API 调用

```bash
# 查看统计
curl http://localhost:8000/stats

# 健康检查
curl http://localhost:8000/health

# 查询知识库
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SAMD21", "top_k": 3}'
```

### 方式 3: 查看原始文件

```bash
# 芯片文档
ls -la knowledge_base/chips/
cat knowledge_base/chips/SAMD21.md

# 最佳实践
ls -la knowledge_base/best_practices/
cat knowledge_base/best_practices/README.md
```

---

## 📊 向量化说明

### 什么是向量化？

知识库使用 **nomic-embed-text** 模型将文本转换为 768 维向量：

```
文本: "SAMD21 是一款 ARM Cortex-M0+ 微控制器"
      ↓
向量: [0.023, -0.156, 0.089, ..., 0.034] (768 个数字)
      ↓
存储: 内存中的向量库
```

### 向量库特点

| 特性 | 说明 |
|------|------|
| 存储位置 | 内存中（启动时加载） |
| 向量维度 | 768 维 |
| 相似度算法 | 余弦相似度 |
| 持久化 | 原始 Markdown 文件 |

### 为什么向量在内存中？

1. **快速查询** - 内存访问比磁盘快 1000 倍
2. **实时更新** - 修改文件后重新加载即可
3. **无需数据库** - 简化部署，适合中小规模知识库

---

## 🔄 同步流程

```
GitHub Push
    ↓
Webhook 触发 / 定时同步
    ↓
download_file() - 下载原始文件
    ↓
convert_to_markdown() - 转换格式
    ↓
保存到 knowledge_base/chips/
    ↓
通知 KB Service /reload
    ↓
重新生成向量嵌入
    ↓
完成！
```

### 手动同步命令

```bash
# 立即同步一次
python scripts/github_repo_watcher.py --sync

# 强制重新同步所有文件
python scripts/github_repo_watcher.py --sync --force

# 后台持续监控
python scripts/github_repo_watcher.py --daemon --interval 300
```

---

## 🔍 查看同步状态

```bash
# 查看已同步的文档
python scripts/github_repo_watcher.py --status

# 输出示例：
# 📊 同步状态: tangjie133/knowledge-base
#    远程文件: 15
#    已同步: 12
#
# 🆕 新文件 (3):
#    - chips/NEW_CHIP.pdf
```

---

## 🔄 完整工作流程

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub 仓库   │     │   知识库同步工具  │     │   KB Service    │
│                 │     │                  │     │                 │
│  chips/         │────▶│  Webhook/定时   │────▶│  加载文档       │
│  ├── SD3031.pdf │push │  监控仓库变化   │     │  向量嵌入       │
│  └── DS3231.md  │     │  转换格式       │     │  提供查询       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       │                                                        │
       │         用户查询 "SD3031 寄存器"                        │
       └────────────────────────────────────────────────────────┘
                              ▼
                    返回相关知识片段
```

---

## 🛠️ 故障排查

### Webhook 不触发
```bash
# 检查服务器是否运行
curl http://localhost:9000/health

# 检查 GitHub Webhook 状态
# 在 GitHub 仓库 → Settings → Webhooks → Recent Deliveries
```

### 同步失败
```bash
# 查看详细日志
python scripts/github_repo_watcher.py --sync

# 检查网络连接
curl https://api.github.com/repos/tangjie133/knowledge-base
```

### PDF 转换失败
```bash
# 安装 pdftotext
sudo apt-get install poppler-utils

# 验证安装
which pdftotext
```

### 文档数量为 0？

**原因:**
1. GitHub 同步未启用
2. 同步尚未完成
3. 知识库未重新加载

**解决:**
```bash
# 1. 检查配置
grep KB_GITHUB_SYNC_ENABLED .env

# 2. 手动同步
python scripts/github_repo_watcher.py --sync

# 3. 重新加载
python scripts/kb_query.py -r
```

---

## 💡 最佳实践

1. **使用 Markdown 格式**：效果最好，无需转换
2. **文件命名规范**：使用芯片型号，如 `SD3031.md`
3. **添加文档头**：便于检索
   ```markdown
   # SD3031 实时时钟芯片
   
   ## 简介
   SD3031 是一款...
   ```
4. **定期清理旧版本**：避免知识库过大

---

## 📚 相关文档

- [项目架构设计](./ARCHITECTURE.md)
- [主 README](./README.md)
