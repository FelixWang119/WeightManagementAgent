# LangChain 技术架构文档

**文档版本**: 2.0
**创建日期**: 2026-02-07
**最后更新**: 2026-02-13
**状态**: 生产就绪

---

## 一、架构概述

### 1.1 技术选型

| 组件 | 开发环境 | 生产环境（预留） |
|------|---------|----------------|
| **LLM** | Qwen (通义千问) | OpenAI GPT-4 / Claude 3 |
| **嵌入模型** | SimpleEmbedding (词频哈希) | OpenAI Embeddings |
| **向量数据库** | ChromaDB (本地) | Pinecone / Milvus |
| **Agent 框架** | SimpleAgent (推荐) | SimpleAgent (生产验证) |
| **部署方式** | SQLite + 本地文件 | PostgreSQL + 云存储 |

### 1.2 目录结构

```
services/
├── langchain/              # LangChain 核心模块
│   ├── __init__.py
│   ├── base.py             # 配置中心
│   ├── memory.py           # 记忆管理（简化版）
│   ├── tools.py            # 工具函数
│   ├── agents.py           # Agent 入口点（兼容层）
│   ├── agent.py            # 主实现（最新版本）
│   ├── agent_simple.py     # 简化版（推荐使用）
│   ├── agent_selector.py   # 版本选择器
│   ├── monitoring.py       # 性能监控
│   ├── tools.py            # 工具函数
│   └── memory.py           # 记忆管理
├── vectorstore/            # 向量存储模块
│   ├── __init__.py
│   ├── embedding.py        # 嵌入服务（Simple/OpenAI）
│   └── chroma_store.py     # ChromaDB 实现
└── rag/                    # RAG 模块（预留）
    └── ...
```

---

## 二、核心组件

### 2.1 配置中心 (`langchain/base.py`)

**功能**: 统一管理不同 AI 提供商的配置

```python
from services.langchain.base import LangChainConfig

# 获取聊天模型
llm = LangChainConfig.get_chat_model(
    provider="qwen",  # 或 "openai"
    temperature=0.7,
    max_tokens=2000
)

# 获取嵌入模型
embeddings = LangChainConfig.get_embeddings()
```

**生产环境切换**: 修改 `config/settings.py` 中的 `DEFAULT_AI_PROVIDER` 即可。

---

### 2.2 记忆管理系统 (`langchain/memory.py`)

**记忆架构**（简化版）:

| 层级 | 类型 | 容量 | 用途 |
|------|------|------|------|
| **短期记忆** | List[Dict] | 无限制 | 当前对话上下文 |
| **长期记忆** | ChromaDB | 无限 | 用户画像、历史记录 |

```python
from services.langchain.memory import get_user_memory

# 获取用户记忆
memory = await get_user_memory(user_id=1, db=session)

# 保存消息
await memory.save_message("user", "我今天65kg")

# 搜索记忆
results = await memory.search_memory("上周体重", k=5)
```

---

### 2.3 向量存储 (`vectorstore/`)

#### 2.3.1 嵌入服务 (`embedding.py`)

**当前实现**: SimpleEmbedding（词频哈希方案）

```python
from services.vectorstore.embedding import get_embedding_service

# 获取嵌入服务
embedding = get_embedding_service()

# 生成嵌入向量
vector = embedding.embed("我今天65kg")  # 返回 384 维向量
vectors = embedding.embed_batch(["文本1", "文本2"])
```

**特点**:
- 无需 GPU，零依赖冲突
- 完全本地运行，离线可用
- 适合开发测试环境

**嵌入维度**: 384 维（与 Sentence-Transformers 兼容）

#### 2.3.2 升级到 OpenAI Embeddings

```python
from services.vectorstore.embedding import use_openai_embedding

# 切换到 OpenAI Embedding
use_openai_embedding(
    api_key="your-api-key",
    base_url="https://api.openai.com/v1",
    model="text-embedding-3-small"  # 或 text-embedding-3-large
)
```

**对比**:

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| SimpleEmbedding | 免费、本地、零依赖 | 语义理解弱 | 开发测试 |
| OpenAI Embeddings | 高质量语义 | 需 API 费用 | 生产环境 |
| 本地 Sentence-Transformers | 免费、高质量 | 需 GPU/内存 | 私有部署 |

**ChromaDB 向量库**:

```python
from services.vectorstore.chroma_store import get_user_vector_store

# 获取用户的向量存储
store = get_user_vector_store(user_id=1)

# 添加文档
store.add_documents(
    documents=["用户说：我今天65kg"],
    metadatas=[{"category": "weight", "date": "2024-01-01"}]
)

# 相似性搜索
results = store.similarity_search("体重变化", k=5)
```

---

### 2.4 工具函数 (`langchain/tools.py`)

**可用工具**:

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `record_weight` | 记录体重 | 用户说"我今天65kg" |
| `analyze_meal` | 分析餐食 | 用户上传食物图片 |
| `query_history` | 查询历史 | 用户问"上周减了多少" |
| `get_user_profile` | 获取画像 | 了解用户基本信息 |
| `get_today_data` | 获取今日数据 | 查看今天的记录 |

**创建工具**:

```python
from services.langchain.tools import create_tools_for_user

tools = create_tools_for_user(db=session, user_id=1)
# 返回工具列表，可直接传给 Agent
```

---

### 2.5 SimpleAgent (`langchain/agents.py`)

**特点**:

- **轻量级**: 不依赖复杂的 LangChain Agent API
- **记忆集成**: 自动保存和检索上下文
- **降级策略**: LLM 调用失败时回退到旧系统

**使用示例**:

```python
from services.langchain.agents import chat_with_agent

# 对话
result = await chat_with_agent(
    user_id=1,
    db=session,
    message="我今天65kg"
)

print(result["response"])
# Agent 会自动记录体重，并回复用户

# 返回完整信息
{
    "response": "好的，记录今天体重65kg...",
    "intermediate_steps": []  # 当前为空，后续可扩展
}
```

**架构说明**:

```
┌─────────────────────────────────────┐
│           SimpleAgent                │
├─────────────────────────────────────┤
│ 1. 构建系统提示（性格+用户画像）       │
│ 2. 构建对话消息                      │
│ 3. 调用 LLM (Qwen/OpenAI)           │
│ 4. 提取回复内容                      │
│ 5. 保存到记忆系统                    │
└─────────────────────────────────────┘
```

---

## 三、API 集成

### 3.1 对话 API (`api/routes/chat.py`)

**并行运行策略**（开发环境）:

```python
try:
    # 优先使用 LangChain Agent
    result = await chat_with_agent(user_id, db, content)
    response = result["response"]
except Exception as e:
    # 失败时回退到旧系统
    logger.warning(f"LangChain failed: {e}")
    response = await legacy_chat_service(content)
```

**完整流程**:

1. 用户发送消息
2. 加载用户记忆（短期+中期+长期）
3. 构建系统提示（包含用户画像、性格设置）
4. 调用 ReAct Agent
5. Agent 思考是否需要调用工具
6. 执行工具（如记录体重）
7. 生成最终回复
8. 保存对话到记忆系统

---

## 四、数据流

```
用户消息
    │
    ▼
┌─────────────────────────────┐
│     加载记忆                │
│  ├─ 短期: 对话历史         │
│  └─ 长期: 向量检索         │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│     构建提示                │
│  ├─ 性格设置               │
│  ├─ 用户画像               │
│  └─ 回复原则               │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│     SimpleAgent 处理        │
│  1. 调用 LLM               │
│  2. 提取回复               │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│     保存记忆                │
│  ├─ 短期: 对话历史         │
│  └─ 长期: 向量存储         │
└─────────────────────────────┘
    │
    ▼
返回用户回复
```

---

## 五、生产环境迁移指南

### 5.1 嵌入模型切换

**当前实现**: SimpleEmbedding（词频哈希）

```python
# 当前配置
from services.vectorstore.embedding import get_embedding_service
embedding = get_embedding_service()  # 返回 SimpleEmbedding 实例
```

**方案 A: 升级到 OpenAI Embeddings（推荐）**

```python
from services.vectorstore.embedding import use_openai_embedding

# 一键切换
use_openai_embedding(
    api_key="your-openai-api-key",
    base_url="https://api.openai.com/v1",  # 可用代理地址
    model="text-embedding-3-small"  # 高性价比选择
)

# 或使用 Azure OpenAI
use_openai_embedding(
    api_key="your-azure-key",
    base_url="https://your-resource.openai.azure.com/openai/deployments/embedding",
    model="text-embedding-3-small"
)
```

**方案 B: 恢复本地 Sentence-Transformers**

```bash
# 安装依赖
pip install sentence-transformers torch

# 注意：需要 PyTorch 2.4+ 或 NumPy 1.x
pip install "numpy<2"
```

**操作步骤**:

1. **测试新嵌入效果**
   ```python
   # 对比新旧嵌入的搜索结果
   results_new = embedding.embed_batch(queries)
   ```

2. **重新生成所有向量**（重要！）
   ```python
   # 切换嵌入模型后必须重新生成
   for doc in all_documents:
       store.add_documents(
           documents=[doc.content],
           embedding=embedding  # 使用新嵌入函数
       )
   ```

3. **验证检索质量**
   ```python
   # 确保语义搜索结果符合预期
   results = store.similarity_search("减脂饮食", k=5)
   ```

---

### 5.2 向量数据库切换

**开发环境**: ChromaDB (本地文件)

```python
# 当前配置
from services.vectorstore.chroma_store import ChromaVectorStore

store = ChromaVectorStore(
    collection_name="user_1",
    persist_dir="./data/vector_db"
)
```

**生产环境**: Pinecone

```python
# 切换方案
import pinecone
from pinecone import Pinecone

pc = Pinecone(api_key="your-api-key")
index = pc.Index("weight-management")
```

**操作步骤**:

1. 导出 ChromaDB 数据
2. 导入到 Pinecone
3. 更新连接配置
4. 测试检索效果

---

### 5.3 LLM 切换

**当前**: Qwen (通义千问)

```python
# config/settings.py
DEFAULT_AI_PROVIDER = "qwen"
QWEN_API_KEY = "your-key"
```

**切换为**: OpenAI GPT-4

```python
# config/settings.py
DEFAULT_AI_PROVIDER = "openai"
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "gpt-4"
```

**注意**: 切换后可能需要调整 system prompt 和工具函数。

---

## 六、监控与调试

### 6.1 日志记录

```python
import logging

logger = logging.getLogger(__name__)

# 记录 Agent 思考过程
logger.info(f"User message: {message}")
logger.info(f"Intermediate steps: {result['intermediate_steps']}")
```

### 6.2 性能监控

- **Token 使用量**: 统计每次对话的 token 消耗
- **响应时间**: 记录 Agent 思考时间
- **错误率**: 监控降级到旧系统的次数

---

## 七、常见问题

### Q1: 嵌入服务报错？

**问题**: "PyTorch >= 2.4 is required but found 2.2.2"

**原因**: Sentence-Transformers 与 PyTorch/NumPy 版本冲突

**解决方案**（已采用）:

```python
# 当前使用 SimpleEmbedding（无需 PyTorch）
from services.vectorstore.embedding import get_embedding_service
```

如需使用本地模型：

```bash
# 方案1: 降级 NumPy
pip install "numpy<2"

# 方案2: 升级 PyTorch
pip install torch --upgrade
```

### Q2: 首次使用 Embedding 很慢？

A: SimpleEmbedding 无需下载模型。如使用 Sentence-Transformers，首次会自动下载模型（约90MB）。

### Q3: ChromaDB 占用空间过大?

A: 定期清理旧文档或切换到云端向量库。

### Q3: Agent 回复太慢?

A: 
- 检查网络连接
- 考虑使用缓存
- 调低 `max_iterations` 参数

### Q4: 工具调用失败?

A: 检查工具函数是否有权限访问数据库。

---

## 八、后续扩展

### 8.1 短期计划（v1.x）

- [ ] 添加工具调用支持（record_weight、query_history 等）
- [ ] 实现完整的 ReAct Agent 循环
- [ ] 添加对话历史摘要功能
- [ ] 支持多性格切换

### 8.2 中期计划（v2.0）

- [ ] 升级到 LangGraph 工作流
- [ ] 添加图片分析工具（餐食识别）
- [ ] 实现个性化 system prompt 生成
- [ ] 添加用户画像自动更新

### 8.3 长期计划（v3.0）

- [ ] RAG 知识库（营养学知识）
- [ ] 多模态支持（图片输入）
- [ ] 语音交互
- [ ] 生产环境部署（Pinecone + GPT-4）

### 8.4 嵌入模型升级路径

```python
# 1. 开发环境：SimpleEmbedding（当前）
from services.vectorstore.embedding import get_embedding_service

# 2. 预生产：测试 OpenAI Embeddings
from services.vectorstore.embedding import use_openai_embedding
use_openai_embedding(api_key="...", model="text-embedding-3-small")

# 3. 生产环境：根据需求选择
# - 高质量：text-embedding-3-large
# - 高性价比：text-embedding-3-small
# - 私有部署：本地 Sentence-Transformers + GPU
```

---

**文档更新**: 2026-02-07
**维护者**: 开发团队
