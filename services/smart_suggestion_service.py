"""
智能建议服务
提供上下文感知建议、预测性建议、建议效果追踪
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from collections import defaultdict

from models.database import (
    User,
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    ReminderSetting,
)
from services.ai_insights_service import (
    AIInsightsService,
    TrendPredictionService,
    AnomalyDetectionService,
)
from services.memory_enhancement_service import AccuracyTracker
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class SuggestionEffectTracker:
    """建议效果追踪服务"""

    _suggestions: List[Dict] = []

    @classmethod
    def record_suggestion(cls, suggestion: Dict):
        """记录已给出的建议"""
        cls._suggestions.append(
            {
                **suggestion,
                "timestamp": datetime.now().isoformat(),
                "status": "pending",
                "user_action": None,
                "effect_score": None,
            }
        )

    @classmethod
    def record_user_action(cls, suggestion_id: str, action: str):
        """记录用户对建议的行动"""
        for s in cls._suggestions:
            if s.get("id") == suggestion_id:
                s["user_action"] = action
                s["status"] = "responded"
                break

    @classmethod
    def calculate_effect_score(cls, suggestion_id: str) -> float:
        """计算建议效果评分"""
        for s in cls._suggestions:
            if s.get("id") == suggestion_id:
                action = s.get("user_action")
                if action == "accepted":
                    return 0.9
                elif action == "partial":
                    return 0.5
                elif action == "rejected":
                    return 0.1
                return 0.0
        return 0.0

    @classmethod
    def get_effect_stats(cls, days: int = 7) -> Dict:
        """获取效果统计"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            s
            for s in cls._suggestions
            if datetime.fromisoformat(s["timestamp"]) > cutoff
        ]

        if not recent:
            return {"total": 0, "accepted": 0, "rejected": 0, "effect_rate": 0}

        accepted = sum(1 for s in recent if s.get("user_action") == "accepted")
        rejected = sum(1 for s in recent if s.get("user_action") == "rejected")

        return {
            "total": len(recent),
            "accepted": accepted,
            "rejected": rejected,
            "effect_rate": round(accepted / len(recent), 2) if recent else 0,
        }


class ContextAwareSuggestionService:
    """上下文感知建议服务"""

    @staticmethod
    async def get_suggestions(
        user_id: int, db: AsyncSession, context: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        获取基于上下文的建议

        Args:
            user_id: 用户ID
            db: 数据库会话
            context: 当前上下文（时间、位置、状态等）

        Returns:
            建议列表
        """
        suggestions = []

        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()

        hour = datetime.now().hour
        is_morning = 6 <= hour < 9
        is_noon = 11 <= hour < 14
        is_evening = 17 <= hour < 21
        is_night = hour >= 21 or hour < 6

        if is_morning:
            suggestions.extend(
                await ContextAwareSuggestionService._morning_suggestions(
                    user_id, db, profile
                )
            )
        if is_noon:
            suggestions.extend(
                await ContextAwareSuggestionService._noon_suggestions(
                    user_id, db, profile
                )
            )
        if is_evening:
            suggestions.extend(
                await ContextAwareSuggestionService._evening_suggestions(
                    user_id, db, profile
                )
            )
        if is_night:
            suggestions.extend(
                await ContextAwareSuggestionService._night_suggestions(
                    user_id, db, profile
                )
            )

        patterns = await AIInsightsService.discover_hidden_patterns(
            user_id, db, days=14
        )
        for pattern in patterns.get("patterns", []):
            suggestions.append(
                {
                    "id": f"pattern_{pattern['type']}",
                    "type": "insight",
                    "title": f"发现{pattern.get('type_name', '新模式')}",
                    "content": pattern.get("recommendation", ""),
                    "priority": "high",
                    "category": "pattern",
                    "context": {"pattern_type": pattern.get("type")},
                }
            )

        anomalies = await AnomalyDetectionService.detect_anomalies(user_id, db, days=7)
        if anomalies.get("anomalies"):
            for anomaly in anomalies.get("anomalies", []):
                suggestions.append(
                    {
                        "id": f"anomaly_{anomaly['type']}",
                        "type": "warning",
                        "title": f"{anomaly.get('type', '数据')}异常提醒",
                        "content": anomaly.get("recommendation", ""),
                        "priority": "high"
                        if anomaly.get("severity") == "high"
                        else "medium",
                        "category": "anomaly",
                        "context": anomaly,
                    }
                )

        for s in suggestions:
            SuggestionEffectTracker.record_suggestion(s)

        return suggestions

    @staticmethod
    async def _morning_suggestions(
        user_id: int, db: AsyncSession, profile
    ) -> List[Dict]:
        """早间建议"""
        suggestions = []

        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_date.desc())
            .limit(1)
        )
        latest_weight = result.scalar_one_or_none()

        if latest_weight:
            suggestions.append(
                {
                    "id": f"morning_weight_{user_id}_{datetime.now().date()}",
                    "type": "reminder",
                    "title": "晨重记录",
                    "content": "早上好！记得记录今天的体重哦",
                    "priority": "medium",
                    "category": "weight",
                    "context": {"time": "morning"},
                }
            )

        suggestions.append(
            {
                "id": f"morning_water_{user_id}_{datetime.now().date()}",
                "type": "tip",
                "title": "晨起饮水",
                "content": "建议起床后喝一杯温水，帮助代谢",
                "priority": "low",
                "category": "water",
                "context": {"time": "morning"},
            }
        )

        return suggestions

    @staticmethod
    async def _noon_suggestions(user_id: int, db: AsyncSession, profile) -> List[Dict]:
        """午间建议"""
        suggestions = []

        suggestions.append(
            {
                "id": f"noon_meal_{user_id}_{datetime.now().date()}",
                "type": "reminder",
                "title": "午餐记录",
                "content": "午餐时间到，记得记录饮食哦",
                "priority": "medium",
                "category": "meal",
                "context": {"time": "noon"},
            }
        )

        return suggestions

    @staticmethod
    async def _evening_suggestions(
        user_id: int, db: AsyncSession, profile
    ) -> List[Dict]:
        """晚间建议"""
        suggestions = []

        suggestions.append(
            {
                "id": f"evening_exercise_{user_id}_{datetime.now().date()}",
                "type": "reminder",
                "title": "运动时间",
                "content": "下班后可以适当运动一下哦",
                "priority": "medium",
                "category": "exercise",
                "context": {"time": "evening"},
            }
        )

        return suggestions

    @staticmethod
    async def _night_suggestions(user_id: int, db: AsyncSession, profile) -> List[Dict]:
        """夜间建议"""
        suggestions = []

        suggestions.append(
            {
                "id": f"night_sleep_{user_id}_{datetime.now().date()}",
                "type": "reminder",
                "title": "睡眠提醒",
                "content": "夜深了，准备休息吧！保证充足睡眠对减重很重要",
                "priority": "low",
                "category": "sleep",
                "context": {"time": "night"},
            }
        )

        return suggestions


class PredictiveSuggestionService:
    """预测性建议服务"""

    @staticmethod
    async def get_predictive_suggestions(
        user_id: int, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取预测性建议"""
        suggestions = []

        weight_prediction = await TrendPredictionService.predict_weight_trend(
            user_id, db, days_ahead=7
        )

        if weight_prediction.get("success"):
            trend = weight_prediction.get("trend")
            if trend == "increasing":
                suggestions.append(
                    {
                        "id": f"predict_weight_up_{user_id}",
                        "type": "prediction",
                        "title": "体重趋势预警",
                        "content": "预测未来7天体重可能上升，建议控制饮食",
                        "priority": "high",
                        "category": "prediction",
                        "context": {
                            "predicted_change": weight_prediction.get(
                                "avg_daily_change"
                            )
                        },
                    }
                )
            elif trend == "decreasing":
                suggestions.append(
                    {
                        "id": f"predict_weight_down_{user_id}",
                        "type": "prediction",
                        "title": "减重趋势良好",
                        "content": "继续保持，当前趋势很好！",
                        "priority": "medium",
                        "category": "prediction",
                        "context": {
                            "predicted_change": weight_prediction.get(
                                "avg_daily_change"
                            )
                        },
                    }
                )

        calorie_needs = await TrendPredictionService.predict_calorie_needs(user_id, db)
        if calorie_needs.get("success"):
            suggestions.append(
                {
                    "id": f"predict_calorie_{user_id}",
                    "type": "prediction",
                    "title": "热量需求建议",
                    "content": f"今日建议摄入 {calorie_needs.get('recommended_calories')} 千卡",
                    "priority": "medium",
                    "category": "calorie",
                    "context": {
                        "tdee": calorie_needs.get("tdee"),
                        "recommended": calorie_needs.get("recommended_calories"),
                    },
                }
            )

        return suggestions


async def get_all_suggestions(user_id: int, db: AsyncSession) -> Dict[str, Any]:
    """获取所有建议（整合上下文感知和预测性建议）"""
    context_suggestions = await ContextAwareSuggestionService.get_suggestions(
        user_id, db
    )
    predictive_suggestions = (
        await PredictiveSuggestionService.get_predictive_suggestions(user_id, db)
    )

    all_suggestions = context_suggestions + predictive_suggestions

    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_suggestions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

    effect_stats = SuggestionEffectTracker.get_effect_stats()

    return {
        "success": True,
        "data": {
            "suggestions": all_suggestions,
            "count": len(all_suggestions),
            "effect_stats": effect_stats,
            "generated_at": datetime.now().isoformat(),
        },
    }
