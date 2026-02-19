"""
数据仪表盘服务
提供用户关键指标的集中展示
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json

from models.database import (
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    HabitCompletion,
)
from config.logging_config import get_module_logger
from services.achievement_service import AchievementService, PointsService
from services.challenge_service import ChallengeService
from services.chart_service import ChartService

logger = get_module_logger(__name__)


class DashboardService:
    """仪表盘服务"""

    @staticmethod
    async def get_user_dashboard(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取用户仪表盘数据"""
        try:
            # 获取基础数据
            achievements = await AchievementService.get_user_achievements(user_id, db)
            points = await PointsService.get_user_points(user_id, db)
            challenges = await ChallengeService.get_user_challenges(user_id, db)

            # 获取健康数据统计
            health_stats = await DashboardService._get_health_stats(user_id, db)

            # 获取趋势数据
            trends = await DashboardService._get_trend_data(user_id, db)

            # 获取图表数据
            charts = await ChartService.get_all_charts(user_id, db)

            # 获取今日状态
            today_status = await DashboardService._get_today_status(user_id, db)

            # 组合所有数据
            dashboard_data = {
                "success": True,
                "data": {
                    "overview": {
                        "date": datetime.utcnow().isoformat(),
                        "greeting": DashboardService._get_greeting(),
                    },
                    "achievements": achievements.get("data", {})
                    if achievements.get("success")
                    else {},
                    "points": points.get("data", {}) if points.get("success") else {},
                    "challenges": challenges.get("data", {})
                    if challenges.get("success")
                    else {},
                    "health_stats": health_stats,
                    "trends": trends,
                    "today_status": today_status,
                    "quick_stats": await DashboardService._get_quick_stats(
                        achievements, points, challenges, health_stats
                    ),
                    "charts": charts.get("data", {}) if charts.get("success") else {},
                },
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"获取用户仪表盘失败: {e}")
            return {
                "success": False,
                "error": "获取仪表盘数据失败",
                "data": {
                    "overview": {
                        "date": datetime.utcnow().isoformat(),
                        "greeting": "欢迎回来",
                    },
                    "achievements": {},
                    "points": {},
                    "challenges": {},
                    "health_stats": {},
                    "trends": {},
                    "today_status": {},
                    "quick_stats": {},
                },
            }

    @staticmethod
    async def _get_health_stats(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取健康数据统计"""
        try:
            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # 体重统计
            weight_stats = await DashboardService._get_weight_stats(
                user_id, db, today, week_ago
            )

            # 饮食统计
            nutrition_stats = await DashboardService._get_nutrition_stats(
                user_id, db, today, week_ago
            )

            # 运动统计
            exercise_stats = await DashboardService._get_exercise_stats(
                user_id, db, today, week_ago
            )

            # 饮水统计
            water_stats = await DashboardService._get_water_stats(user_id, db, today)

            # 睡眠统计
            sleep_stats = await DashboardService._get_sleep_stats(
                user_id, db, today, week_ago
            )

            # 习惯统计
            habit_stats = await DashboardService._get_habit_stats(
                user_id, db, today, week_ago
            )

            return {
                "weight": weight_stats,
                "nutrition": nutrition_stats,
                "exercise": exercise_stats,
                "water": water_stats,
                "sleep": sleep_stats,
                "habits": habit_stats,
            }

        except Exception as e:
            logger.error(f"获取健康数据统计失败: {e}")
            return {}

    @staticmethod
    async def _get_weight_stats(
        user_id: int, db: AsyncSession, today: date, week_ago: date
    ) -> Dict[str, Any]:
        """获取体重统计"""
        try:
            # 获取最新体重
            result = await db.execute(
                select(WeightRecord.weight, WeightRecord.record_date)
                .where(WeightRecord.user_id == user_id)
                .order_by(WeightRecord.record_date.desc())
                .limit(1)
            )
            latest_weight = result.first()

            # 获取一周前体重
            result = await db.execute(
                select(WeightRecord.weight)
                .where(
                    and_(
                        WeightRecord.user_id == user_id,
                        WeightRecord.record_date >= week_ago,
                        WeightRecord.record_date <= today - timedelta(days=6),
                    )
                )
                .order_by(WeightRecord.record_date.asc())
                .limit(1)
            )
            week_ago_weight = result.scalar()

            # 计算变化
            current_weight = latest_weight[0] if latest_weight else None
            weight_change = None
            if current_weight and week_ago_weight:
                weight_change = current_weight - week_ago_weight

            return {
                "current": current_weight,
                "latest_date": latest_weight[1].isoformat() if latest_weight else None,
                "week_change": weight_change,
                "trend": "down"
                if weight_change and weight_change < 0
                else "up"
                if weight_change and weight_change > 0
                else "stable",
            }
        except Exception as e:
            logger.error(f"获取体重统计失败: {e}")
            return {"current": None, "week_change": None, "trend": "unknown"}

    @staticmethod
    async def _get_nutrition_stats(
        user_id: int, db: AsyncSession, today: date, week_ago: date
    ) -> Dict[str, Any]:
        """获取饮食统计"""
        try:
            # 获取今日热量
            result = await db.execute(
                select(func.sum(MealRecord.total_calories)).where(
                    and_(
                        MealRecord.user_id == user_id,
                        func.date(MealRecord.record_time) == today,
                    )
                )
            )
            today_calories = result.scalar() or 0

            # 获取本周平均热量
            result = await db.execute(
                select(func.avg(MealRecord.total_calories)).where(
                    and_(
                        MealRecord.user_id == user_id,
                        MealRecord.record_time >= week_ago,
                    )
                )
            )
            weekly_avg_calories = result.scalar() or 0

            return {
                "today_calories": today_calories,
                "weekly_avg_calories": round(weekly_avg_calories, 1),
                "meals_today": await DashboardService._count_records_today(
                    MealRecord, user_id, db
                ),
                "meals_this_week": await DashboardService._count_records_this_week(
                    MealRecord, user_id, db, week_ago
                ),
            }
        except Exception as e:
            logger.error(f"获取饮食统计失败: {e}")
            return {
                "today_calories": 0,
                "weekly_avg_calories": 0,
                "meals_today": 0,
                "meals_this_week": 0,
            }

    @staticmethod
    async def _get_exercise_stats(
        user_id: int, db: AsyncSession, today: date, week_ago: date
    ) -> Dict[str, Any]:
        """获取运动统计"""
        try:
            # 获取今日运动
            result = await db.execute(
                select(
                    func.sum(ExerciseRecord.duration_minutes),
                    func.sum(ExerciseRecord.calories_burned),
                ).where(
                    and_(
                        ExerciseRecord.user_id == user_id,
                        func.date(ExerciseRecord.record_time) == today,
                    )
                )
            )
            today_exercise = result.first()
            today_duration = today_exercise[0] or 0 if today_exercise else 0
            today_calories_burned = today_exercise[1] or 0 if today_exercise else 0

            # 获取本周运动天数
            result = await db.execute(
                select(
                    func.count(func.distinct(func.date(ExerciseRecord.record_time)))
                ).where(
                    and_(
                        ExerciseRecord.user_id == user_id,
                        ExerciseRecord.record_time >= week_ago,
                    )
                )
            )
            exercise_days_this_week = result.scalar() or 0

            return {
                "today_duration": today_duration,
                "today_calories_burned": today_calories_burned,
                "exercise_days_this_week": exercise_days_this_week,
                "exercises_this_week": await DashboardService._count_records_this_week(
                    ExerciseRecord, user_id, db, week_ago
                ),
            }
        except Exception as e:
            logger.error(f"获取运动统计失败: {e}")
            return {
                "today_duration": 0,
                "today_calories_burned": 0,
                "exercise_days_this_week": 0,
                "exercises_this_week": 0,
            }

    @staticmethod
    async def _get_water_stats(
        user_id: int, db: AsyncSession, today: date
    ) -> Dict[str, Any]:
        """获取饮水统计"""
        try:
            # 获取今日饮水量
            result = await db.execute(
                select(func.sum(WaterRecord.amount_ml)).where(
                    and_(
                        WaterRecord.user_id == user_id,
                        func.date(WaterRecord.record_time) == today,
                    )
                )
            )
            today_water = result.scalar() or 0

            # 目标饮水量（默认2000ml）
            target_water = 2000

            return {
                "today_water": today_water,
                "target_water": target_water,
                "progress": min(100, (today_water / target_water) * 100)
                if target_water > 0
                else 0,
                "records_today": await DashboardService._count_records_today(
                    WaterRecord, user_id, db
                ),
            }
        except Exception as e:
            logger.error(f"获取饮水统计失败: {e}")
            return {
                "today_water": 0,
                "target_water": 2000,
                "progress": 0,
                "records_today": 0,
            }

    @staticmethod
    async def _get_sleep_stats(
        user_id: int, db: AsyncSession, today: date, week_ago: date
    ) -> Dict[str, Any]:
        """获取睡眠统计"""
        try:
            # 获取昨晚睡眠
            yesterday = today - timedelta(days=1)
            result = await db.execute(
                select(SleepRecord.total_minutes, SleepRecord.quality)
                .where(
                    and_(
                        SleepRecord.user_id == user_id,
                        func.date(SleepRecord.bed_time) == yesterday,
                    )
                )
                .order_by(SleepRecord.bed_time.desc())
                .limit(1)
            )
            last_night_sleep = result.first()

            last_night_duration = last_night_sleep[0] if last_night_sleep else None
            last_night_quality = last_night_sleep[1] if last_night_sleep else None

            # 获取本周平均睡眠
            result = await db.execute(
                select(func.avg(SleepRecord.total_minutes)).where(
                    and_(
                        SleepRecord.user_id == user_id, SleepRecord.bed_time >= week_ago
                    )
                )
            )
            weekly_avg_sleep = result.scalar()

            return {
                "last_night_duration": last_night_duration,
                "last_night_quality": last_night_quality,
                "weekly_avg_sleep": round(weekly_avg_sleep, 1)
                if weekly_avg_sleep
                else None,
                "sleep_records_this_week": await DashboardService._count_records_this_week(
                    SleepRecord, user_id, db, week_ago
                ),
            }
        except Exception as e:
            logger.error(f"获取睡眠统计失败: {e}")
            return {
                "last_night_duration": None,
                "last_night_quality": None,
                "weekly_avg_sleep": None,
                "sleep_records_this_week": 0,
            }

    @staticmethod
    async def _get_habit_stats(
        user_id: int, db: AsyncSession, today: date, week_ago: date
    ) -> Dict[str, Any]:
        """获取习惯统计"""
        try:
            # 获取今日习惯完成情况
            result = await db.execute(
                select(func.count(HabitCompletion.id)).where(
                    and_(
                        HabitCompletion.user_id == user_id,
                        HabitCompletion.completion_date == today,
                    )
                )
            )
            habits_today = result.scalar() or 0

            # 获取本周习惯完成率
            result = await db.execute(
                select(func.count(HabitCompletion.id)).where(
                    and_(
                        HabitCompletion.user_id == user_id,
                        HabitCompletion.completion_date >= week_ago,
                    )
                )
            )
            habits_this_week = result.scalar() or 0

            # 假设每天有3个习惯目标
            daily_habit_target = 3
            weekly_habit_target = daily_habit_target * 7

            return {
                "habits_today": habits_today,
                "daily_target": daily_habit_target,
                "today_completion_rate": min(
                    100, (habits_today / daily_habit_target) * 100
                )
                if daily_habit_target > 0
                else 0,
                "habits_this_week": habits_this_week,
                "weekly_target": weekly_habit_target,
                "weekly_completion_rate": min(
                    100, (habits_this_week / weekly_habit_target) * 100
                )
                if weekly_habit_target > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"获取习惯统计失败: {e}")
            return {
                "habits_today": 0,
                "daily_target": 3,
                "today_completion_rate": 0,
                "habits_this_week": 0,
                "weekly_target": 21,
                "weekly_completion_rate": 0,
            }

    @staticmethod
    async def _count_records_today(model, user_id: int, db: AsyncSession) -> int:
        """统计今日记录数"""
        try:
            today = date.today()
            result = await db.execute(
                select(func.count(model.id)).where(
                    and_(
                        model.user_id == user_id, func.date(model.record_time) == today
                    )
                )
            )
            return result.scalar() or 0
        except Exception:
            return 0

    @staticmethod
    async def _count_records_this_week(
        model, user_id: int, db: AsyncSession, week_ago: date
    ) -> int:
        """统计本周记录数"""
        try:
            result = await db.execute(
                select(func.count(model.id)).where(
                    and_(model.user_id == user_id, model.record_time >= week_ago)
                )
            )
            return result.scalar() or 0
        except Exception:
            return 0

    @staticmethod
    async def _get_trend_data(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取趋势数据"""
        try:
            # 简化版本，返回基本趋势信息
            return {
                "weight_trend": "需要更多数据",
                "exercise_trend": "需要更多数据",
                "nutrition_trend": "需要更多数据",
                "consistency_trend": "需要更多数据",
            }
        except Exception as e:
            logger.error(f"获取趋势数据失败: {e}")
            return {}

    @staticmethod
    async def _get_today_status(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取今日状态"""
        try:
            today = date.today()

            # 检查各项记录
            has_weight = await DashboardService._has_record_today(
                WeightRecord, user_id, db, today
            )
            has_meal = await DashboardService._has_record_today(
                MealRecord, user_id, db, today
            )
            has_exercise = await DashboardService._has_record_today(
                ExerciseRecord, user_id, db, today
            )
            has_water = await DashboardService._has_record_today(
                WaterRecord, user_id, db, today
            )

            # 计算完成度
            total_checks = 4
            completed_checks = sum([has_weight, has_meal, has_exercise, has_water])
            completion_rate = (
                (completed_checks / total_checks) * 100 if total_checks > 0 else 0
            )

            return {
                "has_weight": has_weight,
                "has_meal": has_meal,
                "has_exercise": has_exercise,
                "has_water": has_water,
                "completion_rate": completion_rate,
                "status": "excellent"
                if completion_rate >= 75
                else "good"
                if completion_rate >= 50
                else "fair"
                if completion_rate >= 25
                else "poor",
                "message": DashboardService._get_today_status_message(completion_rate),
            }
        except Exception as e:
            logger.error(f"获取今日状态失败: {e}")
            return {
                "completion_rate": 0,
                "status": "unknown",
                "message": "数据获取失败",
            }

    @staticmethod
    async def _has_record_today(
        model, user_id: int, db: AsyncSession, today: date
    ) -> bool:
        """检查今日是否有记录"""
        try:
            result = await db.execute(
                select(func.count(model.id)).where(
                    and_(
                        model.user_id == user_id, func.date(model.record_time) == today
                    )
                )
            )
            count = result.scalar() or 0
            return count > 0
        except Exception:
            return False

    @staticmethod
    def _get_today_status_message(completion_rate: float) -> str:
        """获取今日状态消息"""
        if completion_rate >= 90:
            return "🎉 完美的一天！继续保持！"
        elif completion_rate >= 70:
            return "👍 今天做得很好！"
        elif completion_rate >= 50:
            return "💪 继续努力，你可以做得更好！"
        elif completion_rate >= 30:
            return "📝 今天还有进步空间"
        else:
            return "🚀 新的一天，新的开始！"

    @staticmethod
    def _get_greeting() -> str:
        """获取问候语"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "早上好！"
        elif 12 <= hour < 14:
            return "中午好！"
        elif 14 <= hour < 18:
            return "下午好！"
        elif 18 <= hour < 22:
            return "晚上好！"
        else:
            return "夜深了，注意休息！"

    @staticmethod
    async def _get_quick_stats(
        achievements: Dict[str, Any],
        points: Dict[str, Any],
        challenges: Dict[str, Any],
        health_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """获取快速统计"""
        try:
            achievement_data = (
                achievements.get("data", {}) if achievements.get("success") else {}
            )
            points_data = points.get("data", {}) if points.get("success") else {}
            challenge_data = (
                challenges.get("data", {}) if challenges.get("success") else {}
            )

            return {
                "unlocked_achievements": achievement_data.get("unlocked_count", 0),
                "total_achievements": achievement_data.get("total_count", 0),
                "current_points": points_data.get("current_points", 0),
                "active_challenges": challenge_data.get("active_count", 0),
                "completed_challenges": challenge_data.get("completed_count", 0),
                "weight_current": health_stats.get("weight", {}).get("current"),
                "water_progress": health_stats.get("water", {}).get("progress", 0),
                "exercise_today": health_stats.get("exercise", {}).get(
                    "today_duration", 0
                ),
            }
        except Exception as e:
            logger.error(f"获取快速统计失败: {e}")
            return {}
