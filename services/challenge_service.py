"""
挑战服务
提供时间限制的挑战任务，增加用户参与度和趣味性
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from enum import Enum
from dataclasses import dataclass
import json

from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class ChallengeType(Enum):
    """挑战类型"""

    DAILY = "daily"  # 每日挑战
    WEEKLY = "weekly"  # 每周挑战
    MONTHLY = "monthly"  # 每月挑战
    SPECIAL = "special"  # 特殊挑战


class ChallengeStatus(Enum):
    """挑战状态"""

    ACTIVE = "active"  # 进行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 已失败
    LOCKED = "locked"  # 未解锁


@dataclass
class Challenge:
    """挑战数据类"""

    id: str
    name: str
    description: str
    challenge_type: ChallengeType
    icon: str
    reward_points: int
    difficulty: str  # easy, medium, hard
    condition: Dict[str, Any]
    duration_days: int  # 挑战持续时间（天）
    max_participants: Optional[int] = None  # 最大参与人数（None表示无限制）


# 预定义挑战
CHALLENGES = {
    "daily_water": Challenge(
        id="daily_water",
        name="每日饮水挑战",
        description="今天喝够2000ml水",
        challenge_type=ChallengeType.DAILY,
        icon="💧",
        reward_points=20,
        difficulty="easy",
        condition={"type": "water_intake", "target_ml": 2000},
        duration_days=1,
    ),
    "daily_exercise": Challenge(
        id="daily_exercise",
        name="每日运动挑战",
        description="今天运动30分钟",
        challenge_type=ChallengeType.DAILY,
        icon="🏃",
        reward_points=30,
        difficulty="medium",
        condition={"type": "exercise_duration", "target_minutes": 30},
        duration_days=1,
    ),
    "daily_nutrition": Challenge(
        id="daily_nutrition",
        name="均衡饮食挑战",
        description="记录三餐饮食",
        challenge_type=ChallengeType.DAILY,
        icon="🍽️",
        reward_points=25,
        difficulty="easy",
        condition={"type": "meal_records", "target_count": 3},
        duration_days=1,
    ),
    "weekly_streak": Challenge(
        id="weekly_streak",
        name="连续打卡挑战",
        description="连续7天记录体重",
        challenge_type=ChallengeType.WEEKLY,
        icon="🔥",
        reward_points=100,
        difficulty="hard",
        condition={"type": "weight_streak", "target_days": 7},
        duration_days=7,
    ),
    "weekly_exercise": Challenge(
        id="weekly_exercise",
        name="每周运动挑战",
        description="本周运动3次",
        challenge_type=ChallengeType.WEEKLY,
        icon="💪",
        reward_points=150,
        difficulty="medium",
        condition={"type": "exercise_count", "target_count": 3},
        duration_days=7,
    ),
    "weekly_sleep": Challenge(
        id="weekly_sleep",
        name="优质睡眠挑战",
        description="本周5天睡眠达标",
        challenge_type=ChallengeType.WEEKLY,
        icon="😴",
        reward_points=120,
        difficulty="medium",
        condition={"type": "sleep_quality", "target_days": 5},
        duration_days=7,
    ),
    "monthly_weight_loss": Challenge(
        id="monthly_weight_loss",
        name="月度减重挑战",
        description="本月减重2kg",
        challenge_type=ChallengeType.MONTHLY,
        icon="⚖️",
        reward_points=500,
        difficulty="hard",
        condition={"type": "weight_loss", "target_kg": 2.0},
        duration_days=30,
    ),
    "monthly_consistency": Challenge(
        id="monthly_consistency",
        name="月度坚持挑战",
        description="本月记录25天",
        challenge_type=ChallengeType.MONTHLY,
        icon="📅",
        reward_points=400,
        difficulty="hard",
        condition={"type": "record_days", "target_days": 25},
        duration_days=30,
    ),
    "special_perfect_week": Challenge(
        id="special_perfect_week",
        name="完美一周挑战",
        description="完成所有每日挑战",
        challenge_type=ChallengeType.SPECIAL,
        icon="🏆",
        reward_points=300,
        difficulty="hard",
        condition={"type": "complete_all_daily", "target_weeks": 1},
        duration_days=7,
        max_participants=1000,
    ),
}


class ChallengeService:
    """挑战服务"""

    @staticmethod
    async def get_available_challenges(
        user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """获取可用挑战"""
        try:
            # 这里应该从数据库获取用户当前的挑战状态
            # 暂时返回所有挑战
            available_challenges = []

            for challenge_id, challenge in CHALLENGES.items():
                available_challenges.append(
                    {
                        "id": challenge.id,
                        "name": challenge.name,
                        "description": challenge.description,
                        "type": challenge.challenge_type.value,
                        "icon": challenge.icon,
                        "reward_points": challenge.reward_points,
                        "difficulty": challenge.difficulty,
                        "duration_days": challenge.duration_days,
                        "max_participants": challenge.max_participants,
                        "status": ChallengeStatus.ACTIVE.value,  # 默认状态
                        "progress": 0.0,  # 进度百分比
                        "time_remaining": challenge.duration_days * 24,  # 剩余小时
                    }
                )

            # 按难度和奖励排序
            available_challenges.sort(
                key=lambda x: (
                    {"easy": 0, "medium": 1, "hard": 2}[x["difficulty"]],
                    -x["reward_points"],
                )
            )

            return {
                "success": True,
                "data": {
                    "challenges": available_challenges,
                    "total_count": len(available_challenges),
                    "daily_count": len(
                        [c for c in available_challenges if c["type"] == "daily"]
                    ),
                    "weekly_count": len(
                        [c for c in available_challenges if c["type"] == "weekly"]
                    ),
                    "monthly_count": len(
                        [c for c in available_challenges if c["type"] == "monthly"]
                    ),
                },
            }
        except Exception as e:
            logger.error(f"获取可用挑战失败: {e}")
            return {
                "success": False,
                "error": "获取挑战失败",
                "data": {
                    "challenges": [],
                    "total_count": 0,
                    "daily_count": 0,
                    "weekly_count": 0,
                    "monthly_count": 0,
                },
            }

    @staticmethod
    async def get_user_challenges(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取用户参与的挑战"""
        try:
            # 这里应该从数据库获取用户参与的挑战
            # 暂时返回模拟数据
            user_challenges = []

            # 模拟一些进行中的挑战
            sample_challenges = [
                {
                    "id": "daily_water",
                    "name": "每日饮水挑战",
                    "description": "今天喝够2000ml水",
                    "type": "daily",
                    "icon": "💧",
                    "reward_points": 20,
                    "difficulty": "easy",
                    "status": ChallengeStatus.ACTIVE.value,
                    "progress": 0.65,  # 65%完成
                    "time_remaining": 8,  # 剩余8小时
                    "started_at": datetime.utcnow().isoformat(),
                    "ends_at": (datetime.utcnow() + timedelta(hours=8)).isoformat(),
                },
                {
                    "id": "weekly_exercise",
                    "name": "每周运动挑战",
                    "description": "本周运动3次",
                    "type": "weekly",
                    "icon": "💪",
                    "reward_points": 150,
                    "difficulty": "medium",
                    "status": ChallengeStatus.ACTIVE.value,
                    "progress": 0.33,  # 完成1/3
                    "time_remaining": 120,  # 剩余120小时（5天）
                    "started_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                    "ends_at": (datetime.utcnow() + timedelta(days=5)).isoformat(),
                },
                {
                    "id": "monthly_consistency",
                    "name": "月度坚持挑战",
                    "description": "本月记录25天",
                    "type": "monthly",
                    "icon": "📅",
                    "reward_points": 400,
                    "difficulty": "hard",
                    "status": ChallengeStatus.ACTIVE.value,
                    "progress": 0.2,  # 完成5/25
                    "time_remaining": 600,  # 剩余600小时（25天）
                    "started_at": (datetime.utcnow() - timedelta(days=5)).isoformat(),
                    "ends_at": (datetime.utcnow() + timedelta(days=25)).isoformat(),
                },
            ]

            # 模拟一些已完成的挑战
            completed_challenges = [
                {
                    "id": "daily_nutrition",
                    "name": "均衡饮食挑战",
                    "description": "记录三餐饮食",
                    "type": "daily",
                    "icon": "🍽️",
                    "reward_points": 25,
                    "difficulty": "easy",
                    "status": ChallengeStatus.COMPLETED.value,
                    "progress": 1.0,
                    "time_remaining": 0,
                    "started_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "reward_claimed": True,
                },
                {
                    "id": "weekly_streak",
                    "name": "连续打卡挑战",
                    "description": "连续7天记录体重",
                    "type": "weekly",
                    "icon": "🔥",
                    "reward_points": 100,
                    "difficulty": "hard",
                    "status": ChallengeStatus.COMPLETED.value,
                    "progress": 1.0,
                    "time_remaining": 0,
                    "started_at": (datetime.utcnow() - timedelta(days=14)).isoformat(),
                    "completed_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                    "reward_claimed": True,
                },
            ]

            user_challenges = sample_challenges + completed_challenges

            # 计算统计数据
            active_count = len(
                [
                    c
                    for c in user_challenges
                    if c["status"] == ChallengeStatus.ACTIVE.value
                ]
            )
            completed_count = len(
                [
                    c
                    for c in user_challenges
                    if c["status"] == ChallengeStatus.COMPLETED.value
                ]
            )
            total_rewards = sum(
                c["reward_points"] for c in user_challenges if c.get("reward_claimed")
            )

            return {
                "success": True,
                "data": {
                    "challenges": user_challenges,
                    "active_count": active_count,
                    "completed_count": completed_count,
                    "total_rewards": total_rewards,
                    "total_participated": len(user_challenges),
                },
            }
        except Exception as e:
            logger.error(f"获取用户挑战失败: {e}")
            return {
                "success": False,
                "error": "获取用户挑战失败",
                "data": {
                    "challenges": [],
                    "active_count": 0,
                    "completed_count": 0,
                    "total_rewards": 0,
                    "total_participated": 0,
                },
            }

    @staticmethod
    async def join_challenge(
        user_id: int, challenge_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """加入挑战"""
        try:
            if challenge_id not in CHALLENGES:
                return {
                    "success": False,
                    "error": "挑战不存在",
                }

            challenge = CHALLENGES[challenge_id]

            # 这里应该将挑战加入用户数据库
            # 暂时返回成功响应

            logger.info(f"用户 {user_id} 加入挑战: {challenge.name}")

            return {
                "success": True,
                "message": f"成功加入挑战: {challenge.name}",
                "data": {
                    "challenge_id": challenge.id,
                    "challenge_name": challenge.name,
                    "reward_points": challenge.reward_points,
                    "duration_days": challenge.duration_days,
                    "started_at": datetime.utcnow().isoformat(),
                    "ends_at": (
                        datetime.utcnow() + timedelta(days=challenge.duration_days)
                    ).isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"加入挑战失败: {e}")
            return {
                "success": False,
                "error": "加入挑战失败",
                "message": f"加入挑战失败: {str(e)}",
            }

    @staticmethod
    async def check_challenge_progress(
        user_id: int,
        activity_type: str,
        activity_data: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """检查挑战进度"""
        try:
            # 这里应该根据用户活动更新挑战进度
            # 暂时返回模拟数据

            updated_challenges = []

            if activity_type == "water_record":
                # 检查饮水挑战
                water_amount = activity_data.get("amount_ml", 0)
                if water_amount >= 2000:
                    updated_challenges.append(
                        {
                            "challenge_id": "daily_water",
                            "progress": 1.0,
                            "completed": True,
                            "message": "完成每日饮水挑战！",
                        }
                    )

            elif activity_type == "exercise_record":
                # 检查运动挑战
                duration = activity_data.get("duration_minutes", 0)
                if duration >= 30:
                    updated_challenges.append(
                        {
                            "challenge_id": "daily_exercise",
                            "progress": 1.0,
                            "completed": True,
                            "message": "完成每日运动挑战！",
                        }
                    )

            elif activity_type == "meal_record":
                # 检查饮食挑战
                meal_count = activity_data.get("meal_count", 0)
                if meal_count >= 3:
                    updated_challenges.append(
                        {
                            "challenge_id": "daily_nutrition",
                            "progress": 1.0,
                            "completed": True,
                            "message": "完成均衡饮食挑战！",
                        }
                    )

            return {
                "success": True,
                "data": {
                    "updated_challenges": updated_challenges,
                    "activity_type": activity_type,
                },
            }
        except Exception as e:
            logger.error(f"检查挑战进度失败: {e}")
            return {
                "success": False,
                "error": "检查挑战进度失败",
                "data": {
                    "updated_challenges": [],
                    "activity_type": activity_type,
                },
            }

    @staticmethod
    async def claim_challenge_reward(
        user_id: int, challenge_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """领取挑战奖励"""
        try:
            if challenge_id not in CHALLENGES:
                return {
                    "success": False,
                    "error": "挑战不存在",
                }

            challenge = CHALLENGES[challenge_id]

            # 这里应该检查用户是否完成挑战并领取奖励
            # 暂时返回成功响应

            logger.info(
                f"用户 {user_id} 领取挑战奖励: {challenge.name} ({challenge.reward_points}积分)"
            )

            return {
                "success": True,
                "message": f"成功领取挑战奖励: {challenge.reward_points}积分",
                "data": {
                    "challenge_id": challenge.id,
                    "challenge_name": challenge.name,
                    "reward_points": challenge.reward_points,
                    "claimed_at": datetime.utcnow().isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"领取挑战奖励失败: {e}")
            return {
                "success": False,
                "error": "领取挑战奖励失败",
                "message": f"领取挑战奖励失败: {str(e)}",
            }

    @staticmethod
    async def get_challenge_leaderboard(
        challenge_id: str, limit: int = 20, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取挑战排行榜"""
        try:
            if challenge_id not in CHALLENGES:
                return {
                    "success": False,
                    "error": "挑战不存在",
                }

            challenge = CHALLENGES[challenge_id]

            # 模拟排行榜数据
            leaderboard = []
            for i in range(min(limit, 10)):
                leaderboard.append(
                    {
                        "rank": i + 1,
                        "user_id": 1000 + i,
                        "nickname": f"用户{i + 1}",
                        "avatar_url": f"https://example.com/avatar{i + 1}.jpg",
                        "progress": min(1.0, (i + 1) * 0.1),  # 10%递增
                        "completed_at": datetime.utcnow().isoformat()
                        if i < 3
                        else None,
                        "points_earned": challenge.reward_points if i < 3 else 0,
                    }
                )

            return {
                "success": True,
                "data": {
                    "challenge_id": challenge.id,
                    "challenge_name": challenge.name,
                    "leaderboard": leaderboard,
                    "total_participants": len(leaderboard),
                    "your_rank": 5,  # 模拟当前用户排名
                    "your_progress": 0.5,  # 模拟当前用户进度
                },
            }
        except Exception as e:
            logger.error(f"获取挑战排行榜失败: {e}")
            return {
                "success": False,
                "error": "获取排行榜失败",
                "data": {
                    "challenge_id": challenge_id,
                    "challenge_name": "",
                    "leaderboard": [],
                    "total_participants": 0,
                    "your_rank": None,
                    "your_progress": 0,
                },
            }


class ChallengeNotification:
    """挑战通知"""

    @staticmethod
    def get_daily_challenge_notification() -> str:
        """获取每日挑战通知"""
        daily_challenges = [
            c for c in CHALLENGES.values() if c.challenge_type == ChallengeType.DAILY
        ]

        if not daily_challenges:
            return "今天没有可用的每日挑战"

        challenge = daily_challenges[0]  # 取第一个每日挑战
        return f"📢 今日挑战: {challenge.name}\n{challenge.description}\n奖励: {challenge.reward_points}积分"

    @staticmethod
    def get_weekly_challenge_summary(progress: float) -> str:
        """获取每周挑战总结"""
        if progress >= 1.0:
            return "🎉 恭喜完成本周所有挑战！继续保持！"
        elif progress >= 0.7:
            return "👍 本周挑战进度良好，继续加油！"
        elif progress >= 0.4:
            return "💪 本周挑战进行中，坚持就是胜利！"
        else:
            return "🚀 新的一周开始啦！快来参加本周挑战吧！"

    @staticmethod
    def get_challenge_completion_message(
        challenge_name: str, reward_points: int
    ) -> str:
        """获取挑战完成消息"""
        return f"🎊 恭喜完成挑战: {challenge_name}\n获得奖励: {reward_points}积分"
