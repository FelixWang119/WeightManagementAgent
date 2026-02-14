"""
应用内聊天渠道
将通知作为机器人消息发送到用户的聊天界面
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from services.channels.base import NotificationChannel, NotificationResult, ChannelType
from models.database import AsyncSessionLocal, ChatHistory, MessageRole, MessageType

logger = logging.getLogger(__name__)


class ChatChannel(NotificationChannel):
    """应用内聊天渠道"""

    def __init__(self):
        super().__init__(ChannelType.CHAT)

    async def send(
        self,
        user_id: int,
        content: str,
        reminder_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """发送聊天消息"""
        async with AsyncSessionLocal() as db:
            try:
                chat_message = ChatHistory(
                    user_id=user_id,
                    role=MessageRole.ASSISTANT,
                    content=content,
                    msg_type=MessageType.TEXT,
                    meta_data={
                        "reminder_type": reminder_type,
                        "is_reminder": True,
                        **(metadata or {}),
                    },
                )
                db.add(chat_message)
                await db.commit()

                logger.info("聊天消息已发送: 用户 %d, 类型: %s", user_id, reminder_type)

                return NotificationResult(
                    success=True,
                    channel=self.channel_type,
                    message_id=str(chat_message.id),
                    sent_at=datetime.now(),
                )

            except Exception as e:
                logger.exception("发送聊天消息失败: %s", e)
                return NotificationResult(
                    success=False, channel=self.channel_type, error_message=str(e)
                )

    async def check_available(self, user_id: int) -> bool:
        """检查聊天渠道是否可用（总是可用）"""
        return True

    def get_channel_name(self) -> str:
        return "应用内聊天"


# 注册渠道实例
chat_channel = ChatChannel()
