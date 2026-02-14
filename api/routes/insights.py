"""
AI洞察 API
提供隐藏模式发现、异常检测、趋势预测、提醒策略优化
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from models.database import get_db, User
from api.routes.user import get_current_user
from services.ai_insights_service import (
    AIInsightsService,
    AnomalyDetectionService,
    TrendPredictionService,
    ReminderStrategyOptimizer,
)

router = APIRouter()


@router.get("/patterns")
async def get_hidden_patterns(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取隐藏模式发现

    - days: 分析天数（默认30天）
    - 返回发现的隐藏模式（睡眠-饮食关联、情绪性进食等）
    """
    result = await AIInsightsService.discover_hidden_patterns(
        current_user.id, db, days=days
    )
    return result


@router.get("/anomalies")
async def get_anomalies(
    days: int = 14,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取异常检测结果

    - days: 分析天数（默认14天）
    - 返回检测到的数据异常（体重波动、热量异常、睡眠异常）
    """
    result = await AnomalyDetectionService.detect_anomalies(
        current_user.id, db, days=days
    )
    return result


@router.get("/prediction/weight")
async def predict_weight_trend(
    days_ahead: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    预测体重趋势

    - days_ahead: 预测天数（默认7天）
    - 返回预测的体重趋势和建议
    """
    result = await TrendPredictionService.predict_weight_trend(
        current_user.id, db, days_ahead=days_ahead
    )
    return result


@router.get("/prediction/calorie-needs")
async def predict_calorie_needs(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    预测每日热量需求

    - 基于用户基础代谢率和活动水平计算TDEE
    - 返回推荐每日摄入热量
    """
    result = await TrendPredictionService.predict_calorie_needs(current_user.id, db)
    return result


@router.get("/reminder-optimization")
async def get_reminder_optimization(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取优化的提醒策略

    - 基于用户行为模式和异常情况
    - 返回个性化的提醒策略建议
    """
    result = await ReminderStrategyOptimizer.optimize_reminder_strategy(
        current_user.id, db
    )
    return result


@router.get("/dashboard")
async def get_insights_dashboard(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取AI洞察仪表盘

    - 综合展示所有洞察数据
    - 包括模式发现、异常检测、趋势预测、策略优化
    """
    patterns = await AIInsightsService.discover_hidden_patterns(
        current_user.id, db, days=days
    )
    anomalies = await AnomalyDetectionService.detect_anomalies(
        current_user.id, db, days=min(days, 14)
    )
    weight_prediction = await TrendPredictionService.predict_weight_trend(
        current_user.id, db
    )
    calorie_needs = await TrendPredictionService.predict_calorie_needs(
        current_user.id, db
    )
    reminder_strategy = await ReminderStrategyOptimizer.optimize_reminder_strategy(
        current_user.id, db
    )

    return {
        "success": True,
        "data": {
            "summary": {
                "patterns_found": patterns.get("patterns_found", 0),
                "anomalies_count": anomalies.get("anomalies_count", 0),
                "risk_level": anomalies.get("risk_level", "low"),
            },
            "patterns": patterns.get("patterns", []),
            "anomalies": anomalies.get("anomalies", []),
            "predictions": {
                "weight_trend": weight_prediction,
                "calorie_needs": calorie_needs,
            },
            "reminder_strategy": reminder_strategy,
        },
    }
