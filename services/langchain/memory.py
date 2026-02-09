"""
记忆管理系统（简化版）

实现三层记忆架构：
1. 短期记忆：最近对话
2. 中期记忆：对话摘要
3. 长期记忆：用户画像 + 向量检索

使用 LangChain 的 Memory 组件，与现有数据库结合
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.vectorstore.chroma_store import (
    get_user_vector_store,
    search_user_memory,
    add_user_memory,
)


class SimpleMemory:
    """
    简化版记忆系统
    """

    def __init__(self, user_id: int, short_term_limit: int = 20):
        self.user_id = user_id
        self.short_term_limit = short_term_limit
        self.chat_history: List[Dict[str, str]] = []

    async def load_context(self) -> Dict[str, Any]:
        return {"chat_history": self.chat_history}

    def save_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        self.chat_history.append({"role": role, "content": content})
        # 如果超过限制，只保留最近的对话轮次
        if len(self.chat_history) > self.short_term_limit * 2:
            self.chat_history = self.chat_history[-self.short_term_limit * 2:]

    def get_chat_history(self) -> List[Dict[str, str]]:
        return self.chat_history

    async def search_memory(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        return search_user_memory(self.user_id, query, k=k)

    async def clear(self):
        self.chat_history = []


class WeightManagementMemory:
    """
    体重管理专用记忆系统
    """

    def __init__(
        self,
        user_id: int,
        short_term_limit: int = 10,
        enable_vector_memory: bool = True
    ):
        self.user_id = user_id
        self.short_term_limit = short_term_limit
        self.enable_vector_memory = enable_vector_memory
        self.memory = SimpleMemory(user_id, short_term_limit=short_term_limit)
        self.vector_store = get_user_vector_store(user_id) if enable_vector_memory else None

    async def load_context(self) -> Dict[str, Any]:
        return await self.memory.load_context()

    async def save_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        self.memory.save_message(role, content, metadata)
        if self.vector_store and role == "user":
            await add_user_memory(
                user_id=self.user_id,
                content=content,
                category=metadata.get("category", "general") if metadata else "general",
                metadata={**(metadata or {}), "saved_at": datetime.now().isoformat()}
            )

    def get_chat_history(self) -> List[Dict[str, str]]:
        return self.memory.get_chat_history()

    async def get_summary(self) -> str:
        return ""

    async def search_memory(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if not self.vector_store:
            return []
        return search_user_memory(self.user_id, query, k=k)

    async def clear(self):
        await self.memory.clear()


class MemoryManager:
    _instances: Dict[int, WeightManagementMemory] = {}

    @classmethod
    async def get_memory(
        cls,
        user_id: int,
        db: AsyncSession  # 保留参数以保持API兼容性，但不再使用
    ) -> WeightManagementMemory:
        if user_id not in cls._instances:
            cls._instances[user_id] = WeightManagementMemory(
                user_id=user_id,
            )
        # 注意：内存类不再存储数据库会话
        # 如果未来需要数据库操作，应该传递db参数给具体方法
        return cls._instances[user_id]

    @classmethod
    async def save_message(
        cls,
        user_id: int,
        db: AsyncSession,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        memory = await cls.get_memory(user_id, db)
        await memory.save_message(role, content, metadata)

    @classmethod
    async def load_context(
        cls,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        memory = await cls.get_memory(user_id, db)
        return await memory.load_context()

    @classmethod
    def clear_user_memory(cls, user_id: int):
        if user_id in cls._instances:
            del cls._instances[user_id]


async def get_user_memory(user_id: int, db: AsyncSession) -> WeightManagementMemory:
    return await MemoryManager.get_memory(user_id, db)


async def save_to_memory(
    user_id: int,
    db: AsyncSession,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
):
    await MemoryManager.save_message(user_id, db, role, content, metadata)
