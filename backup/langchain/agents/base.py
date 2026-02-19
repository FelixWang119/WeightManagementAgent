"""
基础Agent接口和抽象类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

# 使用自定义的消息类，避免LangChain版本兼容问题
from services.langchain.memory.manager import BaseMessage, HumanMessage, AIMessage
from services.langchain.memory import MemoryManager, MemoryType


class BaseAgent(ABC):
    """
    Agent基础抽象类
    所有具体Agent都应继承此类
    """

    def __init__(self, user_id: int, memory_manager: Optional[MemoryManager] = None):
        """
        初始化Agent

        Args:
            user_id: 用户ID
            memory_manager: 记忆管理器实例
        """
        self.user_id = user_id
        self.memory_manager = memory_manager or MemoryManager(user_id)
        self.agent_name = self.__class__.__name__

    @abstractmethod
    async def chat(self, message: str, **kwargs) -> Dict[str, Any]:
        """
        处理用户消息

        Args:
            message: 用户消息
            **kwargs: 额外参数

        Returns:
            响应结果
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取系统提示

        Returns:
            系统提示文本
        """
        pass

    def add_to_memory(
        self, user_message: str, assistant_response: str
    ) -> Dict[str, Any]:
        """
        添加对话到记忆

        Args:
            user_message: 用户消息
            assistant_response: 助手回复

        Returns:
            记忆添加结果
        """
        results = {}

        # 添加用户消息到记忆
        user_msg = HumanMessage(content=user_message)
        user_result = self.memory_manager.add_message(
            message=user_msg,
            memory_type=MemoryType.CONVERSATION,
            metadata={"agent": self.agent_name},
        )
        results["user_message_added"] = user_result

        # 添加助手回复到记忆
        assistant_msg = AIMessage(content=assistant_response)
        assistant_result = self.memory_manager.add_message(
            message=assistant_msg,
            memory_type=MemoryType.CONVERSATION,
            metadata={"agent": self.agent_name, "role": "assistant"},
        )
        results["assistant_message_added"] = assistant_result

        return results

    def get_context(self, query: Optional[str] = None, **kwargs) -> str:
        """
        获取对话上下文

        Args:
            query: 查询文本（用于检索长期记忆）
            **kwargs: 额外参数

        Returns:
            上下文文本
        """
        return self.memory_manager.get_context(
            checkin_limit=kwargs.get("checkin_limit", 10),
            conversation_limit=kwargs.get("conversation_limit", 10),
            include_long_term=kwargs.get("include_long_term", True),
            query=query,
        )

    def search_memories(self, query: str, **kwargs) -> Dict[str, List[Dict[str, Any]]]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            **kwargs: 额外参数

        Returns:
            搜索结果
        """
        return self.memory_manager.search_memories(
            query=query,
            memory_type=kwargs.get("memory_type"),
            limit=kwargs.get("limit", 10),
            include_short_term=kwargs.get("include_short_term", True),
            include_long_term=kwargs.get("include_long_term", True),
        )

    def get_checkin_history(self, **kwargs) -> List[Dict[str, Any]]:
        """
        获取打卡历史

        Args:
            **kwargs: 额外参数

        Returns:
            打卡记录列表
        """
        return self.memory_manager.get_checkin_history(
            checkin_type=kwargs.get("checkin_type"),
            limit=kwargs.get("limit", 20),
            include_short_term=kwargs.get("include_short_term", True),
            include_long_term=kwargs.get("include_long_term", True),
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        获取Agent统计信息

        Returns:
            统计信息
        """
        return {
            "agent_name": self.agent_name,
            "user_id": self.user_id,
            "memory_stats": self.memory_manager.get_stats(),
        }

    def clear_memories(self, **kwargs) -> Dict[str, int]:
        """
        清理记忆

        Args:
            **kwargs: 额外参数

        Returns:
            清理结果
        """
        return self.memory_manager.clear_memories(
            memory_type=kwargs.get("memory_type"),
            clear_short_term=kwargs.get("clear_short_term", True),
            clear_long_term=kwargs.get("clear_long_term", False),
        )
