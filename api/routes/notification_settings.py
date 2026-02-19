"""
通知设置 API 路由
管理用户通知偏好设置
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Dict, Any, List
from datetime import time
import json

from models.database import (
    get_db,
    User,
    ReminderSetting,
    ReminderType,
    UserProfile,
)
from api.routes.user import get_current_user
from services.notification_service import (
    NotificationService,
    NotificationChannel,
    NotificationTrigger,
)
from config.logging_config import get_module_logger

router = APIRouter()
logger = get_module_logger(__name__)
notification_service = NotificationService()


@router.get("/preferences")
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户通知偏好设置"""
    try:
        # 获取用户画像
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        user_profile = result.scalar_one_or_none()

        # 获取提醒设置
        result = await db.execute(
            select(ReminderSetting).where(ReminderSetting.user_id == current_user.id)
        )
        reminder_settings = result.scalars().all()

        # 构建提醒设置字典
        reminders = {}
        for setting in reminder_settings:
            reminders[setting.reminder_type.value] = {
                "enabled": setting.enabled,
                "reminder_time": setting.reminder_time.isoformat()
                if setting.reminder_time
                else None,
                "weekdays_only": setting.weekdays_only,
                "interval_minutes": setting.interval_minutes,
                "last_triggered": setting.last_triggered.isoformat()
                if setting.last_triggered
                else None,
            }

        # 默认通知偏好
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
            "enable_snack_reminder": True,
            "enable_exercise_reminder": True,
            "enable_water_reminder": True,
            "enable_sleep_reminder": True,
            "enable_daily_report": True,
            "enable_weekly_report": True,
            "preferred_channel": NotificationChannel.CHAT.value,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            "notification_frequency": "normal",  # normal, minimal, frequent
            "reminders": reminders,
        }

        # 如果有用户画像，调整默认设置
        if user_profile:
            # 根据动力类型调整通知频率
            if user_profile.motivation_type:
                if user_profile.motivation_type.value == "data_driven":
                    preferences["notification_frequency"] = "frequent"
                elif user_profile.motivation_type.value == "emotional_support":
                    preferences["notification_frequency"] = "normal"
                elif user_profile.motivation_type.value == "goal_oriented":
                    preferences["notification_frequency"] = "normal"

            # 如果有自定义设置，从JSON字段读取
            if user_profile.notification_settings:
                try:
                    custom_settings = json.loads(user_profile.notification_settings)
                    preferences.update(custom_settings)
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "success": True,
            "data": preferences,
            "user_profile": {
                "motivation_type": user_profile.motivation_type.value
                if user_profile and user_profile.motivation_type
                else None,
                "communication_style": user_profile.communication_style
                if user_profile
                else None,
            }
            if user_profile
            else None,
        }

    except Exception as e:
        logger.exception("获取通知偏好设置失败: %s", e)
        raise HTTPException(status_code=500, detail="获取通知设置失败")


@router.post("/preferences")
async def update_notification_preferences(
    preferences: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户通知偏好设置"""
    try:
        # 验证输入
        valid_channels = [ch.value for ch in NotificationChannel]
        valid_frequencies = ["normal", "minimal", "frequent"]

        if "preferred_channel" in preferences:
            if preferences["preferred_channel"] not in valid_channels:
                raise HTTPException(status_code=400, detail="无效的通知渠道")

        if "notification_frequency" in preferences:
            if preferences["notification_frequency"] not in valid_frequencies:
                raise HTTPException(status_code=400, detail="无效的通知频率")

        # 验证免打扰时间格式
        if "quiet_hours_start" in preferences:
            try:
                time.fromisoformat(preferences["quiet_hours_start"])
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的免打扰开始时间格式")

        if "quiet_hours_end" in preferences:
            try:
                time.fromisoformat(preferences["quiet_hours_end"])
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的免打扰结束时间格式")

        # 获取或创建用户画像
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        user_profile = result.scalar_one_or_none()

        if not user_profile:
            # 创建用户画像
            user_profile = UserProfile(
                user_id=current_user.id, notification_settings=json.dumps(preferences)
            )
            db.add(user_profile)
        else:
            # 更新用户画像中的通知设置
            current_settings = {}
            if user_profile.notification_settings:
                try:
                    current_settings = json.loads(user_profile.notification_settings)
                except (json.JSONDecodeError, TypeError):
                    pass

            current_settings.update(preferences)
            user_profile.notification_settings = json.dumps(current_settings)

        await db.commit()

        return {"success": True, "message": "通知偏好设置已更新", "data": preferences}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新通知偏好设置失败: %s", e)
        raise HTTPException(status_code=500, detail="更新通知设置失败")


@router.get("/reminders")
async def get_reminder_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户提醒设置"""
    try:
        result = await db.execute(
            select(ReminderSetting).where(ReminderSetting.user_id == current_user.id)
        )
        reminder_settings = result.scalars().all()

        reminders = []
        for setting in reminder_settings:
            reminders.append(
                {
                    "id": setting.id,
                    "reminder_type": setting.reminder_type.value,
                    "enabled": setting.enabled,
                    "reminder_time": setting.reminder_time.isoformat()
                    if setting.reminder_time
                    else None,
                    "weekdays_only": setting.weekdays_only,
                    "interval_minutes": setting.interval_minutes,
                    "last_triggered": setting.last_triggered.isoformat()
                    if setting.last_triggered
                    else None,
                    "skip_count": setting.skip_count,
                    "created_at": setting.created_at.isoformat()
                    if setting.created_at
                    else None,
                }
            )

        # 默认提醒类型
        default_reminder_types = [
            ReminderType.WEIGHT.value,
            ReminderType.BREAKFAST.value,
            ReminderType.LUNCH.value,
            ReminderType.DINNER.value,
            ReminderType.SNACK.value,
            ReminderType.EXERCISE.value,
            ReminderType.WATER.value,
            ReminderType.SLEEP.value,
            ReminderType.DAILY.value,
            ReminderType.WEEKLY.value,
        ]

        # 检查是否有缺失的提醒类型
        existing_types = {s.reminder_type.value for s in reminder_settings}
        missing_types = [t for t in default_reminder_types if t not in existing_types]

        return {
            "success": True,
            "data": reminders,
            "missing_types": missing_types,
            "default_types": default_reminder_types,
        }

    except Exception as e:
        logger.exception("获取提醒设置失败: %s", e)
        raise HTTPException(status_code=500, detail="获取提醒设置失败")


@router.post("/reminders")
async def update_reminder_setting(
    reminder_type: str,
    enabled: bool = None,
    reminder_time: str = None,
    weekdays_only: bool = None,
    interval_minutes: int = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新或创建提醒设置"""
    try:
        # 验证提醒类型
        valid_types = [rt.value for rt in ReminderType]
        if reminder_type not in valid_types:
            raise HTTPException(status_code=400, detail="无效的提醒类型")

        # 验证时间格式
        reminder_time_obj = None
        if reminder_time:
            try:
                reminder_time_obj = time.fromisoformat(reminder_time)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="无效的时间格式，请使用 HH:MM:SS 格式"
                )

        # 查找现有设置
        result = await db.execute(
            select(ReminderSetting).where(
                ReminderSetting.user_id == current_user.id,
                ReminderSetting.reminder_type == reminder_type,
            )
        )
        setting = result.scalar_one_or_none()

        if setting:
            # 更新现有设置
            if enabled is not None:
                setting.enabled = enabled
            if reminder_time_obj is not None:
                setting.reminder_time = reminder_time_obj
            if weekdays_only is not None:
                setting.weekdays_only = weekdays_only
            if interval_minutes is not None:
                setting.interval_minutes = interval_minutes
        else:
            # 创建新设置
            setting = ReminderSetting(
                user_id=current_user.id,
                reminder_type=ReminderType(reminder_type),
                enabled=enabled if enabled is not None else True,
                reminder_time=reminder_time_obj,
                weekdays_only=weekdays_only if weekdays_only is not None else False,
                interval_minutes=interval_minutes,
                created_at=datetime.utcnow(),
            )
            db.add(setting)

        await db.commit()

        return {
            "success": True,
            "message": "提醒设置已更新",
            "data": {
                "id": setting.id,
                "reminder_type": setting.reminder_type.value,
                "enabled": setting.enabled,
                "reminder_time": setting.reminder_time.isoformat()
                if setting.reminder_time
                else None,
                "weekdays_only": setting.weekdays_only,
                "interval_minutes": setting.interval_minutes,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新提醒设置失败: %s", e)
        raise HTTPException(status_code=500, detail="更新提醒设置失败")


@router.delete("/reminders/{reminder_type}")
async def delete_reminder_setting(
    reminder_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除提醒设置"""
    try:
        # 验证提醒类型
        valid_types = [rt.value for rt in ReminderType]
        if reminder_type not in valid_types:
            raise HTTPException(status_code=400, detail="无效的提醒类型")

        result = await db.execute(
            select(ReminderSetting).where(
                ReminderSetting.user_id == current_user.id,
                ReminderSetting.reminder_type == reminder_type,
            )
        )
        setting = result.scalar_one_or_none()

        if not setting:
            raise HTTPException(status_code=404, detail="未找到该提醒设置")

        await db.delete(setting)
        await db.commit()

        return {"success": True, "message": "提醒设置已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除提醒设置失败: %s", e)
        raise HTTPException(status_code=500, detail="删除提醒设置失败")


@router.get("/notifications")
async def get_user_notifications(
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户通知列表"""
    try:
        notifications = await notification_service.get_user_notifications(
            current_user.id, db, limit, unread_only
        )

        return {"success": True, "count": len(notifications), "data": notifications}

    except Exception as e:
        logger.exception("获取用户通知失败: %s", e)
        raise HTTPException(status_code=500, detail="获取通知失败")


@router.post("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    try:
        success = await notification_service.mark_notification_as_read(
            notification_id, db
        )

        if not success:
            raise HTTPException(status_code=404, detail="通知不存在或已处理")

        return {"success": True, "message": "通知已标记为已读"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("标记通知为已读失败: %s", e)
        raise HTTPException(status_code=500, detail="标记通知失败")


@router.get("/stats")
async def get_notification_stats(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知统计信息"""
    try:
        stats = await notification_service.get_notification_stats(
            current_user.id, db, days
        )

        return {"success": True, "data": stats}

    except Exception as e:
        logger.exception("获取通知统计失败: %s", e)
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.post("/test")
async def test_notification(
    reminder_type: str = "test",
    message: str = "测试通知",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送测试通知"""
    try:
        from datetime import datetime

        notification = NotificationQueue(
            user_id=current_user.id,
            reminder_type=reminder_type,
            message=message,
            scheduled_at=datetime.now(),
            status="pending",
            retry_count=0,
            max_retries=3,
            channel="chat",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        db.add(notification)
        await db.commit()

        return {
            "success": True,
            "message": "测试通知已发送",
            "data": {
                "id": notification.id,
                "message": notification.message,
                "created_at": notification.created_at.isoformat(),
            },
        }

    except Exception as e:
        logger.exception("发送测试通知失败: %s", e)
        raise HTTPException(status_code=500, detail="发送测试通知失败")


# 导入 datetime
from datetime import datetime
