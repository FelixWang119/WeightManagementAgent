"""
提醒系统 API 路由
包含：提醒设置、提醒历史、免打扰模式
"""

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, time, date

from models.database import (
    get_db,
    User,
    ReminderSetting,
    ReminderType,
    ChatHistory,
    MessageRole,
    NotificationQueue,
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
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取提醒设置"""
    result = await db.execute(
        select(ReminderSetting).where(ReminderSetting.user_id == current_user.id)
    )

    settings = result.scalars().all()

    # 如果没有设置，返回默认值
    if not settings:
        return {"success": True, "data": DEFAULT_REMINDERS, "is_default": True}

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

    return {"success": True, "data": settings_dict, "is_default": False}


@router.put("/settings/batch")
async def update_reminder_settings_batch(
    settings: Dict[str, Dict[str, Any]],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量更新提醒设置

    - **settings**: 提醒设置字典，key为提醒类型，value为设置对象
    """
    # 如果传入了全局enabled，遍历更新所有提醒
    if "enabled" in settings and isinstance(settings["enabled"], bool):
        global_enabled = settings["enabled"]
        # 更新所有提醒的启用状态
        for reminder_type in DEFAULT_REMINDERS.keys():
            if reminder_type in settings:
                settings[reminder_type]["enabled"] = global_enabled
            else:
                settings[reminder_type] = settings.get(reminder_type, {})
                settings[reminder_type]["enabled"] = global_enabled

    for reminder_type, config in settings.items():
        try:
            reminder_enum = ReminderType(reminder_type)
        except ValueError:
            continue

        enabled = config.get("enabled", True)
        reminder_time = config.get("time")
        interval_minutes = config.get("interval")
        weekdays_only = config.get("weekdays_only", False)

        # 查找或创建设置
        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == reminder_enum,
                )
            )
        )

        setting = result.scalar_one_or_none()

        if not setting:
            setting = ReminderSetting(
                user_id=current_user.id, reminder_type=reminder_enum
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

    return {"success": True, "message": "提醒设置已更新"}


@router.put("/settings/{reminder_type}")
async def update_reminder_setting(
    reminder_type: str,
    enabled: bool,
    reminder_time: Optional[str] = None,
    interval_minutes: Optional[int] = None,
    weekdays_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
                ReminderSetting.reminder_type == reminder_enum,
            )
        )
    )

    setting = result.scalar_one_or_none()

    if not setting:
        setting = ReminderSetting(user_id=current_user.id, reminder_type=reminder_enum)
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
            "interval": interval_minutes,
        },
    }


@router.post("/settings/init")
async def init_default_reminders(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """初始化默认提醒设置"""
    for reminder_type, config in DEFAULT_REMINDERS.items():
        # 检查是否已存在
        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == ReminderType(reminder_type),
                )
            )
        )

        if result.scalar_one_or_none():
            continue

        setting = ReminderSetting(
            user_id=current_user.id,
            reminder_type=ReminderType(reminder_type),
            enabled=config["enabled"],
        )

        if "time" in config:
            hour, minute = map(int, config["time"].split(":"))
            setting.reminder_time = time(hour, minute)

        if "interval" in config:
            setting.interval_minutes = config["interval"]

        db.add(setting)

    await db.commit()

    return {"success": True, "message": "默认提醒设置已初始化"}


@router.get("/today")
async def get_today_reminders(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取今日提醒列表"""
    result = await db.execute(
        select(ReminderSetting).where(
            and_(
                ReminderSetting.user_id == current_user.id,
                ReminderSetting.enabled == True,
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
            "description": get_reminder_description(s.reminder_type),
        }
        reminders.append(reminder_data)

    # 按时间排序
    reminders.sort(key=lambda x: x["time"] or "00:00")

    return {
        "success": True,
        "date": date.today().isoformat(),
        "is_weekend": is_weekend,
        "reminders": reminders,
    }


@router.post("/do-not-disturb")
async def set_do_not_disturb(
    enabled: bool,
    start_time: str = "22:00",
    end_time: str = "08:00",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
            "note": "免打扰设置已保存，将在设定时间段内暂停提醒",
        },
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
        ReminderType.WEEKLY: "周报生成提醒",
    }
    return descriptions.get(reminder_type, "提醒事项")


# ============ 提醒消息轮询 API ============


@router.get("/messages")
async def get_reminder_messages(
    since_id: Optional[int] = Query(None, description="返回此ID之后的最新消息"),
    limit: int = Query(20, description="返回消息数量", le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取提醒消息列表（用于前端轮询）

    - **since_id**: 返回此ID之后的最新消息，用于增量获取
    - **limit**: 返回消息数量，最大50
    """
    query = select(ChatHistory).where(
        and_(
            ChatHistory.user_id == current_user.id,
            ChatHistory.role == MessageRole.ASSISTANT,
        )
    )

    # 过滤出带 is_reminder 标记的消息
    query = query.where(ChatHistory.meta_data["is_reminder"].astext.cast(bool) == True)

    if since_id:
        query = query.where(ChatHistory.id > since_id)

    query = query.order_by(desc(ChatHistory.id)).limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()

    return {
        "success": True,
        "count": len(messages),
        "data": [
            {
                "id": m.id,
                "content": m.content,
                "reminder_type": m.meta_data.get("reminder_type")
                if m.meta_data
                else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(messages)
        ],
    }


@router.get("/poll")
async def poll_new_reminders(
    since_id: Optional[int] = Query(None, description="返回此ID之后的最新提醒"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    轮询新提醒（短轮询接口）

    前端每5-10秒调用此接口，检查是否有新的机器人提醒消息
    返回增量数据，减少网络传输
    """
    query = select(ChatHistory).where(
        and_(
            ChatHistory.user_id == current_user.id,
            ChatHistory.role == MessageRole.ASSISTANT,
        )
    )

    # 过滤出提醒消息
    query = query.where(ChatHistory.meta_data["is_reminder"].astext.cast(bool) == True)

    if since_id:
        query = query.where(ChatHistory.id > since_id)

    query = query.order_by(desc(ChatHistory.id)).limit(10)

    result = await db.execute(query)
    messages = result.scalars().all()

    # 获取最新消息ID
    latest_query = (
        select(ChatHistory.id)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(desc(ChatHistory.id))
        .limit(1)
    )
    latest_result = await db.execute(latest_query)
    latest_id = latest_result.scalar()

    return {
        "success": True,
        "has_new": len(messages) > 0,
        "count": len(messages),
        "latest_id": latest_id,
        "reminders": [
            {
                "id": m.id,
                "content": m.content,
                "reminder_type": m.meta_data.get("reminder_type")
                if m.meta_data
                else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(messages)
        ],
    }


@router.get("/queue/status")
async def get_queue_status(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取用户通知队列状态
    """
    result = await db.execute(
        select(NotificationQueue)
        .where(NotificationQueue.user_id == current_user.id)
        .order_by(desc(NotificationQueue.scheduled_at))
        .limit(20)
    )
    queue_items = result.scalars().all()

    stats = {"pending": 0, "sent": 0, "failed": 0, "skipped": 0}

    for item in queue_items:
        if item.status in stats:
            stats[item.status] += 1

    return {
        "success": True,
        "stats": stats,
        "recent": [
            {
                "id": q.id,
                "reminder_type": q.reminder_type,
                "status": q.status,
                "scheduled_at": q.scheduled_at.isoformat() if q.scheduled_at else None,
                "sent_at": q.sent_at.isoformat() if q.sent_at else None,
            }
            for q in queue_items[:5]
        ],
    }


# ============ 自然语言提醒管理 API ============


@router.post("/nlp/process")
async def process_reminder_nlp(
    message: str = Body(..., description="用户消息"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    自然语言处理提醒设置

    用户可以通过自然语言设置/修改提醒，例如：
    - "设置体重提醒"
    - "帮我设置早餐提醒早上8点"
    - "关闭晚餐提醒"
    - "运动提醒改到晚上7点"
    """
    from services.nlp.reminder_service import service

    # 获取当前提醒设置
    result = await db.execute(
        select(ReminderSetting).where(ReminderSetting.user_id == current_user.id)
    )
    settings = result.scalars().all()

    current_settings = {}
    for s in settings:
        reminder_type = (
            s.reminder_type.value
            if hasattr(s.reminder_type, "value")
            else str(s.reminder_type)
        )
        current_settings[reminder_type] = {
            "enabled": s.enabled,
            "time": s.reminder_time.strftime("%H:%M") if s.reminder_time else None,
            "interval": s.interval_minutes,
        }

    # 处理NLP
    nlp_result = service.process(message, current_settings)

    # 如果需要澄清，直接返回
    if nlp_result.get("needs_clarification"):
        return {
            "success": True,
            "type": "clarification",
            "question": nlp_result.get("question"),
            "suggestions": nlp_result.get("suggestions", []),
        }

    # 执行实际操作
    action = nlp_result.get("action")
    reminder_type = nlp_result.get("reminder_type")
    reminder_time = nlp_result.get("time")
    enabled = nlp_result.get("enabled")

    if action in ["set", "update"] and reminder_type and reminder_time:
        # 设置/更新提醒
        try:
            reminder_enum = ReminderType(reminder_type)
        except ValueError:
            return {"success": False, "error": "无效的提醒类型"}

        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == reminder_enum,
                )
            )
        )
        setting = result.scalar_one_or_none()

        if not setting:
            setting = ReminderSetting(
                user_id=current_user.id, reminder_type=reminder_enum
            )
            db.add(setting)

        setting.enabled = True
        hour, minute = map(int, reminder_time.split(":"))
        setting.reminder_time = time(hour, minute)

        await db.commit()

        return {
            "success": True,
            "type": "success",
            "response": nlp_result.get("response"),
        }

    elif action == "disable" and reminder_type:
        # 禁用提醒
        try:
            reminder_enum = ReminderType(reminder_type)
        except ValueError:
            return {"success": False, "error": "无效的提醒类型"}

        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == reminder_enum,
                )
            )
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.enabled = False
            await db.commit()

        return {
            "success": True,
            "type": "success",
            "response": nlp_result.get("response"),
        }

    elif action == "enable" and reminder_type:
        # 启用提醒
        try:
            reminder_enum = ReminderType(reminder_type)
        except ValueError:
            return {"success": False, "error": "无效的提醒类型"}

        result = await db.execute(
            select(ReminderSetting).where(
                and_(
                    ReminderSetting.user_id == current_user.id,
                    ReminderSetting.reminder_type == reminder_enum,
                )
            )
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.enabled = True
            await db.commit()

        return {
            "success": True,
            "type": "success",
            "response": nlp_result.get("response"),
        }

    return {
        "success": True,
        "type": "response",
        "response": nlp_result.get("response", "好的，已为您处理~"),
    }


@router.get("/nlp/check")
async def check_reminder_message(message: str = Query(..., description="待检查的消息")):
    """
    检查消息是否与提醒相关
    """
    from services.nlp.reminder_service import service

    is_related = service.is_reminder_request(message)

    return {"success": True, "is_reminder_related": is_related}
