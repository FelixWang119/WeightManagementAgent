"""
饮水记录 API 路由
包含：饮水记录、饮水统计、饮水提醒
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta

from models.database import (
    get_db,
    User,
    WaterRecord,
    ChatHistory,
    MessageRole,
    MessageType,
)
from api.routes.user import get_current_user
from services.integration_service import AchievementIntegrationService
from services.langchain.memory import CheckinSyncService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter()

# 默认每日饮水目标（毫升）
DEFAULT_DAILY_GOAL = 2000


@router.post("/record")
async def record_water(
    amount_ml: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    记录饮水

    - **amount_ml**: 饮水量（毫升）
    """
    if amount_ml <= 0:
        raise HTTPException(status_code=400, detail="饮水量必须大于0")

    if amount_ml > 2000:
        raise HTTPException(status_code=400, detail="单次饮水量不能超过2000毫升")

    record = WaterRecord(
        user_id=current_user.id, amount_ml=amount_ml, record_time=datetime.utcnow()
    )

    db.add(record)
    await db.commit()

    # 异步处理成就和积分检查
    try:
        await AchievementIntegrationService.process_water_record(
            user_id=int(current_user.id), record_id=int(record.id), db=db
        )
    except Exception as e:
        # 记录集成失败告警，但不影响主流程
        logger.warning("饮水记录成就积分集成失败: %s", e)

    # 保存饮水记录到对话历史，让AI助手记住
    try:
        # 构建饮水记录描述
        water_description = f"【饮水打卡】喝了{amount_ml}毫升水"

        # 保存到对话历史
        meta_data = {
            "event_type": "water_record",
            "amount_ml": amount_ml,
            "record_id": record.id,
        }

        chat_message = ChatHistory(
            user_id=current_user.id,
            role=MessageRole.USER,
            content=water_description,
            msg_type=MessageType.TEXT,
            meta_data=meta_data,
            created_at=datetime.utcnow(),
        )
        db.add(chat_message)
        await db.commit()

        logger.info(f"饮水记录已保存到对话历史: {water_description}")
    except Exception as chat_error:
        logger.warning(f"保存饮水记录到对话历史失败: {chat_error}")
        # 不中断主流程，继续执行

    # 同步到LangChain记忆系统
    try:
        sync_service = CheckinSyncService()
        sync_result = await sync_service.sync_recent_checkins(
            int(current_user.id), hours=1
        )
        logger.info(f"饮水记录同步到记忆系统: {sync_result}")
    except Exception as sync_error:
        logger.warning(f"同步饮水记录到记忆系统失败: {sync_error}")
        # 不中断主流程，继续执行

    # 计算今日总饮水量
    today_total = await get_today_water_total(int(current_user.id), db)

    return {
        "success": True,
        "message": "饮水记录成功",
        "data": {
            "id": record.id,
            "amount_ml": amount_ml,
            "today_total_ml": today_total,
            "daily_goal_ml": DEFAULT_DAILY_GOAL,
            "progress_percent": min(100, int(today_total / DEFAULT_DAILY_GOAL * 100)),
            "record_time": record.record_time.isoformat(),
        },
    }


@router.get("/today")
async def get_today_water(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取今日饮水记录"""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(WaterRecord)
        .where(
            and_(
                WaterRecord.user_id == current_user.id,
                WaterRecord.record_time >= today_start,
                WaterRecord.record_time <= today_end,
            )
        )
        .order_by(WaterRecord.record_time.desc())
    )

    records = result.scalars().all()
    total_ml = sum(r.amount_ml for r in records)

    return {
        "success": True,
        "date": today.isoformat(),
        "daily_goal_ml": DEFAULT_DAILY_GOAL,
        "current_ml": total_ml,
        "remaining_ml": max(0, DEFAULT_DAILY_GOAL - total_ml),
        "progress_percent": min(100, int(total_ml / DEFAULT_DAILY_GOAL * 100)),
        "is_goal_reached": total_ml >= DEFAULT_DAILY_GOAL,
        "record_count": len(records),
        "records": [
            {
                "id": r.id,
                "amount_ml": r.amount_ml,
                "record_time": r.record_time.strftime("%H:%M"),
            }
            for r in records
        ],
    }


@router.get("/history")
async def get_water_history(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取饮水历史（按天汇总）"""
    start_date = date.today() - timedelta(days=days - 1)

    # 获取所有记录
    result = await db.execute(
        select(WaterRecord)
        .where(
            and_(
                WaterRecord.user_id == current_user.id,
                WaterRecord.record_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
        .order_by(WaterRecord.record_time.desc())
    )

    records = result.scalars().all()

    # 按天汇总
    daily_data = {}
    for record in records:
        record_date = record.record_time.date().isoformat()
        if record_date not in daily_data:
            daily_data[record_date] = 0
        daily_data[record_date] += record.amount_ml

    # 填充没有记录的日期
    history = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        history.append(
            {
                "date": d,
                "amount_ml": daily_data.get(d, 0),
                "goal_reached": daily_data.get(d, 0) >= DEFAULT_DAILY_GOAL,
            }
        )

    return {"success": True, "daily_goal_ml": DEFAULT_DAILY_GOAL, "history": history}


@router.get("/stats")
async def get_water_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取饮水统计"""
    # 本周数据
    week_start = date.today() - timedelta(days=date.today().weekday())
    result = await db.execute(
        select(WaterRecord).where(
            and_(
                WaterRecord.user_id == current_user.id,
                WaterRecord.record_time
                >= datetime.combine(week_start, datetime.min.time()),
            )
        )
    )
    week_records = result.scalars().all()
    week_total = sum(r.amount_ml for r in week_records)
    week_days = len(set(r.record_time.date() for r in week_records))

    # 本月数据
    month_start = date.today().replace(day=1)
    result = await db.execute(
        select(WaterRecord).where(
            and_(
                WaterRecord.user_id == current_user.id,
                WaterRecord.record_time
                >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    )
    month_records = result.scalars().all()
    month_total = sum(r.amount_ml for r in month_records)

    # 连续达标天数
    consecutive_days = 0
    check_date = date.today()
    while True:
        result = await db.execute(
            select(func.sum(WaterRecord.amount_ml)).where(
                and_(
                    WaterRecord.user_id == current_user.id,
                    WaterRecord.record_time
                    >= datetime.combine(check_date, datetime.min.time()),
                    WaterRecord.record_time
                    < datetime.combine(
                        check_date + timedelta(days=1), datetime.min.time()
                    ),
                )
            )
        )
        day_total = result.scalar() or 0

        if day_total >= DEFAULT_DAILY_GOAL:
            consecutive_days += 1
            check_date -= timedelta(days=1)
        else:
            break

    return {
        "success": True,
        "data": {
            "daily_goal_ml": DEFAULT_DAILY_GOAL,
            "this_week": {
                "total_ml": week_total,
                "average_daily_ml": week_total // 7 if week_days > 0 else 0,
                "active_days": week_days,
            },
            "this_month": {
                "total_ml": month_total,
                "average_daily_ml": month_total // 30,
            },
            "consecutive_goal_days": consecutive_days,
            "today": await get_today_water_summary(current_user.id, db),
        },
    }


@router.delete("/record/{record_id}")
async def delete_water_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除饮水记录"""
    result = await db.execute(
        select(WaterRecord).where(
            and_(WaterRecord.id == record_id, WaterRecord.user_id == current_user.id)
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()

    return {"success": True, "message": "饮水记录已删除"}


# ============ 辅助函数 ============


async def get_today_water_total(user_id: int, db: AsyncSession) -> int:
    """获取今日饮水总量"""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(func.sum(WaterRecord.amount_ml)).where(
            and_(
                WaterRecord.user_id == user_id,
                WaterRecord.record_time >= today_start,
                WaterRecord.record_time <= today_end,
            )
        )
    )

    total = result.scalar()
    return total or 0


async def get_today_water_summary(user_id: int, db: AsyncSession) -> dict:
    """获取今日饮水摘要"""
    total = await get_today_water_total(user_id, db)
    return {
        "current_ml": total,
        "goal_ml": DEFAULT_DAILY_GOAL,
        "remaining_ml": max(0, DEFAULT_DAILY_GOAL - total),
        "progress_percent": min(100, int(total / DEFAULT_DAILY_GOAL * 100)),
        "is_goal_reached": total >= DEFAULT_DAILY_GOAL,
    }


@router.post("/sync-memory")
async def sync_water_memory(
    current_user: User = Depends(get_current_user),
):
    """
    同步饮水记录到LangChain记忆系统
    """
    try:
        sync_service = CheckinSyncService()
        sync_result = await sync_service.sync_user_checkins(
            int(current_user.id), force=True
        )

        return {
            "success": True,
            "message": "饮水记录同步完成",
            "data": sync_result,
        }
    except Exception as e:
        logger.error(f"同步饮水记录到记忆系统失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")
