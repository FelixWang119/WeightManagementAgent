"""
饮水记录 API 路由
包含：饮水记录、饮水统计、饮水提醒
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta

from models.database import get_db, User, WaterRecord
from api.routes.user import get_current_user
from services.event_triggers import publish_water_recorded_event

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
        user_id=current_user.id, amount_ml=amount_ml, record_time=datetime.now()
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Publish event to event bus
    try:
        await publish_water_recorded_event(
            user_id=current_user.id, amount_ml=amount_ml, record_id=record.id
        )
    except Exception as e:
        # Log error but don't fail the API call
        import logging

        logging.getLogger(__name__).warning(f"Failed to publish water event: {e}")

    # 计算今日总饮水量
    today_total = await get_today_water_total(current_user.id, db)

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
