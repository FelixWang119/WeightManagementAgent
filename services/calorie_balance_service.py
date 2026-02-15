"""
热量平衡图表服务
提供每日热量摄入、消耗、平衡数据的聚合和图表生成
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date
import numpy as np

from models.database import MealRecord, ExerciseRecord, UserProfile, Goal, GoalStatus
from services.calorie_calculator import CalorieCalculator
from sqlalchemy import select


class CalorieBalanceService:
    """热量平衡图表服务类"""

    @staticmethod
    async def get_daily_calorie_data(
        user_id: int,
        days: int = 7,  # 默认获取最近7天数据
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """
        获取用户每日热量数据（摄入、消耗、平衡）

        Args:
            user_id: 用户ID
            days: 获取最近多少天的数据
            db: 数据库会话

        Returns:
            包含每日热量数据的字典
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        # 获取用户BMR/TDEE（用于计算基础消耗）
        # TODO: 考虑缓存用户BMR数据，避免每次查询
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()

        # 获取用户当前目标（用于获取每日热量目标）
        goal_result = await db.execute(
            select(Goal)
            .where(and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
        goal = goal_result.scalar_one_or_none()

        # 调试日志：检查查询结果
        print(
            f"DEBUG: User {user_id} profile query result - profile exists: {profile is not None}"
        )
        if profile:
            print(
                f"DEBUG: User {user_id} BMR value: {profile.bmr}, type: {type(profile.bmr)}"
            )

        print(
            f"DEBUG: User {user_id} goal query result - goal exists: {goal is not None}"
        )
        if goal:
            print(
                f"DEBUG: User {user_id} daily calorie target: {goal.daily_calorie_target}"
            )

        # 获取每日摄入热量（餐食记录）
        intake_query = (
            select(
                func.date(MealRecord.record_time).label("record_date"),
                func.sum(MealRecord.total_calories).label("total_calories"),
            )
            .where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) >= start_date,
                    func.date(MealRecord.record_time) <= end_date,
                )
            )
            .group_by(func.date(MealRecord.record_time))
        )

        intake_result = await db.execute(intake_query)
        intake_data = {row.record_date: row.total_calories for row in intake_result}

        # 获取每日消耗热量（运动记录）
        # 优先使用checkin_date字段（运动打卡专用），其次使用record_time
        exercise_query = (
            select(
                func.coalesce(
                    ExerciseRecord.checkin_date, func.date(ExerciseRecord.record_time)
                ).label("record_date"),
                func.sum(ExerciseRecord.calories_burned).label("calories_burned"),
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
            .group_by(
                func.coalesce(
                    ExerciseRecord.checkin_date, func.date(ExerciseRecord.record_time)
                )
            )
        )

        exercise_result = await db.execute(exercise_query)
        exercise_data = {
            row.record_date: row.calories_burned for row in exercise_result
        }

        # 构建每日数据
        daily_data = []
        current_date = start_date

        # 估算用户TDEE（如果没有BMR数据，使用默认值）
        bmr = None
        tdee = None

        # 检查用户是否真的有有效的BMR数据
        has_real_bmr_data = False

        if profile is not None and profile.bmr is not None:
            bmr_value = float(profile.bmr)
            # 只有当BMR是有效值（大于0）时才视为有真实数据
            # 不再检查是否为1500，因为1500可能也是用户真实测算的值
            if bmr_value > 0:
                has_real_bmr_data = True
                bmr = bmr_value
                tdee = CalorieCalculator.calculate_tdee(bmr, activity_level="light")
            else:
                # BMR值无效（小于等于0）
                has_real_bmr_data = False
                bmr = 1500
                tdee = 1800
        else:
            # 没有BMR数据
            has_real_bmr_data = False
            bmr = 1500
            tdee = 1800

        # 统一日期键格式（确保查询结果和当前日期匹配）
        intake_data = {
            date.fromisoformat(k) if isinstance(k, str) else k: v
            for k, v in intake_data.items()
        }
        exercise_data = {
            date.fromisoformat(k) if isinstance(k, str) else k: v
            for k, v in exercise_data.items()
        }

        while current_date <= end_date:
            date_str = current_date.isoformat()

            # 获取该日期的数据
            intake = intake_data.get(current_date, 0)
            exercise = exercise_data.get(current_date, 0)

            # 计算基础消耗（基于TDEE）
            base_burned = tdee if bmr else 1800

            # 总消耗 = 基础消耗 + 运动消耗
            total_burned = base_burned + exercise

            # 热量平衡 = 总消耗 - 摄入
            balance = total_burned - intake

            # 判断热量状态
            if balance > 300:
                status = "deficit"  # 热量赤字（减重）
            elif balance < -300:
                status = "surplus"  # 热量盈余（增重）
            else:
                status = "maintenance"  # 维持

            daily_data.append(
                {
                    "date": date_str,
                    "date_display": current_date.strftime("%m-%d"),
                    "intake": int(intake),
                    "base_burned": int(base_burned),
                    "exercise_burned": int(exercise),
                    "total_burned": int(total_burned),
                    "balance": int(balance),
                    "status": status,
                    "is_today": current_date == date.today(),
                    # 添加目标热量（如果有目标）
                    "target_calories": goal.daily_calorie_target if goal else None,
                    # 计算进度百分比（相对于目标）
                    "progress_percent": (
                        min(
                            100,
                            max(
                                0,
                                int(
                                    (goal.daily_calorie_target - intake)
                                    / goal.daily_calorie_target
                                    * 100
                                ),
                            ),
                        )
                        if goal
                        and goal.daily_calorie_target
                        and goal.daily_calorie_target > 0
                        else None
                    ),
                    # 添加详细说明，帮助用户理解数据含义
                    "explanation": {
                        "base_burned": "基础代谢消耗（身体维持基本功能所需）",
                        "exercise_burned": "运动消耗（通过运动打卡记录）",
                        "total_burned": "总消耗 = 基础代谢 + 运动消耗",
                        "target_calories": "每日热量目标（来自您的减重目标）",
                    },
                }
            )

            current_date += timedelta(days=1)

        # 计算统计数据
        total_intake = sum(d["intake"] for d in daily_data)
        total_burned = sum(d["total_burned"] for d in daily_data)
        avg_intake = int(total_intake / len(daily_data)) if daily_data else 0
        avg_burned = int(total_burned / len(daily_data)) if daily_data else 0
        net_balance = total_burned - total_intake

        # 计算趋势（最近3天 vs 之前3天）
        trend = "stable"
        if len(daily_data) >= 6:
            recent_intake = sum(d["intake"] for d in daily_data[-3:])
            previous_intake = sum(d["intake"] for d in daily_data[:3])

            if recent_intake < previous_intake * 0.9:
                trend = "decreasing"
            elif recent_intake > previous_intake * 1.1:
                trend = "increasing"

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "user_stats": {
                "bmr": bmr,
                "estimated_tdee": tdee,
                "has_bmr_data": has_real_bmr_data,
                "has_goal": goal is not None,
                "daily_calorie_target": goal.daily_calorie_target if goal else None,
                "goal_target_weight": goal.target_weight if goal else None,
                "goal_target_date": goal.target_date.isoformat()
                if goal and goal.target_date
                else None,
            },
            "daily_data": daily_data,
            "summary": {
                "total_intake": total_intake,
                "total_burned": total_burned,
                "avg_daily_intake": avg_intake,
                "avg_daily_burned": avg_burned,
                "net_balance": net_balance,
                "weekly_trend": trend,
                "deficit_days": sum(1 for d in daily_data if d["status"] == "deficit"),
                "surplus_days": sum(1 for d in daily_data if d["status"] == "surplus"),
            },
        }

    @staticmethod
    async def get_calorie_balance_chart_data(
        user_id: int,
        chart_type: str = "daily",  # daily, weekly, monthly
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """
        获取图表格式的热量平衡数据

        Args:
            user_id: 用户ID
            chart_type: 图表类型（daily, weekly, monthly）
            db: 数据库会话

        Returns:
            图表数据（适合Chart.js等图表库）
        """
        # 根据图表类型确定天数
        days_map = {
            "daily": 7,  # 最近7天（每日）
            "weekly": 28,  # 最近4周（每周）
            "monthly": 90,  # 最近3个月（每月）
        }

        days = days_map.get(chart_type, 7)
        daily_data = await CalorieBalanceService.get_daily_calorie_data(
            user_id, days, db
        )

        if not daily_data.get("success"):
            return daily_data

        # 根据图表类型聚合数据
        if chart_type == "daily":
            # 每日数据直接使用
            chart_labels = [d["date_display"] for d in daily_data["daily_data"]]
            intake_data = [d["intake"] for d in daily_data["daily_data"]]
            burned_data = [d["total_burned"] for d in daily_data["daily_data"]]
            balance_data = [d["balance"] for d in daily_data["daily_data"]]

        elif chart_type == "weekly":
            # 按周聚合（最近4周）
            weekly_data = []
            current_date = date.today()

            for week in range(4):
                week_end = current_date - timedelta(days=week * 7)
                week_start = week_end - timedelta(days=6)

                week_intake = 0
                week_burned = 0

                for day_data in daily_data["daily_data"]:
                    day_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()
                    if week_start <= day_date <= week_end:
                        week_intake += day_data["intake"]
                        week_burned += day_data["total_burned"]

                weekly_data.append(
                    {
                        "week": f"W{4 - week}",
                        "intake": week_intake,
                        "burned": week_burned,
                        "balance": week_burned - week_intake,
                    }
                )

            chart_labels = [w["week"] for w in weekly_data]
            intake_data = [w["intake"] for w in weekly_data]
            burned_data = [w["burned"] for w in weekly_data]
            balance_data = [w["balance"] for w in weekly_data]

        else:  # monthly
            # 按月聚合（最近3个月）
            monthly_data = []
            current_date = date.today()

            for month in range(3):
                month_date = current_date.replace(day=1)  # 当月第一天
                month_date = month_date - timedelta(days=month * 30)  # 近似每月30天

                month_intake = 0
                month_burned = 0
                days_in_month = 0

                for day_data in daily_data["daily_data"]:
                    day_date = datetime.strptime(day_data["date"], "%Y-%m-%d").date()
                    if (
                        day_date.year == month_date.year
                        and day_date.month == month_date.month
                    ):
                        month_intake += day_data["intake"]
                        month_burned += day_data["total_burned"]
                        days_in_month += 1

                if days_in_month > 0:
                    # 按天数平均，然后乘以30得到月度估算
                    avg_daily_intake = month_intake / days_in_month
                    avg_daily_burned = month_burned / days_in_month

                    monthly_data.append(
                        {
                            "month": month_date.strftime("%Y-%m"),
                            "intake": int(avg_daily_intake * 30),
                            "burned": int(avg_daily_burned * 30),
                            "balance": int(
                                avg_daily_burned * 30 - avg_daily_intake * 30
                            ),
                        }
                    )

            chart_labels = [m["month"] for m in monthly_data]
            intake_data = [m["intake"] for m in monthly_data]
            burned_data = [m["burned"] for m in monthly_data]
            balance_data = [m["balance"] for m in monthly_data]

        # 构建Chart.js格式的数据
        chart_datasets = [
            {
                "label": "热量摄入",
                "data": intake_data,
                "backgroundColor": "rgba(255, 99, 132, 0.5)",
                "borderColor": "rgba(255, 99, 132, 1)",
                "borderWidth": 2,
            },
            {
                "label": "热量消耗",
                "data": burned_data,
                "backgroundColor": "rgba(54, 162, 235, 0.5)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 2,
            },
            {
                "label": "热量平衡",
                "data": balance_data,
                "type": "line",  # 折线图
                "borderColor": "rgba(75, 192, 192, 1)",
                "backgroundColor": "rgba(75, 192, 192, 0.2)",
                "borderWidth": 3,
                "fill": False,
                "tension": 0.4,
            },
        ]

        return {
            "success": True,
            "chart_type": chart_type,
            "labels": chart_labels,
            "datasets": chart_datasets,
            "summary": daily_data["summary"],
            "period": daily_data["period"],
        }

    @staticmethod
    async def get_calorie_distribution(
        user_id: int, days: int = 7, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取热量来源分布（餐食类型、运动类型）
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        # 获取餐食类型分布
        meal_type_query = (
            select(
                MealRecord.meal_type,
                func.sum(MealRecord.total_calories).label("total_calories"),
            )
            .where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) >= start_date,
                    func.date(MealRecord.record_time) <= end_date,
                )
            )
            .group_by(MealRecord.meal_type)
        )

        meal_result = await db.execute(meal_type_query)
        meal_distribution = [
            {"type": row.meal_type.value, "calories": row.total_calories}
            for row in meal_result
        ]

        # 获取运动类型分布
        exercise_type_query = (
            select(
                ExerciseRecord.exercise_type,
                func.sum(ExerciseRecord.calories_burned).label("calories_burned"),
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
            .group_by(ExerciseRecord.exercise_type)
        )

        exercise_result = await db.execute(exercise_type_query)
        exercise_distribution = [
            {"type": row.exercise_type, "calories": row.calories_burned}
            for row in exercise_result
        ]

        # 计算总热量
        total_intake = sum(m["calories"] for m in meal_distribution)
        total_burned = sum(e["calories"] for e in exercise_distribution)

        # 构建饼图数据
        intake_labels = [m["type"] for m in meal_distribution]
        intake_data = [m["calories"] for m in meal_distribution]
        intake_colors = [
            "rgba(255, 99, 132, 0.7)",
            "rgba(255, 159, 64, 0.7)",
            "rgba(255, 205, 86, 0.7)",
            "rgba(75, 192, 192, 0.7)",
        ]

        exercise_labels = [e["type"] for e in exercise_distribution]
        exercise_data = [e["calories"] for e in exercise_distribution]
        exercise_colors = [
            "rgba(54, 162, 235, 0.7)",
            "rgba(153, 102, 255, 0.7)",
            "rgba(201, 203, 207, 0.7)",
            "rgba(255, 99, 132, 0.7)",
        ]

        return {
            "success": True,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "intake_distribution": {
                "total": total_intake,
                "data": meal_distribution,
                "chart_data": {
                    "labels": intake_labels,
                    "datasets": [
                        {
                            "data": intake_data,
                            "backgroundColor": intake_colors[: len(intake_labels)],
                        }
                    ],
                },
            },
            "exercise_distribution": {
                "total": total_burned,
                "data": exercise_distribution,
                "chart_data": {
                    "labels": exercise_labels,
                    "datasets": [
                        {
                            "data": exercise_data,
                            "backgroundColor": exercise_colors[: len(exercise_labels)],
                        }
                    ],
                },
            },
        }
