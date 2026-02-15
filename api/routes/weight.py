"""
体重记录 API 路由
包含：记录体重、查询趋势、统计数据
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta

from models.database import get_db, WeightRecord, User
from api.routes.user import get_current_user
from services.event_triggers import publish_weight_recorded_event

router = APIRouter()


@router.post("/record")
async def record_weight(
    weight: float,
    body_fat: Optional[float] = None,
    record_date: Optional[date] = None,
    note: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    记录体重

    - **weight**: 体重（kg）
    - **body_fat**: 体脂率（%，可选）
    - **record_date**: 记录日期（默认今天）
    - **note**: 备注（可选）
    """
    # 使用当前日期或指定日期
    target_date = record_date or date.today()
    target_time = datetime.combine(target_date, datetime.now().time())

    # 检查当天是否已有记录
    result = await db.execute(
        select(WeightRecord).where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date == target_date,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # 更新已有记录
        existing.weight = weight
        if body_fat is not None:
            existing.body_fat = body_fat
        if note:
            existing.note = note
        existing.record_time = target_time
        message = "体重记录已更新"
    else:
        # 创建新记录
        record = WeightRecord(
            user_id=current_user.id,
            weight=weight,
            body_fat=body_fat,
            record_date=target_date,
            record_time=target_time,
            note=note,
        )
        db.add(record)
        message = "体重记录成功"

    await db.commit()

    # Publish event to event bus (after commit to ensure record exists)
    try:
        # Get the record ID if it was just created
        if not existing:
            await db.refresh(record)
            record_id = record.id
        else:
            record_id = existing.id

        await publish_weight_recorded_event(
            user_id=current_user.id,
            weight=weight,
            body_fat=body_fat,
            record_date=target_date,
            record_id=record_id,
        )
    except Exception as e:
        # Log error but don't fail the API call
        import logging

        logging.getLogger(__name__).warning(f"Failed to publish weight event: {e}")

    return {
        "success": True,
        "message": message,
        "data": {
            "weight": weight,
            "body_fat": body_fat,
            "record_date": target_date.isoformat(),
            "note": note,
        },
    }


@router.get("/history")
async def get_weight_history(
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取体重历史记录

    - **days**: 查询最近多少天（默认30天）
    """
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(WeightRecord)
        .where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= start_date,
            )
        )
        .order_by(WeightRecord.record_date.desc())
    )

    records = result.scalars().all()

    return {
        "success": True,
        "count": len(records),
        "data": [
            {
                "id": r.id,
                "weight": r.weight,
                "body_fat": r.body_fat,
                "record_date": r.record_date.isoformat(),
                "note": r.note,
            }
            for r in records
        ],
    }


@router.get("/trend")
async def get_weight_trend(
    days: int = Query(30, ge=7, le=365, description="趋势天数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取体重趋势数据（用于图表展示）

    - **days**: 查询天数（默认30天）

    返回：
    - 日期列表
    - 体重数据列表
    - 变化趋势
    """
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(WeightRecord)
        .where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= start_date,
            )
        )
        .order_by(WeightRecord.record_date.asc())
    )

    records = result.scalars().all()

    if len(records) < 2:
        return {
            "success": True,
            "message": "数据不足，无法生成趋势",
            "data": {
                "dates": [r.record_date.isoformat() for r in records],
                "weights": [r.weight for r in records],
                "change": None,
                "trend": "insufficient_data",
            },
        }

    # 计算变化
    first_weight = records[0].weight
    last_weight = records[-1].weight
    change = last_weight - first_weight

    # 判断趋势
    if change < -0.5:
        trend = "decreasing"  # 明显下降
        trend_text = "呈下降趋势"
    elif change > 0.5:
        trend = "increasing"  # 明显上升
        trend_text = "呈上升趋势"
    else:
        trend = "stable"  # 基本稳定
        trend_text = "基本稳定"

    return {
        "success": True,
        "data": {
            "dates": [r.record_date.isoformat() for r in records],
            "weights": [r.weight for r in records],
            "body_fats": [r.body_fat for r in records if r.body_fat],
            "first_weight": first_weight,
            "last_weight": last_weight,
            "change": round(change, 2),
            "change_percent": round(change / first_weight * 100, 2)
            if first_weight > 0
            else 0,
            "trend": trend,
            "trend_text": trend_text,
            "min_weight": min(r.weight for r in records),
            "max_weight": max(r.weight for r in records),
            "avg_weight": round(sum(r.weight for r in records) / len(records), 2),
        },
    }


@router.get("/stats")
async def get_weight_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取体重统计数据

    返回：
    - 最新体重
    - 本周/本月统计
    - 历史最高/最低
    """
    # 最新体重
    result = await db.execute(
        select(WeightRecord)
        .where(WeightRecord.user_id == current_user.id)
        .order_by(WeightRecord.record_date.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if not latest:
        return {"success": True, "message": "暂无体重记录", "data": None}

    # 本周统计
    week_start = date.today() - timedelta(days=date.today().weekday())
    result = await db.execute(
        select(func.avg(WeightRecord.weight), func.count(WeightRecord.id)).where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= week_start,
            )
        )
    )
    week_avg, week_count = result.one()

    # 本月统计
    month_start = date.today().replace(day=1)
    result = await db.execute(
        select(func.avg(WeightRecord.weight), func.count(WeightRecord.id)).where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= month_start,
            )
        )
    )
    month_avg, month_count = result.one()

    # 历史最高/最低
    result = await db.execute(
        select(func.min(WeightRecord.weight), func.max(WeightRecord.weight)).where(
            WeightRecord.user_id == current_user.id
        )
    )
    min_weight, max_weight = result.one()

    return {
        "success": True,
        "data": {
            "latest": {
                "weight": latest.weight,
                "body_fat": latest.body_fat,
                "date": latest.record_date.isoformat(),
            },
            "this_week": {
                "average": round(week_avg, 2) if week_avg else None,
                "count": week_count,
            },
            "this_month": {
                "average": round(month_avg, 2) if month_avg else None,
                "count": month_count,
            },
            "all_time": {
                "min": min_weight,
                "max": max_weight,
                "range": round(max_weight - min_weight, 2)
                if min_weight and max_weight
                else 0,
            },
        },
    }


@router.delete("/record/{record_id}")
async def delete_weight_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除体重记录"""
    result = await db.execute(
        select(WeightRecord).where(
            and_(WeightRecord.id == record_id, WeightRecord.user_id == current_user.id)
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()

    return {"success": True, "message": "记录已删除"}
