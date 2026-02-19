"""
日报和周报调度器
扩展原有通知调度器，支持日报和周报的定时生成
"""

import asyncio
import threading
import logging
from datetime import datetime, time as dt_time, date, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    ReminderSetting,
    ReminderType,
    AsyncSessionLocal,
    NotificationQueue,
)
from services.report_push_service import report_push_service

logger = logging.getLogger(__name__)


class ReportScheduler:
    """日报和周报调度器 - 每5分钟检查并触发报告生成"""

    def __init__(self):
        self._timer: Optional[threading.Timer] = None
        self._interval_seconds = 300  # 5分钟
        self._running = False
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_daily_check: Optional[date] = None
        self._last_weekly_check: Optional[date] = None

    def start(self):
        """启动调度器"""
        with self._lock:
            if self._running:
                logger.warning("报告调度器已在运行中")
                return

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            self._schedule_next()
            logger.info("报告调度器已启动 (间隔: %d秒)", self._interval_seconds)

    def stop(self):
        """停止调度器"""
        with self._lock:
            if not self._running:
                return

            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

            if self._loop:
                self._loop.stop()

            logger.info("报告调度器已停止")

    def _schedule_next(self):
        """安排下一次检查"""
        if not self._running:
            return

        self._timer = threading.Timer(self._interval_seconds, self._run_check)
        self._timer.daemon = True
        self._timer.start()

    def _run_check(self):
        """运行检查（在后台线程中）"""
        try:
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._check_and_generate_reports(), self._loop
                )
        except Exception as e:
            logger.exception("运行报告检查时发生错误: %s", e)
        finally:
            self._schedule_next()

    async def _check_and_generate_reports(self):
        """检查并生成报告"""
        current_time = datetime.now().time()
        current_date = date.today()
        current_weekday = datetime.now().weekday()  # 0=周一, 6=周日

        logger.debug(
            "检查报告生成 - 时间: %s, 日期: %s, 星期: %d",
            current_time,
            current_date,
            current_weekday,
        )

        async with AsyncSessionLocal() as db:
            try:
                # 查询所有提醒设置
                result = await db.execute(
                    select(ReminderSetting).where(ReminderSetting.enabled == True)
                )
                reminder_settings = result.scalars().all()

                for setting in reminder_settings:
                    if self._should_generate_report(
                        setting, current_time, current_date, current_weekday
                    ):
                        await self._generate_report(db, setting)

                await db.commit()

            except Exception as e:
                await db.rollback()
                logger.exception("检查报告生成时发生错误: %s", e)

    def _should_generate_report(
        self,
        setting: ReminderSetting,
        current_time: dt_time,
        current_date: date,
        current_weekday: int,
    ) -> bool:
        """判断是否应该生成报告"""
        # 检查提醒类型
        if setting.reminder_type not in [ReminderType.DAILY, ReminderType.WEEKLY]:
            return False

        # 检查是否工作日限定
        if setting.weekdays_only and current_weekday >= 5:
            return False

        # 检查提醒时间
        if setting.reminder_time is None:
            return False

        # 计算时间差
        reminder_time = setting.reminder_time
        time_diff = (
            datetime.combine(datetime.today(), current_time)
            - datetime.combine(datetime.today(), reminder_time)
        ).total_seconds()

        # 在提醒时间前后5分钟内触发
        if not (0 <= time_diff <= 300):
            return False

        # 日报：每天只生成一次
        if setting.reminder_type == ReminderType.DAILY:
            if self._last_daily_check == current_date:
                return False
            self._last_daily_check = current_date
            return True

        # 周报：每周日生成（current_weekday == 6）
        elif setting.reminder_type == ReminderType.WEEKLY:
            if current_weekday != 6:  # 不是周日
                return False
            if self._last_weekly_check == current_date:
                return False
            self._last_weekly_check = current_date
            return True

        return False

    async def _generate_report(self, db: AsyncSession, setting: ReminderSetting):
        """生成报告"""
        try:
            if setting.reminder_type == ReminderType.DAILY:
                success = await report_push_service.generate_and_push_daily_report(
                    setting.user_id, db
                )
                if success:
                    logger.info("日报生成成功 - 用户ID: %d", setting.user_id)
                else:
                    logger.warning("日报生成失败 - 用户ID: %d", setting.user_id)

            elif setting.reminder_type == ReminderType.WEEKLY:
                success = await report_push_service.generate_and_push_weekly_report(
                    setting.user_id, db
                )
                if success:
                    logger.info("周报生成成功 - 用户ID: %d", setting.user_id)
                else:
                    logger.warning("周报生成失败 - 用户ID: %d", setting.user_id)

        except Exception as e:
            logger.exception("生成报告时发生错误 - 用户ID: %d: %s", setting.user_id, e)

    async def force_generate_daily_reports(self):
        """强制立即生成所有日报（用于测试或手动触发）"""
        await report_push_service.process_daily_reports()

    async def force_generate_weekly_reports(self):
        """强制立即生成所有周报（用于测试或手动触发）"""
        await report_push_service.process_weekly_reports()

    async def force_check(self):
        """强制立即检查（用于测试或手动触发）"""
        await self._check_and_generate_reports()


# 全局实例
report_scheduler = ReportScheduler()
