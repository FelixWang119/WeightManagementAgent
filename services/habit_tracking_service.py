"""
习惯打卡服务
提供连续打卡统计、习惯养成可视化、打卡热力图
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, distinct, Date
from collections import defaultdict

from models.database import (
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    MealType,
)


class CheckinType:
    """打卡类型常量"""

    WEIGHT = "weight"  # 体重打卡
    BREAKFAST = "breakfast"  # 早餐打卡
    LUNCH = "lunch"  # 午餐打卡
    DINNER = "dinner"  # 晚餐打卡
    SNACK = "snack"  # 加餐打卡
    EXERCISE = "exercise"  # 运动打卡
    WATER = "water"  # 饮水打卡
    SLEEP = "sleep"  # 睡眠打卡


class HabitTrackingService:
    """习惯打卡追踪服务"""

    @staticmethod
    async def get_streak_stats(
        user_id: int, days: int = 90, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取用户各维度的连续打卡统计

        Args:
            user_id: 用户ID
            days: 分析天数（默认90天）
            db: 数据库会话

        Returns:
            各维度的连续打卡统计
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取各维度的打卡日期
        checkin_dates = await HabitTrackingService._get_all_checkin_dates(
            user_id, start_date, end_date, db
        )

        # 计算各维度的连续打卡
        streaks = {}
        for checkin_type, dates in checkin_dates.items():
            streak_info = HabitTrackingService._calculate_streak(dates)
            streaks[checkin_type] = {
                "current_streak": streak_info["current"],
                "max_streak": streak_info["max"],
                "total_days": len(dates),
                "completion_rate": round(len(dates) / days * 100, 1),
                "last_checkin": max(dates).isoformat() if dates else None,
            }

        # 计算综合打卡统计
        all_dates = set()
        for dates in checkin_dates.values():
            all_dates.update(dates)

        overall_streak = HabitTrackingService._calculate_streak(sorted(all_dates))

        # 活跃天数（有任何记录的天数）
        active_dates = set()
        for checkin_type, dates in checkin_dates.items():
            if checkin_type in [
                CheckinType.WEIGHT,
                CheckinType.EXERCISE,
                CheckinType.SLEEP,
            ]:
                active_dates.update(dates)

        return {
            "success": True,
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "overall": {
                "any_record_days": len(all_dates),
                "active_days": len(active_dates),
                "current_streak": overall_streak["current"],
                "max_streak": overall_streak["max"],
                "activity_rate": round(len(active_dates) / days * 100, 1),
            },
            "streaks": streaks,
            "summary": HabitTrackingService._generate_streak_summary(streaks),
        }

    @staticmethod
    async def get_checkin_heatmap(
        user_id: int, year: int = None, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取打卡热力图数据

        Args:
            user_id: 用户ID
            year: 年份（默认当前年）
            db: 数据库会话

        Returns:
            热力图数据（GitHub风格）
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        if year is None:
            year = date.today().year

        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # 获取所有打卡日期
        checkin_dates = await HabitTrackingService._get_all_checkin_dates(
            user_id, start_date, end_date, db
        )

        # 构建热力图数据
        heatmap_data = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.isoformat()

            # 统计该日期的打卡类型数
            checkin_count = 0
            checkin_types = []

            for checkin_type, dates in checkin_dates.items():
                if current_date in dates:
                    checkin_count += 1
                    checkin_types.append(checkin_type)

            # 确定热力等级
            if checkin_count == 0:
                level = 0
            elif checkin_count <= 2:
                level = 1
            elif checkin_count <= 4:
                level = 2
            elif checkin_count <= 6:
                level = 3
            else:
                level = 4

            heatmap_data.append(
                {
                    "date": date_str,
                    "count": checkin_count,
                    "level": level,
                    "types": checkin_types,
                }
            )

            current_date += timedelta(days=1)

        # 统计信息
        total_checkins = sum(d["count"] for d in heatmap_data)
        active_days = sum(1 for d in heatmap_data if d["count"] > 0)

        # 按月份分组
        months_data = defaultdict(list)
        for d in heatmap_data:
            month = d["date"][:7]  # YYYY-MM
            months_data[month].append(d)

        return {
            "success": True,
            "year": year,
            "summary": {
                "total_checkins": total_checkins,
                "active_days": active_days,
                "total_days": len(heatmap_data),
            },
            "heatmap": heatmap_data,
            "by_month": dict(months_data),
        }

    @staticmethod
    async def get_habit_progress(
        user_id: int, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取习惯养成进度

        分析用户各健康习惯的养成情况
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        # 获取最近30天的数据
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        checkin_dates = await HabitTrackingService._get_all_checkin_dates(
            user_id, start_date, end_date, db
        )

        # 定义习惯目标
        habits = {
            "daily_weight": {
                "name": "每日称重",
                "target_days": 30,
                "actual_days": len(checkin_dates.get(CheckinType.WEIGHT, [])),
                "icon": "⚖️",
                "description": "每天记录体重变化",
            },
            "regular_meals": {
                "name": "规律三餐",
                "target_days": 30,
                "actual_days": min(
                    len(checkin_dates.get(CheckinType.BREAKFAST, [])),
                    len(checkin_dates.get(CheckinType.LUNCH, [])),
                    len(checkin_dates.get(CheckinType.DINNER, [])),
                ),
                "icon": "🍽️",
                "description": "每天记录早餐、午餐和晚餐",
            },
            "daily_exercise": {
                "name": "每日运动",
                "target_days": 30,
                "actual_days": len(checkin_dates.get(CheckinType.EXERCISE, [])),
                "icon": "🏃",
                "description": "每天进行运动打卡",
            },
            "water_goal": {
                "name": "饮水达标",
                "target_days": 30,
                "actual_days": len(checkin_dates.get(CheckinType.WATER, [])),
                "icon": "💧",
                "description": "每天记录饮水量",
            },
            "sleep_record": {
                "name": "睡眠记录",
                "target_days": 30,
                "actual_days": len(checkin_dates.get(CheckinType.SLEEP, [])),
                "icon": "😴",
                "description": "每天记录睡眠情况",
            },
        }

        # 计算进度
        for habit_id, habit in habits.items():
            progress = min(
                100, round(habit["actual_days"] / habit["target_days"] * 100)
            )
            habit["progress"] = progress

            if progress >= 80:
                habit["status"] = "excellent"
                habit["status_text"] = "习惯已养成"
            elif progress >= 50:
                habit["status"] = "good"
                habit["status_text"] = "正在养成中"
            elif progress >= 20:
                habit["status"] = "developing"
                habit["status_text"] = "需要加强"
            else:
                habit["status"] = "weak"
                habit["status_text"] = "尚未开始"

        # 计算综合习惯评分
        total_progress = sum(h["progress"] for h in habits.values())
        avg_progress = round(total_progress / len(habits))

        # 连续打卡天数（有任何记录）
        all_dates = set()
        for dates in checkin_dates.values():
            all_dates.update(dates)
        streak_info = HabitTrackingService._calculate_streak(sorted(all_dates))

        return {
            "success": True,
            "period": "最近30天",
            "overall_score": avg_progress,
            "current_streak": streak_info["current"],
            "habits": habits,
            "recommendations": HabitTrackingService._generate_habit_recommendations(
                habits
            ),
        }

    @staticmethod
    async def get_recent_checkins(
        user_id: int, limit: int = 10, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取最近打卡记录

        Args:
            user_id: 用户ID
            limit: 返回数量
            db: 数据库会话

        Returns:
            最近打卡记录列表
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        checkins = []

        # 最近体重记录
        weight_result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(limit)
        )
        for record in weight_result.scalars():
            checkins.append(
                {
                    "type": CheckinType.WEIGHT,
                    "type_name": "体重记录",
                    "icon": "⚖️",
                    "date": record.record_time.date().isoformat(),
                    "time": record.record_time.strftime("%H:%M"),
                    "content": f"{record.weight}kg",
                    "record_time": record.record_time.isoformat(),
                }
            )

        # 最近餐食记录
        meal_result = await db.execute(
            select(MealRecord)
            .where(MealRecord.user_id == user_id)
            .order_by(MealRecord.record_time.desc())
            .limit(limit)
        )
        meal_names = {
            MealType.BREAKFAST: ("早餐", "🌅"),
            MealType.LUNCH: ("午餐", "☀️"),
            MealType.DINNER: ("晚餐", "🌙"),
            MealType.SNACK: ("加餐", "🍿"),
        }
        for record in meal_result.scalars():
            meal_name, icon = meal_names.get(record.meal_type, ("餐食", "🍽️"))
            checkins.append(
                {
                    "type": record.meal_type.value,
                    "type_name": meal_name,
                    "icon": icon,
                    "date": record.record_time.date().isoformat(),
                    "time": record.record_time.strftime("%H:%M"),
                    "content": f"{record.total_calories} kcal",
                    "record_time": record.record_time.isoformat(),
                }
            )

        # 最近运动记录
        exercise_result = await db.execute(
            select(ExerciseRecord)
            .where(ExerciseRecord.user_id == user_id)
            .order_by(ExerciseRecord.record_time.desc())
            .limit(limit)
        )
        for record in exercise_result.scalars():
            checkins.append(
                {
                    "type": CheckinType.EXERCISE,
                    "type_name": "运动打卡" if record.is_checkin else "运动记录",
                    "icon": "🏃",
                    "date": (
                        record.checkin_date or record.record_time.date()
                    ).isoformat(),
                    "time": record.record_time.strftime("%H:%M"),
                    "content": f"{record.exercise_type} {record.duration_minutes}分钟",
                    "record_time": record.record_time.isoformat(),
                }
            )

        # 最近饮水记录
        water_result = await db.execute(
            select(WaterRecord)
            .where(WaterRecord.user_id == user_id)
            .order_by(WaterRecord.record_time.desc())
            .limit(limit)
        )
        for record in water_result.scalars():
            checkins.append(
                {
                    "type": CheckinType.WATER,
                    "type_name": "饮水记录",
                    "icon": "💧",
                    "date": record.record_time.date().isoformat(),
                    "time": record.record_time.strftime("%H:%M"),
                    "content": f"{record.amount_ml}ml",
                    "record_time": record.record_time.isoformat(),
                }
            )

        # 最近睡眠记录
        sleep_result = await db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id)
            .order_by(SleepRecord.bed_time.desc())
            .limit(limit)
        )
        for record in sleep_result.scalars():
            duration_hours = round(record.total_minutes / 60, 1)
            checkins.append(
                {
                    "type": CheckinType.SLEEP,
                    "type_name": "睡眠记录",
                    "icon": "😴",
                    "date": record.bed_time.date().isoformat(),
                    "time": record.bed_time.strftime("%H:%M"),
                    "content": f"{duration_hours}小时",
                    "record_time": record.bed_time.isoformat(),
                }
            )

        # 按时间排序并限制数量
        checkins.sort(key=lambda x: x["record_time"], reverse=True)
        checkins = checkins[:limit]

        return {"success": True, "count": len(checkins), "checkins": checkins}

    # ============ 私有辅助方法 ============

    @staticmethod
    async def _get_all_checkin_dates(
        user_id: int, start_date: date, end_date: date, db: AsyncSession
    ) -> Dict[str, Set[date]]:
        """获取所有维度的打卡日期"""
        checkin_dates = {
            CheckinType.WEIGHT: set(),
            CheckinType.BREAKFAST: set(),
            CheckinType.LUNCH: set(),
            CheckinType.DINNER: set(),
            CheckinType.SNACK: set(),
            CheckinType.EXERCISE: set(),
            CheckinType.WATER: set(),
            CheckinType.SLEEP: set(),
        }

        # 体重记录
        weight_result = await db.execute(
            select(func.date(WeightRecord.record_time).label("record_date"))
            .where(
                and_(
                    WeightRecord.user_id == user_id,
                    func.date(WeightRecord.record_time) >= start_date,
                    func.date(WeightRecord.record_time) <= end_date,
                )
            )
            .distinct()
        )
        checkin_dates[CheckinType.WEIGHT] = {row.record_date for row in weight_result}

        # 餐食记录（按类型分组）
        meal_result = await db.execute(
            select(
                MealRecord.meal_type,
                func.date(MealRecord.record_time).label("record_date"),
            )
            .where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) >= start_date,
                    func.date(MealRecord.record_time) <= end_date,
                )
            )
            .distinct()
        )
        for row in meal_result:
            if row.meal_type == MealType.BREAKFAST:
                checkin_dates[CheckinType.BREAKFAST].add(row.record_date)
            elif row.meal_type == MealType.LUNCH:
                checkin_dates[CheckinType.LUNCH].add(row.record_date)
            elif row.meal_type == MealType.DINNER:
                checkin_dates[CheckinType.DINNER].add(row.record_date)
            elif row.meal_type == MealType.SNACK:
                checkin_dates[CheckinType.SNACK].add(row.record_date)

        # 运动记录
        exercise_result = await db.execute(
            select(
                func.coalesce(
                    ExerciseRecord.checkin_date, func.date(ExerciseRecord.record_time)
                ).label("record_date")
            )
            .where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.coalesce(
                        ExerciseRecord.checkin_date,
                        func.date(ExerciseRecord.record_time),
                    )
                    >= start_date,
                    func.coalesce(
                        ExerciseRecord.checkin_date,
                        func.date(ExerciseRecord.record_time),
                    )
                    <= end_date,
                )
            )
            .distinct()
        )
        checkin_dates[CheckinType.EXERCISE] = {
            row.record_date for row in exercise_result
        }

        # 饮水记录
        water_result = await db.execute(
            select(func.date(WaterRecord.record_time).label("record_date"))
            .where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) >= start_date,
                    func.date(WaterRecord.record_time) <= end_date,
                )
            )
            .distinct()
        )
        checkin_dates[CheckinType.WATER] = {row.record_date for row in water_result}

        # 睡眠记录
        sleep_result = await db.execute(
            select(func.date(SleepRecord.bed_time).label("record_date"))
            .where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.bed_time) >= start_date,
                    func.date(SleepRecord.bed_time) <= end_date,
                )
            )
            .distinct()
        )
        checkin_dates[CheckinType.SLEEP] = {row.record_date for row in sleep_result}

        return checkin_dates

    @staticmethod
    def _calculate_streak(dates: List[date]) -> Dict[str, int]:
        """
        计算连续打卡天数

        Args:
            dates: 打卡日期列表（已排序）

        Returns:
            current: 当前连续天数
            max: 最大连续天数
        """
        if not dates:
            return {"current": 0, "max": 0}

        if isinstance(dates, set):
            dates = sorted(dates)

        today = date.today()
        yesterday = today - timedelta(days=1)

        # 计算当前连续天数
        current_streak = 0
        if dates[-1] == today or dates[-1] == yesterday:
            current_streak = 1
            for i in range(len(dates) - 2, -1, -1):
                if (dates[i + 1] - dates[i]).days == 1:
                    current_streak += 1
                else:
                    break

        # 计算最大连续天数
        max_streak = 0
        current_max = 1

        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                current_max += 1
            else:
                max_streak = max(max_streak, current_max)
                current_max = 1

        max_streak = max(max_streak, current_max)

        return {"current": current_streak, "max": max_streak}

    @staticmethod
    def _generate_streak_summary(streaks: Dict) -> List[str]:
        """生成连续打卡摘要"""
        summary = []

        # 找出表现最好的习惯
        best_habits = sorted(
            [(k, v) for k, v in streaks.items() if v["current_streak"] > 0],
            key=lambda x: x[1]["current_streak"],
            reverse=True,
        )

        if best_habits:
            best = best_habits[0]
            type_names = {
                CheckinType.WEIGHT: "体重记录",
                CheckinType.BREAKFAST: "早餐打卡",
                CheckinType.LUNCH: "午餐打卡",
                CheckinType.DINNER: "晚餐打卡",
                CheckinType.SNACK: "加餐记录",
                CheckinType.EXERCISE: "运动打卡",
                CheckinType.WATER: "饮水记录",
                CheckinType.SLEEP: "睡眠记录",
            }
            summary.append(
                f"您已连续{type_names.get(best[0], best[0])}{best[1]['current_streak']}天，继续保持！"
            )

        # 找出需要改进的习惯
        weak_habits = [
            k
            for k, v in streaks.items()
            if v["current_streak"] == 0 and v["completion_rate"] < 30
        ]
        if weak_habits:
            summary.append(
                "建议关注："
                + "、".join([type_names.get(h, h) for h in weak_habits[:3]])
            )

        if not summary:
            summary.append("开始记录您的健康数据，养成好习惯！")

        return summary

    @staticmethod
    def _generate_habit_recommendations(habits: Dict) -> List[str]:
        """生成习惯养成建议"""
        recommendations = []

        # 检查薄弱环节
        weak_habits = [h for h in habits.values() if h["progress"] < 50]

        if weak_habits:
            weakest = min(weak_habits, key=lambda x: x["progress"])
            recommendations.append(
                f"建议优先养成「{weakest['name']}」习惯，{weakest['description']}"
            )

        # 表扬好习惯
        excellent_habits = [h for h in habits.values() if h["progress"] >= 80]
        if excellent_habits:
            habit_names = "、".join([h["name"] for h in excellent_habits])
            recommendations.append(f"您的「{habit_names}」习惯已养成，继续保持！")

        if not recommendations:
            recommendations.append("持续记录数据，健康习惯正在养成中！")

        return recommendations
