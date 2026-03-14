# 知识库元数据格式规范

本文档定义 ChromaDB 中存储文档的元数据字段规范。

---

## 📋 元数据字段总览

### 通用字段（所有文档类型）

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `source` | string | ✅ | 原始文件路径（GitHub 路径） |
| `doc_type` | string | ✅ | 文档类型：`pdf` / `document` |
| `file_ext` | string | ✅ | 文件扩展名：`.pdf` / `.md` / `.txt` / `.docx` |
| `doc_id` | string | ✅ | 文档唯一标识符 |
| `content_preview` | string | ✅ | 内容前200字符预览 |
| `processed_at` | float | ✅ | 处理时间戳（Unix timestamp） |
| `category` | string | ⚪ | 文档分类：`chip_doc` / `best_practice` |

### PDF 特有字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `page` | int | ✅ | 页码（从1开始） |
| `total_pages` | int | ✅ | PDF 总页数 |
| `vendor` | string | ⚪ | 芯片厂商（从文件名提取） |
| `chip` | string | ⚪ | 芯片型号（从文件名提取） |

### 分段文档特有字段（MD/TXT/DOCX）

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `chunk_index` | int | ✅ | 当前段索引（从1开始） |
| `total_chunks` | int | ✅ | 总段数 |

### ChromaDB 自动添加字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `_text_preview` | string | ChromaDB 自动添加的文本预览 |

---

## 📄 完整示例

### PDF 文档元数据示例

```json
{
  "source": "datasheet/bmi161/bmi161_datasheet.pdf",
  "doc_type": "pdf",
  "file_ext": ".pdf",
  "doc_id": "bmi161_p101_0a7cfb5bfe571e52",
  "content_preview": "BMI160 Data sheet Page 101 BST-BMI160-DS000-07 | Revision 0.8 | February 2015 Bosch Sensortec...",
  "processed_at": 1773452485.4445004,
  "category": "chip_doc",
  "page": 101,
  "total_pages": 110,
  "vendor": "bosch",
  "chip": "bmi161",
  "_text_preview": "BMI160 Data sheet Page 101 BST-BMI160-DS000-07..."
}
```

### Markdown 文档元数据示例

```json
{
  "source": "guides/i2c_protocol.md",
  "doc_type": "document",
  "file_ext": ".md",
  "doc_id": "i2c_protocol_c3a5d2e8f9b1a7c4",
  "content_preview": "# I2C 通信协议指南\n\n## 概述\nI2C（Inter-Integrated Circuit）是一种串行通信总线...",
  "processed_at": 1773452624.0220838,
  "category": "best_practice",
  "chunk_index": 1,
  "total_chunks": 3,
  "_text_preview": "# I2C 通信协议指南\n\n## 概述\nI2C（Inter-Integrated Circuit）..."
}
```

### TXT 文档元数据示例

```json
{
  "source": "guides/sensor_notes.txt",
  "doc_type": "document",
  "file_ext": ".txt",
  "doc_id": "sensor_notes_9f8e7d6c5b4a3210",
  "content_preview": "# sensor_notes\n\n```\n温度传感器使用注意事项：\n1. 避免在高温环境下使用...\n```",
  "processed_at": 1773452700.1234567,
  "category": "best_practice",
  "chunk_index": 1,
  "total_chunks": 1
}
```

### DOCX 文档元数据示例

```json
{
  "source": "guides/coding_standards.docx",
  "doc_type": "document",
  "file_ext": ".docx",
  "doc_id": "coding_standards_a1b2c3d4e5f67890",
  "content_preview": "编码规范\n\n1. 命名规范\n变量名使用小写字母和下划线...",
  "processed_at": 1773452800.9876543,
  "category": "best_practice",
  "chunk_index": 2,
  "total_chunks": 5
}
```

---

## 🏷️ 字段详解

### `source`

**用途**：标识文档的原始来源，用于去重和溯源

**格式**：GitHub 仓库内的文件路径

**示例**：
- `datasheet/bmi161/bmi161_datasheet.pdf`
- `guides/i2c_protocol.md`
- `examples/sensor_demo.txt`

**查询用途**：
```python
# 删除指定文档的所有向量
vector_store.delete_by_source("datasheet/bmi161/bmi161_datasheet.pdf")

# 查询指定文档
result = collection.get(where={"source": "datasheet/bmi161/bmi161_datasheet.pdf"})
```

---

### `doc_type`

**用途**：区分 PDF 和其他文档类型

**取值**：
- `pdf` - PDF 文档（按页存储）
- `document` - Markdown/TXT/DOCX（按段存储）

**查询用途**：
```python
# 只查询 PDF 文档
result = collection.get(where={"doc_type": "pdf"})

# 只查询普通文档
result = collection.get(where={"doc_type": "document"})
```

---

### `category`

**用途**：区分芯片文档和最佳实践文档

**取值**：
- `chip_doc` - 芯片数据手册、硬件参考
- `best_practice` - 开发指南、编码规范

**自动分类规则**：
```python
path_lower = original_path.lower()
if any(keyword in path_lower for keyword in ["chip", "芯片", "hardware", "datasheet"]):
    category = "chip_doc"
else:
    category = "best_practice"
```

**查询用途**：
```python
# 只查询芯片文档
result = collection.get(where={"category": "chip_doc"})

# 只查询最佳实践
result = collection.get(where={"category": "best_practice"})
```

---

### `doc_id`

**用途**：文档的唯一标识符，用于去重和精确定位

**生成规则**：

**PDF**：
```python
f"{chip}_p{page_num}_{hash}"
# 示例: "bmi161_p101_0a7cfb5bfe571e52"
```

**Document**：
```python
f"{filename}_{hash}"
# 示例: "i2c_protocol_c3a5d2e8f9b1a7c4"
```

---

### `page` / `chunk_index`

**用途**：定位文档内的具体位置

| 文档类型 | 字段名 | 含义 |
|---------|--------|------|
| PDF | `page` | 页码（1-N） |
| MD/TXT/DOCX | `chunk_index` | 段索引（1-N） |

**应用场景**：
- 引用来源时显示具体页码
- 重建原始文档结构

---

### `vendor` / `chip`（PDF 特有）

**用途**：标识硬件芯片信息

**提取规则**：
```python
# 从文件名提取，如：
# "esp32_datasheet.pdf" -> vendor: "espressif", chip: "esp32"
# "bmi160_datasheet.pdf" -> vendor: "bosch", chip: "bmi160"
```

**查询用途**：
```python
# 查询特定芯片的所有文档
result = collection.get(where={"chip": "esp32"})

# 查询特定厂商的所有芯片
result = collection.get(where={"vendor": "bosch"})
```

---

## 🔍 查询示例

### 1. 查询特定 PDF 的所有页

```python
from knowledge_base.kb_service import ChromaVectorStore

store = ChromaVectorStore()
result = store.collection.get(
    where={"source": "datasheet/bmi161/bmi161_datasheet.pdf"},
    limit=1000
)

# 按页码排序
pages = sorted(result['metadatas'], key=lambda x: x['page'])
for page in pages:
    print(f"Page {page['page']}: {page['content_preview'][:50]}...")
```

### 2. 查询特定芯片的所有文档

```python
result = store.collection.get(
    where={"chip": "esp32"},
    limit=100
)

print(f"找到 {len(result['ids'])} 条关于 ESP32 的记录")
```

### 3. 查询最佳实践文档

```python
result = store.collection.get(
    where={"category": "best_practice"},
    limit=100
)

# 去重统计文档数
sources = set(m['source'] for m in result['metadatas'])
print(f"共有 {len(sources)} 篇最佳实践文档")
```

### 4. 查询最近处理的文档

```python
import time

# 获取24小时内处理的文档
one_day_ago = time.time() - 24 * 3600

result = store.collection.get(
    where={"processed_at": {"$gte": one_day_ago}},
    limit=100
)
```

---

## 🛠️ 元数据修改

### 批量更新元数据

```python
# 为所有 PDF 添加 doc_type（如果需要修复）
result = store.collection.get()

for i, meta in enumerate(result['metadatas']):
    if 'page' in meta and 'doc_type' not in meta:
        # 更新元数据
        store.collection.update(
            ids=[result['ids'][i]],
            metadatas=[{**meta, "doc_type": "pdf", "file_ext": ".pdf"}]
        )
```

### 删除特定类型的文档

```python
# 删除所有 TXT 文档
result = store.collection.get(where={"file_ext": ".txt"})
if result['ids']:
    store.collection.delete(ids=result['ids'])
    print(f"删除了 {len(result['ids'])} 条 TXT 记录")
```

---

## 📊 元数据统计

### 查看文档类型分布

```python
from collections import Counter

result = store.collection.get()

doc_types = Counter(m.get('doc_type', 'unknown') for m in result['metadatas'])
print("文档类型分布:")
for doc_type, count in doc_types.most_common():
    print(f"  {doc_type}: {count}")
```

### 查看分类分布

```python
categories = Counter(m.get('category', 'unknown') for m in result['metadatas'])
print("分类分布:")
for category, count in categories.most_common():
    print(f"  {category}: {count}")
```

### 查看芯片分布

```python
chips = Counter(m.get('chip', 'unknown') for m in result['metadatas'] if m.get('chip'))
print("芯片分布:")
for chip, count in chips.most_common():
    print(f"  {chip}: {count} 页")
```

---

## 📝 版本历史

### v2.2.0（当前）
- ✅ 添加 `doc_type` 字段区分 PDF 和普通文档
- ✅ 添加 `file_ext` 字段标识文件类型
- ✅ 添加 `category` 字段分类文档
- ✅ PDF 和 Document 统一元数据格式

### v2.1.0
- ✅ PDF 直接处理，不按页转 Markdown
- ✅ 添加 `page`, `total_pages` 字段
- ✅ 添加 `vendor`, `chip` 字段

### v2.0.0
- ✅ 初始元数据格式
- ✅ 基础字段：`source`, `doc_id`, `content_preview`
