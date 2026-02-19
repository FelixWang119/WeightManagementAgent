"""
每周报告 API 路由
包含：生成周报告、报告历史、AI洞察分析
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import json

from models.database import (
    get_db,
    User,
    DailyReport,
    WeeklyReport,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    UserProfile,
    Goal,
    GoalStatus,
)
from api.routes.user import get_current_user
from services.ai_service import ai_service
from services.sleep_analysis_service import SleepAnalysisService
from services.habit_tracking_service import HabitTrackingService
from config.settings import fastapi_settings

router = APIRouter()


@router.get("/daily/history")
async def get_daily_report_history(
    limit: int = 30,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取日报历史"""
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.user_id == current_user.id)
        .order_by(desc(DailyReport.report_date))
        .limit(limit)
        .offset(offset)
    )
    reports = result.scalars().all()

    # 获取总数
    count_result = await db.execute(
        select(func.count(DailyReport.id)).where(DailyReport.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "id": r.id,
                "report_date": r.report_date.isoformat(),
                "weight": r.weight,
                "calories_in": r.calories_in,
                "calories_out": r.calories_out,
                "calorie_deficit": r.calorie_deficit,
                "water_intake": r.water_intake,
                "sleep_hours": r.sleep_hours,
                "exercise_minutes": r.exercise_minutes,
                "highlights": r.highlights,
                "tips": r.tips,
                "suggestions": r.suggestions,
                "summary": r.summary_text,
            }
            for r in reports
        ],
    }


@router.get("/daily/{report_date}")
async def get_daily_report(
    report_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定日期的日报"""
    try:
        date_obj = date.fromisoformat(report_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的日期格式")

    result = await db.execute(
        select(DailyReport).where(
            and_(
                DailyReport.user_id == current_user.id,
                DailyReport.report_date == date_obj,
            )
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="日报不存在")

    return {
        "success": True,
        "data": {
            "id": report.id,
            "report_date": report.report_date.isoformat(),
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
            "summary": report.summary_text,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        },
    }


def get_week_start(d: date) -> date:
    """获取指定日期所在周的开始（周一）"""
    return d - timedelta(days=d.weekday())


@router.post("/generate")
async def generate_weekly_report(
    week_start: Optional[date] = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成每周报告

    - **week_start**: 周开始日期（默认本周一）

    返回 AI 生成的周报内容
    """
    # 确定周开始日期
    if week_start is None:
        week_start = get_week_start(date.today())
    else:
        week_start = get_week_start(week_start)

    week_end = week_start + timedelta(days=6)

    # 检查是否已存在
    result = await db.execute(
        select(WeeklyReport).where(
            and_(
                WeeklyReport.user_id == current_user.id,
                WeeklyReport.week_start == week_start,
            )
        )
    )
    existing_report = result.scalar_one_or_none()

    # 收集本周数据
    data = await collect_week_data(current_user.id, week_start, week_end, db)

    # 生成 AI 周报
    ai_analysis = await generate_ai_weekly_analysis(data, current_user.id, db)

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
        message = "周报已更新"
    else:
        report = WeeklyReport(
            user_id=current_user.id,
            week_start=week_start,
            summary_text=ai_analysis["summary"],
            weight_change=data["weight_change"],
            avg_weight=data["avg_weight"],
            avg_calories_in=data["avg_calories_in"],
            avg_calories_out=data["avg_calories_out"],
            exercise_days=data["exercise_days"],
            highlights=data["highlights"],
            improvements=data["improvements"],
            created_at=datetime.utcnow(),
        )
        db.add(report)
        message = "周报生成成功"

    await db.commit()

    return {
        "success": True,
        "message": message,
        "data": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "summary": ai_analysis["summary"],
            "highlights": data["highlights"],
            "improvements": data["improvements"],
            "statistics": {
                "weight_change": data["weight_change"],
                "avg_weight": data["avg_weight"],
                "avg_calories_in": data["avg_calories_in"],
                "avg_calories_out": data["avg_calories_out"],
                "exercise_days": data["exercise_days"],
                "sleep_avg_hours": data["sleep_avg_hours"],
                "sleep_quality_avg": data["sleep_quality_avg"],
                "sleep_days": data.get("sleep_days", 0),
                "water_goal_days": data["water_goal_days"],
            },
            "sleep_analysis": {
                "pattern": data.get("sleep_pattern", {}),
                "weight_correlation": data.get("sleep_weight_correlation", {}),
            },
            "habit_stats": data.get("habit_stats", {}),
            "habit_completion_rate": data.get("habit_completion_rate", 0),
        },
    }


@router.get("/latest")
async def get_latest_report(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取最新周报"""
    result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.user_id == current_user.id)
        .order_by(desc(WeeklyReport.week_start))
        .limit(1)
    )

    report = result.scalar_one_or_none()

    if not report:
        return {"success": True, "message": "暂无周报，请先生成", "data": None}

    return {
        "success": True,
        "data": {
            "week_start": report.week_start.isoformat(),
            "summary": report.summary_text,
            "weight_change": report.weight_change,
            "avg_weight": report.avg_weight,
            "highlights": report.highlights,
            "improvements": report.improvements,
            "created_at": report.created_at.isoformat(),
        },
    }


@router.get("/history")
async def get_report_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取周报历史"""
    result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.user_id == current_user.id)
        .order_by(desc(WeeklyReport.week_start))
        .limit(limit)
    )

    reports = result.scalars().all()

    return {
        "success": True,
        "count": len(reports),
        "data": [
            {
                "week_start": r.week_start.isoformat(),
                "weight_change": r.weight_change,
                "avg_weight": r.avg_weight,
                "exercise_days": r.exercise_days,
                "highlights": r.highlights,
                "improvements": r.improvements,
            }
            for r in reports
        ],
    }


@router.get("/trends")
async def get_weight_trends(
    weeks: int = 12,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取体重趋势（用于图表）

    - **weeks**: 查询周数（默认12周）
    """
    start_date = date.today() - timedelta(weeks=weeks, days=date.today().weekday())

    # 获取体重记录
    result = await db.execute(
        select(WeightRecord)
        .where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= start_date,
            )
        )
        .order_by(WeightRecord.record_date.asc())
    )

    records = result.scalars().all()

    # 按周汇总
    weekly_data = {}
    for record in records:
        week = get_week_start(record.record_date)
        if week not in weekly_data:
            weekly_data[week] = []
        weekly_data[week].append(record.weight)

    # 计算每周平均
    trends = []
    for week in sorted(weekly_data.keys()):
        avg_weight = sum(weekly_data[week]) / len(weekly_data[week])
        trends.append(
            {
                "week": week.isoformat(),
                "avg_weight": round(avg_weight, 2),
                "record_count": len(weekly_data[week]),
            }
        )

    return {"success": True, "data": trends}


@router.get("/insights")
async def get_ai_insights(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取 AI 洞察分析"""
    # 获取最近30天数据
    start_date = date.today() - timedelta(days=30)

    # 体重变化趋势
    result = await db.execute(
        select(WeightRecord)
        .where(
            and_(
                WeightRecord.user_id == current_user.id,
                WeightRecord.record_date >= start_date,
            )
        )
        .order_by(WeightRecord.record_date.asc())
    )
    weight_records = result.scalars().all()

    if len(weight_records) >= 2:
        weight_trend = weight_records[-1].weight - weight_records[0].weight
        if weight_trend < -0.5:
            trend_desc = "呈下降趋势"
        elif weight_trend > 0.5:
            trend_desc = "呈上升趋势"
        else:
            trend_desc = "基本稳定"
    else:
        weight_trend = 0
        trend_desc = "数据不足"

    # 运动习惯
    result = await db.execute(
        select(func.count(ExerciseRecord.id)).where(
            and_(
                ExerciseRecord.user_id == current_user.id,
                ExerciseRecord.record_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
    )
    exercise_count = result.scalar() or 0

    # 睡眠分析
    result = await db.execute(
        select(func.avg(SleepRecord.total_minutes)).where(
            and_(
                SleepRecord.user_id == current_user.id,
                SleepRecord.bed_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
    )
    avg_sleep = (result.scalar() or 0) / 60

    insights = {
        "weight_trend": {
            "change": round(weight_trend, 2),
            "description": trend_desc,
            "records": len(weight_records),
        },
        "exercise_habit": {
            "days": exercise_count,
            "frequency": "良好"
            if exercise_count >= 10
            else "需加强"
            if exercise_count >= 5
            else "需改善",
        },
        "sleep_quality": {
            "avg_hours": round(avg_sleep, 1),
            "assessment": "充足" if avg_sleep >= 7 else "略少",
        },
        "recommendations": [],
    }

    # 生成建议
    if weight_trend > 0.5:
        insights["recommendations"].append("最近体重有所上升，建议控制饮食并增加运动量")
    elif weight_trend < -0.5:
        insights["recommendations"].append("减重效果不错，继续保持！")

    if exercise_count < 5:
        insights["recommendations"].append("建议每周至少运动3-5次，每次30分钟以上")

    if avg_sleep < 7:
        insights["recommendations"].append("睡眠时间偏少，建议保证每天7-8小时睡眠")

    return {"success": True, "data": insights}


# ============ 辅助函数 ============


async def collect_week_data(
    user_id: int, week_start: date, week_end: date, db: AsyncSession
) -> Dict[str, Any]:
    """收集一周的数据"""
    data = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
    }

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
                >= datetime.combine(week_start, datetime.min.time()),
                MealRecord.record_time
                <= datetime.combine(week_end, datetime.max.time()),
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

    if daily_calories:
        data["avg_calories_in"] = int(
            sum(daily_calories.values()) / len(daily_calories)
        )
    else:
        data["avg_calories_in"] = 0

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

    data["exercise_days"] = len(set(r.record_time.date() for r in exercise_records))
    data["total_exercise_minutes"] = sum(r.duration_minutes for r in exercise_records)
    data["total_calories_out"] = sum(r.calories_burned for r in exercise_records)
    data["avg_calories_out"] = int(data["total_calories_out"] / 7)

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

    daily_water = {}
    for w in water_records:
        w_date = w.record_time.date().isoformat()
        if w_date not in daily_water:
            daily_water[w_date] = 0
        daily_water[w_date] += w.amount_ml

    data["water_goal_days"] = sum(1 for v in daily_water.values() if v >= 2000)

    # 睡眠数据增强
    result = await db.execute(
        select(SleepRecord).where(
            and_(
                SleepRecord.user_id == user_id,
                SleepRecord.bed_time
                >= datetime.combine(week_start, datetime.min.time()),
                SleepRecord.bed_time <= datetime.combine(week_end, datetime.max.time()),
            )
        )
    )
    sleep_records = result.scalars().all()

    if sleep_records:
        data["sleep_avg_hours"] = round(
            sum(r.total_minutes for r in sleep_records) / len(sleep_records) / 60, 1
        )
        data["sleep_quality_avg"] = (
            round(
                sum(r.quality for r in sleep_records if r.quality)
                / len([r for r in sleep_records if r.quality]),
                1,
            )
            if any(r.quality for r in sleep_records)
            else 0
        )
        data["sleep_days"] = len(sleep_records)

        sleep_analysis = await SleepAnalysisService.get_sleep_pattern_analysis(
            user_id, days=7, db=db
        )
        data["sleep_pattern"] = (
            sleep_analysis.get("data", {}) if sleep_analysis.get("success") else {}
        )

        weight_corr = await SleepAnalysisService.analyze_sleep_weight_correlation(
            user_id, db, days=30
        )
        data["sleep_weight_correlation"] = (
            weight_corr.get("data", {}) if weight_corr.get("success") else {}
        )
    else:
        data["sleep_avg_hours"] = 0
        data["sleep_quality_avg"] = 0
        data["sleep_days"] = 0
        data["sleep_pattern"] = {}
        data["sleep_weight_correlation"] = {}

    # 习惯打卡统计
    try:
        habit_stats = await HabitTrackingService.get_streak_stats(
            user_id, days=7, db=db
        )
        data["habit_stats"] = habit_stats.get("streaks", {})

        data["habit_completion_rate"] = sum(
            s.get("completion_rate", 0) for s in data["habit_stats"].values()
        ) / max(len(data["habit_stats"]), 1)
    except Exception:
        data["habit_stats"] = {}
        data["habit_completion_rate"] = 0

    # 获取用户画像用于个性化建议
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    user_profile = result.scalar_one_or_none()

    user_preferences = {}
    if user_profile:
        user_preferences = {
            "motivation_type": user_profile.motivation_type.value
            if user_profile.motivation_type
            else None,
            "communication_style": user_profile.communication_style,
        }

    # 获取目标体重
    goal_result = await db.execute(
        select(Goal)
        .where(and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE))
        .order_by(Goal.created_at.desc())
        .limit(1)
    )
    goal = goal_result.scalar_one_or_none()
    if goal and goal.target_weight:
        user_preferences["target_weight"] = goal.target_weight

    data["user_preferences"] = user_preferences

    # 生成亮点和改进点（增强版）
    data["highlights"] = []
    data["improvements"] = []

    if data["weight_change"] < -0.3:
        data["highlights"].append(
            f"本周减重 {abs(data['weight_change'])}kg，保持势头！"
        )
    elif data["weight_change"] < 0:
        data["highlights"].append(
            f"本周体重下降了{data['weight_change']}kg，继续保持！"
        )

    if data["exercise_days"] >= 4:
        data["highlights"].append(f"本周运动 {data['exercise_days']} 天，非常自律！")
    elif data["exercise_days"] >= 2:
        data["highlights"].append(f"本周运动 {data['exercise_days']} 天，有进步空间！")

    if data["water_goal_days"] >= 5:
        data["highlights"].append(
            f"本周 {data['water_goal_days']} 天饮水达标， hydration 很棒！"
        )
    elif data["water_goal_days"] >= 3:
        data["highlights"].append(f"本周 {data['water_goal_days']} 天饮水基本达标！")

    if data["sleep_avg_hours"] >= 7:
        data["highlights"].append(
            f"平均睡眠 {data['sleep_avg_hours']} 小时，休息充足！"
        )
    elif data["sleep_avg_hours"] >= 6:
        data["highlights"].append(f"睡眠 {data['sleep_avg_hours']} 小时，还不错！")

    if data.get("habit_completion_rate", 0) >= 70:
        data["highlights"].append(
            f"习惯完成率 {data['habit_completion_rate']:.0f}%，养成好习惯！"
        )

    if data["weight_change"] > 0.5:
        data["improvements"].append("体重上升较快，注意控制饮食")
    elif data["weight_change"] > 0.3:
        data["improvements"].append("体重有所波动，建议关注饮食")

    if data["exercise_days"] < 3:
        data["improvements"].append("运动频率偏低，建议增加运动量")

    if data["water_goal_days"] < 3:
        data["improvements"].append("饮水量不足，建议多喝水")

    if data["sleep_avg_hours"] < 6.5:
        data["improvements"].append("睡眠时间偏少，建议早睡早起")

    if data["sleep_avg_hours"] < 6:
        data["improvements"].append("严重睡眠不足，会影响减重效果！")

    if data.get("sleep_pattern", {}).get("irregularity_score", 0) > 30:
        data["improvements"].append("睡眠时间不够规律，建议固定作息")

    if data.get("habit_completion_rate", 0) < 50:
        data["improvements"].append("习惯完成率偏低，每天坚持一点点！")

    return data


async def generate_ai_weekly_analysis(
    data: Dict[str, Any], user_id: int, db: AsyncSession
) -> Dict[str, str]:
    """使用 AI 生成周报分析"""

    # 构建提示词（增强版）
    sleep_info = ""
    if data.get("sleep_avg_hours", 0) > 0:
        sleep_info = f"- 平均睡眠: {data['sleep_avg_hours']} 小时"
        if data.get("sleep_quality_avg"):
            sleep_info += f", 质量评分: {data['sleep_quality_avg']}/10"
        if data.get("sleep_pattern", {}).get("regularity_score"):
            sleep_info += f", 规律性: {data['sleep_pattern']['regularity_score']}/100"

    habit_info = ""
    if data.get("habit_stats"):
        habit_types = []
        for checkin_type, stats in data["habit_stats"].items():
            if stats.get("current_streak", 0) > 0:
                habit_types.append(f"{checkin_type}:{stats['current_streak']}天")
        if habit_types:
            habit_info = f"- 习惯打卡: {', '.join(habit_types)}"
            habit_info += f", 完成率: {data.get('habit_completion_rate', 0):.0f}%"

    prompt = f"""请根据以下数据生成一份个性化的周报总结：

【本周数据】({data["week_start"]} 至 {data["week_end"]})
- 体重变化: {data["weight_change"]}kg (平均 {data["avg_weight"]}kg)
- 运动天数: {data["exercise_days"]} 天 (共 {data["total_exercise_minutes"]} 分钟)
- 消耗热量: {data["total_calories_out"]} 千卡
- 平均摄入: {data["avg_calories_in"]} 千卡/天
- 饮水达标: {data["water_goal_days"]} 天
{sleep_info}
{habit_info}

【用户画像】
- 动力类型: {data.get("user_preferences", {}).get("motivation_type", "未知")}
- 目标体重: {data.get("user_preferences", {}).get("target_weight", "未设置")}kg

【本周亮点】
{chr(10).join(data["highlights"]) if data["highlights"] else "暂无"}

【改进空间】
{chr(10).join(data["improvements"]) if data["improvements"] else "暂无"}

请用温暖、鼓励的语气写一份周报总结（200-300字），包括：
1. 整体评价（根据用户动力类型调整语气）
2. 值得表扬的地方（具体提到各项进步）
3. 下周建议（针对改进空间给出可执行建议）
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

        response = await ai_service.chat(messages, max_tokens=800)

        if response.error:
            # AI 失败，使用模板生成
            summary = generate_fallback_summary(data)
        else:
            summary = response.content
    except Exception:
        summary = generate_fallback_summary(data)

    return {
        "summary": summary,
        "highlights": data["highlights"],
        "improvements": data["improvements"],
    }


def generate_fallback_summary(data: Dict[str, Any]) -> str:
    """AI 失败时的备用总结"""
    parts = []

    # 开头
    if data["weight_change"] < -0.2:
        parts.append(f"本周减重 {abs(data['weight_change'])}kg，效果很不错！")
    elif data["weight_change"] > 0.2:
        parts.append("本周体重有所波动，不要气馁，继续加油！")
    else:
        parts.append("本周体重保持稳定，继续保持！")

    # 运动
    if data["exercise_days"] >= 4:
        parts.append(f"你坚持了 {data['exercise_days']} 天运动，非常自律！")
    elif data["exercise_days"] >= 2:
        parts.append(f"本周运动 {data['exercise_days']} 天，还有提升空间。")
    else:
        parts.append("建议下周增加运动量，哪怕只是散步也好。")

    # 结尾
    parts.append("记住，健康减重是一个过程，每一步都算数。下周继续加油！💪")

    return " ".join(parts)
