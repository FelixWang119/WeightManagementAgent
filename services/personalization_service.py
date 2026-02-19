"""
个性化服务
提供用户偏好管理和个性化内容生成
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import json

from models.database import UserProfile, User
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class PersonalizationService:
    """个性化服务"""

    @staticmethod
    async def get_user_preferences(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取用户偏好设置"""
        try:
            # 获取用户画像
            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                return PersonalizationService._get_default_preferences()

            preferences = {
                "motivation_type": profile.motivation_type
                if profile.motivation_type
                else "balanced",
                "communication_style": profile.communication_style or "friendly",
                "weak_points": profile.weak_points or [],
                "diet_preferences": profile.diet_preferences or {},
                "exercise_habits": profile.exercise_habits or {},
                "decision_mode": profile.decision_mode or "balanced",
                "updated_at": profile.updated_at.isoformat()
                if profile.updated_at
                else None,
            }

            return {
                "success": True,
                "data": preferences,
                "has_profile": True,
            }

        except Exception as e:
            logger.error(f"获取用户偏好失败: {e}")
            return {
                "success": False,
                "error": "获取用户偏好失败",
                "data": PersonalizationService._get_default_preferences(),
                "has_profile": False,
            }

    @staticmethod
    async def update_user_preferences(
        user_id: int, preferences: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """更新用户偏好设置"""
        try:
            # 获取现有画像
            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                # 创建新画像
                profile = UserProfile(
                    user_id=user_id,
                    motivation_type=preferences.get("motivation_type", "balanced"),
                    communication_style=preferences.get(
                        "communication_style", "friendly"
                    ),
                    weak_points=preferences.get("weak_points", []),
                    diet_preferences=preferences.get("diet_preferences", {}),
                    exercise_habits=preferences.get("exercise_habits", {}),
                    decision_mode=preferences.get("decision_mode", "balanced"),
                    updated_at=datetime.utcnow(),
                )
                db.add(profile)
            else:
                # 更新现有画像
                if "motivation_type" in preferences:
                    profile.motivation_type = preferences["motivation_type"]
                if "communication_style" in preferences:
                    profile.communication_style = preferences["communication_style"]
                if "weak_points" in preferences:
                    profile.weak_points = preferences["weak_points"]
                if "diet_preferences" in preferences:
                    profile.diet_preferences = preferences["diet_preferences"]
                if "exercise_habits" in preferences:
                    profile.exercise_habits = preferences["exercise_habits"]
                if "decision_mode" in preferences:
                    profile.decision_mode = preferences["decision_mode"]
                profile.updated_at = datetime.utcnow()

            await db.commit()

            return {
                "success": True,
                "message": "偏好设置已更新",
                "data": {
                    "motivation_type": profile.motivation_type
                    if profile.motivation_type
                    else "balanced",
                    "communication_style": profile.communication_style,
                    "updated_at": profile.updated_at.isoformat(),
                },
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"更新用户偏好失败: {e}")
            return {
                "success": False,
                "error": "更新用户偏好失败",
            }

    @staticmethod
    async def personalize_coaching_message(
        message: str,
        user_id: int,
        db: AsyncSession,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """个性化教练消息"""
        try:
            # 获取用户偏好
            preferences_result = await PersonalizationService.get_user_preferences(
                user_id, db
            )
            preferences = (
                preferences_result.get("data", {})
                if preferences_result.get("success")
                else {}
            )

            personalized = message

            # 根据动力类型调整语气
            motivation_type = preferences.get("motivation_type", "balanced")
            if motivation_type == "data_driven":
                personalized = f"数据显示，{personalized}"
            elif motivation_type == "emotional_support":
                personalized = f"{personalized} 我理解你的感受"
            elif motivation_type == "goal_oriented":
                personalized = f"{personalized} 这有助于实现你的目标"

            # 根据沟通风格调整语气
            communication_style = preferences.get("communication_style", "friendly")
            if communication_style == "direct":
                personalized = f"{personalized}（直接建议）"
            elif communication_style == "encouraging":
                personalized = f"{personalized} 你可以做到的！"
            elif communication_style == "analytical":
                personalized = f"分析来看，{personalized}"

            # 添加上下文信息
            if context:
                if "streak_days" in context:
                    personalized = personalized.replace(
                        "{streak_days}", str(context["streak_days"])
                    )
                if "habit_name" in context:
                    personalized = personalized.replace(
                        "{habit_name}", context.get("habit_name", "你的习惯")
                    )
                if "achievement_count" in context:
                    personalized = personalized.replace(
                        "{achievement_count}", str(context.get("achievement_count", 0))
                    )

            return personalized

        except Exception as e:
            logger.error(f"个性化消息失败: {e}")
            return message

    @staticmethod
    async def get_personalized_suggestions(
        user_id: int, category: str, db: AsyncSession, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """获取个性化建议"""
        try:
            # 获取用户偏好
            preferences_result = await PersonalizationService.get_user_preferences(
                user_id, db
            )
            preferences = (
                preferences_result.get("data", {})
                if preferences_result.get("success")
                else {}
            )

            suggestions = []

            if category == "habits":
                # 基于薄弱环节推荐习惯
                weak_points = preferences.get("weak_points", [])
                if "morning_routine" in weak_points:
                    suggestions.append(
                        {
                            "title": "建立晨间习惯",
                            "description": "从简单的5分钟伸展开始",
                            "difficulty": "easy",
                            "reason": "你提到晨间习惯是薄弱环节",
                        }
                    )
                if "water_intake" in weak_points:
                    suggestions.append(
                        {
                            "title": "定时饮水提醒",
                            "description": "每小时喝一杯水",
                            "difficulty": "easy",
                            "reason": "饮水习惯需要加强",
                        }
                    )
                if "evening_wind_down" in weak_points:
                    suggestions.append(
                        {
                            "title": "睡前放松仪式",
                            "description": "睡前一小时关闭电子设备",
                            "difficulty": "medium",
                            "reason": "改善睡眠质量",
                        }
                    )

            elif category == "exercises":
                # 基于运动习惯推荐
                exercise_habits = preferences.get("exercise_habits", {})
                frequency = exercise_habits.get("frequency", "occasional")

                if frequency == "daily":
                    suggestions.append(
                        {
                            "title": "多样化运动组合",
                            "description": "尝试不同运动类型避免枯燥",
                            "difficulty": "medium",
                        }
                    )
                elif frequency == "weekly":
                    suggestions.append(
                        {
                            "title": "增加运动频率",
                            "description": "从每周3次增加到4次",
                            "difficulty": "medium",
                        }
                    )
                else:
                    suggestions.append(
                        {
                            "title": "建立运动习惯",
                            "description": "从每周2次15分钟运动开始",
                            "difficulty": "easy",
                        }
                    )

            elif category == "nutrition":
                # 基于饮食偏好推荐
                diet_preferences = preferences.get("diet_preferences", {})

                suggestions.append(
                    {
                        "title": "均衡饮食计划",
                        "description": "确保蛋白质、碳水、脂肪合理搭配",
                        "difficulty": "medium",
                    }
                )

                if diet_preferences.get("prefers_vegetables", False):
                    suggestions.append(
                        {
                            "title": "蔬菜多样化",
                            "description": "尝试不同颜色的蔬菜获取多种营养",
                            "difficulty": "easy",
                        }
                    )

            # 确保不超过限制
            suggestions = suggestions[:limit]

            return {
                "success": True,
                "data": suggestions,
                "category": category,
                "count": len(suggestions),
            }

        except Exception as e:
            logger.error(f"获取个性化建议失败: {e}")
            return {
                "success": False,
                "error": "获取个性化建议失败",
                "data": [],
                "category": category,
            }

    @staticmethod
    async def track_user_interaction(
        user_id: int, interaction_type: str, details: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """跟踪用户交互（简化版本）"""
        try:
            # 在实际应用中，这里会记录到专门的交互跟踪表
            # 这里简化实现，只记录日志
            logger.info(
                "用户交互跟踪: user_id=%d, type=%s, details=%s",
                user_id,
                interaction_type,
                json.dumps(details, ensure_ascii=False),
            )

            return {
                "success": True,
                "message": "交互已记录",
                "interaction_type": interaction_type,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"跟踪用户交互失败: {e}")
            return {
                "success": False,
                "error": "跟踪用户交互失败",
            }

    @staticmethod
    def _get_default_preferences() -> Dict[str, Any]:
        """获取默认偏好设置"""
        return {
            "motivation_type": "balanced",
            "communication_style": "friendly",
            "weak_points": [],
            "diet_preferences": {},
            "exercise_habits": {},
            "decision_mode": "balanced",
            "updated_at": None,
        }

    @staticmethod
    def get_preference_options() -> Dict[str, List[Dict[str, Any]]]:
        """获取可用的偏好选项"""
        return {
            "motivation_types": [
                {
                    "value": "data_driven",
                    "label": "数据驱动",
                    "description": "喜欢看到数据和统计",
                },
                {
                    "value": "emotional_support",
                    "label": "情感支持",
                    "description": "需要鼓励和情感支持",
                },
                {
                    "value": "goal_oriented",
                    "label": "目标导向",
                    "description": "关注目标和结果",
                },
                {"value": "balanced", "label": "平衡型", "description": "综合多种方式"},
            ],
            "communication_styles": [
                {
                    "value": "friendly",
                    "label": "友好型",
                    "description": "温暖友好的沟通方式",
                },
                {"value": "direct", "label": "直接型", "description": "直接了当的建议"},
                {
                    "value": "encouraging",
                    "label": "鼓励型",
                    "description": "充满鼓励和正能量",
                },
                {
                    "value": "analytical",
                    "label": "分析型",
                    "description": "注重逻辑和分析",
                },
            ],
            "weak_point_categories": [
                {
                    "value": "morning_routine",
                    "label": "晨间习惯",
                    "description": "早上难以建立规律",
                },
                {
                    "value": "water_intake",
                    "label": "饮水习惯",
                    "description": "经常忘记喝水",
                },
                {
                    "value": "evening_wind_down",
                    "label": "睡前放松",
                    "description": "晚上难以放松入睡",
                },
                {
                    "value": "meal_planning",
                    "label": "饮食计划",
                    "description": "饮食计划执行困难",
                },
                {
                    "value": "exercise_consistency",
                    "label": "运动坚持",
                    "description": "难以坚持运动",
                },
                {
                    "value": "stress_management",
                    "label": "压力管理",
                    "description": "压力应对能力",
                },
            ],
            "decision_modes": [
                {
                    "value": "conservative",
                    "label": "保守型",
                    "description": "偏好稳妥的选择",
                },
                {
                    "value": "balanced",
                    "label": "平衡型",
                    "description": "平衡风险和收益",
                },
                {
                    "value": "intelligent",
                    "label": "智能型",
                    "description": "依赖AI建议做决定",
                },
            ],
        }
