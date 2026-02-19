"""
日报生成服务
负责收集当日数据、生成日报内容、保存日报记录
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
import json

from models.database import (
    User,
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    Goal,
    GoalStatus,
    DailyReport,
)
from services.calorie_balance_service import CalorieBalanceService
from services.calorie_calculator import CalorieCalculator
from services.ai_service import ai_service
from config.logging_config import get_module_logger
from utils.exceptions import retry_on_error

logger = get_module_logger(__name__)


class DailyReportService:
    """日报生成服务"""

    @retry_on_error(max_attempts=3, delay=1.0)
    async def generate_daily_report(
        self, user_id: int, report_date: Optional[date] = None, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """生成日报"""
        try:
            # 确定报告日期
            if report_date is None:
                report_date = date.today()

            logger.info("开始生成日报 - 用户ID: %s, 日期: %s", user_id, report_date)

            # 检查是否已存在
            result = await db.execute(
                select(DailyReport).where(
                    and_(
                        DailyReport.user_id == user_id,
                        DailyReport.report_date == report_date,
                    )
                )
            )
            existing_report = result.scalar_one_or_none()

            # 收集当日数据
            data = await self._collect_daily_data(user_id, report_date, db)

            # 生成 AI 日报分析
            ai_analysis = await self._generate_ai_daily_analysis(data, user_id, db)

            # 保存或更新报告
            if existing_report:
                existing_report.summary_text = ai_analysis["summary"]
                existing_report.weight = data["weight"]
                existing_report.calories_in = data["calories_in"]
                existing_report.calories_out = data["calories_out"]
                existing_report.calorie_deficit = data["calorie_deficit"]
                existing_report.water_intake = data["water_intake"]
                existing_report.sleep_hours = data["sleep_hours"]
                existing_report.exercise_minutes = data["exercise_minutes"]
                existing_report.highlights = data["highlights"]
                existing_report.tips = data["tips"]
                existing_report.suggestions = data["suggestions"]
                report = existing_report
                message = "日报已更新"
            else:
                report = DailyReport(
                    user_id=user_id,
                    report_date=report_date,
                    summary_text=ai_analysis["summary"],
                    weight=data["weight"],
                    calories_in=data["calories_in"],
                    calories_out=data["calories_out"],
                    calorie_deficit=data["calorie_deficit"],
                    water_intake=data["water_intake"],
                    sleep_hours=data["sleep_hours"],
                    exercise_minutes=data["exercise_minutes"],
                    highlights=data["highlights"],
                    tips=data["tips"],
                    suggestions=data["suggestions"],
                )
                db.add(report)
                message = "日报生成成功"

            await db.commit()
            logger.info("日报生成完成 - 用户ID: %s, 日期: %s", user_id, report_date)

            return {
                "success": True,
                "message": message,
                "data": {
                    "report_date": report_date.isoformat(),
                    "summary": ai_analysis["summary"],
                    "highlights": data["highlights"],
                    "tips": data["tips"],
                    "suggestions": data["suggestions"],
                    "statistics": {
                        "weight": data["weight"],
                        "calories_in": data["calories_in"],
                        "calories_out": data["calories_out"],
                        "calorie_deficit": data["calorie_deficit"],
                        "water_intake": data["water_intake"],
                        "sleep_hours": data["sleep_hours"],
                        "exercise_minutes": data["exercise_minutes"],
                    },
                },
            }

        except Exception as e:
            logger.exception("生成日报失败: %s", e)
            return {"success": False, "error": str(e)}

    async def _collect_daily_data(
        self, user_id: int, report_date: date, db: AsyncSession
    ) -> Dict[str, Any]:
        """收集当日数据"""
        data = {
            "report_date": report_date.isoformat(),
            "weight": 0,
            "calories_in": 0,
            "calories_out": 0,
            "calorie_deficit": 0,
            "water_intake": 0,
            "sleep_hours": 0,
            "exercise_minutes": 0,
            "highlights": [],
            "tips": [],
            "suggestions": [],
        }

        # 获取用户信息
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        user_profile = result.scalar_one_or_none()

        # 1. 体重数据
        result = await db.execute(
            select(WeightRecord).where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date == report_date,
                )
            )
        )
        weight_record = result.scalar_one_or_none()
        if weight_record:
            data["weight"] = weight_record.weight

        # 2. 饮食数据
        result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == report_date,
                )
            )
        )
        meal_records = result.scalars().all()
        data["calories_in"] = sum(meal.total_calories for meal in meal_records)

        # 3. 运动数据
        result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.date(ExerciseRecord.record_time) == report_date,
                )
            )
        )
        exercise_records = result.scalars().all()
        data["exercise_minutes"] = sum(
            record.duration_minutes for record in exercise_records
        )
        data["calories_out"] = sum(
            record.calories_burned for record in exercise_records
        )

        # 4. 饮水数据
        result = await db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == report_date,
                )
            )
        )
        water_records = result.scalars().all()
        data["water_intake"] = sum(record.amount_ml for record in water_records)

        # 5. 睡眠数据
        result = await db.execute(
            select(SleepRecord).where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.bed_time) == report_date,
                )
            )
        )
        sleep_record = result.scalar_one_or_none()
        if sleep_record and sleep_record.total_minutes:
            data["sleep_hours"] = sleep_record.total_minutes / 60.0

        # 6. 计算热量缺口（基础代谢 + 运动消耗 - 摄入）
        if user_profile:
            # 如果没有当日体重数据，使用默认值70kg
            current_weight = data["weight"] if data["weight"] > 0 else 70.0
            # 从UserProfile对象中获取实际值
            age_val = user_profile.age if user_profile.age else None
            gender_val = user_profile.gender if user_profile.gender else None
            height_val = user_profile.height if user_profile.height else None
            bmr_val = user_profile.bmr if user_profile.bmr else None

            bmr = CalorieCalculator.calculate_bmr(
                age=age_val,
                gender=gender_val,
                height_cm=height_val,
                weight_kg=current_weight,
                use_user_bmr=bmr_val,
            )
            if bmr:
                data["calories_out"] += int(bmr)
            data["calorie_deficit"] = max(0, data["calories_out"] - data["calories_in"])

        # 7. 生成亮点和建议
        data["highlights"] = self._generate_highlights(data, user_profile)
        data["tips"] = self._generate_tips(data, user_profile)
        data["suggestions"] = self._generate_suggestions(data, user_profile)

        return data

    def _generate_highlights(
        self, data: Dict[str, Any], user_profile: Optional[UserProfile]
    ) -> List[str]:
        """生成今日亮点"""
        highlights = []

        # 体重记录
        if data["weight"] > 0:
            highlights.append(f"记录了体重：{data['weight']}kg")

        # 热量控制
        if data["calorie_deficit"] > 0:
            highlights.append(f"热量缺口：{data['calorie_deficit']}千卡")

        # 饮水达标
        if data["water_intake"] >= 2000:
            highlights.append(f"饮水达标：{data['water_intake']}ml")

        # 运动记录
        if data["exercise_minutes"] >= 30:
            highlights.append(f"运动时长：{data['exercise_minutes']}分钟")

        # 睡眠充足
        if data["sleep_hours"] >= 7:
            highlights.append(f"睡眠充足：{data['sleep_hours']}小时")

        return highlights

    def _generate_tips(
        self, data: Dict[str, Any], user_profile: Optional[UserProfile]
    ) -> List[str]:
        """生成温馨提示"""
        tips = []

        # 体重未记录
        if data["weight"] == 0:
            tips.append("今天还没记录体重哦")

        # 饮水不足
        if data["water_intake"] < 1500:
            tips.append(f"今日饮水 {data['water_intake']}ml，建议多喝点水")

        # 睡眠不足
        if 0 < data["sleep_hours"] < 6:
            tips.append(f"今日睡眠 {data['sleep_hours']}小时，建议保证充足睡眠")

        # 热量盈余
        if data["calorie_deficit"] < 0:
            tips.append("今日热量摄入超过消耗，注意控制哦")

        return tips

    def _generate_suggestions(
        self, data: Dict[str, Any], user_profile: Optional[UserProfile]
    ) -> List[str]:
        """生成明日建议"""
        suggestions = []

        # 基于今日数据给出建议
        if data["water_intake"] < 1500:
            suggestions.append("明天记得多喝水，目标2000ml")

        if data["exercise_minutes"] < 30:
            suggestions.append("明天安排30分钟运动吧")

        if data["sleep_hours"] < 7:
            suggestions.append("明天早点休息，保证7小时睡眠")

        if data["calorie_deficit"] < 0:
            suggestions.append("明天注意控制热量摄入，保持缺口")

        if not suggestions:
            suggestions.append("继续保持今天的良好习惯！")

        return suggestions

    async def _generate_ai_daily_analysis(
        self, data: Dict[str, Any], user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """使用AI生成日报分析"""
        try:
            # 获取用户信息
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            user_profile = result.scalar_one_or_none()

            # 构建提示词
            prompt = self._build_daily_report_prompt(data, user, user_profile)

            messages = [
                {
                    "role": "system",
                    "content": "你是一位温暖的体重管理教练，擅长用鼓励的语言总结用户当日的健康数据。",
                },
                {"role": "user", "content": prompt},
            ]

            response = await ai_service.chat(messages, max_tokens=500)

            if response.error:
                summary = self._generate_fallback_summary(data)
            else:
                summary = response.content

            return {
                "summary": summary,
                "highlights": data["highlights"],
                "tips": data["tips"],
                "suggestions": data["suggestions"],
            }

        except Exception as e:
            logger.exception("AI生成日报分析失败: %s", e)
            summary = self._generate_fallback_summary(data)
            return {
                "summary": summary,
                "highlights": data["highlights"],
                "tips": data["tips"],
                "suggestions": data["suggestions"],
            }

    def _build_daily_report_prompt(
        self,
        data: Dict[str, Any],
        user: Optional[User],
        user_profile: Optional[UserProfile],
    ) -> str:
        """构建日报提示词"""
        user_info = ""
        if user or user_profile:
            nickname = user.nickname if user else "用户"
            gender = user_profile.gender if user_profile else "未设置"
            age = user_profile.age if user_profile else "未设置"
            height = user_profile.height if user_profile else "未设置"

            user_info = f"""
【用户信息】
- 昵称: {nickname}
- 性别: {gender}
- 年龄: {age}
- 身高: {height}cm
"""

        highlights_text = (
            "\n".join([f"• {h}" for h in data["highlights"]])
            if data["highlights"]
            else "暂无"
        )
        tips_text = (
            "\n".join([f"• {t}" for t in data["tips"]]) if data["tips"] else "暂无"
        )
        suggestions_text = (
            "\n".join([f"• {s}" for s in data["suggestions"]])
            if data["suggestions"]
            else "暂无"
        )

        prompt = f"""请根据以下数据生成一份个性化的今日健康日报：

{user_info}
【今日数据】({data["report_date"]})
• 体重: {data["weight"]}kg
• 摄入热量: {data["calories_in"]}千卡
• 消耗热量: {data["calories_out"]}千卡
• 热量缺口: {data["calorie_deficit"]}千卡
• 饮水量: {data["water_intake"]}ml
• 睡眠时长: {data["sleep_hours"]}小时
• 运动时长: {data["exercise_minutes"]}分钟

【今日亮点】
{highlights_text}

【温馨提示】
{tips_text}

【明日建议】
{suggestions_text}

请用温暖、鼓励的语气写一份日报总结（150-250字），包括：
1. 今日整体评价
2. 值得表扬的地方（具体提到各项进步）
3. 需要改进的地方（建设性建议）
4. 明日行动建议

直接输出正文内容，不需要标题。使用适当的emoji增加可读性。"""

        return prompt

    def _generate_fallback_summary(self, data: Dict[str, Any]) -> str:
        """AI失败时的备用总结"""
        parts = []

        # 开头
        parts.append(f"📊 {data['report_date']} 健康日报")

        # 亮点
        if data["highlights"]:
            parts.append("🌟 今日亮点：")
            for highlight in data["highlights"]:
                parts.append(f"  • {highlight}")

        # 温馨提示
        if data["tips"]:
            parts.append("💡 温馨提示：")
            for tip in data["tips"]:
                parts.append(f"  • {tip}")

        # 明日建议
        if data["suggestions"]:
            parts.append("🎯 明日建议：")
            for suggestion in data["suggestions"]:
                parts.append(f"  • {suggestion}")

        # 结尾
        parts.append("继续加油，明天会更好！💪")

        return "\n".join(parts)

    @retry_on_error(max_attempts=3, delay=1.0)
    async def get_daily_report(
        self, user_id: int, report_date: Optional[date] = None, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取日报"""
        try:
            if report_date is None:
                report_date = date.today()

            result = await db.execute(
                select(DailyReport).where(
                    and_(
                        DailyReport.user_id == user_id,
                        DailyReport.report_date == report_date,
                    )
                )
            )
            report = result.scalar_one_or_none()

            if not report:
                return {"success": True, "message": "暂无日报", "data": None}

            return {
                "success": True,
                "data": {
                    "id": report.id,
                    "report_date": report.report_date.isoformat(),
                    "summary": report.summary_text,
                    "weight": report.weight,
                    "calories_in": report.calories_in,
                    "calories_out": report.calories_out,
                    "calorie_deficit": report.calorie_deficit,
                    "water_intake": report.water_intake,
                    "sleep_hours": report.sleep_hours,
                    "exercise_minutes": report.exercise_minutes,
                    "highlights": report.highlights,
                    "tips": report.tips,
                    "suggestions": report.suggestions,
                    "created_at": report.created_at.isoformat(),
                },
            }

        except Exception as e:
            logger.exception("获取日报失败: %s", e)
            return {"success": False, "error": str(e)}

    @retry_on_error(max_attempts=3, delay=1.0)
    async def get_daily_report_history(
        self,
        user_id: int,
        limit: int = 30,
        offset: int = 0,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """获取日报历史"""
        try:
            result = await db.execute(
                select(DailyReport)
                .where(DailyReport.user_id == user_id)
                .order_by(desc(DailyReport.report_date))
                .limit(limit)
                .offset(offset)
            )
            reports = result.scalars().all()

            report_list = []
            for report in reports:
                report_list.append(
                    {
                        "id": report.id,
                        "report_date": report.report_date.isoformat(),
                        "summary": report.summary_text[:100] + "..."
                        if len(report.summary_text) > 100
                        else report.summary_text,
                        "weight": report.weight,
                        "calorie_deficit": report.calorie_deficit,
                        "created_at": report.created_at.isoformat(),
                    }
                )

            # 获取总数
            count_result = await db.execute(
                select(func.count(DailyReport.id)).where(DailyReport.user_id == user_id)
            )
            total = count_result.scalar() or 0

            return {
                "success": True,
                "data": {
                    "reports": report_list,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                },
            }

        except Exception as e:
            logger.exception("获取日报历史失败: %s", e)
            return {"success": False, "error": str(e)}


# 全局实例
daily_report_service = DailyReportService()
