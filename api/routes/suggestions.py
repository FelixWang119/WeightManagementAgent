"""
智能建议 API
提供上下文感知建议、预测性建议、建议效果追踪
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from models.database import get_db, User
from api.routes.user import get_current_user
from services.smart_suggestion_service import (
    get_all_suggestions,
    ContextAwareSuggestionService,
    PredictiveSuggestionService,
    SuggestionEffectTracker,
)

router = APIRouter()


class SuggestionFeedback(BaseModel):
    suggestion_id: str
    action: str


@router.get("/suggestions")
async def get_suggestions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取所有智能建议

    - 整合上下文感知建议和预测性建议
    - 按优先级排序
    - 包含效果统计
    """
    result = await get_all_suggestions(current_user.id, db)
    return result


@router.get("/suggestions/context")
async def get_context_suggestions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取上下文感知建议

    - 基于时间、位置、状态的个性化建议
    - 包含异常提醒
    """
    suggestions = await ContextAwareSuggestionService.get_suggestions(
        current_user.id, db
    )
    return {
        "success": True,
        "data": {
            "suggestions": suggestions,
            "count": len(suggestions),
        },
    }


@router.get("/suggestions/predictive")
async def get_predictive_suggestions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取预测性建议

    - 基于体重趋势预测
    - 热量需求建议
    """
    suggestions = await PredictiveSuggestionService.get_predictive_suggestions(
        current_user.id, db
    )
    return {
        "success": True,
        "data": {
            "suggestions": suggestions,
            "count": len(suggestions),
        },
    }


@router.post("/suggestions/feedback")
async def submit_suggestion_feedback(
    feedback: SuggestionFeedback, current_user: User = Depends(get_current_user)
):
    """
    提交建议反馈

    - accepted: 用户接受建议
    - rejected: 用户拒绝建议
    - partial: 部分采纳
    """
    SuggestionEffectTracker.record_user_action(feedback.suggestion_id, feedback.action)
    effect_score = SuggestionEffectTracker.calculate_effect_score(
        feedback.suggestion_id
    )

    return {
        "success": True,
        "message": "反馈已记录",
        "data": {
            "suggestion_id": feedback.suggestion_id,
            "action": feedback.action,
            "effect_score": effect_score,
        },
    }


@router.get("/suggestions/effects")
async def get_suggestion_effects(days: int = 7):
    """
    获取建议效果统计

    - days: 统计天数（默认7天）
    - 返回采纳率、拒绝率等统计
    """
    stats = SuggestionEffectTracker.get_effect_stats(days)
    return {"success": True, "data": stats}
