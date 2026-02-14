"""
习惯打卡追踪 API 路由
包含：连续打卡统计、打卡热力图、习惯养成进度
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from models.database import get_db
from api.routes.user import get_current_user
from services.habit_tracking_service import HabitTrackingService

router = APIRouter()


@router.get("/streaks")
async def get_streak_stats(
    days: int = Query(90, ge=7, le=365),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取连续打卡统计

    - **days**: 统计天数（7-365天，默认90天）

    返回各维度的连续打卡统计：
    - 当前连续天数
    - 最大连续天数
    - 完成率
    - 综合统计
    """
    result = await HabitTrackingService.get_streak_stats(
        user_id=current_user.id, days=days, db=db
    )
    return result


@router.get("/heatmap")
async def get_checkin_heatmap(
    year: Optional[int] = Query(None, ge=2020, le=2100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取打卡热力图数据

    - **year**: 年份（默认当前年）

    返回 GitHub 风格的年度打卡热力图数据
    """
    result = await HabitTrackingService.get_checkin_heatmap(
        user_id=current_user.id, year=year, db=db
    )
    return result


@router.get("/progress")
async def get_habit_progress(
    current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取习惯养成进度

    分析最近30天的习惯养成情况：
    - 每日称重习惯
    - 规律三餐习惯
    - 每日运动习惯
    - 饮水达标习惯
    - 睡眠记录习惯

    返回各习惯的进度百分比和状态评估
    """
    result = await HabitTrackingService.get_habit_progress(
        user_id=current_user.id, db=db
    )
    return result


@router.get("/recent")
async def get_recent_checkins(
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取最近打卡记录

    - **limit**: 返回数量（1-50，默认10）

    返回最近的打卡记录列表
    """
    result = await HabitTrackingService.get_recent_checkins(
        user_id=current_user.id, limit=limit, db=db
    )
    return result


@router.get("/dashboard")
async def get_habit_dashboard(
    days: int = Query(30, ge=7, le=90),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取习惯打卡仪表盘（综合数据）

    - **days**: 统计天数（7-90天，默认30天）

    返回完整的习惯打卡数据：
    - 连续打卡统计
    - 习惯养成进度
    - 最近打卡记录
    """
    # 并行获取数据
    streak_result = await HabitTrackingService.get_streak_stats(
        user_id=current_user.id, days=days, db=db
    )

    progress_result = await HabitTrackingService.get_habit_progress(
        user_id=current_user.id, db=db
    )

    recent_result = await HabitTrackingService.get_recent_checkins(
        user_id=current_user.id, limit=10, db=db
    )

    return {
        "success": True,
        "period": {"days": days, "description": f"最近{days}天"},
        "streaks": streak_result.get("data") if streak_result.get("success") else None,
        "progress": progress_result.get("data")
        if progress_result.get("success")
        else None,
        "recent": recent_result.get("data") if recent_result.get("success") else None,
        "summary": {
            "current_streak": streak_result.get("data", {})
            .get("overall", {})
            .get("current_streak")
            if streak_result.get("success")
            else 0,
            "max_streak": streak_result.get("data", {})
            .get("overall", {})
            .get("max_streak")
            if streak_result.get("success")
            else 0,
            "overall_score": progress_result.get("data", {}).get("overall_score")
            if progress_result.get("success")
            else 0,
        },
    }
