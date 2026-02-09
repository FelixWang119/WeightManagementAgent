"""
聊天记录管理路由
提供聊天记录的查看、搜索和导出功能
"""

import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, and_, or_, func, between
from sqlalchemy.orm import selectinload, aliased
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date
import logging
import json
import csv
import io

from models.database import get_db, ChatHistory, User, MessageRole, MessageType
from api.dependencies.auth_v2 import get_current_admin
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


# ============ 请求/响应模型 ============

class UserBase(BaseModel):
    """用户基础信息"""
    id: int
    nickname: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    is_vip: bool = False
    

class ChatMessageBase(BaseModel):
    """聊天消息基础信息"""
    id: int
    role: MessageRole
    content: str
    msg_type: MessageType
    meta_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    

class ChatMessageResponse(ChatMessageBase):
    """聊天消息响应（包含用户信息）"""
    user: UserBase
    
    class Config:
        from_attributes = True


class ChatMessageDetailResponse(ChatMessageBase):
    """聊天消息详情响应（完整信息）"""
    user: UserBase
    user_id: int
    raw_content: Optional[str] = None  # 原始内容（如需解码）
    
    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """聊天记录列表响应"""
    total: int
    page: int
    page_size: int
    items: List[ChatMessageResponse]


class ChatStatsResponse(BaseModel):
    """聊天统计响应"""
    total_messages: int
    user_messages: int
    assistant_messages: int
    system_messages: int
    today_messages: int
    messages_per_user: Dict[str, int]  # 用户ID -> 消息数
    daily_stats: List[Dict[str, Any]]  # 每日统计


class ExportFormat(str, enum.Enum):
    """导出格式"""
    JSON = "json"
    CSV = "csv"


# ============ 辅助函数 ============

async def get_chat_with_user(db: AsyncSession, message_id: int) -> Optional[ChatHistory]:
    """获取聊天记录及其用户信息"""
    result = await db.execute(
        select(ChatHistory)
        .options(selectinload(ChatHistory.user))
        .where(ChatHistory.id == message_id)
    )
    return result.scalar_one_or_none()


async def search_chat_messages(
    db: AsyncSession,
    *,
    user_id: Optional[int] = None,
    search_text: Optional[str] = None,
    role: Optional[MessageRole] = None,
    msg_type: Optional[MessageType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    exclude_system: bool = True
) -> List[ChatHistory]:
    """搜索聊天消息（通用搜索函数）"""
    conditions = []
    
    if user_id:
        conditions.append(ChatHistory.user_id == user_id)
    
    if search_text:
        conditions.append(ChatHistory.content.ilike(f"%{search_text}%"))
    
    if role:
        conditions.append(ChatHistory.role == role)
    
    if msg_type:
        conditions.append(ChatHistory.msg_type == msg_type)
    
    if start_date:
        conditions.append(ChatHistory.created_at >= start_date)
    
    if end_date:
        conditions.append(ChatHistory.created_at <= end_date)
    
    if exclude_system:
        conditions.append(ChatHistory.role != MessageRole.SYSTEM)
    
    query = select(ChatHistory).options(selectinload(ChatHistory.user))
    
    if conditions:
        query = query.where(*conditions)
    
    result = await db.execute(query.order_by(desc(ChatHistory.created_at)))
    return result.scalars().all()


# ============ API 路由 ============

@router.get("", response_model=ChatListResponse)
async def list_chat_messages(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    search: Optional[str] = Query(None, description="搜索消息内容"),
    role: Optional[MessageRole] = Query(None, description="按角色筛选"),
    msg_type: Optional[MessageType] = Query(None, description="按消息类型筛选"),
    start_date: Optional[date] = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: Optional[date] = Query(None, description="结束日期（YYYY-MM-DD）"),
    exclude_system: bool = Query(True, description="是否排除系统消息"),
    sort_by: str = Query("created_at", description="排序字段: created_at, user_id"),
    sort_order: str = Query("desc", description="排序顺序: asc, desc"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取聊天记录列表（支持分页和筛选）
    
    需要管理员权限
    """
    # 构建查询条件
    conditions = []
    
    if user_id:
        conditions.append(ChatHistory.user_id == user_id)
    
    if search:
        conditions.append(ChatHistory.content.ilike(f"%{search}%"))
    
    if role:
        conditions.append(ChatHistory.role == role)
    
    if msg_type:
        conditions.append(ChatHistory.msg_type == msg_type)
    
    # 日期处理
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        conditions.append(ChatHistory.created_at >= start_dt)
    
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        conditions.append(ChatHistory.created_at <= end_dt)
    
    if exclude_system:
        conditions.append(ChatHistory.role != MessageRole.SYSTEM)
    
    # 构建排序
    sort_column = {
        "created_at": ChatHistory.created_at,
        "user_id": ChatHistory.user_id
    }.get(sort_by, ChatHistory.created_at)
    
    sort_direction = desc if sort_order == "desc" else asc
    
    # 计算总数
    count_query = select(func.count(ChatHistory.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # 获取数据
    query = select(ChatHistory).options(selectinload(ChatHistory.user))
    if conditions:
        query = query.where(*conditions)
    
    query = query.order_by(sort_direction(sort_column)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # 转换为响应模型
    message_responses = []
    for msg in messages:
        user_base = UserBase(
            id=msg.user.id,
            nickname=msg.user.nickname,
            avatar_url=msg.user.avatar_url,
            phone=msg.user.phone,
            is_vip=msg.user.is_vip
        )
        
        message_responses.append(
            ChatMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                msg_type=msg.msg_type,
                meta_data=msg.meta_data,
                created_at=msg.created_at,
                user=user_base
            )
        )
    
    return ChatListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=message_responses
    )


@router.get("/{message_id}", response_model=ChatMessageDetailResponse)
async def get_chat_message(
    message_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取聊天记录详情
    
    需要管理员权限
    """
    msg = await get_chat_with_user(db, message_id)
    
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在"
        )
    
    user_base = UserBase(
        id=msg.user.id,
        nickname=msg.user.nickname,
        avatar_url=msg.user.avatar_url,
        phone=msg.user.phone,
        is_vip=msg.user.is_vip
    )
    
    return ChatMessageDetailResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        msg_type=msg.msg_type,
        meta_data=msg.meta_data,
        created_at=msg.created_at,
        user=user_base,
        user_id=msg.user_id,
        raw_content=msg.content  # 这里可以根据需要添加解码逻辑
    )


@router.get("/stats/summary")
async def get_chat_stats(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取聊天统计摘要
    
    需要管理员权限
    """
    # 统计总消息数
    total_result = await db.execute(select(func.count(ChatHistory.id)))
    total_messages = total_result.scalar_one()
    
    # 按角色统计
    user_count_result = await db.execute(
        select(func.count(ChatHistory.id)).where(ChatHistory.role == MessageRole.USER)
    )
    user_messages = user_count_result.scalar_one()
    
    assistant_count_result = await db.execute(
        select(func.count(ChatHistory.id)).where(ChatHistory.role == MessageRole.ASSISTANT)
    )
    assistant_messages = assistant_count_result.scalar_one()
    
    system_count_result = await db.execute(
        select(func.count(ChatHistory.id)).where(ChatHistory.role == MessageRole.SYSTEM)
    )
    system_messages = system_count_result.scalar_one()
    
    # 今日消息
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(ChatHistory.id)).where(ChatHistory.created_at >= today_start)
    )
    today_messages = today_result.scalar_one()
    
    # 用户消息数排名（前10）
    user_stats_result = await db.execute(
        select(
            User.id,
            User.nickname,
            func.count(ChatHistory.id).label("message_count")
        )
        .join(ChatHistory, User.id == ChatHistory.user_id)
        .where(ChatHistory.role != MessageRole.SYSTEM)
        .group_by(User.id, User.nickname)
        .order_by(desc("message_count"))
        .limit(10)
    )
    messages_per_user = {}
    for row in user_stats_result:
        messages_per_user[f"{row.nickname}(ID:{row.id})"] = row.message_count
    
    # 每日统计
    daily_stats = []
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    current_date = start_date
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())
        
        # 当日消息数
        day_count_result = await db.execute(
            select(func.count(ChatHistory.id)).where(
                ChatHistory.created_at >= day_start,
                ChatHistory.created_at <= day_end,
                ChatHistory.role != MessageRole.SYSTEM
            )
        )
        day_count = day_count_result.scalar_one()
        
        # 当日活跃用户数
        active_users_result = await db.execute(
            select(func.count(func.distinct(ChatHistory.user_id))).where(
                ChatHistory.created_at >= day_start,
                ChatHistory.created_at <= day_end,
                ChatHistory.role != MessageRole.SYSTEM
            )
        )
        active_users = active_users_result.scalar_one()
        
        daily_stats.append({
            "date": current_date,
            "message_count": day_count,
            "active_users": active_users
        })
        
        current_date += timedelta(days=1)
    
    return {
        "total_messages": total_messages,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "system_messages": system_messages,
        "today_messages": today_messages,
        "messages_per_user": messages_per_user,
        "daily_stats": daily_stats
    }


@router.get("/export/json")
async def export_chat_json(
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(1000, ge=1, le=10000, description="导出记录数限制"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    导出聊天记录为JSON格式
    
    需要管理员权限
    """
    # 构建查询条件
    conditions = [ChatHistory.role != MessageRole.SYSTEM]
    
    if user_id:
        conditions.append(ChatHistory.user_id == user_id)
    
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        conditions.append(ChatHistory.created_at >= start_dt)
    
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        conditions.append(ChatHistory.created_at <= end_dt)
    
    # 获取数据
    result = await db.execute(
        select(ChatHistory)
        .options(selectinload(ChatHistory.user))
        .where(*conditions)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()
    
    # 构建导出数据
    export_data = []
    for msg in messages:
        export_data.append({
            "id": msg.id,
            "user_id": msg.user_id,
            "user_nickname": msg.user.nickname,
            "user_phone": msg.user.phone,
            "role": msg.role.value,
            "msg_type": msg.msg_type.value,
            "content": msg.content,
            "meta_data": msg.meta_data,
            "created_at": msg.created_at.isoformat()
        })
    
    # 返回JSON文件
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=chat_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )


@router.get("/export/csv")
async def export_chat_csv(
    user_id: Optional[int] = Query(None, description="按用户ID筛选"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(1000, ge=1, le=10000, description="导出记录数限制"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    导出聊天记录为CSV格式
    
    需要管理员权限
    """
    # 构建查询条件
    conditions = [ChatHistory.role != MessageRole.SYSTEM]
    
    if user_id:
        conditions.append(ChatHistory.user_id == user_id)
    
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        conditions.append(ChatHistory.created_at >= start_dt)
    
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        conditions.append(ChatHistory.created_at <= end_dt)
    
    # 获取数据
    result = await db.execute(
        select(ChatHistory)
        .options(selectinload(ChatHistory.user))
        .where(*conditions)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()
    
    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow([
        "ID", "用户ID", "用户昵称", "用户手机", "角色", "消息类型", 
        "内容", "元数据", "创建时间"
    ])
    
    # 写入数据
    for msg in messages:
        meta_str = json.dumps(msg.meta_data, ensure_ascii=False) if msg.meta_data else ""
        writer.writerow([
            msg.id,
            msg.user_id,
            msg.user.nickname or "",
            msg.user.phone or "",
            msg.role.value,
            msg.msg_type.value,
            msg.content.replace('\n', ' ').replace('\r', ' ')[:500],  # 限制长度，避免CSV问题
            meta_str[:200],  # 限制长度
            msg.created_at.isoformat()
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=chat_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/search/advanced")
async def advanced_search(
    query: str = Query(..., min_length=1, description="搜索关键词"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    role: Optional[MessageRole] = Query(None, description="消息角色"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    高级搜索聊天记录
    
    需要管理员权限
    """
    # 构建条件
    conditions = [ChatHistory.content.ilike(f"%{query}%")]
    
    if user_id:
        conditions.append(ChatHistory.user_id == user_id)
    
    if role:
        conditions.append(ChatHistory.role == role)
    else:
        conditions.append(ChatHistory.role != MessageRole.SYSTEM)
    
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        conditions.append(ChatHistory.created_at >= start_dt)
    
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        conditions.append(ChatHistory.created_at <= end_dt)
    
    # 执行查询
    result = await db.execute(
        select(ChatHistory)
        .options(selectinload(ChatHistory.user))
        .where(*conditions)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()
    
    # 返回结果
    return [
        {
            "id": msg.id,
            "user_id": msg.user_id,
            "user_nickname": msg.user.nickname,
            "role": msg.role.value,
            "msg_type": msg.msg_type.value,
            "content": msg.content[:200] + ("..." if len(msg.content) > 200 else ""),
            "created_at": msg.created_at,
            "highlight_content": msg.content.replace(query, f"**{query}**")  # 高亮显示
        }
        for msg in messages
    ]