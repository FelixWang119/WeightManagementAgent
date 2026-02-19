"""
增强报告服务
支持月度报告生成、报告分享和导出功能
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, extract
from sqlalchemy.orm import selectinload
import json
import base64
from io import BytesIO

from models.database import (
    User,
    WeeklyReport,
    MonthlyReport,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    Goal,
    GoalStatus,
    UserProfile,
    HabitCompletion,
)
from services.chart_service import ChartService
from services.ai_service import ai_service
from config.logging_config import get_module_logger
from utils.exceptions import retry_on_error

logger = get_module_logger(__name__)


class ReportService:
    """增强报告服务"""

    @retry_on_error(max_attempts=3, delay=1.0)
    async def generate_monthly_report(
        self, user_id: int, month: Optional[date] = None, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """生成月度报告"""
        try:
            # 确定月份
            if month is None:
                month = date.today().replace(day=1)
            else:
                month = month.replace(day=1)

            month_start = month
            month_end = (month.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)

            # 检查是否已存在
            result = await db.execute(
                select(MonthlyReport).where(
                    and_(
                        MonthlyReport.user_id == user_id,
                        MonthlyReport.month_start == month_start,
                    )
                )
            )
            existing_report = result.scalar_one_or_none()

            # 收集月度数据
            data = await self._collect_monthly_data(user_id, month_start, month_end, db)

            # 生成 AI 月度分析
            ai_analysis = await self._generate_ai_monthly_analysis(data, user_id, db)

            # 保存或更新报告
            if existing_report:
                existing_report.summary_text = ai_analysis["summary"]
                existing_report.weight_change = data["weight_change"]
                existing_report.avg_weight = data["avg_weight"]
                existing_report.total_exercise_minutes = data["total_exercise_minutes"]
                existing_report.total_calories_in = data["total_calories_in"]
                existing_report.total_calories_out = data["total_calories_out"]
                existing_report.highlights = data["highlights"]
                existing_report.improvements = data["improvements"]
                existing_report.goals_progress = data["goals_progress"]
                existing_report.habit_stats = data["habit_stats"]
                report = existing_report
                message = "月度报告已更新"
            else:
                report = MonthlyReport(
                    user_id=user_id,
                    month_start=month_start,
                    summary_text=ai_analysis["summary"],
                    weight_change=data["weight_change"],
                    avg_weight=data["avg_weight"],
                    total_exercise_minutes=data["total_exercise_minutes"],
                    total_calories_in=data["total_calories_in"],
                    total_calories_out=data["total_calories_out"],
                    highlights=data["highlights"],
                    improvements=data["improvements"],
                    goals_progress=data["goals_progress"],
                    habit_stats=data["habit_stats"],
                    created_at=datetime.utcnow(),
                )
                db.add(report)
                message = "月度报告生成成功"

            await db.commit()

            return {
                "success": True,
                "message": message,
                "data": {
                    "month_start": month_start.isoformat(),
                    "month_end": month_end.isoformat(),
                    "summary": ai_analysis["summary"],
                    "highlights": data["highlights"],
                    "improvements": data["improvements"],
                    "statistics": {
                        "weight_change": data["weight_change"],
                        "avg_weight": data["avg_weight"],
                        "total_exercise_minutes": data["total_exercise_minutes"],
                        "total_calories_in": data["total_calories_in"],
                        "total_calories_out": data["total_calories_out"],
                        "exercise_days": data["exercise_days"],
                        "sleep_avg_hours": data["sleep_avg_hours"],
                        "water_goal_days": data["water_goal_days"],
                        "habit_completion_rate": data["habit_completion_rate"],
                    },
                    "goals_progress": data["goals_progress"],
                    "habit_stats": data["habit_stats"],
                    "charts": await self._generate_monthly_charts(
                        user_id, month_start, month_end, db
                    ),
                },
            }

        except Exception as e:
            logger.exception("生成月度报告失败: %s", e)
            return {"success": False, "error": "生成月度报告失败", "message": str(e)}

    async def _collect_monthly_data(
        self, user_id: int, month_start: date, month_end: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """收集月度数据"""
        data = {
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
        }

        # 体重数据
        result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date >= month_start,
                    WeightRecord.record_date <= month_end,
                )
            )
            .order_by(WeightRecord.record_date.asc())
        )
        weight_records = result.scalars().all()

        if weight_records:
            first_weight = weight_records[0].weight
            last_weight = weight_records[-1].weight
            data["weight_change"] = round(last_weight - first_weight, 2)
            data["avg_weight"] = round(
                sum(r.weight for r in weight_records) / len(weight_records), 2
            )
            data["weight_records"] = len(weight_records)
        else:
            data["weight_change"] = 0
            data["avg_weight"] = 0
            data["weight_records"] = 0

        # 饮食数据
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time
                    >= datetime.combine(month_start, datetime.min.time()),
                    MealRecord.record_time
                    <= datetime.combine(month_end, datetime.max.time()),
                )
            )
        )
        meal_records = result.scalars().all()

        daily_calories = {}
        for meal in meal_records:
            meal_date = meal.record_time.date().isoformat()
            if meal_date not in daily_calories:
                daily_calories[meal_date] = 0
            daily_calories[meal_date] += meal.total_calories

        data["total_calories_in"] = sum(daily_calories.values())
        data["avg_daily_calories"] = (
            int(data["total_calories_in"] / len(daily_calories))
            if daily_calories
            else 0
        )

        # 运动数据
        result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    ExerciseRecord.record_time
                    >= datetime.combine(month_start, datetime.min.time()),
                    ExerciseRecord.record_time
                    <= datetime.combine(month_end, datetime.max.time()),
                )
            )
        )
        exercise_records = result.scalars().all()

        data["exercise_days"] = len(set(r.record_time.date() for r in exercise_records))
        data["total_exercise_minutes"] = sum(
            r.duration_minutes for r in exercise_records
        )
        data["total_calories_out"] = sum(r.calories_burned for r in exercise_records)
        data["avg_daily_exercise"] = int(
            data["total_exercise_minutes"] / 30
        )  # 假设30天

        # 饮水数据
        result = await db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == user_id,
                    WaterRecord.record_time
                    >= datetime.combine(month_start, datetime.min.time()),
                    WaterRecord.record_time
                    <= datetime.combine(month_end, datetime.max.time()),
                )
            )
        )
        water_records = result.scalars().all()

        daily_water = {}
        for w in water_records:
            w_date = w.record_time.date().isoformat()
            if w_date not in daily_water:
                daily_water[w_date] = 0
            daily_water[w_date] += w.amount_ml

        data["water_goal_days"] = sum(1 for v in daily_water.values() if v >= 2000)
        data["total_water"] = sum(daily_water.values())

        # 睡眠数据
        result = await db.execute(
            select(SleepRecord).where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(month_start, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(month_end, datetime.max.time()),
                )
            )
        )
        sleep_records = result.scalars().all()

        if sleep_records:
            data["sleep_avg_hours"] = round(
                sum(r.total_minutes for r in sleep_records) / len(sleep_records) / 60, 1
            )
            data["sleep_days"] = len(sleep_records)
        else:
            data["sleep_avg_hours"] = 0
            data["sleep_days"] = 0

        # 习惯数据
        result = await db.execute(
            select(HabitCompletion).where(
                and_(
                    HabitCompletion.user_id == user_id,
                    HabitCompletion.completion_date >= month_start,
                    HabitCompletion.completion_date <= month_end,
                )
            )
        )
        habit_completions = result.scalars().all()

        daily_habits = {}
        for h in habit_completions:
            h_date = h.completion_date.isoformat()
            if h_date not in daily_habits:
                daily_habits[h_date] = 0
            daily_habits[h_date] += 1

        data["habit_completion_rate"] = (
            (len(daily_habits) / 30) * 100 if daily_habits else 0  # 假设30天
        )
        data["total_habits_completed"] = len(habit_completions)

        # 目标进度
        data["goals_progress"] = await self._get_goals_progress(
            user_id, month_start, month_end, db
        )

        # 习惯统计
        data["habit_stats"] = await self._get_habit_stats(
            user_id, month_start, month_end, db
        )

        # 生成亮点和改进点
        data["highlights"] = self._generate_highlights(data)
        data["improvements"] = self._generate_improvements(data)

        return data

    async def _get_goals_progress(
        self, user_id: int, month_start: date, month_end: date, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取目标进度"""
        goals_progress = []

        result = await db.execute(
            select(Goal).where(
                and_(
                    Goal.user_id == user_id,
                    Goal.status == GoalStatus.ACTIVE,
                    or_(Goal.end_date >= month_start, Goal.end_date.is_(None)),
                )
            )
        )
        goals = result.scalars().all()

        for goal in goals:
            if goal.target_weight:
                # 获取本月开始和结束的体重
                start_result = await db.execute(
                    select(WeightRecord)
                    .where(
                        and_(
                            WeightRecord.user_id == user_id,
                            WeightRecord.record_date >= month_start,
                            WeightRecord.record_date <= month_start + timedelta(days=7),
                        )
                    )
                    .order_by(WeightRecord.record_date.asc())
                    .limit(1)
                )
                start_weight_record = start_result.scalar_one_or_none()

                end_result = await db.execute(
                    select(WeightRecord)
                    .where(
                        and_(
                            WeightRecord.user_id == user_id,
                            WeightRecord.record_date >= month_end - timedelta(days=7),
                            WeightRecord.record_date <= month_end,
                        )
                    )
                    .order_by(WeightRecord.record_date.desc())
                    .limit(1)
                )
                end_weight_record = end_result.scalar_one_or_none()

                if start_weight_record and end_weight_record:
                    month_progress = (
                        start_weight_record.weight - end_weight_record.weight
                    )
                    total_progress = goal.start_weight - end_weight_record.weight
                    target_progress = goal.start_weight - goal.target_weight

                    goals_progress.append(
                        {
                            "goal_id": goal.id,
                            "goal_type": "weight_loss",
                            "description": f"减重到 {goal.target_weight}kg",
                            "month_progress": round(month_progress, 2),
                            "total_progress": round(total_progress, 2),
                            "target_progress": round(target_progress, 2),
                            "completion_rate": round(
                                (total_progress / target_progress) * 100, 1
                            )
                            if target_progress > 0
                            else 0,
                            "status": "on_track"
                            if month_progress > 0
                            else "needs_attention",
                        }
                    )

        return goals_progress

    async def _get_habit_stats(
        self, user_id: int, month_start: date, month_end: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """获取习惯统计"""
        result = await db.execute(
            select(HabitCompletion.checkin_type, func.count(HabitCompletion.id))
            .where(
                and_(
                    HabitCompletion.user_id == user_id,
                    HabitCompletion.completion_date >= month_start,
                    HabitCompletion.completion_date <= month_end,
                )
            )
            .group_by(HabitCompletion.checkin_type)
        )
        habit_counts = result.all()

        stats = {}
        for checkin_type, count in habit_counts:
            stats[checkin_type] = {
                "count": count,
                "avg_per_day": round(count / 30, 1),  # 假设30天
            }

        return stats

    def _generate_highlights(self, data: Dict[str, Any]) -> List[str]:
        """生成亮点"""
        highlights = []

        if data["weight_change"] < -1.0:
            highlights.append(f"本月减重 {abs(data['weight_change'])}kg，效果显著！")
        elif data["weight_change"] < -0.5:
            highlights.append(f"本月减重 {abs(data['weight_change'])}kg，继续保持！")

        if data["exercise_days"] >= 15:
            highlights.append(f"本月运动 {data['exercise_days']} 天，非常自律！")
        elif data["exercise_days"] >= 10:
            highlights.append(f"本月运动 {data['exercise_days']} 天，表现不错！")

        if data["water_goal_days"] >= 20:
            highlights.append(
                f"本月 {data['water_goal_days']} 天饮水达标，保持水分充足！"
            )

        if data["sleep_avg_hours"] >= 7:
            highlights.append(f"平均睡眠 {data['sleep_avg_hours']} 小时，休息充足！")

        if data["habit_completion_rate"] >= 70:
            highlights.append(
                f"习惯完成率 {data['habit_completion_rate']:.0f}%，养成好习惯！"
            )

        return highlights

    def _generate_improvements(self, data: Dict[str, Any]) -> List[str]:
        """生成改进点"""
        improvements = []

        if data["weight_change"] > 0.5:
            improvements.append("本月体重有所上升，注意控制饮食")

        if data["exercise_days"] < 10:
            improvements.append("运动频率偏低，建议增加运动量")

        if data["water_goal_days"] < 15:
            improvements.append("饮水量不足，建议多喝水")

        if data["sleep_avg_hours"] < 6.5:
            improvements.append("睡眠时间偏少，建议保证充足睡眠")

        if data["habit_completion_rate"] < 50:
            improvements.append("习惯完成率偏低，每天坚持一点点！")

        return improvements

    async def _generate_ai_monthly_analysis(
        self, data: Dict[str, Any], user_id: int, db: AsyncSession
    ) -> Dict[str, str]:
        """使用 AI 生成月度分析"""
        prompt = f"""请根据以下月度数据生成一份个性化的月度报告总结：

【月度数据】({data["month_start"]} 至 {data["month_end"]})
- 体重变化: {data["weight_change"]}kg (平均 {data["avg_weight"]}kg)
- 运动天数: {data["exercise_days"]} 天 (共 {data["total_exercise_minutes"]} 分钟)
- 消耗热量: {data["total_calories_out"]} 千卡
- 摄入热量: {data["total_calories_in"]} 千卡
- 饮水达标: {data["water_goal_days"]} 天
- 平均睡眠: {data["sleep_avg_hours"]} 小时
- 习惯完成率: {data["habit_completion_rate"]:.1f}%

【本月亮点】
{chr(10).join(data["highlights"]) if data["highlights"] else "暂无"}

【改进空间】
{chr(10).join(data["improvements"]) if data["improvements"] else "暂无"}

【目标进度】
{chr(10).join([f"- {g['description']}: 完成{g['completion_rate']}%" for g in data.get("goals_progress", [])]) if data.get("goals_progress") else "暂无活跃目标"}

请用温暖、鼓励的语气写一份月度报告总结（300-400字），包括：
1. 整体评价（总结本月表现）
2. 值得表扬的地方（具体提到各项进步）
3. 下月建议（针对改进空间给出可执行建议）
4. 鼓励的话

直接输出正文内容，不需要标题。"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一位专业的体重管理教练，擅长用温暖的语言鼓励用户。",
                },
                {"role": "user", "content": prompt},
            ]

            response = await ai_service.chat(messages, max_tokens=1000)

            if response.error:
                summary = self._generate_fallback_monthly_summary(data)
            else:
                summary = response.content
        except Exception:
            summary = self._generate_fallback_monthly_summary(data)

        return {
            "summary": summary,
            "highlights": data["highlights"],
            "improvements": data["improvements"],
        }

    def _generate_fallback_monthly_summary(self, data: Dict[str, Any]) -> str:
        """AI 失败时的备用月度总结"""
        parts = []

        # 开头
        if data["weight_change"] < -1.0:
            parts.append(f"本月减重 {abs(data['weight_change'])}kg，效果非常棒！")
        elif data["weight_change"] < -0.5:
            parts.append(f"本月减重 {abs(data['weight_change'])}kg，继续保持！")
        elif data["weight_change"] > 0.5:
            parts.append("本月体重有所波动，不要气馁，调整策略继续努力！")
        else:
            parts.append("本月体重保持稳定，也是不错的成绩！")

        # 运动
        if data["exercise_days"] >= 15:
            parts.append(f"你坚持了 {data['exercise_days']} 天运动，非常了不起！")
        elif data["exercise_days"] >= 10:
            parts.append(f"本月运动 {data['exercise_days']} 天，表现不错！")

        # 结尾
        parts.append(
            "健康管理是一个长期的过程，每一个月都是新的开始。下个月继续加油！💪"
        )

        return " ".join(parts)

    async def _generate_monthly_charts(
        self, user_id: int, month_start: date, month_end: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """生成月度图表数据"""
        charts = {}

        # 体重趋势图（月度）
        weight_chart = await ChartService.get_weight_trend_chart(
            user_id, days=(month_end - month_start).days, db=db
        )
        if weight_chart.get("success"):
            charts["weight_trend"] = weight_chart["data"]

        # 热量趋势图（月度）
        calorie_chart = await ChartService.get_calorie_trend_chart(
            user_id, days=(month_end - month_start).days, db=db
        )
        if calorie_chart.get("success"):
            charts["calorie_trend"] = calorie_chart["data"]

        # 运动趋势图（月度）
        exercise_chart = await ChartService.get_exercise_trend_chart(
            user_id, days=(month_end - month_start).days, db=db
        )
        if exercise_chart.get("success"):
            charts["exercise_trend"] = exercise_chart["data"]

        # 习惯完成率图（月度）
        habit_chart = await ChartService.get_habit_completion_chart(
            user_id, days=(month_end - month_start).days, db=db
        )
        if habit_chart.get("success"):
            charts["habit_completion"] = habit_chart["data"]

        return charts

    @retry_on_error(max_attempts=3, delay=1.0)
    async def share_report(
        self,
        report_id: int,
        report_type: str,  # "weekly" 或 "monthly"
        share_type: str = "image",  # "image", "pdf", "text"
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """分享报告"""
        try:
            if report_type == "weekly":
                result = await db.execute(
                    select(WeeklyReport).where(WeeklyReport.id == report_id)
                )
                report = result.scalar_one_or_none()
                report_title = "周度报告"
            elif report_type == "monthly":
                result = await db.execute(
                    select(MonthlyReport).where(MonthlyReport.id == report_id)
                )
                report = result.scalar_one_or_none()
                report_title = "月度报告"
            else:
                return {"success": False, "error": "无效的报告类型"}

            if not report:
                return {"success": False, "error": "报告不存在"}

            # 生成分享内容
            if share_type == "image":
                share_content = await self._generate_report_image(report, report_type)
                content_type = "image/png"
                file_extension = "png"
            elif share_type == "pdf":
                share_content = await self._generate_report_pdf(report, report_type)
                content_type = "application/pdf"
                file_extension = "pdf"
            else:  # text
                share_content = self._generate_report_text(report, report_type)
                content_type = "text/plain"
                file_extension = "txt"

            # 生成分享链接或直接返回内容
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_title}_{timestamp}.{file_extension}"

            return {
                "success": True,
                "data": {
                    "report_id": report_id,
                    "report_type": report_type,
                    "share_type": share_type,
                    "filename": filename,
                    "content_type": content_type,
                    "content": share_content,  # 可能是base64编码或文本
                    "share_url": f"/api/reports/share/{report_id}/{report_type}/{share_type}",
                    "created_at": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.exception("分享报告失败: %s", e)
            return {"success": False, "error": "分享报告失败", "message": str(e)}

    async def _generate_report_image(self, report, report_type: str) -> str:
        """生成报告图片（base64编码）"""
        # 这里可以集成图表生成库，如 matplotlib 或 reportlab
        # 暂时返回占位符
        placeholder = f"{report_type.capitalize()} Report Image - ID: {report.id}"
        return base64.b64encode(placeholder.encode()).decode()

    async def _generate_report_pdf(self, report, report_type: str) -> str:
        """生成报告PDF（base64编码）"""
        # 这里可以集成PDF生成库，如 reportlab 或 weasyprint
        # 暂时返回占位符
        placeholder = f"{report_type.capitalize()} Report PDF - ID: {report.id}"
        return base64.b64encode(placeholder.encode()).decode()

    def _generate_report_text(self, report, report_type: str) -> str:
        """生成报告文本"""
        if report_type == "weekly":
            period_start = report.week_start
            period_end = report.week_start + timedelta(days=6)
        else:  # monthly
            period_start = report.month_start
            period_end = (
                report.month_start.replace(day=28) + timedelta(days=4)
            ).replace(day=1) - timedelta(days=1)

        text = f"""
{report_type.capitalize()} Report
Period: {period_start} to {period_end}

Summary:
{report.summary_text}

Statistics:
- Weight Change: {report.weight_change} kg
- Average Weight: {report.avg_weight} kg
- Exercise Days: {getattr(report, "exercise_days", "N/A")}
- Total Exercise Minutes: {getattr(report, "total_exercise_minutes", "N/A")}

Highlights:
{chr(10).join(report.highlights) if report.highlights else "None"}

Improvements:
{chr(10).join(report.improvements) if report.improvements else "None"}

Generated on: {report.created_at}
"""
        return text

    @retry_on_error(max_attempts=3, delay=1.0)
    async def get_report_history(
        self,
        user_id: int,
        report_type: str = "all",  # "all", "weekly", "monthly"
        limit: int = 10,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """获取报告历史"""
        try:
            reports = []

            if report_type in ["all", "weekly"]:
                result = await db.execute(
                    select(WeeklyReport)
                    .where(WeeklyReport.user_id == user_id)
                    .order_by(desc(WeeklyReport.week_start))
                    .limit(limit)
                )
                weekly_reports = result.scalars().all()

                for report in weekly_reports:
                    reports.append(
                        {
                            "id": report.id,
                            "type": "weekly",
                            "period_start": report.week_start.isoformat(),
                            "period_end": (
                                report.week_start + timedelta(days=6)
                            ).isoformat(),
                            "weight_change": report.weight_change,
                            "avg_weight": report.avg_weight,
                            "exercise_days": report.exercise_days,
                            "created_at": report.created_at.isoformat(),
                        }
                    )

            if report_type in ["all", "monthly"]:
                result = await db.execute(
                    select(MonthlyReport)
                    .where(MonthlyReport.user_id == user_id)
                    .order_by(desc(MonthlyReport.month_start))
                    .limit(limit)
                )
                monthly_reports = result.scalars().all()

                for report in monthly_reports:
                    reports.append(
                        {
                            "id": report.id,
                            "type": "monthly",
                            "period_start": report.month_start.isoformat(),
                            "period_end": (
                                report.month_start.replace(day=28) + timedelta(days=4)
                            ).replace(day=1)
                            - timedelta(days=1),
                            "weight_change": report.weight_change,
                            "avg_weight": report.avg_weight,
                            "total_exercise_minutes": report.total_exercise_minutes,
                            "created_at": report.created_at.isoformat(),
                        }
                    )

            # 按创建时间排序
            reports.sort(key=lambda x: x["created_at"], reverse=True)

            return {"success": True, "count": len(reports), "data": reports[:limit]}

        except Exception as e:
            logger.exception("获取报告历史失败: %s", e)
            return {"success": False, "error": "获取报告历史失败", "message": str(e)}

    @retry_on_error(max_attempts=3, delay=1.0)
    async def export_report_data(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        format: str = "json",  # "json", "csv"
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """导出报告数据"""
        try:
            # 收集数据
            data = {
                "user_id": user_id,
                "export_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "exported_at": datetime.now().isoformat(),
                "data": {},
            }

            # 体重数据
            result = await db.execute(
                select(WeightRecord)
                .where(
                    and_(
                        WeightRecord.user_id == user_id,
                        WeightRecord.record_date >= start_date,
                        WeightRecord.record_date <= end_date,
                    )
                )
                .order_by(WeightRecord.record_date.asc())
            )
            weight_records = result.scalars().all()

            data["data"]["weight"] = [
                {
                    "date": r.record_date.isoformat(),
                    "weight": r.weight,
                    "note": r.note,
                }
                for r in weight_records
            ]

            # 运动数据
            result = await db.execute(
                select(ExerciseRecord)
                .where(
                    and_(
                        ExerciseRecord.user_id == user_id,
                        ExerciseRecord.record_time
                        >= datetime.combine(start_date, datetime.min.time()),
                        ExerciseRecord.record_time
                        <= datetime.combine(end_date, datetime.max.time()),
                    )
                )
                .order_by(ExerciseRecord.record_time.asc())
            )
            exercise_records = result.scalars().all()

            data["data"]["exercise"] = [
                {
                    "datetime": r.record_time.isoformat(),
                    "exercise_type": r.exercise_type,
                    "duration_minutes": r.duration_minutes,
                    "calories_burned": r.calories_burned,
                    "intensity": r.intensity,
                }
                for r in exercise_records
            ]

            # 生成导出内容
            if format == "json":
                content = json.dumps(data, ensure_ascii=False, indent=2)
                content_type = "application/json"
                file_extension = "json"
            else:  # csv
                # 简化版本，实际需要更复杂的CSV生成
                import csv
                from io import StringIO

                output = StringIO()
                writer = csv.writer(output)

                # 写入标题
                writer.writerow(["Data Type", "Date", "Value", "Details"])

                # 写入体重数据
                for record in data["data"]["weight"]:
                    writer.writerow(
                        [
                            "weight",
                            record["date"],
                            record["weight"],
                            record.get("note", ""),
                        ]
                    )

                # 写入运动数据
                for record in data["data"]["exercise"]:
                    writer.writerow(
                        [
                            "exercise",
                            record["datetime"],
                            record["duration_minutes"],
                            f"{record['exercise_type']} ({record['intensity']})",
                        ]
                    )

                content = output.getvalue()
                content_type = "text/csv"
                file_extension = "csv"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"health_data_export_{timestamp}.{file_extension}"

            return {
                "success": True,
                "data": {
                    "filename": filename,
                    "content_type": content_type,
                    "content": content,
                    "size_bytes": len(content.encode("utf-8")),
                },
            }

        except Exception as e:
            logger.exception("导出报告数据失败: %s", e)
            return {"success": False, "error": "导出数据失败", "message": str(e)}


# 全局实例
report_service = ReportService()
