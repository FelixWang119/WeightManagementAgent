"""
业务集成服务
处理成就检查和积分发放的自动化集成
"""

from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from models.database import (
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    Goal,
)
from models.points_history import PointsHistory, PointsType
from services.achievement_service import AchievementService, PointsService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class AchievementIntegrationService:
    """成就集成服务"""

    @staticmethod
    async def process_weight_record(
        user_id: int, record_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理体重记录后的成就检查和积分发放"""
        logger.info("处理体重记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)

        results = {"points_earned": 0, "achievements_unlocked": [], "messages": []}

        try:
            # 1. 发放体重记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录体重",
                amount=10,
                db=db,
                description="成功记录体重数据",
                related_record_id=record_id,
                related_record_type="weight_record",
            )

            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(
                    f"获得 {points_result['data']['points_earned']} 积分"
                )

            # 2. 检查是否是首次记录
            total_records = (
                await AchievementIntegrationService._get_total_weight_records(
                    user_id, db
                )
            )
            if total_records == 1:
                # 首次记录成就
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)

                # 首次记录积分奖励
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="weight_record",
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"][
                        "points_earned"
                    ]

            # 3. 检查累计记录数成就
            total_all_records = (
                await AchievementIntegrationService._get_total_all_records(user_id, db)
            )
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            # 4. 检查体重目标成就
            await AchievementIntegrationService._check_weight_goal_achievement(
                user_id, db, results
            )

        except Exception as e:
            logger.exception("处理体重记录成就时出错: %s", e)

        return results

    @staticmethod
    async def process_meal_record(
        user_id: int, record_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理餐食记录后的成就检查和积分发放"""
        logger.info("处理餐食记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)

        results = {"points_earned": 0, "achievements_unlocked": [], "messages": []}

        try:
            # 1. 发放餐食记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录饮食",
                amount=5,
                db=db,
                description="成功记录餐食数据",
                related_record_id=record_id,
                related_record_type="meal_record",
            )

            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(
                    f"获得 {points_result['data']['points_earned']} 积分"
                )

            # 2. 检查是否是首次记录
            total_meals = await AchievementIntegrationService._get_total_meal_records(
                user_id, db
            )
            if total_meals == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)

                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="meal_record",
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"][
                        "points_earned"
                    ]

            # 3. 检查餐食累计成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_meals", total_meals, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            # 4. 检查累计记录数成就
            total_all_records = (
                await AchievementIntegrationService._get_total_all_records(user_id, db)
            )
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            # 5. 检查热量控制成就
            await AchievementIntegrationService._check_calorie_streak(
                user_id, db, results
            )

        except Exception as e:
            logger.exception("处理餐食记录成就时出错: %s", e)

        return results

    @staticmethod
    async def process_exercise_record(
        user_id: int, record_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理运动记录后的成就检查和积分发放"""
        logger.info("处理运动记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)

        results = {"points_earned": 0, "achievements_unlocked": [], "messages": []}

        try:
            # 1. 发放运动记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录运动",
                amount=10,
                db=db,
                description="成功记录运动数据",
                related_record_id=record_id,
                related_record_type="exercise_record",
            )

            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(
                    f"获得 {points_result['data']['points_earned']} 积分"
                )

            # 2. 检查是否是首次记录
            total_exercises = (
                await AchievementIntegrationService._get_total_exercise_records(
                    user_id, db
                )
            )
            if total_exercises == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)

                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="exercise_record",
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"][
                        "points_earned"
                    ]

            # 3. 检查运动累计成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_exercises", total_exercises, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            # 4. 检查累计记录数成就
            total_all_records = (
                await AchievementIntegrationService._get_total_all_records(user_id, db)
            )
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)

        except Exception as e:
            logger.exception("处理运动记录成就时出错: %s", e)

        return results

    @staticmethod
    async def process_water_record(
        user_id: int, record_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理饮水记录后的成就检查和积分发放"""
        logger.info("处理饮水记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)

        results = {"points_earned": 0, "achievements_unlocked": [], "messages": []}

        try:
            # 1. 发放饮水记录积分（如果当天饮水达标）
            is_target_met = await AchievementIntegrationService._is_water_target_met(
                user_id, db
            )

            if is_target_met:
                # 检查今天是否已经发放过积分
                today = date.today()
                has_earned_today = (
                    await AchievementIntegrationService._has_earned_points_today(
                        user_id, "饮水达标", db
                    )
                )

                if not has_earned_today:
                    points_result = await PointsService.earn_points(
                        user_id=user_id,
                        reason="饮水达标",
                        amount=5,
                        db=db,
                        description="今日饮水达到目标",
                        related_record_id=record_id,
                        related_record_type="water_record",
                    )

                    if points_result["success"]:
                        results["points_earned"] += points_result["data"][
                            "points_earned"
                        ]
                        results["messages"].append(
                            f"获得 {points_result['data']['points_earned']} 积分"
                        )

            # 2. 检查是否是首次记录
            total_water = await AchievementIntegrationService._get_total_water_records(
                user_id, db
            )
            if total_water == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)

                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="water_record",
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"][
                        "points_earned"
                    ]

            # 3. 检查饮水连续达标成就
            await AchievementIntegrationService._check_water_streak(
                user_id, db, results
            )

            # 4. 检查累计记录数成就
            total_all_records = (
                await AchievementIntegrationService._get_total_all_records(user_id, db)
            )
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)

        except Exception as e:
            logger.exception("处理饮水记录成就时出错: %s", e)

        return results

    @staticmethod
    async def process_sleep_record(
        user_id: int, record_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """处理睡眠记录后的成就检查和积分发放"""
        logger.info("处理睡眠记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)

        results = {"points_earned": 0, "achievements_unlocked": [], "messages": []}

        try:
            # 1. 发放睡眠记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录睡眠",
                amount=5,
                db=db,
                description="成功记录睡眠数据",
                related_record_id=record_id,
                related_record_type="sleep_record",
            )

            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(
                    f"获得 {points_result['data']['points_earned']} 积分"
                )

            # 2. 检查是否是首次记录
            total_sleep = await AchievementIntegrationService._get_total_sleep_records(
                user_id, db
            )
            if total_sleep == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)

                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="sleep_record",
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"][
                        "points_earned"
                    ]

            # 3. 检查睡眠连续达标成就
            await AchievementIntegrationService._check_sleep_streak(
                user_id, db, results
            )

            # 4. 检查累计记录数成就
            total_all_records = (
                await AchievementIntegrationService._get_total_all_records(user_id, db)
            )
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)

        except Exception as e:
            logger.exception("处理睡眠记录成就时出错: %s", e)

        return results

    # ============ 辅助方法 ============

    @staticmethod
    async def _get_total_weight_records(user_id: int, db: AsyncSession) -> int:
        """获取用户体重记录总数"""
        result = await db.execute(
            select(func.count()).where(WeightRecord.user_id == user_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_total_meal_records(user_id: int, db: AsyncSession) -> int:
        """获取用户餐食记录总数"""
        result = await db.execute(
            select(func.count()).where(MealRecord.user_id == user_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_total_exercise_records(user_id: int, db: AsyncSession) -> int:
        """获取用户运动记录总数"""
        result = await db.execute(
            select(func.count()).where(ExerciseRecord.user_id == user_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_total_water_records(user_id: int, db: AsyncSession) -> int:
        """获取用户饮水记录总数"""
        result = await db.execute(
            select(func.count()).where(WaterRecord.user_id == user_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_total_sleep_records(user_id: int, db: AsyncSession) -> int:
        """获取用户睡眠记录总数"""
        result = await db.execute(
            select(func.count()).where(SleepRecord.user_id == user_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_total_all_records(user_id: int, db: AsyncSession) -> int:
        """获取用户所有健康记录总数"""
        total = 0
        total += await AchievementIntegrationService._get_total_weight_records(
            user_id, db
        )
        total += await AchievementIntegrationService._get_total_meal_records(
            user_id, db
        )
        total += await AchievementIntegrationService._get_total_exercise_records(
            user_id, db
        )
        total += await AchievementIntegrationService._get_total_water_records(
            user_id, db
        )
        total += await AchievementIntegrationService._get_total_sleep_records(
            user_id, db
        )
        return total

    @staticmethod
    async def _is_water_target_met(user_id: int, db: AsyncSession) -> bool:
        """检查用户今日是否饮水达标（简化判断，默认1500ml）"""
        today = date.today()
        result = await db.execute(
            select(func.sum(WaterRecord.amount)).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == today,
                )
            )
        )
        total_amount = result.scalar() or 0
        # 默认目标 1500ml
        return total_amount >= 1500

    @staticmethod
    async def _check_weight_goal_achievement(
        user_id: int, db: AsyncSession, results: Dict
    ):
        """检查体重目标达成成就"""
        # 获取当前体重
        weight_result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()

        if not latest_weight:
            return

        # 获取活跃目标
        goal_result = await db.execute(
            select(Goal).where(and_(Goal.user_id == user_id, Goal.status == "active"))
        )
        active_goal = goal_result.scalar_one_or_none()

        if not active_goal or not active_goal.target_weight:
            return

        # 检查是否达成目标
        if latest_weight.weight <= active_goal.target_weight:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "goal_achieved", True, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            if new_achievements:
                # 目标达成额外积分
                goal_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="达成体重目标",
                    amount=300,
                    db=db,
                    description=f"达成目标体重 {active_goal.target_weight}kg",
                )
                if goal_points["success"]:
                    results["points_earned"] += goal_points["data"]["points_earned"]

    @staticmethod
    async def _check_calorie_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查热量连续达标成就"""
        # 获取最近7天的餐食记录
        end_date = date.today()

        # 简化实现：假设每日热量目标为1800kcal
        streak_days = 0

        for i in range(7):
            check_date = end_date - timedelta(days=i)
            # 查询当天总热量
            result = await db.execute(
                select(func.sum(MealRecord.calories)).where(
                    and_(
                        MealRecord.user_id == user_id,
                        func.date(MealRecord.record_time) == check_date,
                    )
                )
            )
            total_calories = result.scalar() or 0

            # 假设在合理范围内（1500-2100）算达标
            if 1500 <= total_calories <= 2100:
                streak_days += 1
            else:
                break

        if streak_days >= 7:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "calorie_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)

    @staticmethod
    async def _check_water_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查饮水连续达标成就"""
        end_date = date.today()
        streak_days = 0

        for i in range(30):  # 最多检查30天
            check_date = end_date - timedelta(days=i)
            result = await db.execute(
                select(func.sum(WaterRecord.amount)).where(
                    and_(
                        WaterRecord.user_id == user_id,
                        func.date(WaterRecord.record_time) == check_date,
                    )
                )
            )
            total_amount = result.scalar() or 0

            if total_amount >= 1500:  # 1500ml达标
                streak_days += 1
            else:
                break

        if streak_days >= 30:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "water_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)

    @staticmethod
    async def _check_sleep_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查睡眠连续达标成就"""
        end_date = date.today()
        streak_days = 0

        for i in range(14):  # 最多检查14天
            check_date = end_date - timedelta(days=i)
            result = await db.execute(
                select(SleepRecord).where(
                    and_(
                        SleepRecord.user_id == user_id,
                        func.date(SleepRecord.sleep_date) == check_date,
                    )
                )
            )
            sleep_record = result.scalar_one_or_none()

            if sleep_record and sleep_record.duration:
                # 睡眠时长在7-9小时算达标
                hours = sleep_record.duration.total_seconds() / 3600
                if 7 <= hours <= 9:
                    streak_days += 1
                else:
                    break
            else:
                break

        if streak_days >= 14:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "sleep_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)

    @staticmethod
    async def _has_earned_points_today(
        user_id: int, reason: str, db: AsyncSession
    ) -> bool:
        """检查今天是否已经获得过某类积分"""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        result = await db.execute(
            select(PointsHistory).where(
                and_(
                    PointsHistory.user_id == user_id,
                    PointsHistory.reason == reason,
                    PointsHistory.points_type == PointsType.EARN,
                    PointsHistory.created_at >= today,
                    PointsHistory.created_at < tomorrow,
                )
            )
        )
        return result.scalar_one_or_none() is not None


class DailyCheckinService:
    """每日打卡服务"""

    @staticmethod
    async def process_daily_checkin(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理每日打卡"""
        logger.info("处理每日打卡 - 用户ID: %s", user_id)

        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "streak": 0,
            "messages": [],
        }

        try:
            # 1. 发放每日登录积分
            today = date.today()
            has_earned_login = (
                await AchievementIntegrationService._has_earned_points_today(
                    user_id, "每日登录", db
                )
            )

            if not has_earned_login:
                points_result = await PointsService.earn_points(
                    user_id=user_id,
                    reason="每日登录",
                    amount=5,
                    db=db,
                    description="每日首次登录奖励",
                )

                if points_result["success"]:
                    results["points_earned"] += points_result["data"]["points_earned"]
                    results["messages"].append(
                        f"获得 {points_result['data']['points_earned']} 积分"
                    )

            # 2. 计算连续打卡天数
            streak = await DailyCheckinService._calculate_streak(user_id, db)
            results["streak"] = streak

            # 3. 检查连续打卡成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "streak", streak, db
            )
            results["achievements_unlocked"].extend(new_achievements)

            # 4. 连续打卡额外积分
            if streak in [7, 30, 100]:
                streak_bonus = {7: 50, 30: 200, 100: 500}
                bonus_points = streak_bonus.get(streak, 0)

                # 检查今天是否已经发放过连续打卡奖励
                has_earned_streak = (
                    await AchievementIntegrationService._has_earned_points_today(
                        user_id, f"连续打卡{streak}天", db
                    )
                )

                if not has_earned_streak:
                    streak_points = await PointsService.earn_points(
                        user_id=user_id,
                        reason=f"连续打卡{streak}天",
                        amount=bonus_points,
                        db=db,
                        description=f"连续打卡 {streak} 天奖励",
                    )
                    if streak_points["success"]:
                        results["points_earned"] += streak_points["data"][
                            "points_earned"
                        ]
                        results["messages"].append(
                            f"获得连续打卡奖励 {bonus_points} 积分"
                        )

            # 5. 检查完美一周成就
            await DailyCheckinService._check_perfect_week(user_id, db, results)

            # 6. 检查早起鸟儿成就
            await DailyCheckinService._check_early_bird(user_id, db, results)

        except Exception as e:
            logger.exception("处理每日打卡时出错: %s", e)

        return results

    @staticmethod
    async def _calculate_streak(user_id: int, db: AsyncSession) -> int:
        """计算连续打卡天数"""
        today = date.today()
        streak = 0

        for i in range(365):  # 最多检查一年
            check_date = today - timedelta(days=i)

            # 检查当天是否有任何健康记录
            has_record = await DailyCheckinService._has_any_record_on_date(
                user_id, check_date, db
            )

            if has_record:
                streak += 1
            else:
                break

        return streak

    @staticmethod
    async def _has_any_record_on_date(
        user_id: int, check_date: date, db: AsyncSession
    ) -> bool:
        """检查某天是否有任何健康记录"""
        # 检查体重记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WeightRecord.user_id == user_id,
                    func.date(WeightRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            return True

        # 检查餐食记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            return True

        # 检查运动记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.date(ExerciseRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            return True

        # 检查饮水记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            return True

        # 检查睡眠记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.sleep_date) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            return True

        return False

    @staticmethod
    async def _check_perfect_week(user_id: int, db: AsyncSession, results: Dict):
        """检查完美一周成就（7天内每天有至少3种类型的记录）"""
        end_date = date.today()

        # 检查最近7天
        for week_start in range(6, -1, -1):
            week_end = end_date - timedelta(days=week_start)
            week_begin = week_end - timedelta(days=6)

            perfect_days = 0
            for day_offset in range(7):
                check_date = week_begin + timedelta(days=day_offset)

                # 统计当天记录类型数量
                record_types = await DailyCheckinService._count_record_types_on_date(
                    user_id, check_date, db
                )
                if record_types >= 3:  # 至少有3种类型算完美
                    perfect_days += 1

            if perfect_days >= 7:  # 7天都完美
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "perfect_week", True, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                break

    @staticmethod
    async def _count_record_types_on_date(
        user_id: int, check_date: date, db: AsyncSession
    ) -> int:
        """统计某天有多少种类型的健康记录"""
        types = 0

        # 体重
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WeightRecord.user_id == user_id,
                    func.date(WeightRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            types += 1

        # 餐食
        result = await db.execute(
            select(func.count()).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            types += 1

        # 运动
        result = await db.execute(
            select(func.count()).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.date(ExerciseRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            types += 1

        # 饮水
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            types += 1

        # 睡眠
        result = await db.execute(
            select(func.count()).where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.sleep_date) == check_date,
                )
            )
        )
        if result.scalar() > 0:
            types += 1

        return types

    @staticmethod
    async def _check_early_bird(user_id: int, db: AsyncSession, results: Dict):
        """检查早起鸟儿成就（连续7天早上8点前记录）"""
        # 简化实现：检查最近7天是否有早上的记录
        end_date = date.today()
        early_days = 0

        for i in range(7):
            check_date = end_date - timedelta(days=i)

            # 检查当天是否有早上8点前的记录
            result = await db.execute(
                select(func.count()).where(
                    and_(
                        WeightRecord.user_id == user_id,
                        func.date(WeightRecord.record_time) == check_date,
                        func.time(WeightRecord.record_time) < "08:00:00",
                    )
                )
            )
            if result.scalar() > 0:
                early_days += 1
            else:
                break

        if early_days >= 7:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "early_morning_streak", early_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)
