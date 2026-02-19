"""
成就与积分 API
提供成就查询、积分管理
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from models.database import get_db, User
from api.routes.user import get_current_user
from services.achievement_service import AchievementService, PointsService

router = APIRouter()


class PointsRequest(BaseModel):
    reason: str
    amount: int


@router.get("/achievements")
async def get_achievements(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取用户成就

    - 返回所有成就列表和解锁状态
    """
    result = await AchievementService.get_user_achievements(current_user.id, db)
    return result


@router.get("/points")
async def get_points(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取用户积分

    - 当前积分
    - 累计获得
    - 累计消耗
    """
    result = await PointsService.get_user_points(current_user.id, db)
    return result


@router.post("/points/earn")
async def earn_points(
    points_data: PointsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获得积分

    - reason: 获得原因
    - amount: 积分数量
    """
    result = await PointsService.earn_points(
        current_user.id, points_data.reason, points_data.amount, db
    )
    return result


@router.post("/points/spend")
async def spend_points(
    points_data: PointsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    消费积分

    - reason: 消费原因
    - amount: 积分数量
    """
    result = await PointsService.spend_points(
        current_user.id, points_data.reason, points_data.amount, db
    )
    return result


@router.get("/points/history")
async def get_points_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取积分历史

    - limit: 返回数量
    """
    result = await PointsService.get_points_history(current_user.id, db, limit)
    return result


@router.get("/dashboard")
async def get_achievement_dashboard(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取成就仪表盘

    - 成就概览
    - 积分概览
    - 进度统计
    """
    achievements = await AchievementService.get_user_achievements(current_user.id, db)
    points = await PointsService.get_user_points(current_user.id, db)

    return {
        "success": True,
        "data": {
            "achievements": achievements.get("data", {}),
            "points": points.get("data", {}),
        },
    }


@router.get("/leaderboard/points")
async def get_points_leaderboard(
    period: str = "total",  # total, week, month
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取积分排行榜"""
    from services.leaderboard_service import LeaderboardService

    return await LeaderboardService.get_points_leaderboard(db, period, limit)


@router.get("/leaderboard/achievements")
async def get_achievement_leaderboard(
    category: str = "count",  # count, rare
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取成就排行榜"""
    from services.leaderboard_service import LeaderboardService

    return await LeaderboardService.get_achievement_leaderboard(db, category, limit)


@router.get("/leaderboard/streak")
async def get_streak_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取连续打卡排行榜"""
    from services.leaderboard_service import LeaderboardService

    return await LeaderboardService.get_streak_leaderboard(db, limit)


@router.get("/leaderboard/my-rank")
async def get_my_rank(
    type: str = "points",  # points, achievements
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的排名"""
    from services.leaderboard_service import LeaderboardService

    return await LeaderboardService.get_user_rank(current_user.id, db, type)
