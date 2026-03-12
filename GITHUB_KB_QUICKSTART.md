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

- [知识库完整指南](./knowledge_base/README.md)
- [项目架构设计](./ARCHITECTURE.md)
- [主 README](./README.md)
