"""
排行榜服务
提供用户积分、成就、连续打卡等排行榜功能
"""

from typing import Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from models.database import User, UserProfile
from models.points_history import PointsHistory, PointsType
from services.achievement_service import ACHIEVEMENTS, AchievementService
from services.integration_service import DailyCheckinService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class LeaderboardService:
    """排行榜服务"""

    @staticmethod
    async def get_points_leaderboard(
        db: AsyncSession,
        period: str = "total",  # total, week, month
        limit: int = 10,
    ) -> Dict[str, Any]:
        """获取积分排行榜"""
        logger.info("获取积分排行榜 - 周期: %s, 限制: %s", period, limit)

        try:
            if period == "total":
                # 总积分排行榜
                result = await db.execute(
                    select(User.id, User.username, UserProfile.total_points_earned)
                    .join(UserProfile, User.id == UserProfile.user_id)
                    .where(UserProfile.total_points_earned > 0)
                    .order_by(desc(UserProfile.total_points_earned))
                    .limit(limit)
                )

                rankings = []
                rank = 1
                for row in result:
                    rankings.append(
                        {
                            "rank": rank,
                            "user_id": row.id,
                            "username": row.username,
                            "points": row.total_points_earned,
                        }
                    )
                    rank += 1

            elif period == "week":
                # 本周积分排行榜
                week_start = date.today() - timedelta(days=date.today().weekday())
                rankings = await LeaderboardService._get_period_points_leaderboard(
                    db, week_start, limit
                )

            elif period == "month":
                # 本月积分排行榜
                month_start = date.today().replace(day=1)
                rankings = await LeaderboardService._get_period_points_leaderboard(
                    db, month_start, limit
                )
            else:
                return {"success": False, "error": "无效的周期参数"}

            return {
                "success": True,
                "data": {
                    "period": period,
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.exception("获取积分排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}

    @staticmethod
    async def _get_period_points_leaderboard(
        db: AsyncSession, start_date: date, limit: int
    ) -> List[Dict]:
        """获取指定周期内的积分排行榜"""
        from sqlalchemy import text

        # 使用原生SQL查询积分历史
        query = """
            SELECT 
                ph.user_id,
                u.username,
                SUM(ph.amount) as period_points
            FROM points_history ph
            JOIN users u ON ph.user_id = u.id
            WHERE ph.points_type = 'earn'
            AND ph.created_at >= :start_date
            GROUP BY ph.user_id, u.username
            ORDER BY period_points DESC
            LIMIT :limit
        """

        result = await db.execute(
            text(query), {"start_date": start_date, "limit": limit}
        )

        rankings = []
        rank = 1
        for row in result:
            rankings.append(
                {
                    "rank": rank,
                    "user_id": row.user_id,
                    "username": row.username,
                    "points": row.period_points,
                }
            )
            rank += 1

        return rankings

    @staticmethod
    async def get_achievement_leaderboard(
        db: AsyncSession,
        category: str = "count",  # count, rare
        limit: int = 10,
    ) -> Dict[str, Any]:
        """获取成就排行榜"""
        logger.info("获取成就排行榜 - 类别: %s, 限制: %s", category, limit)

        try:
            # 获取所有用户的成就数据
            result = await db.execute(
                select(User.id, User.username, UserProfile.achievements)
                .join(UserProfile, User.id == UserProfile.user_id)
                .where(UserProfile.achievements != None)
            )

            user_achievements = []
            for row in result:
                import json

                achievements = row.achievements
                if isinstance(achievements, str):
                    achievements = json.loads(achievements)

                if not achievements:
                    continue

                achievement_count = len(achievements)

                # 计算稀有成就数量
                rare_count = 0
                epic_count = 0
                legendary_count = 0

                for ach_id in achievements:
                    if ach_id in ACHIEVEMENTS:
                        rarity = ACHIEVEMENTS[ach_id].rarity
                        if rarity == "rare":
                            rare_count += 1
                        elif rarity == "epic":
                            epic_count += 1
                        elif rarity == "legendary":
                            legendary_count += 1

                # 计算成就积分
                total_achievement_points = sum(
                    ACHIEVEMENTS[ach_id].points
                    for ach_id in achievements
                    if ach_id in ACHIEVEMENTS
                )

                user_achievements.append(
                    {
                        "user_id": row.id,
                        "username": row.username,
                        "achievement_count": achievement_count,
                        "rare_count": rare_count,
                        "epic_count": epic_count,
                        "legendary_count": legendary_count,
                        "total_points": total_achievement_points,
                        "score": achievement_count
                        + rare_count * 2
                        + epic_count * 5
                        + legendary_count * 10,
                    }
                )

            # 根据类别排序
            if category == "count":
                user_achievements.sort(
                    key=lambda x: x["achievement_count"], reverse=True
                )
            elif category == "rare":
                user_achievements.sort(key=lambda x: x["score"], reverse=True)

            # 生成排名
            rankings = []
            for i, user in enumerate(user_achievements[:limit]):
                rankings.append(
                    {
                        "rank": i + 1,
                        "user_id": user["user_id"],
                        "username": user["username"],
                        "achievement_count": user["achievement_count"],
                        "rare_count": user["rare_count"],
                        "epic_count": user["epic_count"],
                        "legendary_count": user["legendary_count"],
                        "total_points": user["total_points"],
                    }
                )

            return {
                "success": True,
                "data": {
                    "category": category,
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.exception("获取成就排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}

    @staticmethod
    async def get_streak_leaderboard(
        db: AsyncSession, limit: int = 10
    ) -> Dict[str, Any]:
        """获取连续打卡排行榜"""
        logger.info("获取连续打卡排行榜 - 限制: %s", limit)

        try:
            # 获取所有用户的连续打卡数据
            result = await db.execute(
                select(User.id, User.username)
                .join(UserProfile, User.id == UserProfile.user_id)
                .limit(100)  # 限制查询数量
            )

            user_streaks = []
            for row in result:
                # 计算连续打卡天数
                streak = await DailyCheckinService._calculate_streak(row.id, db)

                if streak > 0:
                    user_streaks.append(
                        {
                            "user_id": row.id,
                            "username": row.username,
                            "streak_days": streak,
                        }
                    )

            # 按连续天数排序
            user_streaks.sort(key=lambda x: x["streak_days"], reverse=True)

            # 生成排名
            rankings = []
            for i, user in enumerate(user_streaks[:limit]):
                rankings.append(
                    {
                        "rank": i + 1,
                        "user_id": user["user_id"],
                        "username": user["username"],
                        "streak_days": user["streak_days"],
                    }
                )

            return {
                "success": True,
                "data": {
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            logger.exception("获取连续打卡排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}

    @staticmethod
    async def get_user_rank(
        user_id: int, db: AsyncSession, leaderboard_type: str = "points"
    ) -> Dict[str, Any]:
        """获取用户排名"""
        logger.info("获取用户排名 - 用户ID: %s, 类型: %s", user_id, leaderboard_type)

        try:
            if leaderboard_type == "points":
                # 获取总积分排名
                result = await db.execute(
                    select(UserProfile.total_points_earned).where(
                        UserProfile.user_id == user_id
                    )
                )
                user_points = result.scalar() or 0

                # 计算排名
                rank_result = await db.execute(
                    select(func.count())
                    .select_from(UserProfile)
                    .where(UserProfile.total_points_earned > user_points)
                )
                rank = rank_result.scalar() + 1

                # 获取总人数
                total_result = await db.execute(
                    select(func.count())
                    .select_from(UserProfile)
                    .where(UserProfile.total_points_earned > 0)
                )
                total_users = total_result.scalar()

                return {
                    "success": True,
                    "data": {
                        "user_id": user_id,
                        "rank": rank,
                        "total_users": total_users,
                        "score": user_points,
                        "percentile": round((1 - rank / total_users) * 100, 1)
                        if total_users > 0
                        else 0,
                    },
                }

            elif leaderboard_type == "achievements":
                # 获取成就数量排名
                result = await db.execute(
                    select(UserProfile.achievements).where(
                        UserProfile.user_id == user_id
                    )
                )
                achievements = result.scalar()

                import json

                if isinstance(achievements, str):
                    achievements = json.loads(achievements)

                achievement_count = len(achievements) if achievements else 0

                # 获取所有用户的成就数量并排序
                all_result = await db.execute(
                    select(UserProfile.user_id, UserProfile.achievements).where(
                        UserProfile.achievements != None
                    )
                )

                all_counts = []
                for row in all_result:
                    ach = row.achievements
                    if isinstance(ach, str):
                        ach = json.loads(ach)
                    all_counts.append(len(ach) if ach else 0)

                # 计算排名
                rank = sum(1 for count in all_counts if count > achievement_count) + 1
                total_users = len(all_counts)

                return {
                    "success": True,
                    "data": {
                        "user_id": user_id,
                        "rank": rank,
                        "total_users": total_users,
                        "score": achievement_count,
                        "percentile": round((1 - rank / total_users) * 100, 1)
                        if total_users > 0
                        else 0,
                    },
                }

            else:
                return {"success": False, "error": "无效的排行榜类型"}

        except Exception as e:
            logger.exception("获取用户排名失败: %s", e)
            return {"success": False, "error": "获取排名失败"}
