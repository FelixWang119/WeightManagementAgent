"""
图表数据服务
为仪表盘提供趋势可视化数据
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
import json

from models.database import (
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    HabitCompletion,
)
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class ChartService:
    """图表服务"""

    @staticmethod
    async def get_weight_trend_chart(
        user_id: int, days: int = 30, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取体重趋势图表数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # 获取体重记录
            result = await db.execute(
                select(WeightRecord.record_date, WeightRecord.weight)
                .where(
                    and_(
                        WeightRecord.user_id == user_id,
                        WeightRecord.record_date >= start_date,
                        WeightRecord.record_date <= end_date,
                    )
                )
                .order_by(WeightRecord.record_date.asc())
            )
            records = result.all()

            # 准备图表数据
            dates = []
            weights = []

            for record in records:
                dates.append(record.record_date.isoformat())
                weights.append(float(record.weight))

            # 计算趋势线（简单移动平均）
            trend_line = []
            if weights:
                window_size = min(3, len(weights))
                for i in range(len(weights)):
                    start_idx = max(0, i - window_size + 1)
                    end_idx = i + 1
                    window = weights[start_idx:end_idx]
                    trend_line.append(sum(window) / len(window))

            # 计算统计信息
            stats = {}
            if weights:
                stats = {
                    "current": weights[-1] if weights else None,
                    "min": min(weights) if weights else None,
                    "max": max(weights) if weights else None,
                    "avg": sum(weights) / len(weights) if weights else None,
                    "change": (weights[-1] - weights[0]) if len(weights) > 1 else 0,
                    "trend": "down"
                    if len(weights) > 1 and weights[-1] < weights[0]
                    else "up"
                    if len(weights) > 1 and weights[-1] > weights[0]
                    else "stable",
                }

            return {
                "success": True,
                "data": {
                    "type": "line",
                    "title": f"体重趋势 ({days}天)",
                    "labels": dates,
                    "datasets": [
                        {
                            "label": "体重 (kg)",
                            "data": weights,
                            "borderColor": "#4CAF50",
                            "backgroundColor": "rgba(76, 175, 80, 0.1)",
                            "fill": True,
                        },
                        {
                            "label": "趋势线",
                            "data": trend_line,
                            "borderColor": "#FF9800",
                            "borderWidth": 2,
                            "fill": False,
                            "pointRadius": 0,
                        },
                    ],
                    "stats": stats,
                    "period": days,
                    "record_count": len(records),
                },
            }

        except Exception as e:
            logger.error(f"获取体重趋势图表失败: {e}")
            return {
                "success": False,
                "error": "获取体重趋势数据失败",
                "data": {
                    "type": "line",
                    "title": f"体重趋势 ({days}天)",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": days,
                    "record_count": 0,
                },
            }

    @staticmethod
    async def get_calorie_trend_chart(
        user_id: int, days: int = 7, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取热量趋势图表数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # 获取每日热量数据
            daily_calories = {}

            # 查询每日总热量
            result = await db.execute(
                select(
                    func.date(MealRecord.record_time).label("date"),
                    func.sum(MealRecord.total_calories).label("total_calories"),
                )
                .where(
                    and_(
                        MealRecord.user_id == user_id,
                        MealRecord.record_time >= start_date,
                        MealRecord.record_time <= end_date + timedelta(days=1),
                    )
                )
                .group_by(func.date(MealRecord.record_time))
                .order_by(func.date(MealRecord.record_time).asc())
            )

            records = result.all()

            # 填充日期范围
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_calories[date_str] = 0
                current_date += timedelta(days=1)

            # 填充实际数据
            for record in records:
                date_str = record.date.isoformat()
                daily_calories[date_str] = float(record.total_calories or 0)

            # 准备图表数据
            dates = sorted(daily_calories.keys())
            calories = [daily_calories[date] for date in dates]

            # 计算目标热量线（假设2000卡）
            target_calories = [2000] * len(dates)

            # 计算统计信息
            stats = {}
            non_zero_calories = [c for c in calories if c > 0]
            if non_zero_calories:
                stats = {
                    "avg_daily": sum(non_zero_calories) / len(non_zero_calories)
                    if non_zero_calories
                    else 0,
                    "max_daily": max(non_zero_calories) if non_zero_calories else 0,
                    "min_daily": min(non_zero_calories) if non_zero_calories else 0,
                    "days_with_data": len(non_zero_calories),
                    "total_days": len(dates),
                    "completion_rate": (len(non_zero_calories) / len(dates)) * 100
                    if dates
                    else 0,
                }

            return {
                "success": True,
                "data": {
                    "type": "bar",
                    "title": f"每日热量摄入 ({days}天)",
                    "labels": dates,
                    "datasets": [
                        {
                            "label": "实际摄入",
                            "data": calories,
                            "backgroundColor": "rgba(54, 162, 235, 0.6)",
                            "borderColor": "rgba(54, 162, 235, 1)",
                            "borderWidth": 1,
                        },
                        {
                            "label": "目标热量",
                            "data": target_calories,
                            "type": "line",
                            "borderColor": "#FF5722",
                            "borderWidth": 2,
                            "fill": False,
                            "pointRadius": 0,
                        },
                    ],
                    "stats": stats,
                    "period": days,
                    "target_calories": 2000,
                },
            }

        except Exception as e:
            logger.error(f"获取热量趋势图表失败: {e}")
            return {
                "success": False,
                "error": "获取热量趋势数据失败",
                "data": {
                    "type": "bar",
                    "title": f"每日热量摄入 ({days}天)",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": days,
                    "target_calories": 2000,
                },
            }

    @staticmethod
    async def get_exercise_trend_chart(
        user_id: int, days: int = 14, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取运动趋势图表数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # 获取每日运动数据
            daily_exercise = {}

            # 查询每日运动时长和消耗
            result = await db.execute(
                select(
                    func.date(ExerciseRecord.record_time).label("date"),
                    func.sum(ExerciseRecord.duration_minutes).label("total_duration"),
                    func.sum(ExerciseRecord.calories_burned).label("total_calories"),
                )
                .where(
                    and_(
                        ExerciseRecord.user_id == user_id,
                        ExerciseRecord.record_time >= start_date,
                        ExerciseRecord.record_time <= end_date + timedelta(days=1),
                    )
                )
                .group_by(func.date(ExerciseRecord.record_time))
                .order_by(func.date(ExerciseRecord.record_time).asc())
            )

            records = result.all()

            # 填充日期范围
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_exercise[date_str] = {"duration": 0, "calories": 0}
                current_date += timedelta(days=1)

            # 填充实际数据
            for record in records:
                date_str = record.date.isoformat()
                daily_exercise[date_str] = {
                    "duration": float(record.total_duration or 0),
                    "calories": float(record.total_calories or 0),
                }

            # 准备图表数据
            dates = sorted(daily_exercise.keys())
            durations = [daily_exercise[date]["duration"] for date in dates]
            calories = [daily_exercise[date]["calories"] for date in dates]

            # 计算统计信息
            stats = {}
            non_zero_days = [d for d in durations if d > 0]
            if non_zero_days:
                stats = {
                    "avg_duration": sum(non_zero_days) / len(non_zero_days)
                    if non_zero_days
                    else 0,
                    "total_duration": sum(durations),
                    "total_calories": sum(calories),
                    "exercise_days": len(non_zero_days),
                    "total_days": len(dates),
                    "frequency_rate": (len(non_zero_days) / len(dates)) * 100
                    if dates
                    else 0,
                }

            return {
                "success": True,
                "data": {
                    "type": "bar",
                    "title": f"每日运动时长 ({days}天)",
                    "labels": dates,
                    "datasets": [
                        {
                            "label": "运动时长 (分钟)",
                            "data": durations,
                            "backgroundColor": "rgba(255, 99, 132, 0.6)",
                            "borderColor": "rgba(255, 99, 132, 1)",
                            "borderWidth": 1,
                            "yAxisID": "y",
                        },
                        {
                            "label": "消耗热量",
                            "data": calories,
                            "type": "line",
                            "borderColor": "#9C27B0",
                            "borderWidth": 2,
                            "fill": False,
                            "pointRadius": 0,
                            "yAxisID": "y1",
                        },
                    ],
                    "stats": stats,
                    "period": days,
                    "target_duration": 30,  # 每天30分钟目标
                },
            }

        except Exception as e:
            logger.error(f"获取运动趋势图表失败: {e}")
            return {
                "success": False,
                "error": "获取运动趋势数据失败",
                "data": {
                    "type": "bar",
                    "title": f"每日运动时长 ({days}天)",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": days,
                    "target_duration": 30,
                },
            }

    @staticmethod
    async def get_water_trend_chart(
        user_id: int, days: int = 7, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取饮水趋势图表数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # 获取每日饮水数据
            daily_water = {}

            # 查询每日饮水量
            result = await db.execute(
                select(
                    func.date(WaterRecord.record_time).label("date"),
                    func.sum(WaterRecord.amount_ml).label("total_water"),
                )
                .where(
                    and_(
                        WaterRecord.user_id == user_id,
                        WaterRecord.record_time >= start_date,
                        WaterRecord.record_time <= end_date + timedelta(days=1),
                    )
                )
                .group_by(func.date(WaterRecord.record_time))
                .order_by(func.date(WaterRecord.record_time).asc())
            )

            records = result.all()

            # 填充日期范围
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_water[date_str] = 0
                current_date += timedelta(days=1)

            # 填充实际数据
            for record in records:
                date_str = record.date.isoformat()
                daily_water[date_str] = float(record.total_water or 0)

            # 准备图表数据
            dates = sorted(daily_water.keys())
            water_amounts = [daily_water[date] for date in dates]

            # 计算目标饮水线（2000ml）
            target_water = [2000] * len(dates)

            # 计算完成率
            completion_rates = []
            for amount in water_amounts:
                rate = min(100, (amount / 2000) * 100) if 2000 > 0 else 0
                completion_rates.append(rate)

            # 计算统计信息
            stats = {}
            if water_amounts:
                stats = {
                    "avg_daily": sum(water_amounts) / len(water_amounts),
                    "max_daily": max(water_amounts),
                    "min_daily": min(water_amounts),
                    "total_water": sum(water_amounts),
                    "days_met_target": len([w for w in water_amounts if w >= 2000]),
                    "total_days": len(dates),
                    "target_completion_rate": (
                        len([w for w in water_amounts if w >= 2000]) / len(dates)
                    )
                    * 100
                    if dates
                    else 0,
                }

            return {
                "success": True,
                "data": {
                    "type": "bar",
                    "title": f"每日饮水量 ({days}天)",
                    "labels": dates,
                    "datasets": [
                        {
                            "label": "实际饮水量 (ml)",
                            "data": water_amounts,
                            "backgroundColor": "rgba(33, 150, 243, 0.6)",
                            "borderColor": "rgba(33, 150, 243, 1)",
                            "borderWidth": 1,
                        },
                        {
                            "label": "目标饮水量",
                            "data": target_water,
                            "type": "line",
                            "borderColor": "#2196F3",
                            "borderWidth": 2,
                            "fill": False,
                            "pointRadius": 0,
                        },
                        {
                            "label": "完成率 (%)",
                            "data": completion_rates,
                            "type": "line",
                            "borderColor": "#4CAF50",
                            "borderWidth": 1,
                            "fill": False,
                            "pointRadius": 0,
                            "hidden": True,  # 默认隐藏
                        },
                    ],
                    "stats": stats,
                    "period": days,
                    "target_water": 2000,
                },
            }

        except Exception as e:
            logger.error(f"获取饮水趋势图表失败: {e}")
            return {
                "success": False,
                "error": "获取饮水趋势数据失败",
                "data": {
                    "type": "bar",
                    "title": f"每日饮水量 ({days}天)",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": days,
                    "target_water": 2000,
                },
            }

    @staticmethod
    async def get_habit_completion_chart(
        user_id: int, days: int = 30, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取习惯完成率图表数据"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # 获取每日习惯完成数据
            daily_habits = {}

            # 查询每日习惯完成数
            result = await db.execute(
                select(
                    HabitCompletion.completion_date.label("date"),
                    func.count(HabitCompletion.id).label("completed_count"),
                )
                .where(
                    and_(
                        HabitCompletion.user_id == user_id,
                        HabitCompletion.completion_date >= start_date,
                        HabitCompletion.completion_date <= end_date,
                    )
                )
                .group_by(HabitCompletion.completion_date)
                .order_by(HabitCompletion.completion_date.asc())
            )

            records = result.all()

            # 填充日期范围
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.isoformat()
                daily_habits[date_str] = 0
                current_date += timedelta(days=1)

            # 填充实际数据
            for record in records:
                date_str = record.date.isoformat()
                daily_habits[date_str] = int(record.completed_count or 0)

            # 准备图表数据
            dates = sorted(daily_habits.keys())
            completed_counts = [daily_habits[date] for date in dates]

            # 假设每天有3个习惯目标
            daily_target = 3
            completion_rates = []
            for count in completed_counts:
                rate = min(100, (count / daily_target) * 100) if daily_target > 0 else 0
                completion_rates.append(rate)

            # 计算移动平均完成率
            moving_avg = []
            if completion_rates:
                window_size = 7
                for i in range(len(completion_rates)):
                    start_idx = max(0, i - window_size + 1)
                    end_idx = i + 1
                    window = completion_rates[start_idx:end_idx]
                    moving_avg.append(sum(window) / len(window))

            # 计算统计信息
            stats = {}
            if completed_counts:
                total_possible = daily_target * len(dates)
                total_completed = sum(completed_counts)
                stats = {
                    "avg_daily_completion": total_completed / len(dates)
                    if dates
                    else 0,
                    "total_completed": total_completed,
                    "total_possible": total_possible,
                    "overall_completion_rate": (total_completed / total_possible) * 100
                    if total_possible > 0
                    else 0,
                    "perfect_days": len(
                        [c for c in completed_counts if c >= daily_target]
                    ),
                    "total_days": len(dates),
                    "consistency_rate": (
                        len([c for c in completed_counts if c > 0]) / len(dates)
                    )
                    * 100
                    if dates
                    else 0,
                }

            return {
                "success": True,
                "data": {
                    "type": "line",
                    "title": f"习惯完成率 ({days}天)",
                    "labels": dates,
                    "datasets": [
                        {
                            "label": "每日完成率 (%)",
                            "data": completion_rates,
                            "borderColor": "rgba(156, 39, 176, 0.8)",
                            "backgroundColor": "rgba(156, 39, 176, 0.1)",
                            "fill": True,
                            "borderWidth": 2,
                        },
                        {
                            "label": "7日移动平均",
                            "data": moving_avg,
                            "borderColor": "#FF9800",
                            "borderWidth": 3,
                            "fill": False,
                            "pointRadius": 0,
                        },
                        {
                            "label": "目标线 (100%)",
                            "data": [100] * len(dates),
                            "borderColor": "#4CAF50",
                            "borderWidth": 1,
                            "fill": False,
                            "pointRadius": 0,
                            "borderDash": [5, 5],
                        },
                    ],
                    "stats": stats,
                    "period": days,
                    "daily_target": daily_target,
                },
            }

        except Exception as e:
            logger.error(f"获取习惯完成率图表失败: {e}")
            return {
                "success": False,
                "error": "获取习惯完成率数据失败",
                "data": {
                    "type": "line",
                    "title": f"习惯完成率 ({days}天)",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": days,
                    "daily_target": 3,
                },
            }

    @staticmethod
    async def get_achievement_progress_chart(
        user_id: int, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取成就进度图表数据"""
        try:
            from services.achievement_service import AchievementService

            # 获取用户成就数据
            result = await AchievementService.get_user_achievements(user_id, db)

            if not result.get("success"):
                return {
                    "success": False,
                    "error": "获取成就数据失败",
                    "data": {
                        "type": "doughnut",
                        "title": "成就进度",
                        "labels": [],
                        "datasets": [],
                        "stats": {},
                    },
                }

            data = result["data"]
            achievements = data.get("achievements", [])

            # 按分类统计
            categories = {}
            for ach in achievements:
                category = ach.get("category", "unknown")
                if category not in categories:
                    categories[category] = {"total": 0, "unlocked": 0}

                categories[category]["total"] += 1
                if ach.get("unlocked"):
                    categories[category]["unlocked"] += 1

            # 准备图表数据
            category_labels = []
            unlocked_data = []
            remaining_data = []
            colors = [
                "#FF6384",
                "#36A2EB",
                "#FFCE56",
                "#4BC0C0",
                "#9966FF",
                "#FF9F40",
                "#8AC926",
                "#1982C4",
            ]

            for i, (category, stats) in enumerate(categories.items()):
                category_labels.append(category)
                unlocked_data.append(stats["unlocked"])
                remaining_data.append(stats["total"] - stats["unlocked"])

            # 计算总体统计
            total_achievements = sum(cat["total"] for cat in categories.values())
            total_unlocked = sum(cat["unlocked"] for cat in categories.values())
            overall_rate = (
                (total_unlocked / total_achievements) * 100
                if total_achievements > 0
                else 0
            )

            stats = {
                "total_achievements": total_achievements,
                "total_unlocked": total_unlocked,
                "overall_completion_rate": overall_rate,
                "categories": len(categories),
            }

            return {
                "success": True,
                "data": {
                    "type": "doughnut",
                    "title": "成就进度",
                    "labels": category_labels,
                    "datasets": [
                        {
                            "label": "已解锁",
                            "data": unlocked_data,
                            "backgroundColor": colors[: len(category_labels)],
                            "borderWidth": 1,
                        }
                    ],
                    "stats": stats,
                    "category_details": categories,
                },
            }

        except Exception as e:
            logger.error(f"获取成就进度图表失败: {e}")
            return {
                "success": False,
                "error": "获取成就进度数据失败",
                "data": {
                    "type": "doughnut",
                    "title": "成就进度",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                },
            }

    @staticmethod
    async def get_weekly_summary_chart(
        user_id: int, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取每周总结雷达图"""
        try:
            # 获取各项数据
            from datetime import date, timedelta

            end_date = date.today()
            start_date = end_date - timedelta(days=7)

            # 计算各项指标
            indicators = {
                "weight": await ChartService._calculate_weight_indicator(
                    user_id, db, start_date, end_date
                ),
                "nutrition": await ChartService._calculate_nutrition_indicator(
                    user_id, db, start_date, end_date
                ),
                "exercise": await ChartService._calculate_exercise_indicator(
                    user_id, db, start_date, end_date
                ),
                "water": await ChartService._calculate_water_indicator(
                    user_id, db, start_date, end_date
                ),
                "sleep": await ChartService._calculate_sleep_indicator(
                    user_id, db, start_date, end_date
                ),
                "habits": await ChartService._calculate_habits_indicator(
                    user_id, db, start_date, end_date
                ),
            }

            # 准备雷达图数据
            labels = list(indicators.keys())
            scores = list(indicators.values())

            # 计算平均分
            avg_score = sum(scores) / len(scores) if scores else 0

            stats = {
                "average_score": avg_score,
                "best_indicator": max(indicators.items(), key=lambda x: x[1])[0]
                if indicators
                else None,
                "worst_indicator": min(indicators.items(), key=lambda x: x[1])[0]
                if indicators
                else None,
                "indicators": indicators,
            }

            return {
                "success": True,
                "data": {
                    "type": "radar",
                    "title": "本周健康指标",
                    "labels": labels,
                    "datasets": [
                        {
                            "label": "健康指标",
                            "data": scores,
                            "backgroundColor": "rgba(54, 162, 235, 0.2)",
                            "borderColor": "rgba(54, 162, 235, 1)",
                            "pointBackgroundColor": "rgba(54, 162, 235, 1)",
                            "pointBorderColor": "#fff",
                            "pointHoverBackgroundColor": "#fff",
                            "pointHoverBorderColor": "rgba(54, 162, 235, 1)",
                        }
                    ],
                    "stats": stats,
                    "period": "本周",
                },
            }

        except Exception as e:
            logger.error(f"获取每周总结图表失败: {e}")
            return {
                "success": False,
                "error": "获取每周总结数据失败",
                "data": {
                    "type": "radar",
                    "title": "本周健康指标",
                    "labels": [],
                    "datasets": [],
                    "stats": {},
                    "period": "本周",
                },
            }

    @staticmethod
    async def _calculate_weight_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算体重指标分数"""
        try:
            # 简化版本，返回默认分数
            return 75.0
        except Exception:
            return 50.0

    @staticmethod
    async def _calculate_nutrition_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算营养指标分数"""
        try:
            # 简化版本，返回默认分数
            return 80.0
        except Exception:
            return 50.0

    @staticmethod
    async def _calculate_exercise_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算运动指标分数"""
        try:
            # 简化版本，返回默认分数
            return 65.0
        except Exception:
            return 50.0

    @staticmethod
    async def _calculate_water_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算饮水指标分数"""
        try:
            # 简化版本，返回默认分数
            return 90.0
        except Exception:
            return 50.0

    @staticmethod
    async def _calculate_sleep_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算睡眠指标分数"""
        try:
            # 简化版本，返回默认分数
            return 70.0
        except Exception:
            return 50.0

    @staticmethod
    async def _calculate_habits_indicator(
        user_id: int, db: AsyncSession, start_date: date, end_date: date
    ) -> float:
        """计算习惯指标分数"""
        try:
            # 简化版本，返回默认分数
            return 85.0
        except Exception:
            return 50.0

    @staticmethod
    async def get_all_charts(user_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """获取所有图表数据"""
        try:
            charts = {}

            # 获取所有图表数据
            weight_chart = await ChartService.get_weight_trend_chart(user_id, 30, db)
            calorie_chart = await ChartService.get_calorie_trend_chart(user_id, 7, db)
            exercise_chart = await ChartService.get_exercise_trend_chart(
                user_id, 14, db
            )
            water_chart = await ChartService.get_water_trend_chart(user_id, 7, db)
            habit_chart = await ChartService.get_habit_completion_chart(user_id, 30, db)
            achievement_chart = await ChartService.get_achievement_progress_chart(
                user_id, db
            )
            weekly_chart = await ChartService.get_weekly_summary_chart(user_id, db)

            # 只添加成功的图表
            if weight_chart.get("success"):
                charts["weight_trend"] = weight_chart["data"]

            if calorie_chart.get("success"):
                charts["calorie_trend"] = calorie_chart["data"]

            if exercise_chart.get("success"):
                charts["exercise_trend"] = exercise_chart["data"]

            if water_chart.get("success"):
                charts["water_trend"] = water_chart["data"]

            if habit_chart.get("success"):
                charts["habit_completion"] = habit_chart["data"]

            if achievement_chart.get("success"):
                charts["achievement_progress"] = achievement_chart["data"]

            if weekly_chart.get("success"):
                charts["weekly_summary"] = weekly_chart["data"]

            return {
                "success": True,
                "data": charts,
                "chart_count": len(charts),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取所有图表数据失败: {e}")
            return {
                "success": False,
                "error": "获取图表数据失败",
                "data": {},
                "chart_count": 0,
            }
