"""
用户管理路由
提供用户的查看、统计和行为分析功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, and_, or_, func, case, extract
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date
import logging

from models.database import get_db, User, UserProfile, WeightRecord, MealRecord, ExerciseRecord, WaterRecord, SleepRecord, ChatHistory, Goal, MessageRole, MotivationType
from api.dependencies.auth_v2 import get_current_admin
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


# ============ 请求/响应模型 ============

class UserBase(BaseModel):
    """用户基础信息"""
    openid: str = Field(..., description="微信用户唯一标识")
    nickname: str = Field(..., description="用户昵称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    phone: Optional[str] = Field(None, description="手机号")


class UserProfileBase(BaseModel):
    """用户画像信息"""
    age: Optional[int] = Field(None, description="年龄")
    gender: Optional[str] = Field(None, description="性别")
    height: Optional[float] = Field(None, description="身高（cm）")
    bmr: Optional[int] = Field(None, description="基础代谢率（BMR）")
    motivation_type: Optional[str] = Field(None, description="动力类型")


class UserResponse(UserBase):
    """用户响应"""
    id: int
    is_vip: bool
    vip_expire: Optional[date]
    is_admin: bool
    admin_role: Optional[str]
    created_at: datetime
    last_login: datetime
    profile: Optional[UserProfileBase] = None
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """用户详情响应"""
    # 统计信息
    total_weight_records: int = 0
    total_meal_records: int = 0
    total_exercise_records: int = 0
    total_chat_messages: int = 0
    current_goal: Optional[Dict[str, Any]] = None
    recent_activity: Optional[Dict[str, Any]] = None


class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    page: int
    page_size: int
    items: List[UserResponse]


class UserStatsResponse(BaseModel):
    """用户统计响应"""
    total_users: int
    active_users_7d: int
    active_users_30d: int
    vip_users: int
    new_users_today: int
    new_users_7d: int
    avg_records_per_user: Dict[str, float]  # 平均记录数
    retention_rate_7d: float  # 7日留存率


class UserActivityResponse(BaseModel):
    """用户活跃度响应"""
    date: date
    active_users: int
    new_users: int
    chat_messages: int
    weight_records: int
    meal_records: int


# ============ 辅助函数 ============

async def get_user_with_profile(db: AsyncSession, user_id: int) -> Optional[User]:
    """获取用户及其画像信息"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_stats(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """获取用户统计数据"""
    stats = {}
    
    # 获取各种记录数量
    tables = [
        (WeightRecord, "weight_records"),
        (MealRecord, "meal_records"),
        (ExerciseRecord, "exercise_records"),
        (WaterRecord, "water_records"),
        (SleepRecord, "sleep_records"),
        (ChatHistory, "chat_messages")
    ]
    
    for model, stat_name in tables:
        count_query = select(func.count(model.id)).where(model.user_id == user_id)
        if model == ChatHistory:
            count_query = count_query.where(ChatHistory.role != MessageRole.SYSTEM)
        result = await db.execute(count_query)
        stats[stat_name] = result.scalar_one() or 0
    
    return stats


async def get_current_goal(db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    """获取用户当前目标"""
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == user_id, Goal.status == "active")
        .order_by(desc(Goal.created_at))
        .limit(1)
    )
    goal = result.scalar_one_or_none()
    
    if goal:
        return {
            "id": goal.id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date,
            "weekly_plan": goal.weekly_plan,
            "daily_calorie_target": goal.daily_calorie_target,
            "status": goal.status
        }
    return None


# ============ API 路由 ============

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索昵称或手机号"),
    is_vip: Optional[bool] = Query(None, description="按VIP状态筛选"),
    is_admin: Optional[bool] = Query(None, description="按管理员状态筛选"),
    sort_by: str = Query("created_at", description="排序字段: created_at, last_login, nickname"),
    sort_order: str = Query("desc", description="排序顺序: asc, desc"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户列表（支持分页和筛选）
    
    需要管理员权限
    """
    # 构建查询条件
    conditions = []
    
    if search:
        search_condition = or_(
            User.nickname.ilike(f"%{search}%"),
            User.phone.ilike(f"%{search}%")
        )
        conditions.append(search_condition)
    
    if is_vip is not None:
        conditions.append(User.is_vip == is_vip)
    
    if is_admin is not None:
        conditions.append(User.is_admin == is_admin)
    
    # 构建排序
    sort_column = {
        "created_at": User.created_at,
        "last_login": User.last_login,
        "nickname": User.nickname
    }.get(sort_by, User.created_at)
    
    sort_direction = desc if sort_order == "desc" else asc
    
    # 计算总数
    count_query = select(func.count(User.id))
    if conditions:
        count_query = count_query.where(*conditions)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # 获取数据
    query = select(User).options(selectinload(User.profile))
    if conditions:
        query = query.where(*conditions)
    query = query.order_by(sort_direction(sort_column)).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 转换为响应模型
    user_responses = []
    for user_obj in users:
        profile_data = None
        if user_obj.profile:
            profile_data = UserProfileBase(
                age=user_obj.profile.age,
                gender=user_obj.profile.gender,
                height=user_obj.profile.height,
                bmr=user_obj.profile.bmr,
                motivation_type=user_obj.profile.motivation_type.value if user_obj.profile.motivation_type else None
            )
        
        user_responses.append(
            UserResponse(
                id=user_obj.id,
                openid=user_obj.openid,
                nickname=user_obj.nickname,
                avatar_url=user_obj.avatar_url,
                phone=user_obj.phone,
                is_vip=user_obj.is_vip,
                vip_expire=user_obj.vip_expire,
                is_admin=user_obj.is_admin,
                admin_role=user_obj.admin_role,
                created_at=user_obj.created_at,
                last_login=user_obj.last_login,
                profile=profile_data
            )
        )
    
    return UserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=user_responses
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户详情
    
    需要管理员权限
    """
    print(f"DEBUG get_user called for user_id={user_id}")
    import traceback
    try:
        user_obj = await get_user_with_profile(db, user_id)
        
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 获取统计信息
        stats = await get_user_stats(db, user_id)
        current_goal = await get_current_goal(db, user_id)
        
        # 获取最近活动（最近7天）
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # 最近体重记录
        weight_result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(desc(WeightRecord.record_time))
            .limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()
        
        # 最近聊天消息
        chat_result = await db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id, ChatHistory.role != MessageRole.SYSTEM)
            .order_by(desc(ChatHistory.created_at))
            .limit(1)
        )
        latest_chat = chat_result.scalar_one_or_none()
        
        recent_activity = {
            "last_weight_record": latest_weight.record_time if latest_weight else None,
            "last_chat": latest_chat.created_at if latest_chat else None,
            "activity_7d": {
                "weight_records": (await db.execute(
                    select(func.count()).where(
                        WeightRecord.user_id == user_id,
                        WeightRecord.created_at >= seven_days_ago
                    )
                )).scalar_one() or 0,
                "meal_records": (await db.execute(
                    select(func.count()).where(
                        MealRecord.user_id == user_id,
                        MealRecord.created_at >= seven_days_ago
                    )
                )).scalar_one() or 0,
                "chat_messages": (await db.execute(
                    select(func.count()).where(
                        ChatHistory.user_id == user_id,
                        ChatHistory.role != MessageRole.SYSTEM,
                        ChatHistory.created_at >= seven_days_ago
                    )
                )).scalar_one() or 0,
            }
        }
        
        # 构建响应
        profile_data = None
        if user_obj.profile:
            profile_data = UserProfileBase(
                age=user_obj.profile.age,
                gender=user_obj.profile.gender,
                height=user_obj.profile.height,
                bmr=user_obj.profile.bmr,
                motivation_type=user_obj.profile.motivation_type.value if user_obj.profile.motivation_type else None
            )
        
        return UserDetailResponse(
            id=user_obj.id,
            openid=user_obj.openid,
            nickname=user_obj.nickname,
            avatar_url=user_obj.avatar_url,
            phone=user_obj.phone,
            is_vip=user_obj.is_vip,
            vip_expire=user_obj.vip_expire,
            is_admin=user_obj.is_admin,
            admin_role=user_obj.admin_role,
            created_at=user_obj.created_at,
            last_login=user_obj.last_login,
            profile=profile_data,
            total_weight_records=stats.get("weight_records", 0),
            total_meal_records=stats.get("meal_records", 0),
            total_exercise_records=stats.get("exercise_records", 0),
            total_chat_messages=stats.get("chat_messages", 0),
            current_goal=current_goal,
            recent_activity=recent_activity
        )
    except Exception as e:
        print(f"ERROR in get_user: {e}")
        traceback.print_exc()
        raise


@router.get("/stats/summary", response_model=UserStatsResponse)
async def get_user_stats_summary(
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户统计摘要
    
    需要管理员权限
    """
    # 总用户数
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar_one()
    
    # VIP用户数
    vip_result = await db.execute(select(func.count(User.id)).where(User.is_vip == True))
    vip_users = vip_result.scalar_one()
    
    # 活跃用户（7天内登录）
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    active_7d_result = await db.execute(
        select(func.count(User.id)).where(User.last_login >= seven_days_ago)
    )
    active_users_7d = active_7d_result.scalar_one()
    
    # 活跃用户（30天内登录）
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_30d_result = await db.execute(
        select(func.count(User.id)).where(User.last_login >= thirty_days_ago)
    )
    active_users_30d = active_30d_result.scalar_one()
    
    # 今日新增用户
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )
    new_users_today = new_today_result.scalar_one()
    
    # 7日新增用户
    seven_days_start = datetime.utcnow() - timedelta(days=7)
    new_7d_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= seven_days_start)
    )
    new_users_7d = new_7d_result.scalar_one()
    
    # 平均记录数
    avg_records = {}
    
    # 计算留存率（7日留存）
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    seven_to_fourteen_days_ago = fourteen_days_ago + timedelta(days=7)
    
    # 7-14天前注册的用户
    cohort_result = await db.execute(
        select(func.count(User.id)).where(
            User.created_at >= fourteen_days_ago,
            User.created_at < seven_to_fourteen_days_ago
        )
    )
    cohort_size = cohort_result.scalar_one()
    
    # 7-14天前注册且在7天内活跃的用户
    retained_result = await db.execute(
        select(func.count(User.id)).where(
            User.created_at >= fourteen_days_ago,
            User.created_at < seven_to_fourteen_days_ago,
            User.last_login >= seven_days_ago
        )
    )
    retained_users = retained_result.scalar_one()
    
    retention_rate_7d = (retained_users / cohort_size * 100) if cohort_size > 0 else 0
    
    return UserStatsResponse(
        total_users=total_users,
        active_users_7d=active_users_7d,
        active_users_30d=active_users_30d,
        vip_users=vip_users,
        new_users_today=new_users_today,
        new_users_7d=new_users_7d,
        avg_records_per_user=avg_records,
        retention_rate_7d=round(retention_rate_7d, 2)
    )


@router.get("/stats/activity")
async def get_user_activity(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户活跃度趋势
    
    需要管理员权限
    """
    activities = []
    
    # 生成日期范围
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    current_date = start_date
    while current_date <= end_date:
        # 计算每日活跃用户数（当天有登录）
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())
        
        # 活跃用户
        active_result = await db.execute(
            select(func.count(User.id)).where(
                User.last_login >= day_start,
                User.last_login <= day_end
            )
        )
        active_users = active_result.scalar_one()
        
        # 新增用户
        new_result = await db.execute(
            select(func.count(User.id)).where(
                User.created_at >= day_start,
                User.created_at <= day_end
            )
        )
        new_users = new_result.scalar_one()
        
        # 聊天消息数
        chat_result = await db.execute(
            select(func.count(ChatHistory.id)).where(
                ChatHistory.created_at >= day_start,
                ChatHistory.created_at <= day_end,
            ChatHistory.role != MessageRole.SYSTEM
            )
        )
        chat_messages = chat_result.scalar_one()
        
        # 体重记录数
        weight_result = await db.execute(
            select(func.count(WeightRecord.id)).where(
                WeightRecord.created_at >= day_start,
                WeightRecord.created_at <= day_end
            )
        )
        weight_records = weight_result.scalar_one()
        
        # 餐食记录数
        meal_result = await db.execute(
            select(func.count(MealRecord.id)).where(
                MealRecord.created_at >= day_start,
                MealRecord.created_at <= day_end
            )
        )
        meal_records = meal_result.scalar_one()
        
        activities.append({
            "date": current_date,
            "active_users": active_users,
            "new_users": new_users,
            "chat_messages": chat_messages,
            "weight_records": weight_records,
            "meal_records": meal_records
        })
        
        current_date += timedelta(days=1)
    
    return activities


@router.get("/{user_id}/records/weight")
async def get_user_weight_records(
    user_id: int,
    limit: int = Query(50, ge=1, le=200, description="返回记录数"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户体重记录
    
    需要管理员权限
    """
    # 验证用户存在
    user_exists = await db.execute(select(User.id).where(User.id == user_id))
    if not user_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    result = await db.execute(
        select(WeightRecord)
        .where(WeightRecord.user_id == user_id)
        .order_by(desc(WeightRecord.record_time))
        .limit(limit)
    )
    records = result.scalars().all()
    
    return [
        {
            "id": record.id,
            "weight": record.weight,
            "body_fat": record.body_fat,
            "record_date": record.record_date,
            "record_time": record.record_time,
            "note": record.note,
            "created_at": record.created_at
        }
        for record in records
    ]


@router.get("/{user_id}/records/chat")
async def get_user_chat_records(
    user_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页数量"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户聊天记录
    
    需要管理员权限
    """
    # 验证用户存在
    user_exists = await db.execute(select(User.id).where(User.id == user_id))
    if not user_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 计算总数
    count_result = await db.execute(
        select(func.count(ChatHistory.id)).where(
            ChatHistory.user_id == user_id,
            ChatHistory.role != "system"
        )
    )
    total = count_result.scalar_one()
    
    # 获取数据
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id, ChatHistory.role != MessageRole.SYSTEM)
        .order_by(desc(ChatHistory.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": record.id,
                "role": record.role.value,
                "content": record.content,
                "msg_type": record.msg_type.value,
                "meta_data": record.meta_data,
                "created_at": record.created_at
            }
            for record in records
        ]
    }