"""
对话摘要 API 路由
包含：对话摘要生成、关键信息提取、摘要存储与检索
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from api.routes.user import get_current_user
from services.conversation_summary_service import ConversationSummaryService

router = APIRouter()


@router.post("/summary/generate")
async def generate_conversation_summary(
    days: int = Query(7, ge=1, le=30),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    生成对话摘要

    - **days**: 摘要天数（1-30天，默认7天）

    分析用户最近N天的对话，生成摘要并提取关键信息
    """
    result = await ConversationSummaryService.generate_summary(
        user_id=current_user.id, db=db, days=days
    )
    return result


@router.post("/summary/save")
async def save_conversation_summary(
    summary_data: dict,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    保存对话摘要

    - **summary_data**: 摘要数据（从generate接口获取）
    """
    success = await ConversationSummaryService.save_summary(
        user_id=current_user.id, summary_data=summary_data, db=db
    )

    return {"success": success, "message": "摘要保存成功" if success else "保存失败"}


@router.get("/summary/history")
async def get_summary_history(
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取历史摘要列表

    - **limit**: 返回数量（1-50，默认10）
    """
    result = await ConversationSummaryService.get_summaries(
        user_id=current_user.id, db=db, limit=limit
    )
    return result


@router.get("/summary/search")
async def search_summaries(
    query: str,
    limit: int = Query(5, ge=1, le=20),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索历史摘要

    - **query**: 搜索关键词
    - **limit**: 返回数量（1-20，默认5）
    """
    result = await ConversationSummaryService.search_summaries(
        user_id=current_user.id, query=query, db=db, limit=limit
    )
    return result


@router.post("/key-info/extract")
async def extract_key_info(messages: list, current_user=Depends(get_current_user)):
    """
    提取关键信息

    - **messages**: 消息列表

    从文本消息中提取关键健康信息
    """
    key_info = ConversationSummaryService._extract_key_info(messages)

    return {"success": True, "data": key_info}


@router.post("/preferences/extract")
async def extract_preferences(messages: list, current_user=Depends(get_current_user)):
    """
    提取用户偏好

    - **messages**: 消息列表

    分析对话提取用户偏好
    """
    preferences = ConversationSummaryService._extract_preferences(messages)

    return {"success": True, "data": preferences}
