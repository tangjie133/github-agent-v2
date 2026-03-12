# 👋 新上下文？请先阅读这里！

> 如果你是因为上下文重启而看到这个文件，请按以下步骤恢复项目状态。

## 🚀 3 分钟快速恢复

### 1. 了解项目状态 (30秒)

**GitHub Agent V2 已完成开发！**

- ✅ Phase 1-5 全部完成
- ✅ 38 个 Python 文件，6600 行代码
- ✅ 端到端测试通过
- ✅ 文档完整

### 2. 查看关键文件 (1分钟)

```bash
# 项目概览
cat PROGRESS.md

# 详细文档
cat README.md

# 架构设计
cat ARCHITECTURE.md
```

### 3. 验证环境 (1分钟)

```bash
# 检查环境变量
env | grep -E "(GITHUB|OLLAMA)"

# 检查 Ollama
curl -s http://localhost:11434/api/tags | head -1

# 运行测试
python3 tests/test_e2e.py
```

### 4. 启动服务 (30秒)

```bash
./scripts/start.sh --port 8080
```

---

## 📂 核心文件速查

| 文件 | 用途 |
|------|------|
| `PROGRESS.md` | **开发进度记录** (先读这个) |
| `README.md` | 项目介绍和使用指南 |
| `ARCHITECTURE.md` | 系统架构设计文档 |
| `.env.example` | 环境变量模板 |
| `main.py` | 程序入口 |
| `scripts/start.sh` | 启动脚本 |

---

## 🏗️ 项目结构

```
github-agent-v2/
├── core/              # 核心层 (Processor, Models)
├── github_api/        # GitHub API 封装
├── cloud_agent/       # OpenClaw 意图识别
├── knowledge_base/    # RAG 知识库
├── code_executor/     # Ollama 代码生成
├── config/            # 配置管理
├── utils/             # 工具函数
├── tests/             # 测试框架
├── webhook/           # Webhook 服务
├── scripts/           # 部署脚本
├── main.py            # 主入口
├── PROGRESS.md        # 📌 开发进度记录
├── README.md          # 项目文档
└── ARCHITECTURE.md    # 架构文档
```

---

## ⚙️ 关键配置

### 必需
```bash
GITHUB_APP_ID=xxx
GITHUB_PRIVATE_KEY_PATH=/path/to/key.pem
GITHUB_WEBHOOK_SECRET=xxx
```

### 可选
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3-coder:30b
OPENCLAW_URL=http://localhost:3000
```

---

## ✅ 快速验证清单

- [ ] `python3 --version` # 需要 3.12+
- [ ] `curl http://localhost:11434/api/tags` # Ollama 运行中
- [ ] `env | grep GITHUB_APP_ID` # 环境变量已设置
- [ ] `python3 tests/test_e2e.py` # 测试通过

---

## 🆘 需要帮助？

1. 查看 **PROGRESS.md** 了解详细状态
2. 查看 **README.md** 了解使用方法
3. 查看 **ARCHITECTURE.md** 了解系统设计

---

**项目状态:** ✅ 已完成并可运行

**最后更新:** 2026-03-12
