"""
AI洞察服务
提供隐藏模式发现、异常检测、趋势预测、提醒策略优化
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from collections import defaultdict
import statistics
import json

from models.database import (
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    UserProfile,
)
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class AIInsightsService:
    """AI洞察服务"""

    @staticmethod
    async def discover_hidden_patterns(
        user_id: int, db: AsyncSession, days: int = 30
    ) -> Dict[str, Any]:
        """
        发现隐藏模式（如睡眠-饮食关联、情绪性进食等）

        Args:
            user_id: 用户ID
            db: 数据库会话
            days: 分析天数

        Returns:
            发现的隐藏模式列表
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        patterns = []

        sleep_diet_corr = await AIInsightsService._analyze_sleep_diet_correlation(
            user_id, start_date, end_date, db
        )
        if sleep_diet_corr.get("significant"):
            patterns.append(sleep_diet_corr)

        stress_eating = await AIInsightsService._detect_emotional_eating(
            user_id, start_date, end_date, db
        )
        if stress_eating.get("detected"):
            patterns.append(stress_eating)

        exercise_calorie_pattern = (
            await AIInsightsService._analyze_exercise_calorie_pattern(
                user_id, start_date, end_date, db
            )
        )
        if exercise_calorie_pattern.get("detected"):
            patterns.append(exercise_calorie_pattern)

        water_weight_pattern = (
            await AIInsightsService._analyze_water_weight_relationship(
                user_id, start_date, end_date, db
            )
        )
        if water_weight_pattern.get("detected"):
            patterns.append(water_weight_pattern)

        return {
            "success": True,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "patterns_found": len(patterns),
            "patterns": patterns,
        }

    @staticmethod
    async def _analyze_sleep_diet_correlation(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """分析睡眠-饮食关联"""
        sleep_records = await AIInsightsService._get_sleep_data(
            user_id, start_date, end_date, db
        )
        meal_records = await AIInsightsService._get_meal_data(
            user_id, start_date, end_date, db
        )

        if len(sleep_records) < 5 or len(meal_records) < 5:
            return {"type": "sleep_diet", "detected": False}

        sleep_hours = [s["hours"] for s in sleep_records]
        daily_calories = meal_records

        if len(sleep_hours) < 3 or len(daily_calories) < 3:
            return {"type": "sleep_diet", "detected": False}

        correlation = AIInsightsService._calculate_correlation(
            sleep_hours, list(daily_calories.values())
        )

        if abs(correlation) > 0.5:
            direction = "负相关" if correlation < 0 else "正相关"
            return {
                "type": "sleep_diet",
                "detected": True,
                "significant": True,
                "correlation": round(correlation, 2),
                "description": f"睡眠与饮食呈{correlation:.0%}的{direction}",
                "insight": "睡眠不足时倾向于摄入更多热量"
                if correlation < -0.5
                else "睡眠充足时摄入热量更高",
                "recommendation": "保证充足睡眠有助于控制饮食"
                if correlation < -0.5
                else "注意饮食规律",
            }

        return {"type": "sleep_diet", "detected": False, "significant": False}

    @staticmethod
    async def _detect_emotional_eating(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """检测情绪性进食"""
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    MealRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        meals = result.scalars().all()

        if len(meals) < 7:
            return {"type": "emotional_eating", "detected": False}

        daily_calories = defaultdict(list)
        for meal in meals:
            day = meal.record_time.date()
            daily_calories[day].append(meal.total_calories)

        calories_per_day = {day: sum(cals) for day, cals in daily_calories.items()}

        if len(calories_per_day) < 5:
            return {"type": "emotional_eating", "detected": False}

        values = list(calories_per_day.values())
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        high_calorie_days = sum(1 for v in values if v > mean + std)

        if high_calorie_days >= 3:
            return {
                "type": "emotional_eating",
                "detected": True,
                "description": f"检测到{high_calorie_days}天异常高热量摄入",
                "insight": "可能存在情绪性进食倾向",
                "recommendation": "记录进食时的情绪，尝试用其他方式调节情绪",
            }

        return {"type": "emotional_eating", "detected": False}

    @staticmethod
    async def _analyze_exercise_calorie_pattern(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """分析运动-热量消耗模式"""
        result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    ExerciseRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    ExerciseRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        exercises = result.scalars().all()

        if len(exercises) < 3:
            return {"type": "exercise_calorie", "detected": False}

        exercise_days = set(e.record_time.date() for e in exercises)
        exercise_minutes = sum(e.duration_minutes for e in exercises)

        days_count = (end_date - start_date).days
        exercise_rate = len(exercise_days) / days_count

        if exercise_rate > 0.5:
            return {
                "type": "exercise_calorie",
                "detected": True,
                "description": f"运动频率较高({exercise_rate:.0%}的天数)",
                "insight": "运动习惯良好，建议保持",
                "recommendation": "继续坚持，注意运动后补充水分",
            }

        return {"type": "exercise_calorie", "detected": False}

    @staticmethod
    async def _analyze_water_weight_relationship(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """分析饮水量与体重关系"""
        result = await db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == user_id,
                    WaterRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    WaterRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        water_records = result.scalars().all()

        result = await db.execute(
            select(WeightRecord).where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date >= start_date,
                    WeightRecord.record_date <= end_date,
                )
            )
        )
        weight_records = result.scalars().all()

        if len(water_records) < 10 or len(weight_records) < 3:
            return {"type": "water_weight", "detected": False}

        daily_water = defaultdict(int)
        for w in water_records:
            day = w.record_time.date()
            daily_water[day] += w.amount_ml

        weights = {r.record_date: r.weight for r in weight_records}

        if len(daily_water) < 3 or len(weights) < 3:
            return {"type": "water_weight", "detected": False}

        water_values = list(daily_water.values())
        avg_water = statistics.mean(water_values)

        if avg_water < 1500:
            return {
                "type": "water_weight",
                "detected": True,
                "description": f"平均饮水量偏低({avg_water:.0f}ml)",
                "insight": "饮水量不足可能影响代谢",
                "recommendation": "每天建议饮水2000ml以上",
            }

        return {"type": "water_weight", "detected": False}

    @staticmethod
    def _calculate_correlation(x: List[float], y: List[float]) -> float:
        """计算皮尔逊相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denominator_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denominator_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if denominator_x == 0 or denominator_y == 0:
            return 0.0

        return numerator / (denominator_x * denominator_y)

    @staticmethod
    async def _get_sleep_data(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> List[Dict]:
        """获取睡眠数据"""
        result = await db.execute(
            select(SleepRecord).where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        records = result.scalars().all()

        sleep_data = []
        for r in records:
            sleep_data.append(
                {
                    "date": r.bed_time.date(),
                    "hours": r.total_minutes / 60,
                    "quality": r.quality or 0,
                }
            )

        return sleep_data

    @staticmethod
    async def _get_meal_data(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, int]:
        """获取每日饮食热量"""
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    MealRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        meals = result.scalars().all()

        daily_calories = defaultdict(int)
        for meal in meals:
            day = meal.record_time.date()
            daily_calories[day.isoformat()] += meal.total_calories

        return daily_calories


class AnomalyDetectionService:
    """异常检测服务"""

    @staticmethod
    async def detect_anomalies(
        user_id: int, db: AsyncSession, days: int = 14
    ) -> Dict[str, Any]:
        """
        检测数据异常

        Args:
            user_id: 用户ID
            db: 数据库会话
            days: 分析天数

        Returns:
            检测到的异常列表
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        anomalies = []

        weight_anomaly = await AnomalyDetectionService._detect_weight_anomaly(
            user_id, start_date, end_date, db
        )
        if weight_anomaly.get("detected"):
            anomalies.append(weight_anomaly)

        calorie_anomaly = await AnomalyDetectionService._detect_calorie_anomaly(
            user_id, start_date, end_date, db
        )
        if calorie_anomaly.get("detected"):
            anomalies.append(calorie_anomaly)

        sleep_anomaly = await AnomalyDetectionService._detect_sleep_anomaly(
            user_id, start_date, end_date, db
        )
        if sleep_anomaly.get("detected"):
            anomalies.append(sleep_anomaly)

        return {
            "success": True,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "anomalies_count": len(anomalies),
            "anomalies": anomalies,
            "risk_level": "high"
            if len(anomalies) >= 3
            else "medium"
            if len(anomalies) >= 1
            else "low",
        }

    @staticmethod
    async def _detect_weight_anomaly(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """检测体重异常"""
        result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date >= start_date,
                    WeightRecord.record_date <= end_date,
                )
            )
            .order_by(WeightRecord.record_date)
        )
        records = result.scalars().all()

        if len(records) < 3:
            return {"type": "weight", "detected": False}

        weights = [r.weight for r in records]
        mean = statistics.mean(weights)
        std = statistics.stdev(weights) if len(weights) > 1 else 0

        if std > 0:
            z_scores = [(w - mean) / std for w in weights]
            extreme_days = [i for i, z in enumerate(z_scores) if abs(z) > 2]

            if extreme_days:
                return {
                    "type": "weight",
                    "detected": True,
                    "description": f"检测到{len(extreme_days)}天体重异常波动",
                    "severity": "high"
                    if any(abs(z) > 3 for z in z_scores)
                    else "medium",
                    "values": [
                        {
                            "date": records[i].record_date.isoformat(),
                            "weight": weights[i],
                        }
                        for i in extreme_days
                    ],
                    "recommendation": "建议关注体重变化原因",
                }

        return {"type": "weight", "detected": False}

    @staticmethod
    async def _detect_calorie_anomaly(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """检测热量摄入异常"""
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    MealRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        meals = result.scalars().all()

        daily_calories = defaultdict(int)
        for meal in meals:
            day = meal.record_time.date()
            daily_calories[day] += meal.total_calories

        if len(daily_calories) < 5:
            return {"type": "calorie", "detected": False}

        values = list(daily_calories.values())
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        if std > 0:
            very_low_days = [
                day for day, v in daily_calories.items() if v < mean - 2 * std
            ]
            very_high_days = [
                day for day, v in daily_calories.items() if v > mean + 2 * std
            ]

            if very_low_days or very_high_days:
                return {
                    "type": "calorie",
                    "detected": True,
                    "description": f"摄入异常: {len(very_low_days)}天过低, {len(very_high_days)}天过高",
                    "severity": "high"
                    if len(very_low_days) + len(very_high_days) >= 3
                    else "medium",
                    "recommendation": "保持规律饮食，避免暴饮暴食",
                }

        return {"type": "calorie", "detected": False}

    @staticmethod
    async def _detect_sleep_anomaly(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """检测睡眠异常"""
        result = await db.execute(
            select(SleepRecord).where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(end_date, datetime.max.time()),
                )
            )
        )
        records = result.scalars().all()

        if len(records) < 3:
            return {"type": "sleep", "detected": False}

        hours = [r.total_minutes / 60 for r in records]
        mean = statistics.mean(hours)
        std = statistics.stdev(hours) if len(hours) > 1 else 0

        if std > 0:
            very_low_days = [i for i, h in enumerate(hours) if h < mean - 2 * std]

            if very_low_days:
                return {
                    "type": "sleep",
                    "detected": True,
                    "description": f"检测到{len(very_low_days)}天睡眠严重不足",
                    "severity": "high",
                    "recommendation": "保证充足睡眠对减重很重要",
                }

        return {"type": "sleep", "detected": False}


class TrendPredictionService:
    """趋势预测服务"""

    @staticmethod
    async def predict_weight_trend(
        user_id: int, db: AsyncSession, days_ahead: int = 7
    ) -> Dict[str, Any]:
        """
        预测体重趋势

        Args:
            user_id: 用户ID
            db: 数据库会话
            days_ahead: 预测天数

        Returns:
            预测结果
        """
        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_date.desc())
            .limit(30)
        )
        records = result.scalars().all()

        if len(records) < 7:
            return {
                "success": False,
                "message": "数据不足，需要至少7天体重记录",
            }

        weights = [(r.record_date, r.weight) for r in records][::-1]

        recent_weights = weights[-14:]
        avg_change = 0
        if len(recent_weights) >= 2:
            total_change = recent_weights[-1][1] - recent_weights[0][1]
            avg_change = total_change / (len(recent_weights) - 1)

        current_weight = weights[-1][1]
        predicted_weight = current_weight + avg_change * days_ahead

        trend = "stable"
        if avg_change < -0.1:
            trend = "decreasing"
        elif avg_change > 0.1:
            trend = "increasing"

        return {
            "success": True,
            "current_weight": current_weight,
            "predicted_weight": round(predicted_weight, 1),
            "avg_daily_change": round(avg_change, 2),
            "trend": trend,
            "confidence": "medium" if len(records) >= 14 else "low",
            "days_ahead": days_ahead,
            "recommendation": _get_trend_recommendation(trend, avg_change),
        }

    @staticmethod
    async def predict_calorie_needs(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """预测每日热量需求"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_date.desc())
            .limit(1)
        )
        latest_weight = result.scalar_one_or_none()

        result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    ExerciseRecord.record_time >= datetime.now() - timedelta(days=7),
                )
            )
        )
        exercises = result.scalars().all()

        bmr = profile.bmr if profile and profile.bmr else 1500
        activity_factor = 1.2 + (len(exercises) * 0.05)
        activity_factor = min(activity_factor, 1.7)

        tdee = int(bmr * activity_factor)

        weight_goal = (
            profile.target_weight
            if profile and profile.target_weight
            else latest_weight.weight
            if latest_weight
            else 70
        )

        if latest_weight and latest_weight.weight > weight_goal:
            calorie_deficit = 500
        else:
            calorie_deficit = 0

        recommended = tdee - calorie_deficit

        return {
            "success": True,
            "bmr": bmr,
            "tdee": tdee,
            "recommended_calories": recommended,
            "activity_level": "sedentary"
            if activity_factor < 1.4
            else "moderate"
            if activity_factor < 1.6
            else "active",
            "exercise_days_last_week": len(exercises),
        }


def _get_trend_recommendation(trend: str, avg_change: float) -> str:
    """获取趋势建议"""
    recommendations = {
        "decreasing": "体重持续下降，保持当前饮食和运动习惯",
        "increasing": "体重有所上升，建议控制饮食或增加运动",
        "stable": "体重保持稳定，维持健康生活方式",
    }
    return recommendations.get(trend, "继续保持")


class ReminderStrategyOptimizer:
    """提醒策略优化服务"""

    @staticmethod
    async def optimize_reminder_strategy(
        user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """
        基于用户行为优化提醒策略

        Args:
            user_id: 用户ID
            db: 数据库会话

        Returns:
            优化后的提醒策略
        """
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        patterns = await AIInsightsService.discover_hidden_patterns(
            user_id, db, days=14
        )
        anomalies = await AnomalyDetectionService.detect_anomalies(user_id, db, days=14)

        strategies = []

        if anomalies.get("risk_level") == "high":
            strategies.append(
                {
                    "type": "increased_monitoring",
                    "description": "检测到异常，建议增加监测频率",
                    "actions": ["增加体重记录提醒", "加强饮食监督"],
                }
            )

        for pattern in patterns.get("patterns", []):
            if pattern.get("type") == "emotional_eating":
                strategies.append(
                    {
                        "type": "emotional_support",
                        "description": "检测到情绪性进食倾向",
                        "actions": ["增加正向鼓励", "提供情绪调节建议"],
                    }
                )

        if profile and profile.motivation_type:
            motivation = (
                profile.motivation_type.value
                if hasattr(profile.motivation_type, "value")
                else str(profile.motivation_type)
            )
            strategies.append(
                {
                    "type": "personalized_tone",
                    "description": f"基于动力类型({motivation})调整沟通风格",
                    "actions": [_get_motivation_action(motivation)],
                }
            )

        return {
            "success": True,
            "user_id": user_id,
            "strategies_count": len(strategies),
            "strategies": strategies,
            "risk_level": anomalies.get("risk_level", "low"),
        }


def _get_motivation_action(motivation: str) -> str:
    """获取基于动机的行动建议"""
    actions = {
        "data": "多提供数据分析和进度报告",
        "emotional": "多给予情感支持和鼓励",
        "goal": "强调目标达成和里程碑",
    }
    return actions.get(motivation, "提供综合支持")
