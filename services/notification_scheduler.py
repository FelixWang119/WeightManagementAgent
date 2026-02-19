"""
通知调度器服务
使用 APScheduler 进行定时任务调度
"""

import logging
from datetime import datetime, time as dt_time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    ReminderSetting,
    NotificationQueue,
    AsyncSessionLocal,
)

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """通知调度器 - 使用 APScheduler 进行定时任务调度"""

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._interval_seconds = 300  # 5分钟
        self._running = False

    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("通知调度器已在运行中")
            return

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._check_and_trigger_reminders,
            IntervalTrigger(seconds=self._interval_seconds),
            id="reminder_check",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("通知调度器已启动 (间隔: %d秒)", self._interval_seconds)

    def stop(self):
        """停止调度器"""
        if not self._running:
            return

        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

        self._running = False
        logger.info("通知调度器已停止")

    async def _check_and_trigger_reminders(self):
        """检查并触发提醒"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ReminderSetting).where(ReminderSetting.enabled.is_(True))
                )
                reminder_settings = result.scalars().all()

                current_time = datetime.now().time()
                current_weekday = datetime.now().weekday()

                for setting in reminder_settings:
                    if self._should_trigger(setting, current_time, current_weekday):
                        await self._create_notification(db, setting)

                await db.commit()

        except Exception as e:
            logger.exception("检查提醒时发生错误: %s", e)

    def _should_trigger(
        self, setting: ReminderSetting, current_time: dt_time, current_weekday: int
    ) -> bool:
        """判断是否应该触发提醒"""
        if setting.weekdays_only and current_weekday >= 5:
            return False

        if setting.reminder_time is None:
            return False

        reminder_time = setting.reminder_time
        time_diff = (
            datetime.combine(datetime.today(), current_time)
            - datetime.combine(datetime.today(), reminder_time)
        ).total_seconds()

        return 0 <= time_diff <= 300

    async def _create_notification(self, db: AsyncSession, setting: ReminderSetting):
        """创建通知记录"""
        notification = NotificationQueue(
            user_id=setting.user_id,
            reminder_type=setting.reminder_type.value,
            scheduled_at=datetime.now(),
            status="pending",
            retry_count=0,
        )
        db.add(notification)
        logger.info(
            "为用户 %d 创建 %s 提醒", setting.user_id, setting.reminder_type.value
        )

    async def force_check(self):
        """强制立即检查（用于测试或手动触发）"""
        await self._check_and_trigger_reminders()


scheduler = NotificationScheduler()
