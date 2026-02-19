"""
增强版对话缓冲记忆，支持类型化容量控制
短期记忆：30条打卡记录 + 200条对话记录

注意：由于LangChain 1.x版本变化，这里实现一个简化的内存系统
不依赖langchain.memory模块
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime


# 简单的消息类定义
class BaseMessage:
    def __init__(self, content: str):
        self.content = content


class HumanMessage(BaseMessage):
    pass


class AIMessage(BaseMessage):
    pass


class MemoryType(Enum):
    """记忆类型枚举"""

    CHECKIN = "checkin"  # 打卡记录
    CONVERSATION = "conversation"  # 对话记录
    SUMMARY = "summary"  # 摘要记录


class TypedConversationBufferMemory:
    """
    类型化对话缓冲记忆
    支持按类型控制容量，自动清理超限记录
    """

    def __init__(
        self,
        checkin_capacity: int = 30,  # 打卡记录容量
        conversation_capacity: int = 200,  # 对话记录容量
        **kwargs,
    ):
        self.checkin_capacity = checkin_capacity
        self.conversation_capacity = conversation_capacity
        self.checkin_messages: List[Dict[str, Any]] = []  # 打卡记录
        self.conversation_messages: List[Dict[str, Any]] = []  # 对话记录

    def add_message(
        self, message: BaseMessage, memory_type: MemoryType = MemoryType.CONVERSATION
    ) -> None:
        """
        添加消息到指定类型的记忆

        Args:
            message: 消息对象
            memory_type: 记忆类型
        """
        # 获取记忆类型的字符串值
        if isinstance(memory_type, MemoryType):
            type_str = memory_type.value
        else:
            type_str = str(memory_type)

        message_dict = {
            "type": type_str,
            "content": message.content,
            "timestamp": datetime.now().isoformat(),
            "role": "human" if isinstance(message, HumanMessage) else "ai",
        }

        # 检查记忆类型
        if type_str == MemoryType.CHECKIN.value or type_str == "checkin":
            self.checkin_messages.append(message_dict)
            # 检查容量，清理最旧的记录
            if len(self.checkin_messages) > self.checkin_capacity:
                self.checkin_messages = self.checkin_messages[-self.checkin_capacity :]
        elif type_str == MemoryType.CONVERSATION.value or type_str == "conversation":
            self.conversation_messages.append(message_dict)
            # 检查容量，清理最旧的记录
            if len(self.conversation_messages) > self.conversation_capacity:
                self.conversation_messages = self.conversation_messages[
                    -self.conversation_capacity :
                ]
        elif type_str == MemoryType.SUMMARY.value or type_str == "summary":
            self.summary_messages.append(message_dict)
            # 检查容量，清理最旧的记录
            if len(self.summary_messages) > self.summary_capacity:
                self.summary_messages = self.summary_messages[-self.summary_capacity :]

    def get_messages_by_type(
        self, memory_type: MemoryType, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定类型的消息

        Args:
            memory_type: 记忆类型
            limit: 限制返回数量

        Returns:
            消息列表
        """
        # 获取记忆类型的字符串值
        if isinstance(memory_type, MemoryType):
            type_str = memory_type.value
        else:
            type_str = str(memory_type)

        if type_str == MemoryType.CHECKIN.value or type_str == "checkin":
            messages = self.checkin_messages
        elif type_str == MemoryType.CONVERSATION.value or type_str == "conversation":
            messages = self.conversation_messages
        elif type_str == MemoryType.SUMMARY.value or type_str == "summary":
            messages = self.summary_messages
        else:
            messages = self.conversation_messages  # 默认返回对话消息

        if limit:
            return messages[-limit:]
        return messages.copy()

    def get_recent_checkins(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的打卡记录

        Args:
            limit: 限制返回数量

        Returns:
            打卡记录列表
        """
        return self.get_messages_by_type(MemoryType.CHECKIN, limit)

    def get_recent_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的对话记录

        Args:
            limit: 限制返回数量

        Returns:
            对话记录列表
        """
        return self.get_messages_by_type(MemoryType.CONVERSATION, limit)

    def get_combined_context(
        self, checkin_limit: int = 10, conversation_limit: int = 10
    ) -> str:
        """
        获取组合上下文（打卡记录 + 对话记录）

        Args:
            checkin_limit: 打卡记录限制
            conversation_limit: 对话记录限制

        Returns:
            组合后的上下文文本
        """
        context_parts = []

        # 添加打卡记录
        checkins = self.get_recent_checkins(checkin_limit)
        if checkins:
            context_parts.append("=== 最近打卡记录 ===")
            for checkin in checkins:
                context_parts.append(f"[{checkin['timestamp']}] {checkin['content']}")

        # 添加对话记录
        conversations = self.get_recent_conversations(conversation_limit)
        if conversations:
            context_parts.append("\n=== 最近对话 ===")
            for conv in conversations:
                role = "用户" if conv["role"] == "human" else "助手"
                context_parts.append(f"[{conv['timestamp']}] {role}: {conv['content']}")

        return "\n".join(context_parts)

    def clear(self) -> None:
        """
        清理所有记忆
        """
        self.checkin_messages.clear()
        self.conversation_messages.clear()

    def clear_memory_by_type(self, memory_type: MemoryType) -> None:
        """
        清理指定类型的记忆

        Args:
            memory_type: 记忆类型
        """
        if memory_type == MemoryType.CHECKIN:
            self.checkin_messages.clear()
        else:
            self.conversation_messages.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息字典
        """
        return {
            "checkin_count": len(self.checkin_messages),
            "checkin_capacity": self.checkin_capacity,
            "conversation_count": len(self.conversation_messages),
            "conversation_capacity": self.conversation_capacity,
            "total_count": len(self.checkin_messages) + len(self.conversation_messages),
        }
