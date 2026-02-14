"""
配置相关 API
提供配置热更新能力
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from models.database import get_db, User, UserProfile
from api.routes.user import get_current_user
from config.profiling_questions import get_profiling_questions, get_default_suggestions
from services.intelligent_decision_engine import DecisionMode

router = APIRouter()


class DecisionModeUpdate(BaseModel):
    decision_mode: str


@router.get("/decision-mode")
async def get_decision_mode(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取用户决策模式配置"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    decision_mode = profile.decision_mode if profile else "balanced"

    mode_descriptions = {
        "conservative": "保守模式：80%规则 + 20%AI，适合新手用户",
        "balanced": "平衡模式：50%规则 + 50%AI，默认推荐",
        "intelligent": "智能模式：20%规则 + 80%AI，适合高级用户",
    }

    return {
        "success": True,
        "data": {
            "decision_mode": decision_mode,
            "description": mode_descriptions.get(decision_mode, ""),
            "available_modes": list(mode_descriptions.keys()),
        },
    }


@router.post("/decision-mode")
async def update_decision_mode(
    mode_data: DecisionModeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户决策模式"""
    valid_modes = ["conservative", "balanced", "intelligent"]

    if mode_data.decision_mode not in valid_modes:
        return {"success": False, "error": f"无效的决策模式，可选值: {valid_modes}"}

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if profile:
        profile.decision_mode = mode_data.decision_mode
    else:
        profile = UserProfile(
            user_id=current_user.id, decision_mode=mode_data.decision_mode
        )
        db.add(profile)

    await db.commit()

    mode_names = {
        "conservative": "保守模式",
        "balanced": "平衡模式",
        "intelligent": "智能模式",
    }

    return {
        "success": True,
        "message": f"决策模式已更新为 {mode_names.get(mode_data.decision_mode, mode_data.decision_mode)}",
        "data": {"decision_mode": mode_data.decision_mode},
    }


@router.get("/context-events")
async def get_context_events(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取用户当前上下文事件（商务应酬/身体不适/旅行等）"""
    from services.configurable_event_detector import ConfigurableEventDetector

    detector = ConfigurableEventDetector()

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    events = await detector.detect_events_from_user_history(current_user.id, db)

    event_names = {
        "business_dinner": "商务应酬",
        "illness": "身体不适",
        "travel": "旅行出差",
        "overtime": "加班工作",
        "family_event": "家庭事务",
        "special_occasion": "特殊场合",
    }

    return {
        "success": True,
        "data": {
            "user_id": current_user.id,
            "decision_mode": profile.decision_mode if profile else "balanced",
            "active_events": [
                {
                    "type": e.type,
                    "type_name": event_names.get(e.type, e.type),
                    "description": e.description,
                    "confidence": e.confidence,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "end_time": e.end_time.isoformat() if e.end_time else None,
                    "source": e.source,
                }
                for e in events
            ],
            "event_count": len(events),
        },
    }

    return {
        "success": True,
        "message": f"决策模式已更新为 {mode_names.get(mode_data.decision_mode, mode_data.decision_mode)}",
        "data": {"decision_mode": mode_data.decision_mode},
    }


@router.get("/default-suggestions")
async def get_default_suggestions_api():
    """获取默认建议列表"""
    return {"success": True, "suggestions": get_default_suggestions()}


@router.post("/reload-profiling-questions")
async def reload_profiling_questions():
    """重新加载画像问题库（用于热更新）"""
    qb = get_profiling_questions()
    qb.reload()

    return {
        "success": True,
        "message": f"已重新加载 {qb.get_answer_count()} 个问题",
        "categories": qb.get_categories(),
    }


@router.get("/profiling-questions")
async def get_profiling_questions_info():
    """获取画像问题库信息"""
    qb = get_profiling_questions()

    return {
        "success": True,
        "total_count": qb.get_answer_count(),
        "categories": [
            {"name": cat, "count": len(qb.get_questions_by_category(cat))}
            for cat in qb.get_categories()
        ],
    }
