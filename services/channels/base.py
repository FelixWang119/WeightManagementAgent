"""
通知渠道抽象基类
定义渠道接口，支持扩展到微信、企业微信等
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ChannelType(str, Enum):
    """渠道类型"""

    CHAT = "chat"  # 应用内聊天
    WECHAT = "wechat"  # 微信公众号
    WECHAT_WORK = "wechat_work"  # 企业微信
    SMS = "sms"  # 短信
    PUSH = "push"  # 推送通知


@dataclass
class NotificationResult:
    """通知发送结果"""

    success: bool
    channel: ChannelType
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "channel": self.channel.value,
            "message_id": self.message_id,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


class NotificationChannel(ABC):
    """通知渠道基类"""

    def __init__(self, channel_type: ChannelType):
        self.channel_type = channel_type

    @abstractmethod
    async def send(
        self,
        user_id: int,
        content: str,
        reminder_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """
        发送通知

        Args:
            user_id: 用户ID
            content: 通知内容
            reminder_type: 提醒类型
            metadata: 额外元数据

        Returns:
            NotificationResult: 发送结果
        """
        pass

    @abstractmethod
    async def check_available(self, user_id: int) -> bool:
        """
        检查渠道是否可用

        Args:
            user_id: 用户ID

        Returns:
            bool: 渠道是否可用
        """
        pass

    @abstractmethod
    def get_channel_name(self) -> str:
        """获取渠道名称"""
        pass

    async def send_batch(
        self, notifications: list[Dict[str, Any]]
    ) -> list[NotificationResult]:
        """
        批量发送通知

        默认实现：逐个发送
        子类可以重写以优化批量发送
        """
        results = []
        for notif in notifications:
            result = await self.send(
                user_id=notif["user_id"],
                content=notif["content"],
                reminder_type=notif.get("reminder_type", "general"),
                metadata=notif.get("metadata"),
            )
            results.append(result)
        return results


class ChannelManager:
    """渠道管理器"""

    _channels: Dict[ChannelType, NotificationChannel] = {}
    _default_channel: ChannelType = ChannelType.CHAT

    @classmethod
    def register(cls, channel: NotificationChannel):
        """注册渠道"""
        cls._channels[channel.channel_type] = channel

    @classmethod
    def get(cls, channel_type: ChannelType) -> Optional[NotificationChannel]:
        """获取渠道"""
        return cls._channels.get(channel_type)

    @classmethod
    def get_default(cls) -> NotificationChannel:
        """获取默认渠道"""
        return cls._channels.get(cls._default_channel)

    @classmethod
    def set_default(cls, channel_type: ChannelType):
        """设置默认渠道"""
        cls._default_channel = channel_type

    @classmethod
    async def send_to_user(
        cls,
        user_id: int,
        content: str,
        reminder_type: str,
        preferred_channel: Optional[ChannelType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """
        发送通知到用户（自动选择可用渠道）

        优先级：
        1. 指定渠道（如可用）
        2. 用户配置的偏好渠道
        3. 默认渠道
        """
        # 尝试指定渠道
        if preferred_channel:
            channel = cls.get(preferred_channel)
            if channel and await channel.check_available(user_id):
                return await channel.send(user_id, content, reminder_type, metadata)

        # 尝试默认渠道
        default_channel = cls.get_default()
        if default_channel and await default_channel.check_available(user_id):
            return await default_channel.send(user_id, content, reminder_type, metadata)

        # 尝试所有可用渠道
        for channel in cls._channels.values():
            if await channel.check_available(user_id):
                return await channel.send(user_id, content, reminder_type, metadata)

        # 所有渠道都不可用
        return NotificationResult(
            success=False, channel=ChannelType.CHAT, error_message="没有可用的通知渠道"
        )

    @classmethod
    def list_channels(cls) -> list[str]:
        """列出所有已注册的渠道"""
        return [ch.get_channel_name() for ch in cls._channels.values()]
