"""
通知调度器服务
使用后台线程定时检查并触发提醒
"""

import asyncio
import threading
import logging
from datetime import datetime, time as dt_time
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    ReminderSetting,
    ReminderType,
    User,
    AsyncSessionLocal,
    NotificationQueue,
)
from services.notification_worker import worker

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """通知调度器 - 每5分钟检查并触发提醒"""

    def __init__(self):
        self._timer: Optional[threading.Timer] = None
        self._interval_seconds = 300  # 5分钟
        self._running = False
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self):
        """启动调度器"""
        with self._lock:
            if self._running:
                logger.warning("通知调度器已在运行中")
                return

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            self._schedule_next()
            logger.info("通知调度器已启动 (间隔: %d秒)", self._interval_seconds)

    def stop(self):
        """停止调度器"""
        with self._lock:
            if not self._running:
                return

            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._loop = None

            logger.info("通知调度器已停止")

    def _schedule_next(self):
        """安排下次执行"""
        if not self._running:
            return

        self._timer = threading.Timer(self._interval_seconds, self._run_check)
        self._timer.daemon = True
        self._timer.start()

    def _run_check(self):
        """执行检查"""
        try:
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._check_and_trigger_reminders(), self._loop
                ).result(timeout=60)
        except Exception as e:
            logger.exception("执行提醒检查时发生错误: %s", e)
        finally:
            with self._lock:
                if self._running:
                    self._schedule_next()

    async def _check_and_trigger_reminders(self):
        """检查并触发提醒"""
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(ReminderSetting).where(ReminderSetting.enabled == True)
                )
                reminder_settings = result.scalars().all()

                current_time = datetime.now().time()
                current_weekday = datetime.now().weekday()

                for setting in reminder_settings:
                    if self._should_trigger(setting, current_time, current_weekday):
                        await self._create_notification(db, setting)

                await db.commit()

                processed = await worker.process_queue(db)
                if processed > 0:
                    await db.commit()
                    logger.info("通知Worker处理了 %d 条通知", processed)

            except Exception as e:
                await db.rollback()
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
