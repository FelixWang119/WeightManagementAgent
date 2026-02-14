"""
通知Worker服务
处理队列中的通知并发送
"""

import logging
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import ReminderSetting, User, NotificationQueue
from services.channels import ChannelManager, ChannelType

logger = logging.getLogger(__name__)


class NotificationWorker:
    """通知Worker - 处理队列中的通知"""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    async def process_queue(self, db: AsyncSession) -> int:
        """处理队列，返回处理数量"""
        try:
            result = await db.execute(
                select(NotificationQueue)
                .where(
                    and_(
                        NotificationQueue.status == "pending",
                        NotificationQueue.retry_count < NotificationQueue.max_retries,
                    )
                )
                .order_by(NotificationQueue.scheduled_at)
                .limit(self.batch_size)
            )
            notifications = result.scalars().all()

            processed = 0
            for notification in notifications:
                await self._process_notification(db, notification)
                processed += 1

            return processed

        except Exception as e:
            logger.exception("处理通知队列时发生错误: %s", e)
            return 0

    async def _process_notification(
        self, db: AsyncSession, notification: NotificationQueue
    ):
        """处理单条通知"""
        try:
            user_result = await db.execute(
                select(User).where(User.id == notification.user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                notification.status = "failed"
                notification.error_message = "用户不存在"
                notification.sent_at = datetime.now()
                logger.warning(
                    "通知 %d: 用户 %d 不存在", notification.id, notification.user_id
                )
                return

            reminder_result = await db.execute(
                select(ReminderSetting).where(
                    and_(
                        ReminderSetting.user_id == notification.user_id,
                        ReminderSetting.reminder_type == notification.reminder_type,
                    )
                )
            )
            reminder = reminder_result.scalar_one_or_none()

            if not reminder or not reminder.enabled:
                notification.status = "skipped"
                notification.sent_at = datetime.now()
                logger.info(
                    "通知 %d: 用户 %d 的 %s 提醒已禁用",
                    notification.id,
                    notification.user_id,
                    notification.reminder_type,
                )
                return

            message = await self._generate_message(
                notification.reminder_type.value
                if hasattr(notification.reminder_type, "value")
                else str(notification.reminder_type),
                user,
                reminder,
            )
            notification.message = message

            success = await self._send_via_channel(notification, message, user)

            if success:
                notification.status = "sent"
                notification.sent_at = datetime.now()
                logger.info(
                    "通知 %d 已发送到用户 %d", notification.id, notification.user_id
                )
            else:
                notification.retry_count += 1
                if notification.retry_count >= notification.max_retries:
                    notification.status = "failed"
                    notification.error_message = "发送失败，已达最大重试次数"
                logger.warning(
                    "通知 %d 发送失败，重试次数: %d",
                    notification.id,
                    notification.retry_count,
                )

        except Exception as e:
            notification.retry_count += 1
            notification.error_message = str(e)
            if notification.retry_count >= notification.max_retries:
                notification.status = "failed"
            logger.exception("处理通知 %d 时发生错误: %s", notification.id, e)

    async def _generate_message(
        self, reminder_type: str, user: User, reminder: ReminderSetting
    ) -> str:
        """生成通知消息"""
        templates = {
            "weight": "早上好{username}！记得记录今天的体重哦，坚持就是胜利！",
            "breakfast": "{username}，早餐时间到！记得记录早餐内容，开启元气满满的一天！",
            "lunch": "{username}，午餐时间！记录午餐内容，注意营养均衡哦~",
            "dinner": "{username}，晚餐时间！记得记录晚餐，晚餐建议清淡一些哦~",
            "exercise": "{username}，运动时间！起来活动一下吧，健康体魄从运动开始！",
            "water": "{username}，该喝水啦！保持充足水分，促进新陈代谢~",
            "sleep": "{username}，夜深了，该准备休息了。良好的睡眠是健康的基础，晚安！",
        }

        template = templates.get(reminder_type, "该记录{type}了哦~")
        username = user.username or "朋友"

        return template.format(username=username, type=reminder_type)

    async def _send_via_channel(
        self,
        notification: NotificationQueue,
        message: str,
        user: User,
    ) -> bool:
        """通过渠道发送通知"""
        try:
            result = await ChannelManager.send_to_user(
                user_id=user.id,
                content=message,
                reminder_type=notification.reminder_type,
                preferred_channel=ChannelType.CHAT,
                metadata={
                    "notification_id": notification.id,
                    "channel": notification.channel,
                },
            )

            if result.success:
                logger.info(
                    "通知 %d 发送成功: 用户 %d, 渠道: %s",
                    notification.id,
                    user.id,
                    result.channel.value,
                )
            else:
                logger.warning(
                    "通知 %d 发送失败: %s", notification.id, result.error_message
                )

            return result.success

        except Exception as e:
            logger.exception("发送通知失败: %s", e)
            return False

    async def cleanup_old_notifications(self, db: AsyncSession, days: int = 7):
        """清理旧通知记录"""
        try:
            from datetime import timedelta

            cutoff = datetime.now() - timedelta(days=days)

            result = await db.execute(
                select(NotificationQueue).where(
                    NotificationQueue.status.in_(["sent", "failed", "skipped"]),
                    NotificationQueue.created_at < cutoff,
                )
            )
            old_notifications = result.scalars().all()

            for notif in old_notifications:
                await db.delete(notif)

            await db.commit()
            logger.info("已清理 %d 条旧通知记录", len(old_notifications))

        except Exception as e:
            await db.rollback()
            logger.exception("清理旧通知失败: %s", e)


worker = NotificationWorker()
