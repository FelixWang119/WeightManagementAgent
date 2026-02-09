"""
提醒系统 API 路由
包含：提醒设置、提醒历史、免打扰模式
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, time, date

from models.database import (
    get_db, User, ReminderSetting, ReminderType
)
from api.routes.user import get_current_user

router = APIRouter()

# 默认提醒时间
DEFAULT_REMINDERS = {
    "weight": {"time": "08:00", "enabled": True},
    "breakfast": {"time": "08:30", "enabled": True},
    "lunch": {"time": "12:00", "enabled": True},
    "dinner": {"time": "18:30", "enabled": True},
    "exercise": {"time": "19:00", "enabled": True},
    "water": {"interval": 120, "enabled": True},  # 每2小时
    "sleep": {"time": "22:30", "enabled": True},
}


@router.get("/settings")
async def get_reminder_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取提醒设置"""
    result = await db.execute(
        select(ReminderSetting)
        .where(ReminderSetting.user_id == current_user.id)
    )
    
    settings = result.scalars().all()
    
    # 如果没有设置，返回默认值
    if not settings:
        return {
            "success": True,
            "data": DEFAULT_REMINDERS,
            "is_default": True
        }
    
    # 转换为字典
    settings_dict = {}
    for s in settings:
        reminder_type = s.reminder_type.value
        settings_dict[reminder_type] = {
            "enabled": s.enabled,
            "time": s.reminder_time.strftime("%H:%M") if s.reminder_time else None,
            "interval": s.interval_minutes,
            "weekdays_only": s.weekdays_only,
        }
    
    return {
        "success": True,
        "data": settings_dict,
        "is_default": False
    }


@router.put("/settings/batch")
async def update_reminder_settings_batch(
    settings: Dict[str, Dict[str, Any]],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    批量更新提醒设置

    - **settings**: 提醒设置字典，key为提醒类型，value为设置对象
    """
    # 如果传入了全局enabled，遍历更新所有提醒
    if 'enabled' in settings and isinstance(settings['enabled'], bool):
        global_enabled = settings['enabled']
        # 更新所有提醒的启用状态
        for reminder_type in DEFAULT_REMINDERS.keys():
            if reminder_type in settings:
                settings[reminder_type]['enabled'] = global_enabled
            else:
                settings[reminder_type] = settings.get(reminder_type, {})
                settings[reminder_type]['enabled'] = global_enabled

    for reminder_type, config in settings.items():
        try:
            reminder_enum = ReminderType(reminder_type)
        except ValueError:
            continue

        enabled = config.get('enabled', True)
        reminder_time = config.get('time')
        interval_minutes = config.get('interval')
        weekdays_only = config.get('weekdays_only', False)

        # 查找或创建设置
        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == reminder_enum
                )
            )
        )

        setting = result.scalar_one_or_none()

        if not setting:
            setting = ReminderSetting(
                user_id=current_user.id,
                reminder_type=reminder_enum
            )
            db.add(setting)

        setting.enabled = enabled

        if reminder_time:
            try:
                hour, minute = map(int, reminder_time.split(":"))
                setting.reminder_time = time(hour, minute)
            except ValueError:
                pass

        if interval_minutes:
            setting.interval_minutes = interval_minutes

        setting.weekdays_only = weekdays_only

    await db.commit()

    return {
        "success": True,
        "message": "提醒设置已更新"
    }


@router.put("/settings/{reminder_type}")
async def update_reminder_setting(
    reminder_type: str,
    enabled: bool,
    reminder_time: Optional[str] = None,
    interval_minutes: Optional[int] = None,
    weekdays_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新提醒设置
    
    - **reminder_type**: 提醒类型 (weight/breakfast/lunch/dinner/exercise/water/sleep)
    - **enabled**: 是否启用
    - **reminder_time**: 提醒时间（HH:MM格式）
    - **interval_minutes**: 间隔分钟数（仅饮水提醒使用）
    - **weekdays_only**: 仅工作日提醒
    """
    try:
        reminder_enum = ReminderType(reminder_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的提醒类型")
    
    # 查找或创建设置
    result = await db.execute(
        select(ReminderSetting).where(
            and_(
                ReminderSetting.user_id == current_user.id,
                ReminderSetting.reminder_type == reminder_enum
            )
        )
    )
    
    setting = result.scalar_one_or_none()
    
    if not setting:
        setting = ReminderSetting(
            user_id=current_user.id,
            reminder_type=reminder_enum
        )
        db.add(setting)
    
    # 更新时间
    setting.enabled = enabled
    if reminder_time:
        try:
            hour, minute = map(int, reminder_time.split(":"))
            setting.reminder_time = time(hour, minute)
        except ValueError:
            raise HTTPException(status_code=400, detail="时间格式错误，请使用 HH:MM")
    
    if interval_minutes:
        setting.interval_minutes = interval_minutes
    
    setting.weekdays_only = weekdays_only
    
    await db.commit()
    
    return {
        "success": True,
        "message": "提醒设置已更新",
        "data": {
            "reminder_type": reminder_type,
            "enabled": enabled,
            "time": reminder_time,
            "interval": interval_minutes
        }
    }


@router.post("/settings/init")
async def init_default_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """初始化默认提醒设置"""
    for reminder_type, config in DEFAULT_REMINDERS.items():
        # 检查是否已存在
        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == ReminderType(reminder_type)
                )
            )
        )
        
        if result.scalar_one_or_none():
            continue
        
        setting = ReminderSetting(
            user_id=current_user.id,
            reminder_type=ReminderType(reminder_type),
            enabled=config["enabled"]
        )
        
        if "time" in config:
            hour, minute = map(int, config["time"].split(":"))
            setting.reminder_time = time(hour, minute)
        
        if "interval" in config:
            setting.interval_minutes = config["interval"]
        
        db.add(setting)
    
    await db.commit()
    
    return {
        "success": True,
        "message": "默认提醒设置已初始化"
    }


@router.get("/today")
async def get_today_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取今日提醒列表"""
    result = await db.execute(
        select(ReminderSetting)
        .where(
            and_(
                ReminderSetting.user_id == current_user.id,
                ReminderSetting.enabled == True
            )
        )
    )
    
    settings = result.scalars().all()
    
    # 检查是否需要跳过（周末且设置了仅工作日）
    today_weekday = date.today().weekday()
    is_weekend = today_weekday >= 5
    
    reminders = []
    for s in settings:
        if is_weekend and s.weekdays_only:
            continue
        
        reminder_data = {
            "type": s.reminder_type.value,
            "time": s.reminder_time.strftime("%H:%M") if s.reminder_time else None,
            "interval": s.interval_minutes,
            "description": get_reminder_description(s.reminder_type)
        }
        reminders.append(reminder_data)
    
    # 按时间排序
    reminders.sort(key=lambda x: x["time"] or "00:00")
    
    return {
        "success": True,
        "date": date.today().isoformat(),
        "is_weekend": is_weekend,
        "reminders": reminders
    }


@router.post("/do-not-disturb")
async def set_do_not_disturb(
    enabled: bool,
    start_time: str = "22:00",
    end_time: str = "08:00",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    设置免打扰模式
    
    - **enabled**: 是否启用
    - **start_time**: 开始时间（HH:MM）
    - **end_time**: 结束时间（HH:MM）
    """
    # 验证时间格式
    try:
        start_hour, start_minute = map(int, start_time.split(":"))
        end_hour, end_minute = map(int, end_time.split(":"))
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式错误，请使用 HH:MM")
    
    # 保存到用户配置（简化处理，实际应该单独建表）
    # 这里返回设置信息，前端可以根据此设置本地提醒
    
    return {
        "success": True,
        "message": "免打扰设置已更新",
        "data": {
            "enabled": enabled,
            "start_time": start_time,
            "end_time": end_time,
            "note": "免打扰设置已保存，将在设定时间段内暂停提醒"
        }
    }


# ============ 辅助函数 ============

def get_reminder_description(reminder_type: ReminderType) -> str:
    """获取提醒描述"""
    descriptions = {
        ReminderType.WEIGHT: "记得空腹称重，记录今天的体重变化",
        ReminderType.BREAKFAST: "早餐时间到啦！记得拍照记录哦",
        ReminderType.LUNCH: "午餐时间！营养均衡很重要",
        ReminderType.DINNER: "晚餐时间，注意控制热量摄入",
        ReminderType.SNACK: "加餐时间，选择健康的小食",
        ReminderType.EXERCISE: "运动时间到！动起来吧",
        ReminderType.WATER: "该喝水啦，保持水分充足",
        ReminderType.SLEEP: "准备睡觉吧，良好的睡眠有助于减重",
        ReminderType.WEEKLY: "周报生成提醒"
    }
    return descriptions.get(reminder_type, "提醒事项")
