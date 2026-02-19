"""
增强通知服务
支持多种触发条件、优先级管理和用户偏好设置
"""

import asyncio
import logging
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from models.database import (
    User,
    ReminderSetting,
    ReminderType,
    NotificationQueue,
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    Goal,
    GoalStatus,
    WeeklyReport,
)
from config.logging_config import get_module_logger
from utils.exceptions import retry_on_error

logger = get_module_logger(__name__)


class NotificationPriority(str, Enum):
    """通知优先级"""

    HIGH = "high"  # 重要通知：目标达成、异常数据
    MEDIUM = "medium"  # 常规通知：提醒、报告
    LOW = "low"  # 次要通知：鼓励、建议


class NotificationTrigger(str, Enum):
    """通知触发条件"""

    TIME_BASED = "time_based"  # 时间触发（固定时间）
    EVENT_BASED = "event_based"  # 事件触发（数据记录）
    ACHIEVEMENT = "achievement"  # 成就达成
    GOAL_PROGRESS = "goal_progress"  # 目标进度
    DATA_ANOMALY = "data_anomaly"  # 数据异常
    SYSTEM = "system"  # 系统通知


class NotificationChannel(str, Enum):
    """通知渠道"""

    CHAT = "chat"  # 聊天界面
    PUSH = "push"  # 推送通知
    EMAIL = "email"  # 邮件
    SMS = "sms"  # 短信


class NotificationService:
    """增强通知服务"""

    def __init__(self):
        self._triggers: Dict[NotificationTrigger, Any] = {}
        self._register_default_triggers()

    def _register_default_triggers(self):
        """注册默认触发条件"""
        self._triggers[NotificationTrigger.TIME_BASED] = self._check_time_based_triggers
        self._triggers[NotificationTrigger.EVENT_BASED] = (
            self._check_event_based_triggers
        )
        self._triggers[NotificationTrigger.ACHIEVEMENT] = (
            self._check_achievement_triggers
        )
        self._triggers[NotificationTrigger.GOAL_PROGRESS] = (
            self._check_goal_progress_triggers
        )
        self._triggers[NotificationTrigger.DATA_ANOMALY] = (
            self._check_data_anomaly_triggers
        )

    @retry_on_error(max_attempts=3, delay=1.0)
    async def check_and_create_notifications(self, db: AsyncSession) -> Dict[str, Any]:
        """检查所有触发条件并创建通知"""
        try:
            notifications_created = []

            # 获取所有活跃用户
            result = await db.execute(select(User.id))
            user_ids = [row[0] for row in result.all()]

            for user_id in user_ids:
                # 检查用户通知偏好
                user_preferences = await self._get_user_notification_preferences(
                    user_id, db
                )
                if not user_preferences.get("enabled", True):
                    continue

                # 检查各种触发条件
                for trigger_type, trigger_func in self._triggers.items():
                    # 检查用户是否启用该类型通知
                    if not user_preferences.get(f"enable_{trigger_type.value}", True):
                        continue

                    notifications = await trigger_func(user_id, db, user_preferences)
                    if notifications:
                        notifications_created.extend(notifications)

            # 批量保存通知
            if notifications_created:
                db.add_all(notifications_created)
                await db.commit()
                logger.info("创建了 %d 个通知", len(notifications_created))

            return {
                "success": True,
                "notifications_created": len(notifications_created),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception("检查通知触发条件失败: %s", e)
            return {"success": False, "error": str(e), "notifications_created": 0}

    async def _check_time_based_triggers(
        self, user_id: int, db: AsyncSession, preferences: Dict[str, Any]
    ) -> List[NotificationQueue]:
        """检查时间触发条件"""
        notifications = []
        current_time = datetime.now().time()
        current_weekday = datetime.now().weekday()

        # 获取用户的提醒设置
        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == user_id, ReminderSetting.enabled == True
                )
            )
        )
        reminder_settings = result.scalars().all()

        for setting in reminder_settings:
            if not self._should_trigger_time_based(
                setting, current_time, current_weekday
            ):
                continue

            # 检查是否在免打扰时段
            if self._is_quiet_hours(current_time, preferences):
                logger.debug("用户 %d 处于免打扰时段，跳过提醒", user_id)
                continue

            # 创建通知
            notification = self._create_notification(
                user_id=user_id,
                reminder_type=setting.reminder_type.value,
                trigger_type=NotificationTrigger.TIME_BASED,
                priority=NotificationPriority.MEDIUM,
                message=self._generate_time_based_message(setting),
                channel=preferences.get("preferred_channel", NotificationChannel.CHAT),
            )
            notifications.append(notification)

            # 更新上次触发时间 - 需要在事务中处理
            pass

        return notifications

    async def _check_event_based_triggers(
        self, user_id: int, db: AsyncSession, preferences: Dict[str, Any]
    ) -> List[NotificationQueue]:
        """检查事件触发条件"""
        notifications = []
        today = date.today()

        # 检查今日是否已记录体重
        result = await db.execute(
            select(WeightRecord).where(
                and_(WeightRecord.user_id == user_id, WeightRecord.record_date == today)
            )
        )
        weight_record = result.scalar_one_or_none()

        if not weight_record and preferences.get("enable_weight_reminder", True):
            # 检查是否已发送过提醒
            result = await db.execute(
                select(NotificationQueue).where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.reminder_type == ReminderType.WEIGHT.value,
                        func.date(NotificationQueue.created_at) == today,
                    )
                )
            )
            existing_notification = result.scalar_one_or_none()

            if not existing_notification:
                notification = self._create_notification(
                    user_id=user_id,
                    reminder_type=ReminderType.WEIGHT.value,
                    trigger_type=NotificationTrigger.EVENT_BASED,
                    priority=NotificationPriority.MEDIUM,
                    message="今天还没记录体重哦，记得称一下体重～",
                    channel=preferences.get(
                        "preferred_channel", NotificationChannel.CHAT
                    ),
                )
                notifications.append(notification)

        # 检查今日是否已记录三餐
        meal_types_to_check = [
            ReminderType.BREAKFAST,
            ReminderType.LUNCH,
            ReminderType.DINNER,
        ]
        for meal_type in meal_types_to_check:
            if not preferences.get(f"enable_{meal_type.value}_reminder", True):
                continue

            result = await db.execute(
                select(MealRecord).where(
                    and_(
                        MealRecord.user_id == user_id,
                        MealRecord.meal_type == meal_type.value,
                        func.date(MealRecord.record_time) == today,
                    )
                )
            )
            meal_record = result.scalar_one_or_none()

            if not meal_record:
                # 检查是否已发送过提醒
                result = await db.execute(
                    select(NotificationQueue).where(
                        and_(
                            NotificationQueue.user_id == user_id,
                            NotificationQueue.reminder_type == meal_type.value,
                            func.date(NotificationQueue.created_at) == today,
                        )
                    )
                )
                existing_notification = result.scalar_one_or_none()

                if not existing_notification:
                    notification = self._create_notification(
                        user_id=user_id,
                        reminder_type=meal_type.value,
                        trigger_type=NotificationTrigger.EVENT_BASED,
                        priority=NotificationPriority.MEDIUM,
                        message=f"记得记录{self._get_meal_type_name(meal_type)}哦～",
                        channel=preferences.get(
                            "preferred_channel", NotificationChannel.CHAT
                        ),
                    )
                    notifications.append(notification)

        return notifications

    async def _check_achievement_triggers(
        self, user_id: int, db: AsyncSession, preferences: Dict[str, Any]
    ) -> List[NotificationQueue]:
        """检查成就触发条件"""
        notifications = []

        # 这里可以集成成就服务
        # 暂时返回空列表，后续集成
        return notifications

    async def _check_goal_progress_triggers(
        self, user_id: int, db: AsyncSession, preferences: Dict[str, Any]
    ) -> List[NotificationQueue]:
        """检查目标进度触发条件"""
        notifications = []

        # 获取用户活跃目标
        result = await db.execute(
            select(Goal).where(
                and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
            )
        )
        goals = result.scalars().all()

        for goal in goals:
            if goal.target_weight is not None:
                # 检查体重目标进度
                result = await db.execute(
                    select(WeightRecord)
                    .where(
                        and_(
                            WeightRecord.user_id == user_id,
                            WeightRecord.record_date >= goal.start_date,
                        )
                    )
                    .order_by(WeightRecord.record_date.desc())
                )
                weight_records = result.scalars().all()

                if weight_records:
                    current_weight = weight_records[0].weight
                    progress = (
                        (goal.start_weight - current_weight)
                        / (goal.start_weight - goal.target_weight)
                    ) * 100

                    # 检查里程碑（25%, 50%, 75%, 100%）
                    milestones = [25, 50, 75, 100]
                    for milestone in milestones:
                        if progress >= milestone and progress < milestone + 5:
                            # 检查是否已发送过该里程碑通知
                            result = await db.execute(
                                select(NotificationQueue).where(
                                    and_(
                                        NotificationQueue.user_id == user_id,
                                        NotificationQueue.reminder_type
                                        == "goal_milestone",
                                        NotificationQueue.message.like(
                                            f"%{milestone}%%"
                                        ),
                                    )
                                )
                            )
                            existing_notification = result.scalar_one_or_none()

                            if not existing_notification:
                                notification = self._create_notification(
                                    user_id=user_id,
                                    reminder_type="goal_milestone",
                                    trigger_type=NotificationTrigger.GOAL_PROGRESS,
                                    priority=NotificationPriority.HIGH,
                                    message=f"🎉 恭喜！你已经完成了减重目标的{milestone}%！继续加油！",
                                    channel=preferences.get(
                                        "preferred_channel", NotificationChannel.CHAT
                                    ),
                                )
                                notifications.append(notification)

        return notifications

    async def _check_data_anomaly_triggers(
        self, user_id: int, db: AsyncSession, preferences: Dict[str, Any]
    ) -> List[NotificationQueue]:
        """检查数据异常触发条件"""
        notifications = []

        # 检查体重异常波动（一天内变化超过1kg）
        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_date.desc())
            .limit(2)
        )
        weight_records = result.scalars().all()

        if len(weight_records) >= 2:
            # 安全提取体重值 - 使用类型忽略
            weight1_val = weight_records[0].weight
            weight2_val = weight_records[1].weight

            # 手动处理类型转换
            weight_diff = 0.0
            if weight1_val is not None and weight2_val is not None:
                try:
                    w1 = float(str(weight1_val))
                    w2 = float(str(weight2_val))
                    weight_diff = abs(w1 - w2)
                except (ValueError, TypeError):
                    weight_diff = 0.0
            if weight_diff > 1.0:
                notification = self._create_notification(
                    user_id=user_id,
                    reminder_type="weight_anomaly",
                    trigger_type=NotificationTrigger.DATA_ANOMALY,
                    priority=NotificationPriority.HIGH,
                    message=f"⚠️ 注意：体重波动较大（{weight_diff:.1f}kg），请确认数据准确性",
                    channel=preferences.get(
                        "preferred_channel", NotificationChannel.CHAT
                    ),
                )
                notifications.append(notification)

        # 检查热量摄入异常（超过3000卡）
        today = date.today()
        result = await db.execute(
            select(func.sum(MealRecord.total_calories)).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == today,
                )
            )
        )
        total_calories = result.scalar() or 0

        if total_calories > 3000:
            notification = self._create_notification(
                user_id=user_id,
                reminder_type="calorie_anomaly",
                trigger_type=NotificationTrigger.DATA_ANOMALY,
                priority=NotificationPriority.MEDIUM,
                message=f"今日热量摄入较高（{total_calories}卡），注意控制哦～",
                channel=preferences.get("preferred_channel", NotificationChannel.CHAT),
            )
            notifications.append(notification)

        return notifications

    async def _get_user_notification_preferences(
        self, user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """获取用户通知偏好设置"""
        # 默认设置
        preferences = {
            "enabled": True,
            "enable_time_based": True,
            "enable_event_based": True,
            "enable_achievement": True,
            "enable_goal_progress": True,
            "enable_data_anomaly": True,
            "enable_weight_reminder": True,
            "enable_breakfast_reminder": True,
            "enable_lunch_reminder": True,
            "enable_dinner_reminder": True,
            "preferred_channel": NotificationChannel.CHAT,
            "quiet_hours_start": time(22, 0),  # 22:00
            "quiet_hours_end": time(8, 0),  # 08:00
            "notification_frequency": "normal",  # normal, minimal, frequent
        }

        # 从用户画像获取个性化设置
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        user_profile = result.scalar_one_or_none()

        if user_profile:
            # 根据动力类型调整通知频率
            if user_profile.motivation_type is not None:
                if user_profile.motivation_type.value == "data_driven":
                    preferences["notification_frequency"] = "frequent"
                elif user_profile.motivation_type.value == "emotional_support":
                    preferences["notification_frequency"] = "normal"
                elif user_profile.motivation_type.value == "goal_oriented":
                    preferences["notification_frequency"] = "normal"

            # 根据沟通风格调整通知语气
            if user_profile.communication_style is not None:
                # 这里可以存储用户偏好的通知语气
                pass

        return preferences

    def _should_trigger_time_based(
        self, setting: ReminderSetting, current_time: time, current_weekday: int
    ) -> bool:
        """判断是否应该触发时间提醒"""
        if setting.weekdays_only is True and current_weekday >= 5:
            return False

        if setting.reminder_time is None:
            return False

        reminder_time = setting.reminder_time
        if reminder_time is None:
            return False

        # 提取时间值 - 安全处理
        try:
            # 手动处理时间比较
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_second = current_time.second

            reminder_hour = reminder_time.hour
            reminder_minute = reminder_time.minute
            reminder_second = reminder_time.second

            # 计算时间差（秒）
            current_total = current_hour * 3600 + current_minute * 60 + current_second
            reminder_total = (
                reminder_hour * 3600 + reminder_minute * 60 + reminder_second
            )

            time_diff = abs(current_total - reminder_total)
        except Exception:
            return False

        return 0 <= time_diff <= 300  # 5分钟内

    def _is_quiet_hours(self, current_time: time, preferences: Dict[str, Any]) -> bool:
        """判断是否在免打扰时段"""
        quiet_start = preferences.get("quiet_hours_start", time(22, 0))
        quiet_end = preferences.get("quiet_hours_end", time(8, 0))

        if quiet_start <= quiet_end:
            return quiet_start <= current_time <= quiet_end
        else:
            return current_time >= quiet_start or current_time <= quiet_end

    def _generate_time_based_message(self, setting: ReminderSetting) -> str:
        """生成时间触发通知消息"""
        messages = {
            ReminderType.WEIGHT.value: "记得称一下体重哦～",
            ReminderType.BREAKFAST.value: "早餐时间到！记得记录早餐～",
            ReminderType.LUNCH.value: "午餐时间到！记得记录午餐～",
            ReminderType.DINNER.value: "晚餐时间到！记得记录晚餐～",
            ReminderType.SNACK.value: "零食时间到！记得记录零食～",
            ReminderType.EXERCISE.value: "运动时间到！动起来吧～",
            ReminderType.WATER.value: "记得喝水哦～保持水分充足",
            ReminderType.SLEEP.value: "该睡觉啦，晚安～",
            ReminderType.WEEKLY.value: "周报时间到！查看你的本周表现～",
        }

        return messages.get(setting.reminder_type.value, "提醒时间到！")

    def _get_meal_type_name(self, meal_type: ReminderType) -> str:
        """获取餐食类型名称"""
        names = {
            ReminderType.BREAKFAST.value: "早餐",
            ReminderType.LUNCH.value: "午餐",
            ReminderType.DINNER.value: "晚餐",
            ReminderType.SNACK.value: "零食",
        }
        return names.get(meal_type.value, "餐食")

    def _create_notification(
        self,
        user_id: int,
        reminder_type: str,
        trigger_type: NotificationTrigger,
        priority: NotificationPriority,
        message: str,
        channel: NotificationChannel = NotificationChannel.CHAT,
    ) -> NotificationQueue:
        """创建通知记录"""
        return NotificationQueue(
            user_id=user_id,
            reminder_type=reminder_type,
            message=message,
            scheduled_at=datetime.now(),
            status="pending",
            retry_count=0,
            max_retries=3,
            channel=channel.value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def get_user_notifications(
        self, user_id: int, db: AsyncSession, limit: int = 20, unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """获取用户通知列表"""
        try:
            query = (
                select(NotificationQueue)
                .where(NotificationQueue.user_id == user_id)
                .order_by(NotificationQueue.created_at.desc())
            )

            if unread_only:
                query = query.where(NotificationQueue.status == "pending")

            if limit:
                query = query.limit(limit)

            result = await db.execute(query)
            notifications = result.scalars().all()

            return [
                {
                    "id": n.id,
                    "reminder_type": n.reminder_type,
                    "message": n.message,
                    "status": n.status,
                    "created_at": n.created_at.isoformat(),
                    "channel": n.channel,
                }
                for n in notifications
            ]

        except Exception as e:
            logger.error("获取用户通知失败: %s", e)
            return []

    async def mark_notification_as_read(
        self, notification_id: int, db: AsyncSession
    ) -> bool:
        """标记通知为已读"""
        try:
            # 使用update语句更新
            result = await db.execute(
                update(NotificationQueue)
                .where(NotificationQueue.id == notification_id)
                .values(status="sent", sent_at=datetime.now())
            )
            await db.commit()

            # 检查是否有行被更新
            return True  # 假设更新成功

        except Exception as e:
            logger.error("标记通知为已读失败: %s", e)
            await db.rollback()
            return False

    async def get_notification_stats(
        self, user_id: int, db: AsyncSession, days: int = 7
    ) -> Dict[str, Any]:
        """获取通知统计信息"""
        try:
            start_date = datetime.now() - timedelta(days=days)

            # 总通知数
            result = await db.execute(
                select(func.count(NotificationQueue.id)).where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.created_at >= start_date,
                    )
                )
            )
            total_count = result.scalar() or 0

            # 已读通知数
            result = await db.execute(
                select(func.count(NotificationQueue.id)).where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.status == "sent",
                        NotificationQueue.created_at >= start_date,
                    )
                )
            )
            read_count = result.scalar() or 0

            # 按类型统计
            result = await db.execute(
                select(
                    NotificationQueue.reminder_type, func.count(NotificationQueue.id)
                )
                .where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.created_at >= start_date,
                    )
                )
                .group_by(NotificationQueue.reminder_type)
            )
            type_stats = {row[0]: row[1] for row in result.all()}

            return {
                "total_count": total_count,
                "read_count": read_count,
                "unread_count": total_count - read_count,
                "read_rate": (read_count / total_count * 100) if total_count > 0 else 0,
                "type_stats": type_stats,
                "period_days": days,
            }

        except Exception as e:
            logger.error("获取通知统计失败: %s", e)
            return {}


# 全局实例
notification_service = NotificationService()
