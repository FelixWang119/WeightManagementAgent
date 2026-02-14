"""
Memory V2 - 使用 LangChain 标准组件的记忆系统

主要改进：
1. 使用 RunnableWithMessageHistory 管理对话历史
2. 正确区分短期记忆（最近对话）和长期记忆（向量检索）
3. 使用 SQLAlchemy 持久化存储对话历史
4. 更好的内存管理（限制 token 数量）
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import json
import logging

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)
from langchain_core.chat_history import BaseChatMessageHistory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_

from models.database import ChatHistory, MessageRole

logger = logging.getLogger(__name__)


class SQLAlchemyMessageHistory(BaseChatMessageHistory):
    """
    基于 SQLAlchemy 的消息历史存储

    实现 LangChain 的 BaseChatMessageHistory 接口，
    用于与 RunnableWithMessageHistory 集成
    """

    def __init__(self, user_id: int, db: AsyncSession, max_messages: int = 50):
        self.user_id = user_id
        self.db = db
        self.max_messages = max_messages
        self._messages: List[BaseMessage] = []
        self._loaded = False

    async def _ensure_loaded(self):
        """确保消息已从数据库加载"""
        if not self._loaded:
            await self._load_messages()
            self._loaded = True

    async def _load_messages(self):
        """从数据库加载消息"""
        try:
            result = await self.db.execute(
                select(ChatHistory)
                .where(ChatHistory.user_id == self.user_id)
                .order_by(desc(ChatHistory.created_at))
                .limit(self.max_messages)
            )
            records = result.scalars().all()

            # 反转顺序（从旧到新）
            records = list(reversed(records))

            self._messages = []
            for record in records:
                if record.role == MessageRole.USER:
                    self._messages.append(HumanMessage(content=record.content))
                elif record.role == MessageRole.ASSISTANT:
                    self._messages.append(AIMessage(content=record.content))
                elif record.role == MessageRole.SYSTEM:
                    self._messages.append(SystemMessage(content=record.content))

        except Exception as e:
            logger.error(f"加载消息历史失败: {e}", exc_info=True)
            self._messages = []

    async def _save_message(self, message: BaseMessage):
        """保存单条消息到数据库"""
        try:
            if isinstance(message, HumanMessage):
                role = MessageRole.USER
            elif isinstance(message, AIMessage):
                role = MessageRole.ASSISTANT
            elif isinstance(message, SystemMessage):
                role = MessageRole.SYSTEM
            else:
                role = MessageRole.USER

            record = ChatHistory(
                user_id=self.user_id,
                role=role,
                content=message.content,
                created_at=datetime.utcnow(),
            )
            self.db.add(record)
            await self.db.commit()

        except Exception as e:
            logger.error(f"保存消息失败: {e}", exc_info=True)
            await self.db.rollback()

    @property
    def messages(self) -> List[BaseMessage]:
        """
        获取消息列表（同步接口）

        注意：由于这是一个同步属性，但我们需要异步加载数据，
        所以实际使用时应该先在异步环境中调用 aget_messages()
        """
        # 返回已加载的消息（如果已加载）
        return self._messages

    async def aget_messages(self) -> List[BaseMessage]:
        """异步获取消息列表"""
        await self._ensure_loaded()
        return self._messages

    def add_message(self, message: BaseMessage):
        """添加消息（同步接口，需要在外部处理异步保存）"""
        self._messages.append(message)

        # 限制消息数量
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]

    async def aadd_message(self, message: BaseMessage):
        """异步添加消息"""
        await self._ensure_loaded()
        self._messages.append(message)
        await self._save_message(message)

        # 限制消息数量
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]

    def add_user_message(self, message: str):
        """添加用户消息"""
        self.add_message(HumanMessage(content=message))

    def add_ai_message(self, message: str):
        """添加 AI 消息"""
        self.add_message(AIMessage(content=message))

    def clear(self):
        """清除内存中的消息（不删除数据库记录）"""
        self._messages = []
        self._loaded = False


class ConversationMemoryManager:
    """
    对话记忆管理器

    管理用户的短期记忆（最近对话）和中期记忆（对话摘要）
    """

    def __init__(
        self,
        user_id: int,
        db: AsyncSession,
        short_term_limit: int = 20,  # 保留最近20轮对话
        enable_summarization: bool = True,
    ):
        self.user_id = user_id
        self.db = db
        self.short_term_limit = short_term_limit
        self.enable_summarization = enable_summarization

        self.message_history = SQLAlchemyMessageHistory(
            user_id=user_id,
            db=db,
            max_messages=short_term_limit * 2,  # 每轮2条消息
        )

        self.logger = logging.getLogger(__name__)

    @classmethod
    async def create(
        cls,
        user_id: int,
        db: AsyncSession,
        short_term_limit: int = 20,
        enable_summarization: bool = True,
    ) -> "ConversationMemoryManager":
        """工厂方法创建记忆管理器"""
        return cls(
            user_id=user_id,
            db=db,
            short_term_limit=short_term_limit,
            enable_summarization=enable_summarization,
        )

    async def get_conversation_context(
        self, max_tokens: int = 2000
    ) -> List[BaseMessage]:
        """
        获取对话上下文（用于输入到 LLM）

        Args:
            max_tokens: 最大 token 数量（用于截断）

        Returns:
            消息列表
        """
        messages = await self.message_history.aget_messages()

        # 简单的 token 估算（每个字符约 0.5 个 token）
        total_chars = sum(len(m.content) for m in messages)
        estimated_tokens = total_chars * 0.5

        if estimated_tokens > max_tokens:
            # 需要截断，保留最近的消息
            truncated = []
            current_tokens = 0

            for msg in reversed(messages):
                msg_tokens = len(msg.content) * 0.5
                if current_tokens + msg_tokens > max_tokens:
                    break
                truncated.insert(0, msg)
                current_tokens += msg_tokens

            return truncated

        return messages

    async def save_interaction(self, user_message: str, ai_response: str):
        """
        保存用户和 AI 的交互

        Args:
            user_message: 用户消息
            ai_response: AI 回复
        """
        await self.message_history.aadd_message(HumanMessage(content=user_message))
        await self.message_history.aadd_message(AIMessage(content=ai_response))

        self.logger.debug(
            f"保存交互 - 用户: {user_message[:50]}..., AI: {ai_response[:50]}..."
        )

    async def get_recent_messages(self, n: int = 5) -> List[Dict[str, str]]:
        """
        获取最近 n 轮对话

        Returns:
            格式化为字典列表的消息
        """
        messages = await self.message_history.aget_messages()
        recent = messages[-(n * 2) :]  # 每轮包含用户和 AI 消息

        result = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})

        return result

    async def clear_memory(self):
        """清除内存"""
        self.message_history.clear()
        self.logger.info(f"已清除用户 {self.user_id} 的内存")


class MemoryManagerV2:
    """
    Memory V2 管理器（全局管理）

    管理所有用户的记忆实例
    """

    _instances: Dict[int, ConversationMemoryManager] = {}

    @classmethod
    async def get_memory(
        cls, user_id: int, db: AsyncSession, **kwargs
    ) -> ConversationMemoryManager:
        """获取或创建记忆管理器"""
        if user_id not in cls._instances:
            cls._instances[user_id] = ConversationMemoryManager(
                user_id=user_id, db=db, **kwargs
            )
        # 更新数据库会话
        cls._instances[user_id].db = db
        cls._instances[user_id].message_history.db = db
        return cls._instances[user_id]

    @classmethod
    async def clear_memory(cls, user_id: int):
        """清除指定用户的记忆"""
        if user_id in cls._instances:
            await cls._instances[user_id].clear_memory()
            del cls._instances[user_id]

    @classmethod
    async def clear_all(cls):
        """清除所有记忆"""
        for memory in cls._instances.values():
            await memory.clear_memory()
        cls._instances.clear()


# ============== 便捷函数 ==============


async def get_user_memory(user_id: int, db: AsyncSession) -> ConversationMemoryManager:
    """获取用户记忆管理器"""
    return await MemoryManagerV2.get_memory(user_id, db)


async def save_conversation(
    user_id: int, db: AsyncSession, user_message: str, ai_response: str
):
    """保存对话到记忆"""
    memory = await get_user_memory(user_id, db)
    await memory.save_interaction(user_message, ai_response)


async def get_conversation_history(
    user_id: int, db: AsyncSession, n: int = 5
) -> List[Dict[str, str]]:
    """获取最近 n 轮对话历史"""
    memory = await get_user_memory(user_id, db)
    return await memory.get_recent_messages(n)


# ============== 兼容性类 ==============


class WeightManagementMemory:
    """
    兼容性类：为 legacy agent 提供兼容的 WeightManagementMemory 接口

    注意：这是一个兼容层，实际功能委托给 ConversationMemoryManager
    """

    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self._memory_manager = None

    async def _get_memory_manager(self):
        """获取实际的记忆管理器"""
        if self._memory_manager is None:
            self._memory_manager = await get_user_memory(self.user_id, self.db)
        return self._memory_manager

    async def save_interaction(self, user_message: str, ai_response: str):
        """保存交互"""
        memory = await self._get_memory_manager()
        await memory.save_interaction(user_message, ai_response)

    async def get_recent_messages(self, n: int = 5) -> List[Dict[str, str]]:
        """获取最近消息"""
        memory = await self._get_memory_manager()
        return await memory.get_recent_messages(n)

    async def clear_memory(self):
        """清除记忆"""
        if self._memory_manager:
            await self._memory_manager.clear_memory()

    async def get_conversation_context(self, limit: int = 10) -> str:
        """获取对话上下文（兼容方法）"""
        memory = await self._get_memory_manager()
        messages = await memory.get_recent_messages(limit)

        # 转换为旧格式
        context = ""
        for msg in messages:
            if msg.get("role") == "user":
                context += f"用户: {msg.get('content', '')}\n"
            elif msg.get("role") == "assistant":
                context += f"助手: {msg.get('content', '')}\n"

        return context
