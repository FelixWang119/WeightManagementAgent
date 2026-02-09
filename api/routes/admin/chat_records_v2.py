"""
聊天记录管理路由 V2
提供按用户+日期聚合的聊天记录查看功能

功能：
1. 获取有聊天记录的用户列表
2. 获取某用户的活跃日期列表
3. 按用户+日期查询消息详情
"""

import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, and_, or_, func, text, cast, Integer
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

from models.database import get_db, ChatHistory, User, MessageRole, MessageType
from api.dependencies.auth_v2 import get_current_admin
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


# ============ 请求/响应模型 ============

class ChatUserBase(BaseModel):
    """用户基础信息（用于聊天记录）"""
    id: int
    nickname: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    is_vip: bool = False
    
    class Config:
        from_attributes = True


class ChatUserResponse(BaseModel):
    """聊天用户响应（包含统计信息）"""
    user_id: int
    nickname: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    is_vip: bool = False
    total_messages: int
    first_chat_date: str  # YYYY-MM-DD
    last_chat_date: str   # YYYY-MM-DD
    active_days: int
    
    class Config:
        from_attributes = True


class ChatUserListResponse(BaseModel):
    """聊天用户列表响应"""
    total: int
    page: int
    page_size: int
    users: List[ChatUserResponse]


class ChatDateResponse(BaseModel):
    """聊天日期响应（单日统计）"""
    date: str  # YYYY-MM-DD
    message_count: int
    first_message_time: str  # HH:MM:SS
    last_message_time: str   # HH:MM:SS
    user_messages: int
    assistant_messages: int
    system_messages: int = 0
    
    class Config:
        from_attributes = True


class ChatUserDatesResponse(BaseModel):
    """用户聊天日期列表响应"""
    user_id: int
    nickname: str
    avatar_url: Optional[str] = None
    dates: List[ChatDateResponse]


class ChatMessageItem(BaseModel):
    """单条消息"""
    id: int
    role: MessageRole
    content: str
    msg_type: MessageType
    meta_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatConversationSummary(BaseModel):
    """对话摘要"""
    first_message_time: datetime
    last_message_time: datetime
    user_messages: int
    assistant_messages: int
    system_messages: int = 0


class ChatDateMessagesResponse(BaseModel):
    """按日期查询的消息详情响应"""
    user_id: int
    nickname: str
    avatar_url: Optional[str] = None
    date: str  # YYYY-MM-DD
    total: int
    page: int
    page_size: int
    summary: ChatConversationSummary
    messages: List[ChatMessageItem]


# ============ 辅助函数 ============

async def get_user_with_chats(db: AsyncSession, user_id: int) -> Optional[User]:
    """获取有聊天记录的用户"""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ============ API 路由 ============

@router.get("/users", response_model=ChatUserListResponse)
async def list_chat_users(
    search: Optional[str] = Query(None, description="搜索用户昵称"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取有聊天记录的用户列表
    
    需要管理员权限
    
    返回所有有聊天记录的用户及其统计信息
    """
    try:
        # 构建子查询：每个用户的聊天统计
        subquery = (
            select(
                ChatHistory.user_id,
                func.count(ChatHistory.id).label('total_messages'),
                func.min(ChatHistory.created_at).label('first_chat'),
                func.max(ChatHistory.created_at).label('last_chat'),
                func.count(func.distinct(func.date(ChatHistory.created_at))).label('active_days')
            )
            .group_by(ChatHistory.user_id)
            .subquery()
        )
        
        # 构建主查询
        query = (
            select(
                User,
                subquery.c.total_messages,
                func.date(subquery.c.first_chat).label('first_chat_date'),
                func.date(subquery.c.last_chat).label('last_chat_date'),
                subquery.c.active_days
            )
            .join(subquery, User.id == subquery.c.user_id)
        )
        
        # 搜索条件
        if search:
            query = query.where(User.nickname.ilike(f"%{search}%"))
        
        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 添加排序和分页
        query = query.order_by(desc(subquery.c.last_chat))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        # 构建响应
        users = []
        for row in rows:
            user, total_messages, first_chat_date, last_chat_date, active_days = row
            
            # 获取用户信息
            user_info = {
                "user_id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "phone": user.phone,
                "is_vip": user.is_vip,
                "total_messages": total_messages,
                "first_chat_date": first_chat_date,
                "last_chat_date": last_chat_date,
                "active_days": active_days
            }
            users.append(ChatUserResponse(**user_info))
        
        return ChatUserListResponse(
            total=total,
            page=page,
            page_size=page_size,
            users=users
        )
        
    except Exception as e:
        logger.exception("获取聊天用户列表失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户列表失败: {str(e)}"
        )


@router.get("/users/{user_id}/dates", response_model=ChatUserDatesResponse)
async def list_user_chat_dates(
    user_id: int,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某用户的活跃日期列表
    
    需要管理员权限
    
    返回该用户所有聊天的日期统计，按日期降序排列
    """
    try:
        # 验证用户存在
        target_user = await get_user_with_chats(db, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 构建日期统计子查询
        date_subquery = (
            select(
                func.date(ChatHistory.created_at).label('chat_date'),
                func.count(ChatHistory.id).label('message_count'),
                func.min(func.time(ChatHistory.created_at)).label('first_time'),
                func.max(func.time(ChatHistory.created_at)).label('last_time'),
                func.sum(func.cast(ChatHistory.role == MessageRole.USER, Integer)).label('user_msgs'),
                func.sum(func.cast(ChatHistory.role == MessageRole.ASSISTANT, Integer)).label('assistant_msgs')
            )
            .where(ChatHistory.user_id == user_id)
        )
        
        # 添加日期范围筛选
        if start_date:
            date_subquery = date_subquery.where(
                func.date(ChatHistory.created_at) >= start_date
            )
        if end_date:
            date_subquery = date_subquery.where(
                func.date(ChatHistory.created_at) <= end_date
            )
        
        # 按日期分组
        date_subquery = date_subquery.group_by(func.date(ChatHistory.created_at))
        
        # 执行查询
        result = await db.execute(date_subquery.order_by(text('chat_date DESC')))
        date_rows = result.fetchall()
        
        # 构建响应
        dates = []
        for row in date_rows:
            chat_date, message_count, first_time, last_time, user_msgs, assistant_msgs = row
            
            date_info = {
                "date": chat_date,
                "message_count": message_count,
                "first_message_time": first_time,
                "last_message_time": last_time,
                "user_messages": user_msgs or 0,
                "assistant_messages": assistant_msgs or 0,
                "system_messages": 0
            }
            dates.append(ChatDateResponse(**date_info))
        
        return ChatUserDatesResponse(
            user_id=user_id,
            nickname=target_user.nickname,
            avatar_url=target_user.avatar_url,
            dates=dates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取用户日期列表失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日期列表失败: {str(e)}"
        )


@router.get("", response_model=ChatDateMessagesResponse)
async def get_chat_messages_by_user_date(
    user_id: int = Query(..., description="用户ID"),
    chat_date: str = Query(..., description="日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    按用户+日期获取聊天消息详情
    
    需要管理员权限
    
    返回指定用户在指定日期的所有聊天消息，按时间升序排列
    """
    try:
        # 验证用户存在
        target_user = await get_user_with_chats(db, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 解析日期
        try:
            target_date = datetime.strptime(chat_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="日期格式错误，请使用 YYYY-MM-DD 格式"
            )
        
        # 日期范围
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())
        
        # 计算统计信息
        stats_query = (
            select(
                func.min(ChatHistory.created_at).label('first_time'),
                func.max(ChatHistory.created_at).label('last_time'),
                func.sum(func.cast(ChatHistory.role == MessageRole.USER, Integer)).label('user_msgs'),
                func.sum(func.cast(ChatHistory.role == MessageRole.ASSISTANT, Integer)).label('assistant_msgs'),
                func.sum(func.cast(ChatHistory.role == MessageRole.SYSTEM, Integer)).label('system_msgs'),
                func.count(ChatHistory.id).label('total')
            )
            .where(
                and_(
                    ChatHistory.user_id == user_id,
                    ChatHistory.created_at >= start_dt,
                    ChatHistory.created_at <= end_dt
                )
            )
        )
        
        stats_result = await db.execute(stats_query)
        stats = stats_result.fetchone()
        
        if not stats or stats.total == 0:
            # 没有消息时返回空结果
            return ChatDateMessagesResponse(
                user_id=user_id,
                nickname=target_user.nickname,
                avatar_url=target_user.avatar_url,
                date=chat_date,
                total=0,
                page=1,
                page_size=page_size,
                summary=ChatConversationSummary(
                    first_message_time=start_dt,
                    last_message_time=end_dt,
                    user_messages=0,
                    assistant_messages=0,
                    system_messages=0
                ),
                messages=[]
            )
        
        # 获取消息列表
        messages_query = (
            select(ChatHistory)
            .where(
                and_(
                    ChatHistory.user_id == user_id,
                    ChatHistory.created_at >= start_dt,
                    ChatHistory.created_at <= end_dt
                )
            )
            .order_by(ChatHistory.created_at.asc())
        )
        
        # 分页
        messages_query = messages_query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(messages_query)
        messages = result.scalars().all()
        
        # 构建响应
        message_list = []
        for msg in messages:
            message_list.append(
                ChatMessageItem(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    msg_type=msg.msg_type,
                    meta_data=msg.meta_data,
                    created_at=msg.created_at
                )
            )
        
        summary = ChatConversationSummary(
            first_message_time=stats.first_time,
            last_message_time=stats.last_time,
            user_messages=stats.user_msgs or 0,
            assistant_messages=stats.assistant_msgs or 0,
            system_messages=stats.system_msgs or 0
        )
        
        return ChatDateMessagesResponse(
            user_id=user_id,
            nickname=target_user.nickname,
            avatar_url=target_user.avatar_url,
            date=chat_date,
            total=stats.total or 0,
            page=page,
            page_size=page_size,
            summary=summary,
            messages=message_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取聊天消息失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取消息失败: {str(e)}"
        )
