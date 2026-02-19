"""
通知轮询API - 用于前端实时获取待处理通知
支持在对话区域展示通知卡片
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from models.database import get_db, User, NotificationQueue
from api.routes.user import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pending")
async def get_pending_notifications(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户的待处理通知（用于前端轮询）

    - 返回pending状态的通知
    - 按优先级和时间排序
    - 自动标记为已发送（sent）
    """
    try:
        user_id = int(current_user.id)

        # 查询pending状态的通知，按scheduled_at排序
        query = (
            select(NotificationQueue)
            .where(
                and_(
                    NotificationQueue.user_id == user_id,
                    NotificationQueue.status == "pending",
                    NotificationQueue.scheduled_at <= datetime.utcnow(),
                )
            )
            .order_by(desc(NotificationQueue.scheduled_at))
            .limit(limit)
        )

        result = await db.execute(query)
        notifications = result.scalars().all()

        # 格式化通知数据
        notification_list = []
        for notif in notifications:
            # 获取通知类型对应的图标和颜色
            type_config = _get_notification_type_config(notif.reminder_type)

            notification_data = {
                "id": notif.id,
                "type": notif.reminder_type,
                "title": type_config.get("title", "提醒"),
                "content": notif.message or type_config.get("default_message", ""),
                "icon": type_config.get("icon", "🔔"),
                "color": type_config.get("color", "#007AFF"),
                "action_url": type_config.get("action_url", ""),
                "action_text": type_config.get("action_text", "去处理"),
                "priority": type_config.get("priority", "normal"),
                "created_at": notif.created_at.isoformat()
                if notif.created_at
                else None,
                "content_type": notif.content_type,
                "content_data": notif.content_data,
            }
            notification_list.append(notification_data)

            # 更新状态为sent（已发送到前端）
            notif.status = "sent"
            notif.sent_at = datetime.utcnow()

        await db.commit()

        logger.info(
            f"[notifications/pending] user_id={user_id}, count={len(notification_list)}"
        )

        return {
            "success": True,
            "count": len(notification_list),
            "notifications": notification_list,
        }

    except Exception as e:
        logger.error(f"[notifications/pending] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{notification_id}/acknowledge")
async def acknowledge_notification(
    notification_id: int,
    action: str = "click",  # click, dismiss, complete
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    标记通知已处理

    - click: 用户点击了通知
    - dismiss: 用户忽略了通知
    - complete: 用户完成了通知要求的操作
    """
    try:
        user_id = int(current_user.id)

        # 查询通知
        query = select(NotificationQueue).where(
            and_(
                NotificationQueue.id == notification_id,
                NotificationQueue.user_id == user_id,
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()

        if not notification:
            raise HTTPException(status_code=404, detail="通知不存在")

        # 根据动作更新状态
        if action == "complete":
            notification.status = "completed"
        elif action == "dismiss":
            notification.status = "dismissed"
        else:  # click
            notification.status = "clicked"

        await db.commit()

        logger.info(
            f"[notifications/acknowledge] id={notification_id}, action={action}"
        )

        return {
            "success": True,
            "message": "通知已标记为已处理",
            "notification_id": notification_id,
            "action": action,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[notifications/acknowledge] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_notification_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知历史记录"""
    try:
        user_id = int(current_user.id)

        # 构建查询
        query = select(NotificationQueue).where(NotificationQueue.user_id == user_id)

        if status:
            query = query.where(NotificationQueue.status == status)

        query = (
            query.order_by(desc(NotificationQueue.created_at))
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(query)
        notifications = result.scalars().all()

        notification_list = []
        for notif in notifications:
            type_config = _get_notification_type_config(notif.reminder_type)
            notification_list.append(
                {
                    "id": notif.id,
                    "type": notif.reminder_type,
                    "title": type_config.get("title", "提醒"),
                    "content": notif.message or type_config.get("default_message", ""),
                    "status": notif.status,
                    "icon": type_config.get("icon", "🔔"),
                    "color": type_config.get("color", "#007AFF"),
                    "created_at": notif.created_at.isoformat()
                    if notif.created_at
                    else None,
                    "sent_at": notif.sent_at.isoformat() if notif.sent_at else None,
                }
            )

        return {
            "success": True,
            "count": len(notification_list),
            "notifications": notification_list,
        }

    except Exception as e:
        logger.error(f"[notifications/history] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_notification_type_config(reminder_type: str) -> dict:
    """获取通知类型配置（图标、颜色、标题等）"""

    configs = {
        "weight": {
            "title": "体重提醒",
            "icon": "⚖️",
            "color": "#34C759",
            "action_url": "/weight.html",
            "action_text": "记录体重",
            "default_message": "该记录今天的体重啦~",
            "priority": "high",
        },
        "breakfast": {
            "title": "早餐提醒",
            "icon": "🍽️",
            "color": "#FF9500",
            "action_url": "/meal.html?type=breakfast",
            "action_text": "记录早餐",
            "default_message": "记得记录今天的早餐哦~",
            "priority": "normal",
        },
        "lunch": {
            "title": "午餐提醒",
            "icon": "🍽️",
            "color": "#FF9500",
            "action_url": "/meal.html?type=lunch",
            "action_text": "记录午餐",
            "default_message": "午餐吃了什么？记录一下吧~",
            "priority": "normal",
        },
        "dinner": {
            "title": "晚餐提醒",
            "icon": "🍽️",
            "color": "#FF9500",
            "action_url": "/meal.html?type=dinner",
            "action_text": "记录晚餐",
            "default_message": "晚餐记得记录哦，控制热量很重要~",
            "priority": "normal",
        },
        "exercise": {
            "title": "运动提醒",
            "icon": "🏃",
            "color": "#007AFF",
            "action_url": "/exercise.html",
            "action_text": "记录运动",
            "default_message": "今天运动了吗？动起来吧！",
            "priority": "normal",
        },
        "water": {
            "title": "饮水提醒",
            "icon": "💧",
            "color": "#00C7FF",
            "action_url": "/water.html",
            "action_text": "记录饮水",
            "default_message": "记得多喝水哦，保持身体水分充足~",
            "priority": "low",
        },
        "sleep": {
            "title": "睡眠提醒",
            "icon": "🌙",
            "color": "#5856D6",
            "action_url": "/sleep.html",
            "action_text": "记录睡眠",
            "default_message": "昨晚睡得好吗？记录一下睡眠质量吧~",
            "priority": "normal",
        },
        "weekly_report": {
            "title": "周报已生成",
            "icon": "📊",
            "color": "#AF52DE",
            "action_url": "/report.html",
            "action_text": "查看周报",
            "default_message": "本周健康周报已生成，快来看看吧！",
            "priority": "high",
        },
        "daily_report": {
            "title": "今日日报",
            "icon": "📋",
            "color": "#FF9500",
            "action_url": "/report.html?type=daily",
            "action_text": "查看日报",
            "default_message": "今日健康日报已送达~",
            "priority": "normal",
        },
        "achievement": {
            "title": "获得新成就",
            "icon": "🏆",
            "color": "#FFD700",
            "action_url": "/habit.html",
            "action_text": "查看成就",
            "default_message": "恭喜你获得新成就！",
            "priority": "high",
        },
        "system": {
            "title": "系统通知",
            "icon": "📢",
            "color": "#FF3B30",
            "action_url": "",
            "action_text": "知道了",
            "default_message": "系统通知",
            "priority": "high",
        },
        "profiling": {
            "title": "了解你多一点",
            "icon": "📝",
            "color": "#5856D6",
            "action_url": "/profiling.html",
            "action_text": "去回答",
            "default_message": "回答几个问题，让我更了解你~",
            "priority": "normal",
        },
    }

    return configs.get(reminder_type, configs["system"])
