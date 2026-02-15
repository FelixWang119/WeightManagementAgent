"""
运动记录 API 路由
包含：运动记录、运动统计、运动类型管理
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta

from models.database import get_db, User, ExerciseRecord, ExerciseIntensity
from api.routes.user import get_current_user
from services.event_triggers import publish_exercise_recorded_event

router = APIRouter()


# 运动类型和消耗热量参考（千卡/小时）
EXERCISE_CALORIES = {
    "跑步": 600,
    "快走": 300,
    "游泳": 500,
    "骑行": 400,
    "瑜伽": 200,
    "力量训练": 350,
    "跳绳": 700,
    "篮球": 450,
    "足球": 500,
    "羽毛球": 350,
    "乒乓球": 250,
    "登山": 500,
    "跳舞": 350,
    "椭圆机": 400,
    "动感单车": 500,
    "HIIT": 600,
    "拉伸": 100,
    "其他": 300,
}


@router.post("/record")
async def record_exercise(
    exercise_type: str,
    duration_minutes: int,
    intensity: str = "medium",
    calories_burned: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    记录运动

    - **exercise_type**: 运动类型（跑步、游泳、瑜伽等）
    - **duration_minutes**: 运动时长（分钟）
    - **intensity**: 强度（low/medium/high）
    - **calories_burned**: 消耗热量（可选，自动计算）
    """
    try:
        intensity_enum = ExerciseIntensity(intensity)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的运动强度")

    # 如果没有提供热量，自动计算
    if calories_burned is None:
        calories_per_hour = EXERCISE_CALORIES.get(exercise_type, 300)
        calories_burned = int(calories_per_hour * duration_minutes / 60)

        # 根据强度调整
        intensity_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.2}
        calories_burned = int(
            calories_burned * intensity_multiplier.get(intensity, 1.0)
        )

    record = ExerciseRecord(
        user_id=current_user.id,
        exercise_type=exercise_type,
        duration_minutes=duration_minutes,
        calories_burned=calories_burned,
        intensity=intensity_enum,
        record_time=datetime.now(),
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Publish event to event bus
    try:
        await publish_exercise_recorded_event(
            user_id=current_user.id,
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            calories_burned=calories_burned,
            intensity=intensity,
            record_id=record.id,
        )
    except Exception as e:
        # Log error but don't fail the API call
        import logging

        logging.getLogger(__name__).warning(f"Failed to publish exercise event: {e}")

    return {
        "success": True,
        "message": "运动记录成功",
        "data": {
            "id": record.id,
            "exercise_type": exercise_type,
            "duration_minutes": duration_minutes,
            "calories_burned": calories_burned,
            "intensity": intensity,
            "record_time": record.record_time.isoformat(),
        },
    }


@router.get("/history")
async def get_exercise_history(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取运动历史"""
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(ExerciseRecord)
        .where(
            and_(
                ExerciseRecord.user_id == current_user.id,
                ExerciseRecord.record_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
        .order_by(ExerciseRecord.record_time.desc())
    )

    records = result.scalars().all()

    return {
        "success": True,
        "count": len(records),
        "data": [
            {
                "id": r.id,
                "exercise_type": r.exercise_type,
                "duration_minutes": r.duration_minutes,
                "calories_burned": r.calories_burned,
                "intensity": r.intensity.value,
                "record_time": r.record_time.isoformat(),
            }
            for r in records
        ],
    }


@router.get("/stats")
async def get_exercise_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取运动统计"""
    # 本周统计
    week_start = date.today() - timedelta(days=date.today().weekday())
    result = await db.execute(
        select(
            func.count(ExerciseRecord.id),
            func.sum(ExerciseRecord.duration_minutes),
            func.sum(ExerciseRecord.calories_burned),
        ).where(
            and_(
                ExerciseRecord.user_id == current_user.id,
                ExerciseRecord.record_time
                >= datetime.combine(week_start, datetime.min.time()),
            )
        )
    )
    week_count, week_duration, week_calories = result.one()

    # 本月统计
    month_start = date.today().replace(day=1)
    result = await db.execute(
        select(
            func.count(ExerciseRecord.id),
            func.sum(ExerciseRecord.duration_minutes),
            func.sum(ExerciseRecord.calories_burned),
        ).where(
            and_(
                ExerciseRecord.user_id == current_user.id,
                ExerciseRecord.record_time
                >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    )
    month_count, month_duration, month_calories = result.one()

    # 运动类型分布
    result = await db.execute(
        select(
            ExerciseRecord.exercise_type,
            func.count(ExerciseRecord.id),
            func.sum(ExerciseRecord.duration_minutes),
        )
        .where(ExerciseRecord.user_id == current_user.id)
        .group_by(ExerciseRecord.exercise_type)
        .order_by(desc(func.count(ExerciseRecord.id)))
        .limit(5)
    )
    type_distribution = result.all()

    return {
        "success": True,
        "data": {
            "this_week": {
                "count": week_count or 0,
                "duration_minutes": week_duration or 0,
                "calories_burned": week_calories or 0,
            },
            "this_month": {
                "count": month_count or 0,
                "duration_minutes": month_duration or 0,
                "calories_burned": month_calories or 0,
            },
            "top_exercises": [
                {"type": t[0], "count": t[1], "total_duration": t[2]}
                for t in type_distribution
            ],
        },
    }


@router.get("/types")
async def get_exercise_types():
    """获取运动类型列表及热量参考"""
    return {
        "success": True,
        "data": [
            {
                "type": exercise_type,
                "calories_per_hour": calories,
                "description": f"每小时约消耗 {calories} 千卡",
            }
            for exercise_type, calories in EXERCISE_CALORIES.items()
        ],
    }


@router.delete("/record/{record_id}")
async def delete_exercise_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除运动记录"""
    result = await db.execute(
        select(ExerciseRecord).where(
            and_(
                ExerciseRecord.id == record_id,
                ExerciseRecord.user_id == current_user.id,
            )
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()

    return {"success": True, "message": "运动记录已删除"}


# ============ 运动打卡功能 ============


@router.post("/checkin")
async def checkin_exercise(
    exercise_type: Optional[str] = Body(None),
    duration_minutes: int = Body(30),
    intensity: ExerciseIntensity = Body(ExerciseIntensity.MEDIUM),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    运动打卡（快速记录）

    简化版运动记录，用于快速打卡，区别于详细运动记录
    """
    # 如果没有提供运动类型，使用默认值
    if not exercise_type:
        exercise_type = "日常活动"

    # 计算消耗热量（后端统一计算）
    calories_per_hour = EXERCISE_CALORIES.get(exercise_type, 200)

    # 强度系数
    intensity_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.2}
    intensity_factor = intensity_multiplier.get(intensity.value, 1.0)

    calories_burned = int(calories_per_hour * duration_minutes / 60 * intensity_factor)

    # 创建打卡记录
    record = ExerciseRecord(
        user_id=current_user.id,
        exercise_type=exercise_type,
        duration_minutes=duration_minutes,
        calories_burned=calories_burned,
        intensity=intensity,
        record_time=datetime.now(),
        is_checkin=True,
        checkin_date=date.today(),
    )

    db.add(record)
    await db.commit()

    return {
        "success": True,
        "message": "打卡成功！",
        "data": {
            "id": record.id,
            "exercise_type": exercise_type,
            "duration_minutes": duration_minutes,
            "calories_burned": calories_burned,
            "intensity": intensity.value,
            "checkin_date": record.checkin_date.isoformat(),
            "created_at": record.created_at.isoformat(),
        },
    }


@router.get("/checkins")
async def get_checkin_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_all: bool = Query(
        False, description="是否包含所有运动记录（包含AI对话记录）"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取打卡历史

    Args:
        include_all: 如果为true，包含通过AI对话记录的运动
    """
    # 构建查询条件
    conditions = [ExerciseRecord.user_id == current_user.id]

    # 打卡记录 or AI对话记录
    if include_all:
        # 包含所有运动记录
        pass
    else:
        # 只显示手动打卡的记录
        conditions.append(ExerciseRecord.is_checkin == True)

    query = select(ExerciseRecord).where(and_(*conditions))

    # 按record_time降序排序（最新在前）
    query = query.order_by(ExerciseRecord.record_time.desc())

    if start_date:
        query = query.where(ExerciseRecord.checkin_date >= start_date)
    if end_date:
        query = query.where(ExerciseRecord.checkin_date <= end_date)

    # 执行查询获取记录
    result = await db.execute(query)
    records = result.scalars().all()

    # 获取所有记录用于计算连续打卡（只统计手动打卡的）
    all_checkin_query = (
        select(ExerciseRecord)
        .where(
            and_(
                ExerciseRecord.user_id == current_user.id,
                ExerciseRecord.is_checkin == True,
            )
        )
        .order_by(ExerciseRecord.checkin_date.desc())
    )

    checkin_result = await db.execute(all_checkin_query)
    checkin_records = checkin_result.scalars().all()

    # 统计连续打卡天数
    checkin_dates = sorted([r.checkin_date for r in checkin_records if r.checkin_date])
    streak = 0
    if checkin_dates:
        today = date.today()
        yesterday = today - timedelta(days=1)

        # 检查昨天是否有打卡
        if yesterday in checkin_dates:
            streak = 1
            current_date = yesterday - timedelta(days=1)
            while current_date in checkin_dates:
                streak += 1
                current_date -= timedelta(days=1)
        # 检查今天是否有打卡
        if today in checkin_dates:
            streak += 1
        elif yesterday not in checkin_dates:
            streak = 1 if today in checkin_dates else 0

    # 获取日期字段的函数
    def get_record_date(record):
        if record.checkin_date:
            return record.checkin_date
        if record.record_time:
            return record.record_time.date()
        return None

    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "exercise_type": r.exercise_type,
                "duration_minutes": r.duration_minutes,
                "calories_burned": r.calories_burned,
                "intensity": r.intensity.value if r.intensity else None,
                "is_checkin": r.is_checkin,
                "checkin_date": r.checkin_date.isoformat() if r.checkin_date else None,
                "record_date": get_record_date(r).isoformat()
                if get_record_date(r)
                else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "stats": {
            "total_checkins": len(checkin_records),
            "current_streak": streak,
            "first_checkin": checkin_dates[0].isoformat() if checkin_dates else None,
            "last_checkin": checkin_dates[-1].isoformat() if checkin_dates else None,
            "total_records": len(records),
        },
    }
