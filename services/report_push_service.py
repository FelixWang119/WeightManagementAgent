"""
日报和周报推送服务
负责定时生成和推送日报/周报
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    ReminderSetting,
    ReminderType,
    AsyncSessionLocal,
    NotificationQueue,
)
from services.daily_report_service import DailyReportService
from services.weekly_report_service import weekly_report_service

logger = logging.getLogger(__name__)


class ReportPushService:
    """日报和周报推送服务"""

    def __init__(self):
        self.daily_service = DailyReportService()
        self.weekly_service = weekly_report_service

    async def generate_and_push_daily_report(
        self, user_id: int, db: AsyncSession
    ) -> bool:
        """
        生成并推送日报

        Args:
            user_id: 用户ID
            db: 数据库会话

        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始生成日报 - 用户ID: %d", user_id)

            # 生成日报
            report_date = date.today()
            result = await self.daily_service.generate_daily_report(
                user_id, report_date, db
            )

            if not result:
                logger.warning("日报生成失败 - 用户ID: %d", user_id)
                return False

            # 创建通知记录
            notification = NotificationQueue(
                user_id=user_id,
                reminder_type=ReminderType.DAILY.value,
                scheduled_at=datetime.now(),
                status="pending",
                retry_count=0,
                content_type="daily_report",
                content_data={
                    "report_date": report_date.isoformat(),
                    "report_id": result.get("id"),
                    "summary": result.get("summary_text", "")[:100] + "...",
                },
            )
            db.add(notification)

            logger.info("日报生成成功 - 用户ID: %d, 报告日期: %s", user_id, report_date)
            return True

        except Exception as e:
            logger.exception("生成日报时发生错误 - 用户ID: %d: %s", user_id, e)
            return False

    async def generate_and_push_weekly_report(
        self, user_id: int, db: AsyncSession
    ) -> bool:
        """
        生成并推送周报

        Args:
            user_id: 用户ID
            db: 数据库会话

        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始生成周报 - 用户ID: %d", user_id)

            # 计算周报日期范围（上周一至周日）
            today = date.today()
            start_date = today - timedelta(days=today.weekday() + 7)
            end_date = start_date + timedelta(days=6)

            # 生成周报
            result = await self.weekly_service.generate_weekly_report(
                user_id, start_date, end_date, db
            )

            if not result:
                logger.warning("周报生成失败 - 用户ID: %d", user_id)
                return False

            # 创建通知记录
            notification = NotificationQueue(
                user_id=user_id,
                reminder_type=ReminderType.WEEKLY.value,
                scheduled_at=datetime.now(),
                status="pending",
                retry_count=0,
                content_type="weekly_report",
                content_data={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "report_id": result.get("id"),
                    "summary": result.get("summary", "")[:100] + "...",
                },
            )
            db.add(notification)

            logger.info(
                "周报生成成功 - 用户ID: %d, 日期范围: %s 至 %s",
                user_id,
                start_date,
                end_date,
            )
            return True

        except Exception as e:
            logger.exception("生成周报时发生错误 - 用户ID: %d: %s", user_id, e)
            return False

    async def process_daily_reports(self):
        """处理所有用户的日报生成"""
        async with AsyncSessionLocal() as db:
            try:
                # 查询所有启用了日报提醒的用户
                result = await db.execute(
                    select(ReminderSetting).where(
                        ReminderSetting.reminder_type == ReminderType.DAILY,
                        ReminderSetting.enabled == True,
                    )
                )
                settings = result.scalars().all()

                logger.info("开始处理日报生成 - 用户数: %d", len(settings))

                success_count = 0
                for setting in settings:
                    success = await self.generate_and_push_daily_report(
                        setting.user_id, db
                    )
                    if success:
                        success_count += 1

                await db.commit()
                logger.info(
                    "日报处理完成 - 成功: %d, 总数: %d", success_count, len(settings)
                )

            except Exception as e:
                await db.rollback()
                logger.exception("处理日报时发生错误: %s", e)

    async def process_weekly_reports(self):
        """处理所有用户的周报生成"""
        async with AsyncSessionLocal() as db:
            try:
                # 查询所有启用了周报提醒的用户
                result = await db.execute(
                    select(ReminderSetting).where(
                        ReminderSetting.reminder_type == ReminderType.WEEKLY,
                        ReminderSetting.enabled == True,
                    )
                )
                settings = result.scalars().all()

                logger.info("开始处理周报生成 - 用户数: %d", len(settings))

                success_count = 0
                for setting in settings:
                    success = await self.generate_and_push_weekly_report(
                        setting.user_id, db
                    )
                    if success:
                        success_count += 1

                await db.commit()
                logger.info(
                    "周报处理完成 - 成功: %d, 总数: %d", success_count, len(settings)
                )

            except Exception as e:
                await db.rollback()
                logger.exception("处理周报时发生错误: %s", e)


# 全局实例
report_push_service = ReportPushService()
