# LangChain记忆体系集成技术架构设计

**文档版本**: 1.0  
**创建日期**: 2026-02-19  
**状态**: 设计阶段  
**负责人**: 开发团队  

---

## 一、项目概述

### 1.1 项目背景
当前体重管理系统已具备完整的健康打卡功能和基础对话能力，但Agent的记忆系统存在以下问题：
1. **Agent实现不完整**：代码中引用了不存在的`AgentFactory`
2. **记忆系统缺失**：虽然有ChatHistory表，但未集成到Agent记忆体系
3. **打卡记录孤立**：健康打卡数据未与Agent记忆打通

### 1.2 项目目标
1. **优化Agent系统**：修复现有Agent实现，集成LangChain对话和记忆机制
2. **实现分层记忆**：建立短期+长期+用户画像的三层记忆体系
3. **打通打卡记录**：将健康打卡数据实时同步到Agent记忆系统
4. **提升用户体验**：使Agent能记住用户历史对话和所有打卡记录

### 1.3 设计原则
- **最小侵入**：不改变现有API核心逻辑，只添加记忆同步钩子
- **事件驱动**：打卡时实时保存到记忆系统
- **分层管理**：不同记忆类型使用不同存储策略
- **渐进实现**：分阶段实施，确保系统稳定性

---

## 二、技术架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                   现有系统层                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 健康打卡API  │ │  对话API    │ │  用户API    │           │
│  │ (weight.py) │ │  (chat.py)  │ │  (user.py)  │           │
│  └──────┬──────┘ └──────┬──────┘ └─────────────┘           │
│         │               │                                  │
│         ▼               ▼                                  │
│  ┌─────────────┐ ┌─────────────┐                          │
│  │ 记忆同步钩子 │ │ 记忆检索钩子 │                          │
│  │ (新增)      │ │ (新增)      │                          │
│  └──────┬──────┘ └──────┬──────┘                          │
└─────────┼───────────────┼─────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│               LangChain记忆层 (新增)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               MemoryManager                         │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ 短期记忆     │ │ 长期记忆     │ │ 用户画像     │   │   │
│  │  │ (230条容量) │ │ (向量存储)   │ │ (结构化)    │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │               │               │
          ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  内存存储    │ │ ChromaDB    │ │ SQLite      │
│  (Python对象)│ │ (向量索引)   │ │ (用户数据)   │
└─────────────┘ └─────────────┘ └─────────────┘
```

### 2.2 数据流设计

#### 2.2.1 打卡事件流
```
用户打卡 → 现有API处理 → 数据库保存 → 记忆同步钩子 → 
MemoryManager.save_checkin() → 短期记忆 + 长期记忆
```

#### 2.2.2 对话记忆流
```
用户对话 → 现有API处理 → 记忆检索钩子 → 
MemoryManager.get_context() → 合并所有记忆层 → 
构建对话上下文 → 返回Agent
```

#### 2.2.3 记忆溢出流
```
短期记忆满 → 智能溢出处理 → 
打卡记录 → 完整保存到长期记忆 →
对话记录 → 生成摘要保存到长期记忆
```

---

## 三、核心组件设计

### 3.1 MemoryManager（记忆管理器）

#### 3.1.1 职责
- 统一管理所有记忆组件
- 提供记忆保存和检索接口
- 处理记忆溢出和压缩
- 维护数据一致性

#### 3.1.2 接口设计
```python
class MemoryManager:
    """统一记忆管理器"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.short_term = TypedConversationBufferMemory(
            max_checkins=30,
            max_chats=200
        )
        self.long_term = EnhancedVectorStoreRetrieverMemory(user_id)
        self.user_profile = UserProfileMemory(user_id)
    
    async def save_checkin(self, checkin_data: Dict) -> None:
        """保存打卡记录到记忆系统"""
        pass
    
    async def save_chat(self, chat_data: Dict) -> None:
        """保存对话记录到记忆系统"""
        pass
    
    async def get_context(self, query: str = None) -> List[Dict]:
        """获取对话上下文（合并所有记忆层）"""
        pass
    
    async def clear_memory(self, memory_type: str = "all") -> None:
        """清理指定类型的记忆"""
        pass
```

### 3.2 TypedConversationBufferMemory（增强版短期记忆）

#### 3.2.1 设计目标
- 继承LangChain的`ConversationBufferMemory`
- 支持按类型分别控制容量
- 精确控制：30条打卡记录 + 200条对话记录

#### 3.2.2 实现方案
```python
from langchain.memory import ConversationBufferMemory
from collections import deque

class TypedConversationBufferMemory(ConversationBufferMemory):
    """按类型控制容量的增强版对话记忆"""
    
    def __init__(self, max_checkins=30, max_chats=200, **kwargs):
        super().__init__(**kwargs)
        self.max_checkins = max_checkins
        self.max_chats = max_chats
        
        # 分别存储打卡和对话记录
        self.checkins = deque(maxlen=max_checkins)
        self.chats = deque(maxlen=max_chats)
        
        # 类型识别器
        self.type_detector = CheckinTypeDetector()
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存上下文，按类型分别存储"""
        # 判断记录类型
        record_type = self.type_detector.detect(inputs)
        
        if record_type == "checkin":
            # 保存到打卡队列
            self.checkins.append({
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": datetime.utcnow(),
                "type": "checkin"
            })
        else:
            # 保存到对话队列
            self.chats.append({
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": datetime.utcnow(),
                "type": "chat"
            })
        
        # 合并所有记录到父类存储
        self._sync_to_parent()
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载记忆变量"""
        # 获取所有记录
        all_records = list(self.checkins) + list(self.chats)
        
        # 按时间排序
        all_records.sort(key=lambda x: x["timestamp"])
        
        # 转换为LangChain消息格式
        messages = []
        for record in all_records:
            messages.extend(self._format_as_messages(record))
        
        return {"history": messages}
    
    def _sync_to_parent(self) -> None:
        """同步记录到父类存储"""
        # 清空父类存储
        self.chat_memory.clear()
        
        # 合并所有记录
        all_records = list(self.checkins) + list(self.chats)
        all_records.sort(key=lambda x: x["timestamp"])
        
        # 保存到父类
        for record in all_records:
            super().save_context(record["inputs"], record["outputs"])
```

### 3.3 EnhancedVectorStoreRetrieverMemory（增强版长期记忆）

#### 3.3.1 设计目标
- 基于现有ChromaDB向量存储
- 支持不同类型数据的差异化存储
- 提供语义检索能力

#### 3.3.2 存储策略
| 数据类型 | 存储方式 | 检索策略 | 重要性 |
|----------|----------|----------|--------|
| **打卡记录** | 原消息存储 | 精确匹配 + 语义检索 | 高 |
| **对话摘要** | 摘要存储 | 语义检索 | 中 |
| **用户习惯** | 模式存储 | 模式匹配 | 高 |

#### 3.3.3 实现方案
```python
class EnhancedVectorStoreRetrieverMemory:
    """增强版向量存储记忆"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.vector_store = get_user_vector_store(user_id)
        self.summarizer = ConversationSummarizer()
        
        # 存储配置
        self.storage_config = {
            "checkin": {
                "store_raw": True,      # 存储原消息
                "importance": "high",   # 重要性高
                "retention_days": 365   # 保留365天
            },
            "chat": {
                "store_raw": False,     # 不存储原消息
                "store_summary": True,  # 存储摘要
                "importance": "medium", # 重要性中
                "retention_days": 90    # 保留90天
            }
        }
    
    async def save_checkin(self, checkin_data: Dict) -> None:
        """保存打卡记录"""
        # 向量化存储完整记录
        document = self._format_checkin_document(checkin_data)
        metadata = {
            "type": "checkin",
            "user_id": self.user_id,
            "checkin_type": checkin_data["type"],
            "timestamp": checkin_data.get("timestamp"),
            "importance": "high"
        }
        
        await self.vector_store.add_documents(
            documents=[document],
            metadatas=[metadata]
        )
    
    async def save_chat_summary(self, chats: List[Dict]) -> None:
        """保存对话摘要"""
        # 生成对话摘要
        summary = await self.summarizer.summarize(chats)
        
        # 向量化存储摘要
        metadata = {
            "type": "chat_summary",
            "user_id": self.user_id,
            "original_count": len(chats),
            "timestamp": datetime.utcnow().isoformat(),
            "importance": "medium"
        }
        
        await self.vector_store.add_documents(
            documents=[summary],
            metadatas=[metadata]
        )
    
    async def search(self, query: str, limit: int = 10) -> List[Dict]:
        """语义搜索"""
        # 基础语义搜索
        results = await self.vector_store.similarity_search(
            query=query,
            k=limit,
            filter={"user_id": self.user_id}
        )
        
        # 结果重排序（基于重要性、时间等）
        ranked_results = self._rerank_results(results, query)
        
        return ranked_results
```

### 3.4 AgentFactory修复

#### 3.4.1 问题分析
当前`chat.py`中引用了不存在的`AgentFactory`：
```python
from services.langchain.agents import AgentFactory  # 引用不存在
agent = await AgentFactory.get_agent(user_id, db)   # 调用失败
```

#### 3.4.2 修复方案
```python
# services/langchain/agents/factory.py
class AgentFactory:
    """Agent工厂类"""
    
    @staticmethod
    async def get_agent(user_id: int, db: AsyncSession) -> "BaseAgent":
        """
        获取用户的Agent实例
        
        Args:
            user_id: 用户ID
            db: 数据库会话
            
        Returns:
            Agent实例
        """
        # 1. 获取用户配置
        agent_config = await get_agent_config(user_id, db)
        
        # 2. 创建记忆管理器
        memory_manager = MemoryManager(user_id)
        
        # 3. 创建Agent实例
        if agent_config.agent_type == "simple":
            agent = SimpleWeightAgent(user_id, db, memory_manager)
        else:
            # 默认使用SimpleWeightAgent
            agent = SimpleWeightAgent(user_id, db, memory_manager)
        
        return agent
    
    @staticmethod
    async def get_agent_config(user_id: int, db: AsyncSession) -> AgentConfig:
        """获取用户Agent配置"""
        # 查询或创建默认配置
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.user_id == user_id)
        )
        config = result.scalar_one_or_none()
        
        if not config:
            # 创建默认配置
            config = AgentConfig(
                user_id=user_id,
                agent_type="simple",
                personality_type="WARM",
                created_at=datetime.utcnow()
            )
            db.add(config)
            await db.commit()
        
        return config
```

### 3.5 SimpleWeightAgent（简化版Agent）

#### 3.5.1 设计目标
- 轻量级Agent实现
- 集成LangChain对话机制
- 支持记忆检索
- 保持与现有系统的兼容性

#### 3.5.2 实现方案
```python
class SimpleWeightAgent:
    """简化版体重管理Agent"""
    
    def __init__(self, user_id: int, db: AsyncSession, memory_manager: MemoryManager):
        self.user_id = user_id
        self.db = db
        self.memory = memory_manager
        self.llm = self._init_llm()
        
        # 对话链配置
        self.conversation_chain = self._create_conversation_chain()
    
    def _init_llm(self):
        """初始化语言模型"""
        from services.ai_service import ai_service
        
        # 使用现有AI服务
        return ai_service
    
    def _create_conversation_chain(self):
        """创建对话链"""
        from langchain.chains import ConversationChain
        from langchain.prompts import PromptTemplate
        
        # 系统提示词模板
        system_template = """
        你是{user_name}的专属体重管理助手。
        
        用户信息：
        {user_profile}
        
        最近打卡记录：
        {recent_checkins}
        
        对话历史：
        {conversation_history}
        
        当前对话：
        {current_input}
        
        请根据以上信息回复用户，保持温暖、专业的语气。
        """
        
        prompt = PromptTemplate(
            input_variables=["user_name", "user_profile", "recent_checkins", 
                           "conversation_history", "current_input"],
            template=system_template
        )
        
        # 创建对话链（简化版，不使用完整LangChain链）
        return None  # 暂时返回None，使用现有AI服务
    
    async def chat(self, message: str) -> Dict[str, Any]:
        """处理用户消息"""
        try:
            # 1. 获取记忆上下文
            context = await self.memory.get_context(message)
            
            # 2. 构建系统提示词
            system_prompt = await self._build_system_prompt(context)
            
            # 3. 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                *context,
                {"role": "user", "content": message}
            ]
            
            # 4. 调用AI服务（使用现有ai_service）
            response = await self.llm.chat_completion(messages)
            
            # 5. 保存对话到记忆
            await self.memory.save_chat({
                "user_message": message,
                "assistant_reply": response.content,
                "timestamp": datetime.utcnow()
            })
            
            return {
                "success": True,
                "response": response.content,
                "context_used": len(context)
            }
            
        except Exception as e:
            logger.error(f"Agent聊天失败: {e}")
            return {
                "success": False,
                "response": "抱歉，我现在有点忙，请稍后再试。",
                "error": str(e)
            }
```

---

## 四、系统集成方案

### 4.1 现有API修改点

#### 4.1.1 健康打卡API修改
```python
# api/routes/weight.py
async def record_weight(
    weight: float,
    body_fat: Optional[float] = None,
    note: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # ... 现有逻辑 ...
    
    # 新增：同步到记忆系统
    try:
        from services.langchain.memory.manager import MemoryManager
        
        memory_manager = MemoryManager(current_user.id)
        await memory_manager.save_checkin({
            "type": "weight",
            "weight": weight,
            "body_fat": body_fat,
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
            "record_id": record_id
        })
        
        logger.info(f"用户{current_user.id}的体重记录已同步到记忆系统")
        
    except Exception as e:
        logger.warning(f"记忆同步失败: {e}")
        # 不中断主流程，继续执行
    
    # ... 返回现有响应 ...
```

#### 4.1.2 对话API修改
```python
# api/routes/chat.py
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # ... 现有逻辑 ...
    
    try:
        # 使用修复后的AgentFactory
        from services.langchain.agents import AgentFactory
        
        agent = await AgentFactory.get_agent(current_user.id, db)
        result = await agent.chat(content)
        
        assistant_reply = result.get("response", "抱歉，我现在有点忙。")
        
    except Exception as agent_error:
        # 降级到现有AI服务
        logger.warning(f"Agent调用失败，降级到传统AI: {agent_error}")
        
        # 使用记忆管理器获取上下文
        from services.langchain.memory.manager import MemoryManager
        
        memory_manager = MemoryManager(current_user.id)
        memory_context = await memory_manager.get_context(content)
        
        # 构建消息列表（包含记忆上下文）
        messages = [
            {"role": "system", "content": system_prompt},
            *memory_context,
            {"role": "user", "content": content}
        ]
        
        # 调用现有AI服务
        response = await call_ai_with_retry(messages)
        assistant_reply = response.content
    
    # ... 保存回复到数据库 ...
```

### 4.2 新增服务模块

#### 4.2.1 目录结构
```
services/langchain/
├── __init__.py
├── memory/
│   ├── __init__.py
│   ├── typed_buffer.py      # TypedConversationBufferMemory
│   ├── vector_memory.py     # EnhancedVectorStoreRetrieverMemory
│   ├── manager.py           # MemoryManager
│   └── sync_service.py      # CheckinSyncService
└── agents/
    ├── __init__.py
    ├── factory.py           # AgentFactory
    ├── simple.py            # SimpleWeightAgent
    └── base.py              # BaseAgent接口
```

#### 4.2.2 依赖管理
```python
# requirements.txt 新增
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0

# 或使用现有依赖（检查是否已安装）
```

---

## 五、实施路线图

### 5.1 阶段1：基础记忆系统（1-2周）
**目标**：建立增强版LangChain记忆系统

**任务**：
1. 创建`services/langchain/`目录结构
2. 实现`TypedConversationBufferMemory`
3. 实现`EnhancedVectorStoreRetrieverMemory`
4. 实现`MemoryManager`
5. 单元测试基础功能

### 5.2 阶段2：修复Agent系统（1周）
**目标**：让现有的`AgentFactory`引用正常工作

**任务**：
1. 实现`AgentFactory.get_agent()`
2. 实现`SimpleWeightAgent`
3. 修复`chat.py`中的引用
4. 测试Agent调用流程

### 5.3 阶段3：打通健康打卡记录（1周）
**目标**：将现有打卡记录同步到LangChain记忆

**任务**：
1. 在体重API中添加记忆同步
2. 在其他健康API中添加同步
3. 实现`CheckinSyncService`
4. 测试记忆同步功能

### 5.4 阶段4：集成记忆到对话系统（1周）
**目标**：Agent对话时能检索记忆

**任务**：
1. 修改对话API使用记忆上下文
2. 实现记忆检索和合并
3. 测试记忆检索功能
4. 优化检索性能

### 5.5 阶段5：测试和优化（1周）
**目标**：确保系统稳定可用

**任务**：
1. 功能测试（打卡记忆、对话记忆）
2. 性能测试（同步延迟、检索延迟）
3. 用户体验优化
4. 文档完善

---

## 六、风险评估与缓解

### 6.1 技术风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **LangChain版本兼容性** | 中 | 中 | 使用稳定版本，充分测试 |
| **记忆同步性能** | 低 | 低 | 异步处理，错误降级 |
| **数据一致性** | 低 | 高 | 事务处理，状态同步 |
| **向量存储性能** | 低 | 中 | 索引优化，批量操作 |

### 6.2 业务风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **用户体验下降** | 低 | 高 | A/B测试，用户反馈 |
| **系统响应变慢** | 中 | 中 | 性能监控，容量规划 |
| **记忆不准确** | 低 | 中 | 数据验证，纠错机制 |

### 6.3 实施风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **开发延期** | 中 | 中 | 分阶段实施，优先级排序 |
| **集成复杂度** | 高 | 中 | 模块化设计，接口清晰 |
| **测试不充分** | 低 | 高 | 自动化测试，代码审查 |

---

## 七、成功标准

### 7.1 功能标准
- ✅ Agent能记住最近30条打卡记录
- ✅ Agent能记住最近200条对话
- ✅ 打卡时自动同步到记忆系统
- ✅ 对话时能检索相关记忆
- ✅ 系统支持记忆清理和管理

### 7.2 性能标准
- ⏱️ 记忆同步延迟 < 100ms
- ⏱️ 记忆检索延迟 < 500ms
- 📊 系统稳定性 > 99%
- 💾 内存使用在合理范围内

### 7.3 用户体验标准
- 😊 用户感觉Agent"记性更好"
- 💬 对话更自然、个性化
- ⚡ 系统响应流畅
- 🔧 支持记忆管理功能

---

## 八、附录

### 8.1 技术栈
- **后端框架**: FastAPI + SQLAlchemy
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **向量存储**: ChromaDB
- **AI服务**: OpenAI / Qwen
- **记忆框架**: LangChain 0.3+
- **缓存**: Redis (可选)

### 8.2 关键文件清单
#### 新增文件：
1. `services/langchain/__init__.py`
2. `services/langchain/memory/__init__.py`
3. `services/langchain/memory/typed_buffer.py`
4. `services/langchain/memory/vector_memory.py`
5. `services/langchain/memory/manager.py`
6. `services/langchain/memory/sync_service.py`
7. `services/langchain/agents/__init__.py`
8. `services/langchain/agents/factory.py`
9. `services/langchain/agents/simple.py`

#### 修改文件：
1. `api/routes/chat.py` - 修复AgentFactory引用，添加记忆检索
2. `api/routes/weight.py` - 添加记忆同步
3. `api/routes/meal.py` - 添加记忆同步
4. `api/routes/exercise.py` - 添加记忆同步
5. `api/routes/water.py` - 添加记忆同步
6. `api/routes/sleep.py` - 添加记忆同步

### 8.3 测试计划
1. **单元测试**: 每个记忆组件独立测试
2. **集成测试**: API集成测试
3. **性能测试**: 记忆同步和检索性能
4. **用户测试**: 小范围用户试用

---

## 九、下一步行动

### 9.1 立即行动
1. ✅ 完成技术架构设计文档
2. ⏳ 等待技术评审确认
3. ⏳ 准备开发环境
4. ⏳ 制定详细开发计划

### 9.2 开发准备
1. 确认LangChain版本和依赖
2. 准备测试数据
3. 设置开发环境
4. 分配开发任务

### 9.3 沟通计划
1. 技术方案评审会议
2. 开发进度周报
3. 测试结果分享
4. 用户反馈收集

---

**文档版本历史**:
- v1.0 (2026-02-19): 初始版本，完成技术架构设计

**审批记录**:
- 设计者: [待填写]
- 评审者: [待填写]  
- 批准者: [待填写]
- 生效日期: [待填写]
