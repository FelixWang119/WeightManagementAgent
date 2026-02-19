"""
周报服务
封装周报生成逻辑
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    WeeklyReport,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    UserProfile,
    User,
)
from services.ai_service import ai_service

logger = logging.getLogger(__name__)


class WeeklyReportService:
    """周报服务"""

    def __init__(self):
        pass

    def get_week_start(self, d: date) -> date:
        """获取指定日期所在周的开始（周一）"""
        return d - timedelta(days=d.weekday())

    async def collect_week_data(
        self, user_id: int, week_start: date, week_end: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """收集一周数据"""
        # 体重数据
        result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date >= week_start,
                    WeightRecord.record_date <= week_end,
                )
            )
            .order_by(WeightRecord.record_date.asc())
        )
        weight_records = result.scalars().all()

        # 计算体重变化
        weight_change = 0
        avg_weight = 0
        if len(weight_records) >= 2:
            weight_change = weight_records[-1].weight - weight_records[0].weight
            avg_weight = sum(r.weight for r in weight_records) / len(weight_records)
        elif weight_records:
            avg_weight = weight_records[0].weight

        # 热量摄入
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time
                    >= datetime.combine(week_start, datetime.min.time()),
                    MealRecord.record_time
                    <= datetime.combine(week_end, datetime.max.time()),
                )
            )
        )
        meal_records = result.scalars().all()
        total_calories_in = sum(r.total_calories or 0 for r in meal_records)
        avg_calories_in = total_calories_in / 7 if meal_records else 0

        # 运动数据
        result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    ExerciseRecord.record_time
                    >= datetime.combine(week_start, datetime.min.time()),
                    ExerciseRecord.record_time
                    <= datetime.combine(week_end, datetime.max.time()),
                )
            )
        )
        exercise_records = result.scalars().all()
        total_calories_out = sum(r.calories_burned or 0 for r in exercise_records)
        avg_calories_out = total_calories_out / 7 if exercise_records else 0
        exercise_days = len(set(r.record_time.date() for r in exercise_records))

        # 饮水数据
        result = await db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == user_id,
                    WaterRecord.record_time
                    >= datetime.combine(week_start, datetime.min.time()),
                    WaterRecord.record_time
                    <= datetime.combine(week_end, datetime.max.time()),
                )
            )
        )
        water_records = result.scalars().all()
        total_water = sum(r.amount_ml or 0 for r in water_records)
        avg_water = total_water / 7 if water_records else 0

        # 睡眠数据
        result = await db.execute(
            select(SleepRecord).where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(week_start, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(week_end, datetime.max.time()),
                )
            )
        )
        sleep_records = result.scalars().all()
        total_sleep = sum(r.total_minutes or 0 for r in sleep_records)
        avg_sleep = total_sleep / (7 * 60) if sleep_records else 0  # 转换为小时

        # 亮点和改进点
        highlights = []
        improvements = []

        if exercise_days >= 3:
            highlights.append(f"本周运动 {exercise_days} 天，继续保持！")
        else:
            improvements.append(f"本周运动 {exercise_days} 天，建议增加运动频率")

        if avg_water >= 2000:
            highlights.append(f"日均饮水 {avg_water:.0f}ml，达标！")
        else:
            improvements.append(f"日均饮水 {avg_water:.0f}ml，建议多喝水")

        if avg_sleep >= 7:
            highlights.append(f"日均睡眠 {avg_sleep:.1f} 小时，充足！")
        else:
            improvements.append(f"日均睡眠 {avg_sleep:.1f} 小时，建议保证睡眠")

        if weight_change < 0:
            highlights.append(f"体重下降 {abs(weight_change):.1f}kg，进步明显！")
        elif weight_change > 0.5:
            improvements.append(f"体重上升 {weight_change:.1f}kg，注意控制饮食")

        return {
            "week_start": week_start,
            "week_end": week_end,
            "weight_change": weight_change,
            "avg_weight": avg_weight,
            "avg_calories_in": avg_calories_in,
            "avg_calories_out": avg_calories_out,
            "exercise_days": exercise_days,
            "avg_water": avg_water,
            "avg_sleep": avg_sleep,
            "highlights": highlights,
            "improvements": improvements,
            "weight_records_count": len(weight_records),
            "meal_records_count": len(meal_records),
            "exercise_records_count": len(exercise_records),
        }

    async def generate_ai_weekly_analysis(
        self, data: Dict[str, Any], user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """使用AI生成周报分析"""
        try:
            # 获取用户信息
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            user_profile = result.scalar_one_or_none()

            # 构建提示词
            prompt = self._build_weekly_report_prompt(data, user, user_profile)

            messages = [
                {
                    "role": "system",
                    "content": "你是一位专业的体重管理教练，擅长分析用户一周的健康数据并提供专业建议。",
                },
                {"role": "user", "content": prompt},
            ]

            response = await ai_service.chat(messages, max_tokens=800)

            if response.error:
                summary = self._generate_fallback_summary(data)
            else:
                summary = response.content

            return {
                "summary": summary,
                "highlights": data["highlights"],
                "improvements": data["improvements"],
            }

        except Exception as e:
            logger.exception("AI生成周报分析失败: %s", e)
            summary = self._generate_fallback_summary(data)
            return {
                "summary": summary,
                "highlights": data["highlights"],
                "improvements": data["improvements"],
            }

    def _build_weekly_report_prompt(
        self,
        data: Dict[str, Any],
        user: Optional[User],
        user_profile: Optional[UserProfile],
    ) -> str:
        """构建周报提示词"""
        nickname = user.nickname if user else "用户"
        gender = user_profile.gender if user_profile else "未设置"
        age = user_profile.age if user_profile else "未设置"
        height = user_profile.height if user_profile else "未设置"

        highlights_text = (
            "\n".join([f"• {h}" for h in data["highlights"]])
            if data["highlights"]
            else "暂无"
        )
        improvements_text = (
            "\n".join([f"• {i}" for i in data["improvements"]])
            if data["improvements"]
            else "暂无"
        )

        prompt = f"""
请根据以下用户一周的健康数据，生成一份温暖、鼓励的周报总结：

【用户信息】
- 昵称: {nickname}
- 性别: {gender}
- 年龄: {age}
- 身高: {height}cm

【本周数据概览】
- 日期范围: {data["week_start"]} 至 {data["week_end"]}
- 体重变化: {data["weight_change"]:.1f}kg
- 平均体重: {data["avg_weight"]:.1f}kg
- 平均每日热量摄入: {data["avg_calories_in"]:.0f}千卡
- 平均每日热量消耗: {data["avg_calories_out"]:.0f}千卡
- 运动天数: {data["exercise_days"]}天
- 平均每日饮水: {data["avg_water"]:.0f}ml
- 平均每日睡眠: {data["avg_sleep"]:.1f}小时

【本周亮点】
{highlights_text}

【改进建议】
{improvements_text}

【数据完整性】
- 体重记录: {data["weight_records_count"]}次
- 饮食记录: {data["meal_records_count"]}次
- 运动记录: {data["exercise_records_count"]}次

请生成一份周报总结，要求：
1. 用温暖、鼓励的语气开头
2. 总结本周的主要成就和进步
3. 针对改进点给出具体、可行的建议
4. 为下周设定1-2个小目标
5. 结尾用积极的语言鼓励用户继续努力
6. 使用emoji增加亲和力
7. 控制在300-500字左右

格式要求：
📊 周报总结
[正文内容]
🎯 下周目标
[目标内容]
💪 继续加油！
"""
        return prompt

    def _generate_fallback_summary(self, data: Dict[str, Any]) -> str:
        """生成备用周报总结"""
        week_range = f"{data['week_start']} 至 {data['week_end']}"

        summary = f"""📊 {week_range} 周报总结

本周你坚持记录了健康数据，这是迈向健康生活的重要一步！

🌟 本周亮点：
{chr(10).join([f"  • {h}" for h in data["highlights"]]) if data["highlights"] else "  • 坚持记录健康数据"}

💡 改进建议：
{chr(10).join([f"  • {i}" for i in data["improvements"]]) if data["improvements"] else "  • 继续保持良好习惯"}

🎯 下周目标：
1. 每天保证2000ml饮水
2. 至少运动3天
3. 保证7小时睡眠

继续加油，下周会更好！💪
"""
        return summary

    async def generate_weekly_report(
        self, user_id: int, week_start: date, week_end: date, db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        生成周报

        Args:
            user_id: 用户ID
            week_start: 周开始日期
            week_end: 周结束日期
            db: 数据库会话

        Returns:
            周报数据字典，包含报告ID和基本信息
        """
        try:
            logger.info(
                "开始生成周报 - 用户ID: %d, 日期范围: %s 至 %s",
                user_id,
                week_start,
                week_end,
            )

            # 检查是否已存在
            result = await db.execute(
                select(WeeklyReport).where(
                    and_(
                        WeeklyReport.user_id == user_id,
                        WeeklyReport.week_start == week_start,
                    )
                )
            )
            existing_report = result.scalar_one_or_none()

            # 收集本周数据
            data = await self.collect_week_data(user_id, week_start, week_end, db)

            # 生成 AI 周报
            ai_analysis = await self.generate_ai_weekly_analysis(data, user_id, db)

            # 保存或更新报告
            if existing_report:
                existing_report.summary_text = ai_analysis["summary"]
                existing_report.weight_change = data["weight_change"]
                existing_report.avg_weight = data["avg_weight"]
                existing_report.avg_calories_in = data["avg_calories_in"]
                existing_report.avg_calories_out = data["avg_calories_out"]
                existing_report.exercise_days = data["exercise_days"]
                existing_report.highlights = data["highlights"]
                existing_report.improvements = data["improvements"]
                report = existing_report
            else:
                report = WeeklyReport(
                    user_id=user_id,
                    week_start=week_start,
                    summary_text=ai_analysis["summary"],
                    weight_change=data["weight_change"],
                    avg_weight=data["avg_weight"],
                    avg_calories_in=data["avg_calories_in"],
                    avg_calories_out=data["avg_calories_out"],
                    exercise_days=data["exercise_days"],
                    highlights=data["highlights"],
                    improvements=data["improvements"],
                )
                db.add(report)

            await db.commit()
            await db.refresh(report)

            logger.info("周报生成成功 - 用户ID: %d, 报告ID: %d", user_id, report.id)

            return {
                "id": report.id,
                "week_start": report.week_start,
                "week_end": week_end,
                "summary": report.summary_text,
                "weight_change": report.weight_change,
                "avg_weight": report.avg_weight,
                "avg_calories_in": report.avg_calories_in,
                "avg_calories_out": report.avg_calories_out,
                "exercise_days": report.exercise_days,
                "highlights": report.highlights,
                "improvements": report.improvements,
                "created_at": report.created_at,
            }

        except Exception as e:
            logger.exception("生成周报时发生错误 - 用户ID: %d: %s", user_id, e)
            await db.rollback()
            return None

    async def get_weekly_report(
        self, user_id: int, week_start: date, db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """获取周报"""
        try:
            result = await db.execute(
                select(WeeklyReport).where(
                    and_(
                        WeeklyReport.user_id == user_id,
                        WeeklyReport.week_start == week_start,
                    )
                )
            )
            report = result.scalar_one_or_none()

            if not report:
                return None

            return {
                "id": report.id,
                "week_start": report.week_start,
                "week_end": report.week_start + timedelta(days=6),
                "summary": report.summary_text,
                "weight_change": report.weight_change,
                "avg_weight": report.avg_weight,
                "avg_calories_in": report.avg_calories_in,
                "avg_calories_out": report.avg_calories_out,
                "exercise_days": report.exercise_days,
                "highlights": report.highlights,
                "improvements": report.improvements,
                "created_at": report.created_at,
            }

        except Exception as e:
            logger.exception("获取周报时发生错误 - 用户ID: %d: %s", user_id, e)
            return None

    async def get_weekly_report_history(
        self, user_id: int, limit: int = 10, offset: int = 0, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取周报历史"""
        try:
            # 查询报告
            result = await db.execute(
                select(WeeklyReport)
                .where(WeeklyReport.user_id == user_id)
                .order_by(WeeklyReport.week_start.desc())
                .limit(limit)
                .offset(offset)
            )
            reports = result.scalars().all()

            # 查询总数
            count_result = await db.execute(
                select(func.count(WeeklyReport.id)).where(
                    WeeklyReport.user_id == user_id
                )
            )
            total = count_result.scalar() or 0

            # 格式化结果
            formatted_reports = []
            for report in reports:
                formatted_reports.append(
                    {
                        "id": report.id,
                        "week_start": report.week_start,
                        "week_end": report.week_start + timedelta(days=6),
                        "summary": report.summary_text[:100] + "..."
                        if len(report.summary_text) > 100
                        else report.summary_text,
                        "weight_change": report.weight_change,
                        "avg_weight": report.avg_weight,
                        "exercise_days": report.exercise_days,
                        "created_at": report.created_at,
                    }
                )

            return {
                "reports": formatted_reports,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.exception("获取周报历史时发生错误 - 用户ID: %d: %s", user_id, e)
            return {"reports": [], "total": 0, "limit": limit, "offset": offset}


# 全局实例
weekly_report_service = WeeklyReportService()
