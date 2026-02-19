# 两级记忆系统设计文档

## 概述
体重管理助手采用两级记忆系统，结合短期记忆（内存缓冲区）和长期记忆（向量存储），为用户提供个性化的AI助手服务。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AI 助手服务层                           │
├─────────────────────────────────────────────────────────────┤
│                    MemoryManager (统一接口)                   │
├───────────────┬─────────────────────────────────────────────┤
│ 短期记忆系统    │ 长期记忆系统                                  │
│ TypedConversationBufferMemory │ EnhancedVectorStoreRetrieverMemory│
│ • 内存存储      │ • ChromaDB向量存储                            │
│ • 快速访问      │ • 语义检索                                    │
│ • 容量控制      │ • 持久化存储                                  │
└───────────────┴─────────────────────────────────────────────┘
```

## 1. 短期记忆系统 (TypedConversationBufferMemory)

### 1.1 设计目标
- **快速访问**：内存存储，毫秒级响应
- **容量控制**：按类型限制存储数量
- **类型化存储**：区分打卡记录和对话记录

### 1.2 存储结构
```python
class TypedConversationBufferMemory:
    checkin_capacity: int = 30      # 打卡记录容量（30条）
    conversation_capacity: int = 200 # 对话记录容量（200条）
    
    checkin_messages: List[Dict]    # 打卡记录存储
    conversation_messages: List[Dict] # 对话记录存储
```

### 1.3 写入流程（写操作）

#### 1.3.1 新打卡记录写入
```
用户打卡 → API路由 → 数据库保存 → 短期记忆添加
      ↓
对话历史保存 → 同步服务调用
```

**代码路径：**
1. **餐食打卡**：`api/routes/meal.py` → `confirm_meal_record()` → `MemoryManager.add_checkin_record()`
2. **运动打卡**：`api/routes/exercise.py` → `record_exercise()` → `CheckinSyncService.sync_recent_checkins()`

**写入逻辑：**
```python
# 1. 构建打卡内容
content = f"【{meal_type}打卡】吃了：{food_names}，总热量：{total_calories}千卡"

# 2. 调用MemoryManager
memory_manager.add_checkin_record(
    checkin_type="meal",
    content=content,
    metadata={
        "meal_type": meal_type,
        "total_calories": total_calories,
        "food_count": len(foods),
        "record_id": record.id,
    }
)

# 3. 内部处理
def add_checkin_record(self, checkin_type, content, metadata):
    # 创建消息对象
    message = HumanMessage(content=content)
    
    # 添加到短期记忆
    self.short_term_memory.add_message(
        message=message,
        memory_type=MemoryType.CHECKIN
    )
    
    # 同步到长期记忆
    self.long_term_memory.add_message(
        message=message,
        memory_type=MemoryType.CHECKIN,
        metadata=metadata
    )
```

#### 1.3.2 初始化加载
当MemoryManager创建时，自动从数据库加载最近记录：
```python
def __init__(self, user_id: int):
    # 从数据库加载最近24小时的记录
    self._load_recent_checkins()
    
def _load_recent_checkins(self):
    # 查询餐食记录（最近24小时，最多10条）
    # 查询运动记录（最近24小时，最多10条）
    # 解析并添加到短期记忆
```

### 1.4 读取流程（读操作）

#### 1.4.1 AI助手查询上下文
```
AI请求 → MemoryManager.get_context() → 组合短期+长期记忆
```

**读取逻辑：**
```python
def get_context(self, checkin_limit=10, conversation_limit=10, query=None):
    # 1. 获取短期记忆上下文
    short_term = self.short_term_memory.get_combined_context(
        checkin_limit=checkin_limit,
        conversation_limit=conversation_limit
    )
    
    # 2. 获取长期记忆上下文（语义检索）
    if query:
        long_term = self.long_term_memory.search(query, limit=5)
    
    # 3. 组合返回
    return f"{short_term}\n{long_term}"
```

#### 1.4.2 短期记忆检索方法
```python
def get_combined_context(self, checkin_limit=10, conversation_limit=10):
    # 获取最近打卡记录
    checkins = self.checkin_messages[-checkin_limit:]
    
    # 获取最近对话记录  
    conversations = self.conversation_messages[-conversation_limit:]
    
    # 格式化为文本
    return format_context(checkins, conversations)
```

### 1.5 容量管理
- **自动清理**：超过容量时自动移除最旧记录
- **LRU策略**：最近最少使用，但实现为FIFO（按时间顺序）
- **类型独立**：打卡和对话记录独立管理容量

## 2. 长期记忆系统 (EnhancedVectorStoreRetrieverMemory)

### 2.1 设计目标
- **持久化存储**：ChromaDB向量数据库
- **语义检索**：基于内容的相似度搜索
- **元数据过滤**：按用户、类型、时间等过滤

### 2.2 存储结构
```
ChromaDB Collection: user_memories_{user_id}
├── 文档: 记忆内容文本
├── 向量: 文本嵌入向量
└── 元数据: {type, timestamp, checkin_type, record_id, ...}
```

### 2.3 写入流程

#### 2.3.1 同步写入
短期记忆添加时自动同步：
```python
def add_message(self, message, memory_type, metadata=None):
    # 1. 文本嵌入
    embedding = self.embedding_model.encode(message.content)
    
    # 2. 构建元数据
    doc_metadata = {
        "user_id": self.user_id,
        "memory_type": memory_type.value,
        "timestamp": datetime.now().isoformat(),
        **metadata
    }
    
    # 3. 存储到ChromaDB
    self.collection.add(
        documents=[message.content],
        embeddings=[embedding],
        metadatas=[doc_metadata],
        ids=[f"{memory_type}_{timestamp}"]
    )
```

#### 2.3.2 批量同步
通过`CheckinSyncService`同步历史记录：
```python
async def sync_recent_checkins(self, user_id, hours=24):
    # 1. 查询数据库记录
    records = await db.query_recent_records(user_id, hours)
    
    # 2. 批量添加到长期记忆
    for record in records:
        memory_manager.add_checkin_record(...)
```

### 2.4 读取流程

#### 2.4.1 语义检索
```python
def search(self, query: str, limit: int = 5, filters: Dict = None):
    # 1. 查询嵌入
    query_embedding = self.embedding_model.encode(query)
    
    # 2. 向量相似度搜索
    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=filters  # 元数据过滤
    )
    
    # 3. 格式化结果
    return format_search_results(results)
```

#### 2.4.2 元数据过滤查询
```python
# 查询用户的所有运动记录
results = self.collection.query(
    where={
        "user_id": user_id,
        "checkin_type": "exercise"
    },
    n_results=20
)

# 查询特定时间范围的记录
results = self.collection.query(
    where={
        "user_id": user_id,
        "timestamp": {"$gte": start_time, "$lte": end_time}
    }
)
```

## 3. 统一接口 (MemoryManager)

### 3.1 核心方法

#### 3.1.1 写入接口
```python
# 添加打卡记录
add_checkin_record(checkin_type, content, metadata)

# 添加对话记录  
add_conversation_record(role, content, metadata)

# 添加消息（通用）
add_message(message, memory_type, metadata, sync_to_long_term=True)
```

#### 3.1.2 读取接口
```python
# 获取组合上下文
get_context(checkin_limit=10, conversation_limit=10, query=None)

# 获取用户画像
get_user_profile(force_refresh=False)

# 获取记忆统计
get_stats()

# 搜索记忆
search_memories(query, limit=5, filters=None)
```

### 3.2 使用示例

#### 3.2.1 AI助手服务使用
```python
# 初始化记忆管理器
memory_manager = MemoryManager(user_id=6)

# 获取对话上下文
context = memory_manager.get_context(
    checkin_limit=15,      # 获取15条打卡记录
    conversation_limit=20,  # 获取20条对话记录
    query=user_query,      # 用于长期记忆检索
    include_long_term=True # 包含长期记忆
)

# 将上下文提供给AI模型
ai_response = ai_model.generate(context + user_query)
```

#### 3.2.2 API路由使用
```python
# 在打卡API中
async def record_exercise(...):
    # 1. 保存到数据库
    record = ExerciseRecord(...)
    await db.commit()
    
    # 2. 添加到记忆系统
    memory_manager = MemoryManager(user_id=current_user.id)
    memory_manager.add_checkin_record(
        checkin_type="exercise",
        content=f"【运动打卡】{exercise_type} {duration}分钟",
        metadata={
            "exercise_type": exercise_type,
            "duration_minutes": duration,
            "calories_burned": calories,
            "record_id": record.id
        }
    )
```

## 4. 数据流图

### 4.1 完整写入流程
```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐
│ 用户打卡 │───▶│ API路由   │───▶│ 数据库    │───▶│ 短期记忆     │
└─────────┘    └──────────┘    └──────────┘    └──────┬───────┘
                                                      │
                                                      ▼
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐
│ 对话历史 │◀───│ 保存历史  │◀───│ 构建内容  │◀───│ 同步服务     │
└─────────┘    └──────────┘    └──────────┘    └──────┬───────┘
                                                      │
                                                      ▼
                                                 ┌──────────────┐
                                                 │ 长期记忆     │
                                                 │ (ChromaDB)   │
                                                 └──────────────┘
```

### 4.2 完整读取流程
```
┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│ AI查询   │───▶│ MemoryManager│───▶│ 获取短期记忆  │───▶│ 组合上下文 │
└─────────┘    └──────┬───────┘    └──────────────┘    └────┬─────┘
                      │                                     │
                      ▼                                     ▼
               ┌──────────────┐                     ┌──────────┐
               │ 语义检索      │                     │ AI响应    │
               │ 长期记忆      │                     └──────────┘
               └──────────────┘
```

## 5. 配置参数

### 5.1 容量配置
```python
# 短期记忆容量
SHORT_TERM_CHECKIN_CAPACITY = 30     # 打卡记录条数
SHORT_TERM_CONVERSATION_CAPACITY = 200 # 对话记录条数

# 检索限制
DEFAULT_CHECKIN_LIMIT = 15          # 默认检索打卡记录数
DEFAULT_CONVERSATION_LIMIT = 20     # 默认检索对话记录数
MAX_CONTEXT_LENGTH = 4000           # 最大上下文长度（字符）
```

### 5.2 同步配置
```python
# 数据库同步
SYNC_RECENT_HOURS = 24              # 同步最近多少小时的记录
MAX_SYNC_RECORDS = 100              # 最大同步记录数

# 长期记忆
VECTOR_DIMENSION = 384              # 向量维度
SIMILARITY_THRESHOLD = 0.7          # 相似度阈值
```

## 6. 监控与调试

### 6.1 日志输出
```python
# 记忆系统日志格式
logger.info(f"初始化MemoryManager，用户ID: {user_id}")
logger.info(f"从数据库加载了 {meal_count} 条餐食记录和 {exercise_count} 条运动记录")
logger.info(f"添加打卡记录 - 类型: {checkin_type}, 内容: {content[:50]}...")
logger.info(f"获取上下文 - 打卡限制: {checkin_limit}, 对话限制: {conversation_limit}")
```

### 6.2 统计指标
```python
# 记忆统计
stats = {
    "short_term_checkins": len(checkin_messages),
    "short_term_conversations": len(conversation_messages),
    "long_term_count": collection.count(),
    "last_sync_time": last_sync,
    "memory_hit_rate": hit_rate  # 记忆命中率
}
```

## 7. 扩展性设计

### 7.1 未来扩展
1. **记忆摘要**：对长期记忆生成摘要，减少上下文长度
2. **记忆重要性评分**：基于使用频率和相关性评分
3. **多模态记忆**：支持图片、语音等多媒体记忆
4. **记忆关联**：建立记忆之间的关联关系

### 7.2 性能优化
1. **缓存策略**：热门记忆的缓存机制
2. **批量操作**：批量写入和读取优化
3. **异步处理**：耗时的向量计算异步化
4. **索引优化**：向量索引和元数据索引优化

---

## 总结

两级记忆系统通过：
1. **短期记忆**：提供快速访问和近期上下文
2. **长期记忆**：提供持久化存储和语义检索
3. **统一接口**：简化上层业务逻辑调用

实现了高效、可扩展的记忆管理，为AI助手提供了丰富的用户上下文信息。