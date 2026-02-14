"""
通知渠道模块
"""

from services.channels.base import (
    NotificationChannel,
    NotificationResult,
    ChannelType,
    ChannelManager,
)
from services.channels.chat import chat_channel
from services.channels.wechat_work import wechat_work_channel


def init_channels():
    """初始化并注册所有渠道"""
    ChannelManager.register(chat_channel)
    ChannelManager.register(wechat_work_channel)
    ChannelManager.set_default(ChannelType.CHAT)
    print(f"已注册渠道: {ChannelManager.list_channels()}")


__all__ = [
    "NotificationChannel",
    "NotificationResult",
    "ChannelType",
    "ChannelManager",
    "chat_channel",
    "wechat_work_channel",
    "init_channels",
]
