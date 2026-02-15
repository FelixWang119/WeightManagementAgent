"""
睡眠记录 API 路由
包含：睡眠记录、睡眠统计、睡眠质量分析
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta

from models.database import get_db, User, SleepRecord
from api.routes.user import get_current_user
from services.sleep_analysis_service import SleepAnalysisService

router = APIRouter()


def convert_12h_to_datetime(time_str: str, period: str, base_date: date) -> datetime:
    """将12小时制时间转换为datetime"""
    hour = int(time_str.split(":")[0])
    minute = int(time_str.split(":")[1]) if ":" in time_str else 0

    if period.upper() == "PM" and hour != 12:
        hour += 12
    elif period.upper() == "AM" and hour == 12:
        hour = 0

    return datetime(base_date.year, base_date.month, base_date.day, hour, minute)


@router.post("/record")
async def record_sleep(
    bed_time: str,
    bed_period: str,
    wake_time: str,
    wake_period: str,
    sleep_date: str = None,
    quality: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    记录睡眠（12小时制）

    - **bed_time**: 入睡时间（HH:MM格式，如 11:00）
    - **bed_period**: 入睡时段（AM 或 PM）
    - **wake_time**: 起床时间（HH:MM格式，如 07:00）
    - **wake_period**: 起床时段（AM 或 PM）
    - **sleep_date**: 睡眠日期（YYYY-MM-DD格式，默认昨天）
    - **quality**: 睡眠质量评分（1-5星，可选）
    """
    if bed_period.upper() not in ["AM", "PM"]:
        raise HTTPException(status_code=400, detail="入睡时段必须是 AM 或 PM")

    if wake_period.upper() not in ["AM", "PM"]:
        raise HTTPException(status_code=400, detail="起床时段必须是 AM 或 PM")

    if sleep_date:
        base_date = date.fromisoformat(sleep_date)
    else:
        base_date = date.today() - timedelta(days=1)

    bed_datetime = convert_12h_to_datetime(bed_time, bed_period, base_date)
    wake_datetime = convert_12h_to_datetime(wake_time, wake_period, base_date)

    if wake_datetime <= bed_datetime:
        wake_datetime += timedelta(days=1)

    duration = (wake_datetime - bed_datetime).total_seconds() / 60

    if duration > 720:
        raise HTTPException(status_code=400, detail="睡眠时长不能超过12小时")

    if duration < 60:
        raise HTTPException(status_code=400, detail="睡眠时长不能少于1小时")

    if quality is not None and (quality < 1 or quality > 5):
        raise HTTPException(status_code=400, detail="睡眠质量评分必须在1-5之间")

    result = await db.execute(
        select(SleepRecord).where(
            and_(
                SleepRecord.user_id == current_user.id,
                SleepRecord.bed_time
                >= datetime.combine(base_date, datetime.min.time()),
                SleepRecord.bed_time
                < datetime.combine(base_date + timedelta(days=1), datetime.min.time()),
            )
        )
    )
    existing_record = result.scalar_one_or_none()

    if existing_record:
        return {
            "success": False,
            "duplicate": True,
            "message": "该日期已有睡眠记录",
            "data": {
                "existing_id": existing_record.id,
                "bed_time": existing_record.bed_time.isoformat(),
                "wake_time": existing_record.wake_time.isoformat(),
                "duration_hours": round(existing_record.total_minutes / 60, 1),
                "duration_minutes": existing_record.total_minutes,
                "quality": existing_record.quality,
                "assessment": assess_sleep_quality(
                    int(existing_record.total_minutes), existing_record.quality
                ),
            },
        }

    record = SleepRecord(
        user_id=current_user.id,
        bed_time=bed_datetime,
        wake_time=wake_datetime,
        total_minutes=int(duration),
        quality=quality,
        created_at=datetime.now(),
    )

    db.add(record)
    await db.commit()
    await db.refresh(record)

    quality_assessment = assess_sleep_quality(int(duration), quality)

    return {
        "success": True,
        "message": "睡眠记录成功",
        "data": {
            "id": record.id,
            "bed_time": bed_datetime.isoformat(),
            "wake_time": wake_datetime.isoformat(),
            "duration_hours": round(duration / 60, 1),
            "duration_minutes": int(duration),
            "quality": quality,
            "assessment": quality_assessment,
        },
    }


@router.put("/overwrite/{record_id}")
async def overwrite_sleep_record(
    record_id: int,
    bed_time: str,
    bed_period: str,
    wake_time: str,
    wake_period: str,
    sleep_date: str = None,
    quality: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """覆盖已有睡眠记录"""
    result = await db.execute(
        select(SleepRecord).where(
            and_(SleepRecord.id == record_id, SleepRecord.user_id == current_user.id)
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    if bed_period.upper() not in ["AM", "PM"] or wake_period.upper() not in [
        "AM",
        "PM",
    ]:
        raise HTTPException(status_code=400, detail="时段必须是 AM 或 PM")

    if sleep_date:
        base_date = date.fromisoformat(sleep_date)
    else:
        base_date = record.bed_time.date()

    bed_datetime = convert_12h_to_datetime(bed_time, bed_period, base_date)
    wake_datetime = convert_12h_to_datetime(wake_time, wake_period, base_date)

    if wake_datetime <= bed_datetime:
        wake_datetime += timedelta(days=1)

    duration = (wake_datetime - bed_datetime).total_seconds() / 60

    if duration > 720 or duration < 60:
        raise HTTPException(status_code=400, detail="睡眠时长必须在1-12小时之间")

    record.bed_time = bed_datetime
    record.wake_time = wake_datetime
    record.total_minutes = int(duration)
    record.quality = quality

    await db.commit()

    return {
        "success": True,
        "message": "睡眠记录已更新",
        "data": {
            "id": record.id,
            "bed_time": bed_datetime.isoformat(),
            "wake_time": wake_datetime.isoformat(),
            "duration_hours": round(duration / 60, 1),
            "duration_minutes": int(duration),
            "quality": quality,
            "assessment": assess_sleep_quality(int(duration), quality),
        },
    }


@router.get("/history")
async def get_sleep_history(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取睡眠历史"""
    start_date = date.today() - timedelta(days=days - 1)

    result = await db.execute(
        select(SleepRecord)
        .where(
            and_(
                SleepRecord.user_id == current_user.id,
                SleepRecord.bed_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
        .order_by(SleepRecord.bed_time.desc())
    )

    records = result.scalars().all()

    return {
        "success": True,
        "count": len(records),
        "data": [
            {
                "id": r.id,
                "bed_time": r.bed_time.isoformat(),
                "wake_time": r.wake_time.isoformat(),
                "duration_hours": round(r.total_minutes / 60, 1),
                "duration_minutes": r.total_minutes,
                "quality": r.quality,
                "date": r.bed_time.date().isoformat(),
            }
            for r in records
        ],
    }


@router.get("/stats")
async def get_sleep_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取睡眠统计"""
    # 本周数据
    week_start = date.today() - timedelta(days=date.today().weekday())
    result = await db.execute(
        select(
            func.count(SleepRecord.id),
            func.avg(SleepRecord.total_minutes),
            func.avg(SleepRecord.quality),
        ).where(
            and_(
                SleepRecord.user_id == current_user.id,
                SleepRecord.bed_time
                >= datetime.combine(week_start, datetime.min.time()),
            )
        )
    )
    week_count, week_avg_duration, week_avg_quality = result.one()

    # 本月数据
    month_start = date.today().replace(day=1)
    result = await db.execute(
        select(
            func.count(SleepRecord.id),
            func.avg(SleepRecord.total_minutes),
            func.avg(SleepRecord.quality),
        ).where(
            and_(
                SleepRecord.user_id == current_user.id,
                SleepRecord.bed_time
                >= datetime.combine(month_start, datetime.min.time()),
            )
        )
    )
    month_count, month_avg_duration, month_avg_quality = result.one()

    # 睡眠规律分析
    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.id)
        .order_by(SleepRecord.bed_time.desc())
        .limit(7)
    )
    recent_records = result.scalars().all()

    if recent_records:
        # 计算平均入睡时间
        bed_times = [r.bed_time.hour + r.bed_time.minute / 60 for r in recent_records]
        avg_bed_time = sum(bed_times) / len(bed_times)

        # 计算平均起床时间
        wake_times = [
            r.wake_time.hour + r.wake_time.minute / 60 for r in recent_records
        ]
        avg_wake_time = sum(wake_times) / len(wake_times)

        sleep_pattern = {
            "avg_bed_time": f"{int(avg_bed_time):02d}:{int((avg_bed_time % 1) * 60):02d}",
            "avg_wake_time": f"{int(avg_wake_time):02d}:{int((avg_wake_time % 1) * 60):02d}",
            "consistency": "规律" if max(bed_times) - min(bed_times) < 2 else "不规律",
        }
    else:
        sleep_pattern = None

    return {
        "success": True,
        "data": {
            "this_week": {
                "record_count": week_count or 0,
                "avg_duration_hours": round((week_avg_duration or 0) / 60, 1),
                "avg_quality": round(week_avg_quality or 0, 1),
            },
            "this_month": {
                "record_count": month_count or 0,
                "avg_duration_hours": round((month_avg_duration or 0) / 60, 1),
                "avg_quality": round(month_avg_quality or 0, 1),
            },
            "sleep_pattern": sleep_pattern,
            "recommendations": generate_sleep_recommendations(
                week_avg_duration or 0, week_avg_quality or 0
            ),
        },
    }


@router.get("/last")
async def get_last_sleep(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取最近一条睡眠记录"""
    result = await db.execute(
        select(SleepRecord)
        .where(SleepRecord.user_id == current_user.id)
        .order_by(SleepRecord.bed_time.desc())
        .limit(1)
    )

    record = result.scalar_one_or_none()

    if not record:
        return {"success": True, "message": "暂无睡眠记录", "data": None}

    return {
        "success": True,
        "data": {
            "id": record.id,
            "bed_time": record.bed_time.isoformat(),
            "wake_time": record.wake_time.isoformat(),
            "duration_hours": round(record.total_minutes / 60, 1),
            "duration_minutes": record.total_minutes,
            "quality": record.quality,
            "date": record.bed_time.date().isoformat(),
            "assessment": assess_sleep_quality(record.total_minutes, record.quality),
        },
    }


@router.delete("/record/{record_id}")
async def delete_sleep_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除睡眠记录"""
    result = await db.execute(
        select(SleepRecord).where(
            and_(SleepRecord.id == record_id, SleepRecord.user_id == current_user.id)
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()

    return {"success": True, "message": "睡眠记录已删除"}


# ============ 辅助函数 ============


def assess_sleep_quality(duration_minutes: int, quality: Optional[int]) -> str:
    """评估睡眠质量"""
    duration_hours = duration_minutes / 60

    if duration_hours < 6:
        return "睡眠不足"
    elif duration_hours < 7:
        return "睡眠略少"
    elif duration_hours <= 9:
        if quality and quality >= 4:
            return "睡眠质量良好"
        elif quality and quality >= 3:
            return "睡眠质量一般"
        else:
            return "睡眠时长充足"
    else:
        return "睡眠过多"


def generate_sleep_recommendations(
    avg_duration_minutes: float, avg_quality: float
) -> List[str]:
    """生成睡眠建议"""
    recommendations = []

    duration_hours = avg_duration_minutes / 60

    if duration_hours < 7:
        recommendations.append("建议每晚保证7-8小时睡眠，有助于体重管理")

    if duration_hours > 9:
        recommendations.append("睡眠时间偏长，建议保持规律作息")

    if avg_quality < 3:
        recommendations.append("睡眠质量有待提高，建议睡前放松，避免使用电子设备")

    if not recommendations:
        recommendations.append("您的睡眠状况良好，请继续保持！")

    return recommendations


# ============ 睡眠分析 API ============


@router.get("/analysis/pattern")
async def get_sleep_pattern_analysis_endpoint(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取睡眠规律性分析

    - **days**: 分析天数（7-90天，默认30天）

    分析指标：
    - 入睡时间规律性
    - 起床时间规律性
    - 睡眠时长规律性
    - 综合规律性评分
    """
    result = await SleepAnalysisService.get_sleep_pattern_analysis(
        user_id=current_user.id, days=days, db=db
    )
    return result


@router.get("/analysis/quality-trend")
async def get_sleep_quality_trend_endpoint(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取睡眠质量趋势分析

    - **days**: 分析天数（7-90天，默认30天）

    返回趋势图表数据，包含：
    - 质量评分变化趋势
    - 睡眠时长变化
    - 质量分布统计
    """
    result = await SleepAnalysisService.get_sleep_quality_trend(
        user_id=current_user.id, days=days, db=db
    )
    return result


@router.get("/analysis/weight-correlation")
async def analyze_sleep_weight_correlation_endpoint(
    days: int = Query(30, ge=14, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    分析睡眠与体重的关联性

    - **days**: 分析天数（14-90天，默认30天）

    检测指标：
    - 睡眠时长与体重变化的相关性
    - 睡眠质量与体重变化的相关性
    - 睡眠不足对体重的影响分析
    """
    result = await SleepAnalysisService.analyze_sleep_weight_correlation(
        user_id=current_user.id, days=days, db=db
    )
    return result


@router.get("/analysis/dashboard")
async def get_sleep_analysis_dashboard(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取睡眠分析仪表盘数据（综合所有分析）

    - **days**: 分析天数（7-90天，默认30天）

    返回完整的睡眠分析报告
    """
    # 并行获取所有分析数据
    pattern_result = await SleepAnalysisService.get_sleep_pattern_analysis(
        user_id=current_user.id, days=days, db=db
    )

    trend_result = await SleepAnalysisService.get_sleep_quality_trend(
        user_id=current_user.id, days=days, db=db
    )

    correlation_result = await SleepAnalysisService.analyze_sleep_weight_correlation(
        user_id=current_user.id, days=days, db=db
    )

    return {
        "success": True,
        "period": {
            "days": days,
            "start_date": (date.today() - timedelta(days=days)).isoformat(),
            "end_date": date.today().isoformat(),
        },
        "pattern_analysis": pattern_result.get("data")
        if pattern_result.get("success")
        else None,
        "quality_trend": trend_result.get("data")
        if trend_result.get("success")
        else None,
        "weight_correlation": correlation_result.get("data")
        if correlation_result.get("success")
        else None,
        "summary": {
            "pattern_score": pattern_result.get("data", {}).get("overall_score")
            if pattern_result.get("success")
            else None,
            "pattern_classification": pattern_result.get("data", {}).get(
                "classification"
            )
            if pattern_result.get("success")
            else None,
            "avg_quality": trend_result.get("data", {})
            .get("summary", {})
            .get("avg_quality")
            if trend_result.get("success")
            else None,
            "correlation_strength": correlation_result.get("data", {})
            .get("correlation", {})
            .get("strength")
            if correlation_result.get("success")
            else None,
        },
    }
