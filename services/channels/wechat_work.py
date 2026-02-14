"""
企业微信渠道
TODO: 实现企业微信消息发送

当前为占位实现，需要配置企业微信应用后完成
"""

import logging
from typing import Optional, Dict, Any

from services.channels.base import NotificationChannel, NotificationResult, ChannelType

logger = logging.getLogger(__name__)


class WeChatWorkChannel(NotificationChannel):
    """企业微信渠道"""

    def __init__(self):
        super().__init__(ChannelType.WECHAT_WORK)
        self._enabled = False

    async def send(
        self,
        user_id: int,
        content: str,
        reminder_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """发送企业微信消息"""
        if not self._enabled:
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="企业微信渠道未启用",
            )

        logger.warning(
            "企业微信发送暂未实现: user_id=%d, type=%s", user_id, reminder_type
        )

        return NotificationResult(
            success=False,
            channel=self.channel_type,
            error_message="企业微信发送功能开发中",
        )

    async def check_available(self, user_id: int) -> bool:
        """检查企业微信是否可用"""
        if not self._enabled:
            return False

        # TODO: 检查用户是否绑定了企业微信
        return False

    def get_channel_name(self) -> str:
        return "企业微信"

    def enable(self):
        """启用企业微信渠道"""
        self._enabled = True
        logger.info("企业微信渠道已启用")

    def disable(self):
        """禁用企业微信渠道"""
        self._enabled = False
        logger.info("企业微信渠道已禁用")


# 注册渠道实例
wechat_work_channel = WeChatWorkChannel()
