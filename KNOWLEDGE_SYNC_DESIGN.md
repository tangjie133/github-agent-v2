# 知识库同步设计 - 可移植的学习成果

## 设计目标

1. **可移植性**: 学习成果可以导出到资料仓库，在新环境部署时拉取
2. **共享性**: 团队可以共享成功案例和代码模式
3. **版本控制**: 知识数据可以版本管理，支持回滚
4. **自动化**: 学习成功后自动同步到资料仓库

## 架构设计

```
┌─────────────────┐     学习成功      ┌─────────────────┐
│   GitHub Agent  │ ───────────────→ │  本地知识库     │
│   (运行时)      │                  │  (SQLite/JSON)  │
└─────────────────┘                  └────────┬────────┘
       │                                      │
       │ 自动同步                             │ 导出
       │                                      │
       ▼                                      ▼
┌─────────────────┐                  ┌─────────────────┐
│   资料仓库      │ ←────────────────│  知识导出器     │
│ (GitHub Repo)   │    定期推送      │                 │
└─────────────────┘                  └─────────────────┘
       ▲                                      
       │ 新环境部署                            
       │                                      
┌─────────────────┐                           
│   新 GitHub     │                           
│   Agent 实例    │                           
└─────────────────┘                           
```

## 知识数据格式

### 1. 成功案例库 (cases/)

```json
// cases/2026/03/sensor_filter_a0.json
{
  "schema_version": "1.0",
  "case_id": "case_20260312_001",
  "created_at": "2026-03-12T10:30:00Z",
  "repository": "owner/arduino-project",
  "issue": {
    "number": 42,
    "title": "Fix analogRead noise on A0",
    "body": "The sensor readings from A0 are very noisy...",
    "keywords": ["analogRead", "A0", "noise", "filter", "sensor"],
    "embedding": [0.12, -0.05, 0.89, ...],  // 768维向量
    "language": "arduino",
    "complexity": "simple"
  },
  "solution": {
    "description": "Add moving average filter to smooth sensor readings",
    "approach": "filter",
    "files_modified": [
      {
        "path": "sensor.ino",
        "language": "arduino",
        "changes": [
          {
            "type": "add",
            "description": "Add filter array and variables"
          },
          {
            "type": "modify",
            "description": "Replace direct read with filtered read"
          }
        ]
      }
    ],
    "code_pattern": {
      "pattern_type": "moving_average_filter",
      "search_context": "int value = analogRead(A0);",
      "replacement_template": "// Moving average filter\nint readings[{window_size}];\nint readIndex = 0;\nint total = 0;\n// ... filter implementation",
      "parameters": {
        "window_size": {
          "type": "int",
          "default": 10,
          "description": "Filter window size"
        }
      }
    },
    "arduino_specific": {
      "pins_involved": ["A0"],
      "libraries_used": ["Wire"],
      "libraries_added": [],
      "memory_impact": "low"  // SRAM usage
    }
  },
  "outcome": {
    "success": true,
    "pr_number": 43,
    "pr_merged": true,
    "user_feedback": "positive",
    "test_results": "passed"
  },
  "metadata": {
    "agent_version": "2.1.0",
    "model_used": "qwen3-coder:30b",
    "confidence_score": 0.92,
    "reviewed_by_human": false
  }
}
```

### 2. 代码模式库 (patterns/)

```json
// patterns/arduino/moving_average_filter.json
{
  "pattern_id": "pattern_moving_average_001",
  "schema_version": "1.0",
  "created_at": "2026-03-12T10:30:00Z",
  "updated_at": "2026-03-12T10:30:00Z",
  "usage_count": 5,
  "success_rate": 1.0,
  
  "pattern": {
    "name": "moving_average_filter",
    "description": "Apply moving average filter to analog sensor readings",
    "language": "arduino",
    "category": "filtering",
    "complexity": "simple",
    
    "applicability": {
      "keywords": ["analogRead", "noise", "smooth", "filter"],
      "code_signatures": [
        "analogRead\\(A\\d+\\)"
      ],
      "file_patterns": ["*.ino", "*.cpp"]
    },
    
    "template": {
      "variables_section": "int readings[{window_size}];\nint readIndex = 0;\nint total = 0;\nint average = 0;",
      "setup_section": "// Initialize filter\nfor (int i = 0; i < {window_size}; i++) {\n  readings[i] = 0;\n}",
      "loop_section": "// Moving average filter\ntotal = total - readings[readIndex];\nreadings[readIndex] = analogRead({pin});\ntotal = total + readings[readIndex];\nreadIndex++;\nif (readIndex >= {window_size}) readIndex = 0;\naverage = total / {window_size};",
      "parameters": {
        "window_size": {
          "type": "int",
          "default": 10,
          "min": 2,
          "max": 100,
          "description": "Number of samples for averaging"
        },
        "pin": {
          "type": "string",
          "placeholder": "A0",
          "description": "Analog pin to read from"
        }
      }
    },
    
    "examples": [
      {
        "case_id": "case_20260312_001",
        "repo": "owner/arduino-project",
        "effectiveness": "high"
      }
    ]
  },
  
  "metadata": {
    "derived_from_cases": ["case_20260312_001", "case_20260312_005"],
    "reviewed": true,
    "author": "agent-learning"
  }
}
```

### 3. 错误模式库 (anti_patterns/)

```json
// anti_patterns/arduino/delay_in_loop.json
{
  "anti_pattern_id": "anti_delay_loop_001",
  "schema_version": "1.0",
  
  "pattern": {
    "name": "delay_in_main_loop",
    "description": "Using delay() in main loop blocks other operations",
    "language": "arduino",
    "severity": "warning",
    
    "detection": {
      "code_pattern": "delay\\(\\d+\\);",
      "context": "loop() function"
    },
    
    "solution": {
      "description": "Use millis() based non-blocking approach",
      "replacement_pattern": "pattern_non_blocking_timer",
      "explanation": "delay() blocks all execution. Use millis() to check elapsed time without blocking."
    }
  },
  
  "occurrences": [
    {
      "case_id": "case_20260310_003",
      "repo": "owner/project-a",
      "resolved": true
    }
  ]
}
```

### 4. 索引文件 (index.json)

```json
{
  "schema_version": "1.0",
  "last_updated": "2026-03-12T12:00:00Z",
  "stats": {
    "total_cases": 156,
    "total_patterns": 42,
    "total_anti_patterns": 18,
    "language_distribution": {
      "arduino": 89,
      "python": 67
    },
    "success_rate": 0.87
  },
  
  "indices": {
    "by_keyword": {
      "analogRead": ["case_20260312_001", "case_20260311_045"],
      "filter": ["case_20260312_001", "pattern_moving_average_001"]
    },
    "by_pin": {
      "A0": ["case_20260312_001", "case_20260310_023"],
      "13": ["case_20260309_012"]
    },
    "by_library": {
      "Wire": ["case_20260312_001", "case_20260311_032"]
    }
  },
  
  "recent_additions": [
    {
      "type": "case",
      "id": "case_20260312_001",
      "date": "2026-03-12T10:30:00Z"
    }
  ]
}
```

## 同步机制

### 1. 自动推送流程

```python
class KnowledgeSyncManager:
    """知识库同步管理器"""
    
    def __init__(self, 
                 knowledge_repo_url: str,
                 local_kb_path: Path,
                 github_token: str):
        self.knowledge_repo_url = knowledge_repo_url
        self.local_kb_path = local_kb_path
        self.github_token = github_token
        
    def on_learning_success(self, case: SuccessCase):
        """学习成功后的回调"""
        # 1. 保存到本地
        self.save_to_local(case)
        
        # 2. 尝试推送到资料仓库
        try:
            self.push_to_knowledge_repo(case)
        except Exception as e:
            # 推送失败不阻塞主流程，记录待同步
            self.mark_pending_sync(case)
    
    def push_to_knowledge_repo(self, case: SuccessCase):
        """推送到资料仓库"""
        # 1. 克隆/拉取资料仓库
        repo_path = self.ensure_knowledge_repo()
        
        # 2. 生成文件路径
        case_file = self.generate_case_path(case)
        
        # 3. 检查是否已存在（去重）
        if self.case_exists(repo_path, case_file):
            # 更新现有案例
            self.update_case(repo_path, case_file, case)
        else:
            # 创建新案例
            self.create_case(repo_path, case_file, case)
        
        # 4. 更新索引
        self.update_index(repo_path, case)
        
        # 5. 提交并推送
        self.commit_and_push(repo_path, case)
    
    def generate_case_path(self, case: SuccessCase) -> Path:
        """生成案例文件路径"""
        # 按年月组织，避免单目录文件过多
        date = datetime.fromisoformat(case.created_at)
        return Path(f"cases/{date.year}/{date.month:02d}/{case.case_id}.json")
```

### 2. 定期同步策略

```python
class KnowledgeSyncScheduler:
    """知识库同步调度器"""
    
    def __init__(self, sync_manager: KnowledgeSyncManager):
        self.sync_manager = sync_manager
        self.pending_queue = []
        
    def start(self):
        """启动定时同步"""
        # 每 30 分钟检查一次待同步项
        schedule.every(30).minutes.do(self.sync_pending)
        
        # 每天一次完整同步（处理冲突）
        schedule.every().day.at("02:00").do(self.full_sync)
    
    def sync_pending(self):
        """同步待处理项"""
        for case in self.pending_queue[:]:
            try:
                self.sync_manager.push_to_knowledge_repo(case)
                self.pending_queue.remove(case)
            except Exception as e:
                logger.warning(f"同步失败，保留在队列: {case.case_id}")
    
    def full_sync(self):
        """完整同步（拉取远程更新）"""
        # 1. 拉取远程最新
        self.sync_manager.pull_from_knowledge_repo()
        
        # 2. 检测冲突
        conflicts = self.detect_conflicts()
        
        # 3. 自动合并或标记人工处理
        for conflict in conflicts:
            self.resolve_conflict(conflict)
```

### 3. 新环境初始化

```python
class KnowledgeInitializer:
    """知识库初始化器（新环境使用）"""
    
    def __init__(self, 
                 knowledge_repo_url: str,
                 local_kb_path: Path,
                 github_token: str):
        self.knowledge_repo_url = knowledge_repo_url
        self.local_kb_path = local_kb_path
        self.github_token = github_token
        
    def initialize(self, sync_mode: str = "full"):
        """初始化本地知识库
        
        Args:
            sync_mode: 
                - "full": 拉取全部知识数据
                - "recent": 只拉取最近 N 天
                - "minimal": 只拉取模式库，不拉案例详情
        """
        # 1. 克隆资料仓库
        repo_path = self.clone_knowledge_repo()
        
        # 2. 根据模式导入
        if sync_mode == "full":
            self.import_all_cases(repo_path)
        elif sync_mode == "recent":
            self.import_recent_cases(repo_path, days=30)
        elif sync_mode == "minimal":
            self.import_patterns_only(repo_path)
        
        # 3. 重建向量索引
        self.rebuild_embeddings()
        
        # 4. 验证完整性
        self.verify_integrity()
        
        logger.info(f"知识库初始化完成，模式: {sync_mode}")
```

## 版本控制策略

### 1. 案例版本管理

```json
{
  "case_id": "case_20260312_001",
  "version": "1.2",
  "version_history": [
    {
      "version": "1.0",
      "date": "2026-03-12T10:30:00Z",
      "change": "initial"
    },
    {
      "version": "1.1", 
      "date": "2026-03-12T14:20:00Z",
      "change": "added_test_results",
      "diff": "..."
    }
  ]
}
```

### 2. 冲突解决规则

| 冲突场景 | 解决策略 |
|---------|---------|
| 同一案例本地和远程都更新 | 合并字段，保留最新时间戳 |
 | 本地新案例 vs 远程新案例 | 都保留，可能产生重复（人工审核）|
| 案例被远程删除但本地有更新 | 保留本地版本，标记待审核 |
| 模式参数冲突 | 创建新模式版本，保留旧版本 |

## 资料仓库结构

```
knowledge-base-repo/
├── README.md                    # 知识库说明
├── SCHEMA.md                    # 数据格式文档
├── index.json                   # 主索引
│
├── cases/                       # 成功案例
│   ├── 2026/
│   │   ├── 03/
│   │   │   ├── case_20260312_001.json
│   │   │   └── case_20260312_002.json
│   │   └── 02/
│   └── 2025/
│
├── patterns/                    # 代码模式
│   ├── arduino/
│   │   ├── moving_average_filter.json
│   │   ├── debounce_button.json
│   │   └── i2c_scanner.json
│   └── python/
│       ├── error_handling.json
│       └── logging_setup.json
│
├── anti_patterns/               # 反模式/常见错误
│   └── arduino/
│       ├── delay_in_loop.json
│       └── blocking_serial.json
│
├── chips/                       # 芯片特定知识
│   ├── SD3031/
│   │   ├── register_map.json
│   │   └── common_issues.json
│   └── DS3231/
│
├── stats/                       # 统计数据
│   ├── monthly_report_2026_03.json
│   └── learning_progress.json
│
└── .github/
    └── workflows/
        └── validate-schema.yml  # 数据格式验证
```

## 隐私和安全考虑

1. **敏感信息过滤**: 自动移除代码中的 API Key、密码等
2. **仓库隐私**: 资料仓库可以是私有的
3. **权限控制**: 使用 GitHub Token 控制读写权限
4. **审计日志**: 记录谁添加了什么知识

## 实现优先级

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| Phase 1 | 案例存储结构 + 本地保存 | 🔴 高 |
| Phase 2 | 推送到资料仓库 | 🔴 高 |
| Phase 3 | 新环境拉取初始化 | 🟡 中 |
| Phase 4 | 模式提取和复用 | 🟡 中 |
| Phase 5 | 自动冲突解决 | 🟢 低 |

---

你觉得这个设计如何？是否需要调整某些部分，或者你想先从哪个阶段开始实现？