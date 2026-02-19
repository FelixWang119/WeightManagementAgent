"""
增强报告 API 路由
包含月度报告、报告分享和导出功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, Dict, Any
from datetime import date, datetime
import json

from models.database import (
    get_db,
    User,
    MonthlyReport,
)
from api.routes.user import get_current_user
from services.report_service import ReportService
from config.logging_config import get_module_logger

router = APIRouter()
logger = get_module_logger(__name__)
report_service = ReportService()


@router.post("/monthly/generate")
async def generate_monthly_report(
    month: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成月度报告"""
    try:
        result = await report_service.generate_monthly_report(
            current_user.id, month, db
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=result.get("error", "生成月度报告失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("生成月度报告失败: %s", e)
        raise HTTPException(status_code=500, detail="生成月度报告失败")


@router.get("/monthly/latest")
async def get_latest_monthly_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取最新月度报告"""
    try:
        result = await db.execute(
            select(MonthlyReport)
            .where(MonthlyReport.user_id == current_user.id)
            .order_by(desc(MonthlyReport.month_start))
            .limit(1)
        )

        report = result.scalar_one_or_none()

        if not report:
            return {"success": True, "message": "暂无月度报告，请先生成", "data": None}

        return {
            "success": True,
            "data": {
                "id": report.id,
                "month_start": report.month_start.isoformat(),
                "summary": report.summary_text,
                "weight_change": report.weight_change,
                "avg_weight": report.avg_weight,
                "total_exercise_minutes": report.total_exercise_minutes,
                "total_calories_in": report.total_calories_in,
                "total_calories_out": report.total_calories_out,
                "highlights": report.highlights,
                "improvements": report.improvements,
                "goals_progress": report.goals_progress,
                "habit_stats": report.habit_stats,
                "created_at": report.created_at.isoformat(),
            },
        }

    except Exception as e:
        logger.exception("获取最新月度报告失败: %s", e)
        raise HTTPException(status_code=500, detail="获取月度报告失败")


@router.get("/monthly/history")
async def get_monthly_report_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取月度报告历史"""
    try:
        result = await db.execute(
            select(MonthlyReport)
            .where(MonthlyReport.user_id == current_user.id)
            .order_by(desc(MonthlyReport.month_start))
            .limit(limit)
        )

        reports = result.scalars().all()

        return {
            "success": True,
            "count": len(reports),
            "data": [
                {
                    "id": r.id,
                    "month_start": r.month_start.isoformat(),
                    "weight_change": r.weight_change,
                    "avg_weight": r.avg_weight,
                    "total_exercise_minutes": r.total_exercise_minutes,
                    "highlights": r.highlights,
                    "improvements": r.improvements,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reports
            ],
        }

    except Exception as e:
        logger.exception("获取月度报告历史失败: %s", e)
        raise HTTPException(status_code=500, detail="获取报告历史失败")


@router.post("/{report_type}/{report_id}/share")
async def share_report(
    report_type: str,
    report_id: int,
    share_type: str = Query("image", regex="^(image|pdf|text)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """分享报告"""
    try:
        # 验证报告所有权
        if report_type == "weekly":
            from models.database import WeeklyReport

            result = await db.execute(
                select(WeeklyReport).where(
                    WeeklyReport.id == report_id,
                    WeeklyReport.user_id == current_user.id,
                )
            )
        elif report_type == "monthly":
            result = await db.execute(
                select(MonthlyReport).where(
                    MonthlyReport.id == report_id,
                    MonthlyReport.user_id == current_user.id,
                )
            )
        else:
            raise HTTPException(status_code=400, detail="无效的报告类型")

        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="报告不存在或无权访问")

        result = await report_service.share_report(
            report_id, report_type, share_type, db
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=result.get("error", "分享报告失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("分享报告失败: %s", e)
        raise HTTPException(status_code=500, detail="分享报告失败")


@router.get("/{report_type}/{report_id}/download")
async def download_report(
    report_type: str,
    report_id: int,
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载报告数据"""
    try:
        # 验证报告所有权并获取报告时间范围
        if report_type == "weekly":
            from models.database import WeeklyReport

            result = await db.execute(
                select(WeeklyReport).where(
                    WeeklyReport.id == report_id,
                    WeeklyReport.user_id == current_user.id,
                )
            )
            report = result.scalar_one_or_none()
            if report:
                start_date = report.week_start
                end_date = report.week_start + timedelta(days=6)
        elif report_type == "monthly":
            result = await db.execute(
                select(MonthlyReport).where(
                    MonthlyReport.id == report_id,
                    MonthlyReport.user_id == current_user.id,
                )
            )
            report = result.scalar_one_or_none()
            if report:
                start_date = report.month_start
                end_date = (
                    report.month_start.replace(day=28) + timedelta(days=4)
                ).replace(day=1) - timedelta(days=1)
        else:
            raise HTTPException(status_code=400, detail="无效的报告类型")

        if not report:
            raise HTTPException(status_code=404, detail="报告不存在或无权访问")

        result = await report_service.export_report_data(
            current_user.id, start_date, end_date, format, db
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=result.get("error", "导出数据失败")
            )

        data = result["data"]
        content = data["content"]

        # 返回文件下载
        headers = {
            "Content-Disposition": f"attachment; filename={data['filename']}",
            "Content-Type": data["content_type"],
        }

        return Response(
            content=content, headers=headers, media_type=data["content_type"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("下载报告数据失败: %s", e)
        raise HTTPException(status_code=500, detail="下载报告数据失败")


@router.get("/history/all")
async def get_all_report_history(
    limit: int = Query(20, ge=1, le=100),
    report_type: str = Query("all", regex="^(all|weekly|monthly)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有报告历史（周报+月报）"""
    try:
        result = await report_service.get_report_history(
            current_user.id, report_type, limit, db
        )

        if not result["success"]:
            raise HTTPException(
                status_code=500, detail=result.get("error", "获取报告历史失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取所有报告历史失败: %s", e)
        raise HTTPException(status_code=500, detail="获取报告历史失败")


@router.get("/comparison")
async def compare_reports(
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """比较两个时间段的数据"""
    try:
        # 收集第一个时间段的数据
        from services.report_service import ReportService

        service = ReportService()

        # 这里简化处理，实际需要更复杂的比较逻辑
        comparison = {
            "period1": {
                "start": period1_start.isoformat(),
                "end": period1_end.isoformat(),
            },
            "period2": {
                "start": period2_start.isoformat(),
                "end": period2_end.isoformat(),
            },
            "comparisons": {
                "weight": await _compare_weight_data(
                    current_user.id,
                    period1_start,
                    period1_end,
                    period2_start,
                    period2_end,
                    db,
                ),
                "exercise": await _compare_exercise_data(
                    current_user.id,
                    period1_start,
                    period1_end,
                    period2_start,
                    period2_end,
                    db,
                ),
                "nutrition": await _compare_nutrition_data(
                    current_user.id,
                    period1_start,
                    period1_end,
                    period2_start,
                    period2_end,
                    db,
                ),
            },
        }

        return {"success": True, "data": comparison}

    except Exception as e:
        logger.exception("比较报告失败: %s", e)
        raise HTTPException(status_code=500, detail="比较报告失败")


async def _compare_weight_data(
    user_id: int,
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
    db: AsyncSession,
) -> Dict[str, Any]:
    """比较体重数据"""
    from sqlalchemy import func

    # 获取第一个时间段的体重数据
    result = await db.execute(
        select(func.avg(WeightRecord.weight)).where(
            WeightRecord.user_id == user_id,
            WeightRecord.record_date >= period1_start,
            WeightRecord.record_date <= period1_end,
        )
    )
    avg_weight1 = result.scalar() or 0

    # 获取第二个时间段的体重数据
    result = await db.execute(
        select(func.avg(WeightRecord.weight)).where(
            WeightRecord.user_id == user_id,
            WeightRecord.record_date >= period2_start,
            WeightRecord.record_date <= period2_end,
        )
    )
    avg_weight2 = result.scalar() or 0

    weight_change = avg_weight2 - avg_weight1

    return {
        "period1_avg": round(avg_weight1, 2),
        "period2_avg": round(avg_weight2, 2),
        "change": round(weight_change, 2),
        "trend": "improving"
        if weight_change < 0
        else "worsening"
        if weight_change > 0
        else "stable",
    }


async def _compare_exercise_data(
    user_id: int,
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
    db: AsyncSession,
) -> Dict[str, Any]:
    """比较运动数据"""
    from sqlalchemy import func
    from datetime import datetime

    # 获取第一个时间段的运动数据
    result = await db.execute(
        select(func.sum(ExerciseRecord.duration_minutes)).where(
            ExerciseRecord.user_id == user_id,
            ExerciseRecord.record_time
            >= datetime.combine(period1_start, datetime.min.time()),
            ExerciseRecord.record_time
            <= datetime.combine(period1_end, datetime.max.time()),
        )
    )
    total_exercise1 = result.scalar() or 0

    # 获取第二个时间段的运动数据
    result = await db.execute(
        select(func.sum(ExerciseRecord.duration_minutes)).where(
            ExerciseRecord.user_id == user_id,
            ExerciseRecord.record_time
            >= datetime.combine(period2_start, datetime.min.time()),
            ExerciseRecord.record_time
            <= datetime.combine(period2_end, datetime.max.time()),
        )
    )
    total_exercise2 = result.scalar() or 0

    exercise_change = total_exercise2 - total_exercise1

    return {
        "period1_total": total_exercise1,
        "period2_total": total_exercise2,
        "change": exercise_change,
        "trend": "improving"
        if exercise_change > 0
        else "worsening"
        if exercise_change < 0
        else "stable",
    }


async def _compare_nutrition_data(
    user_id: int,
    period1_start: date,
    period1_end: date,
    period2_start: date,
    period2_end: date,
    db: AsyncSession,
) -> Dict[str, Any]:
    """比较营养数据"""
    from sqlalchemy import func
    from datetime import datetime

    # 获取第一个时间段的热量数据
    result = await db.execute(
        select(func.sum(MealRecord.total_calories)).where(
            MealRecord.user_id == user_id,
            MealRecord.record_time
            >= datetime.combine(period1_start, datetime.min.time()),
            MealRecord.record_time
            <= datetime.combine(period1_end, datetime.max.time()),
        )
    )
    total_calories1 = result.scalar() or 0

    # 获取第二个时间段的热量数据
    result = await db.execute(
        select(func.sum(MealRecord.total_calories)).where(
            MealRecord.user_id == user_id,
            MealRecord.record_time
            >= datetime.combine(period2_start, datetime.min.time()),
            MealRecord.record_time
            <= datetime.combine(period2_end, datetime.max.time()),
        )
    )
    total_calories2 = result.scalar() or 0

    calories_change = total_calories2 - total_calories1

    return {
        "period1_total": total_calories1,
        "period2_total": total_calories2,
        "change": calories_change,
        "trend": "improving"
        if calories_change < 0
        else "worsening"
        if calories_change > 0
        else "stable",
    }


# 导入必要的模型
from models.database import WeightRecord, ExerciseRecord, MealRecord
from datetime import timedelta
