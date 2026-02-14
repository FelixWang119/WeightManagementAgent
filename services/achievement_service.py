"""
成就与积分服务
提供成就徽章、解锁逻辑、积分管理
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from enum import Enum
from dataclasses import dataclass
import json

from models.database import User, UserProfile
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class AchievementCategory(Enum):
    """成就分类"""

    WEIGHT = "weight"  # 体重管理
    DIET = "diet"  # 饮食控制
    EXERCISE = "exercise"  # 运动健身
    CONSISTENCY = "consistency"  # 坚持打卡
    MILESTONE = "milestone"  # 里程碑
    SPECIAL = "special"  # 特殊成就


class AchievementType(Enum):
    """成就类型"""

    FIRST_STEP = "first_step"  # 第一步
    STREAK_7 = "streak_7"  # 连续7天
    STREAK_30 = "streak_30"  # 连续30天
    STREAK_100 = "streak_100"  # 连续100天
    WEIGHT_GOAL = "weight_goal"  # 达成目标
    PERFECT_WEEK = "perfect_week"  # 完美一周
    EARLY_BIRD = "early_bird"  # 早起鸟儿
    NIGHT_OWL = "night_owl"  # 夜猫子
    WATER_MASTER = "water_master"  # 饮水大师
    EXERCISE_MASTER = "exercise_master"  # 运动大师
    DIET_MASTER = "diet_master"  # 饮食大师
    SOCIAL_SHARE = "social_share"  # 分享达人
    FIRST_MEAL = "first_meal"  # 首次记录
    FIRST_WEIGHT = "first_weight"  # 首次称重
    TOTAL_100 = "total_100"  # 累计100次
    TOTAL_500 = "total_500"  # 累计500次
    TOTAL_1000 = "total_1000"  # 累计1000次


@dataclass
class Achievement:
    """成就数据类"""

    id: str
    name: str
    description: str
    category: AchievementCategory
    icon: str
    points: int
    rarity: str  # common, rare, epic, legendary
    condition: Dict[str, Any]


ACHIEVEMENTS = {
    AchievementType.FIRST_STEP.value: Achievement(
        id=AchievementType.FIRST_STEP.value,
        name="第一步",
        description="完成首次健康记录",
        category=AchievementCategory.MILESTONE,
        icon="🎯",
        points=10,
        rarity="common",
        condition={"type": "first_record"},
    ),
    AchievementType.STREAK_7.value: Achievement(
        id=AchievementType.STREAK_7.value,
        name="一周坚持",
        description="连续打卡7天",
        category=AchievementCategory.CONSISTENCY,
        icon="🔥",
        points=50,
        rarity="common",
        condition={"type": "streak", "days": 7},
    ),
    AchievementType.STREAK_30.value: Achievement(
        id=AchievementType.STREAK_30.value,
        name="月度之星",
        description="连续打卡30天",
        category=AchievementCategory.CONSISTENCY,
        icon="⭐",
        points=200,
        rarity="rare",
        condition={"type": "streak", "days": 30},
    ),
    AchievementType.STREAK_100.value: Achievement(
        id=AchievementType.STREAK_100.value,
        name="百日英雄",
        description="连续打卡100天",
        category=AchievementCategory.CONSISTENCY,
        icon="🏆",
        points=1000,
        rarity="legendary",
        condition={"type": "streak", "days": 100},
    ),
    AchievementType.WEIGHT_GOAL.value: Achievement(
        id=AchievementType.WEIGHT_GOAL.value,
        name="目标达成",
        description="达成减重目标",
        category=AchievementCategory.WEIGHT,
        icon="🎉",
        points=500,
        rarity="epic",
        condition={"type": "goal_achieved"},
    ),
    AchievementType.PERFECT_WEEK.value: Achievement(
        id=AchievementType.PERFECT_WEEK.value,
        name="完美一周",
        description="一周内完成所有健康记录",
        category=AchievementCategory.CONSISTENCY,
        icon="💯",
        points=100,
        rarity="rare",
        condition={"type": "perfect_week"},
    ),
    AchievementType.EARLY_BIRD.value: Achievement(
        id=AchievementType.EARLY_BIRD.value,
        name="早起鸟儿",
        description="连续一周早上记录",
        category=AchievementCategory.MILESTONE,
        icon="🌅",
        points=80,
        rarity="common",
        condition={"type": "early_morning_streak", "days": 7},
    ),
    AchievementType.WATER_MASTER.value: Achievement(
        id=AchievementType.WATER_MASTER.value,
        name="饮水大师",
        description="连续30天饮水达标",
        category=AchievementCategory.DIET,
        icon="💧",
        points=200,
        rarity="rare",
        condition={"type": "water_streak", "days": 30},
    ),
    AchievementType.EXERCISE_MASTER.value: Achievement(
        id=AchievementType.EXERCISE_MASTER.value,
        name="运动达人",
        description="累计运动50次",
        category=AchievementCategory.EXERCISE,
        icon="🏃",
        points=300,
        rarity="rare",
        condition={"type": "total_exercises", "count": 50},
    ),
    AchievementType.DIET_MASTER.value: Achievement(
        id=AchievementType.DIET_MASTER.value,
        name="饮食管理师",
        description="累计记录100次饮食",
        category=AchievementCategory.DIET,
        icon="🍽️",
        points=300,
        rarity="rare",
        condition={"type": "total_meals", "count": 100},
    ),
    AchievementType.TOTAL_100.value: Achievement(
        id=AchievementType.TOTAL_100.value,
        name="健康记录者",
        description="累计记录100条健康数据",
        category=AchievementCategory.MILESTONE,
        icon="📊",
        points=100,
        rarity="common",
        condition={"type": "total_records", "count": 100},
    ),
    AchievementType.TOTAL_500.value: Achievement(
        id=AchievementType.TOTAL_500.value,
        name="数据达人",
        description="累计记录500条健康数据",
        category=AchievementCategory.MILESTONE,
        icon="📈",
        points=500,
        rarity="rare",
        condition={"type": "total_records", "count": 500},
    ),
    AchievementType.TOTAL_1000.value: Achievement(
        id=AchievementType.TOTAL_1000.value,
        name="健康专家",
        description="累计记录1000条健康数据",
        category=AchievementCategory.MILESTONE,
        icon="👑",
        points=1000,
        rarity="legendary",
        condition={"type": "total_records", "count": 1000},
    ),
}


class AchievementService:
    """成就服务"""

    @staticmethod
    async def get_user_achievements(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取用户成就"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        unlocked = []
        if profile and profile.achievements:
            unlocked = (
                json.loads(profile.achievements)
                if isinstance(profile.achievements, str)
                else profile.achievements
            )

        all_achievements = []
        for ach_id, ach in ACHIEVEMENTS.items():
            all_achievements.append(
                {
                    "id": ach.id,
                    "name": ach.name,
                    "description": ach.description,
                    "category": ach.category.value,
                    "icon": ach.icon,
                    "points": ach.points,
                    "rarity": ach.rarity,
                    "unlocked": ach.id in unlocked,
                    "unlocked_at": None,
                }
            )

        return {
            "success": True,
            "data": {
                "achievements": all_achievements,
                "unlocked_count": len(unlocked),
                "total_count": len(ACHIEVEMENTS),
                "total_points": sum(ACHIEVEMENTS[a].points for a in unlocked),
            },
        }

    @staticmethod
    async def check_and_unlock(
        user_id: int, trigger_type: str, value: Any, db: AsyncSession
    ) -> List[Dict]:
        """检查并解锁成就"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        unlocked = []
        if profile and profile.achievements:
            unlocked = (
                json.loads(profile.achievements)
                if isinstance(profile.achievements, str)
                else profile.achievements
            )

        newly_unlocked = []

        for ach_id, ach in ACHIEVEMENTS.items():
            if ach_id in unlocked:
                continue

            should_unlock = False

            if ach.condition.get("type") == "streak" and trigger_type == "streak":
                if value >= ach.condition.get("days", 7):
                    should_unlock = True

            elif (
                ach.condition.get("type") == "total_records"
                and trigger_type == "total_records"
            ):
                if value >= ach.condition.get("count", 100):
                    should_unlock = True

            elif (
                ach.condition.get("type") == "total_exercises"
                and trigger_type == "total_exercises"
            ):
                if value >= ach.condition.get("count", 50):
                    should_unlock = True

            elif (
                ach.condition.get("type") == "total_meals"
                and trigger_type == "total_meals"
            ):
                if value >= ach.condition.get("count", 100):
                    should_unlock = True

            elif (
                ach.condition.get("type") == "first_record"
                and trigger_type == "first_record"
            ):
                should_unlock = True

            elif (
                ach.condition.get("type") == "goal_achieved"
                and trigger_type == "goal_achieved"
            ):
                should_unlock = True

            elif (
                ach.condition.get("type") == "water_streak"
                and trigger_type == "water_streak"
            ):
                if value >= ach.condition.get("days", 30):
                    should_unlock = True

            if should_unlock:
                unlocked.append(ach_id)
                newly_unlocked.append(
                    {
                        "id": ach.id,
                        "name": ach.name,
                        "icon": ach.icon,
                        "points": ach.points,
                        "rarity": ach.rarity,
                    }
                )

        if newly_unlocked and profile:
            profile.achievements = json.dumps(unlocked)
            await db.commit()

        return newly_unlocked


class PointsService:
    """积分服务"""

    POINTS_RULES = {
        "daily_login": 5,
        "weight_record": 10,
        "meal_record": 5,
        "exercise_record": 10,
        "water达标": 5,
        "sleep_record": 5,
        "streak_7": 50,
        "streak_30": 200,
        "streak_100": 500,
        "achievement": "dynamic",
        "goal_achieved": 300,
    }

    @staticmethod
    async def get_user_points(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取用户积分"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        points = profile.points if profile and profile.points else 0
        total_earned = (
            profile.total_points_earned
            if profile and profile.total_points_earned
            else 0
        )
        total_spent = (
            profile.total_points_spent if profile and profile.total_points_spent else 0
        )

        return {
            "success": True,
            "data": {
                "current_points": points,
                "total_earned": total_earned,
                "total_spent": total_spent,
                "lifetime_points": total_earned,
            },
        }

    @staticmethod
    async def earn_points(
        user_id: int, reason: str, amount: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """获取积分"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(
                user_id=user_id, points=0, total_points_earned=0, total_points_spent=0
            )
            db.add(profile)

        profile.points = (profile.points or 0) + amount
        profile.total_points_earned = (profile.total_points_earned or 0) + amount

        await db.commit()

        return {
            "success": True,
            "message": f"获得 {amount} 积分",
            "data": {
                "reason": reason,
                "points_earned": amount,
                "current_points": profile.points,
            },
        }

    @staticmethod
    async def spend_points(
        user_id: int, reason: str, amount: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """消费积分"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or (profile.points or 0) < amount:
            return {"success": False, "error": "积分不足"}

        profile.points = profile.points - amount
        profile.total_points_spent = (profile.total_points_spent or 0) + amount

        await db.commit()

        return {
            "success": True,
            "message": f"消耗 {amount} 积分",
            "data": {
                "reason": reason,
                "points_spent": amount,
                "current_points": profile.points,
            },
        }

    @staticmethod
    async def get_points_history(
        user_id: int, db: AsyncSession, limit: int = 20
    ) -> Dict[str, Any]:
        """获取积分历史"""
        return {
            "success": True,
            "data": {"history": [], "message": "积分历史功能开发中"},
        }


class UserBadges:
    """用户徽章展示"""

    @staticmethod
    def get_display_badges(achievements: List[str]) -> List[Dict]:
        """获取展示徽章（最多6个）"""
        display = []
        priority_order = ["legendary", "epic", "rare", "common"]

        for ach_id in achievements:
            if ach_id in ACHIEVEMENTS:
                display.append(
                    {
                        "id": ach_id,
                        "name": ACHIEVEMENTS[ach_id].name,
                        "icon": ACHIEVEMENTS[ach_id].icon,
                        "rarity": ACHIEVEMENTS[ach_id].rarity,
                    }
                )

        display.sort(
            key=lambda x: (
                priority_order.index(x["rarity"])
                if x["rarity"] in priority_order
                else 4
            )
        )

        return display[:6]
