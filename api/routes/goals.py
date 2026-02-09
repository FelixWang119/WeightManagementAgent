"""
体重目标 API 路由
包含：目标创建、查询、更新、删除、进度计算
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import Optional, Dict, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel
from math import ceil

from models.database import get_db, User, Goal, GoalStatus, WeightRecord
from api.routes.user import get_current_user

router = APIRouter()


# ============ 请求/响应模型 ============

class CreateGoalRequest(BaseModel):
    """创建目标请求"""
    target_weight: float
    target_date: date
    weekly_plan: Optional[float] = 0.5
    daily_calorie_target: Optional[int] = None
    meal_distribution: Optional[Dict[str, float]] = None


class UpdateGoalRequest(BaseModel):
    """更新目标请求"""
    target_weight: Optional[float] = None
    target_date: Optional[date] = None
    weekly_plan: Optional[float] = None
    daily_calorie_target: Optional[int] = None
    meal_distribution: Optional[Dict[str, float]] = None


class GoalResponse(BaseModel):
    """目标响应模型"""
    id: int
    user_id: int
    target_weight: float
    target_date: date
    weekly_plan: float
    daily_calorie_target: Optional[int]
    meal_distribution: Optional[Dict[str, float]]
    status: str
    created_at: datetime
    progress: Optional[Dict[str, Any]] = None


# ============ 辅助函数 ============

async def calculate_goal_progress(
    db: AsyncSession,
    goal: Goal
) -> Dict[str, Any]:
    """
    计算目标进度
    
    返回:
    - current_weight: 当前体重（最近一次记录）
    - start_weight: 起始体重（目标创建时的体重）
    - weight_lost: 已减重（kg）
    - progress_percent: 进度百分比
    - days_remaining: 剩余天数
    - daily_rate: 实际每日减重速率
    - expected_rate: 计划每日减重速率
    - status: 进度状态（ahead/on_track/behind）
    """
    # 获取当前体重（最近一条）
    result = await db.execute(
        select(WeightRecord)
        .where(WeightRecord.user_id == goal.user_id)
        .order_by(desc(WeightRecord.record_date))
        .limit(1)
    )
    current_record = result.scalar_one_or_none()
    current_weight = current_record.weight if current_record else None
    
    # 获取目标创建时的体重（使用目标创建日期前一天或当天的记录）
    result = await db.execute(
        select(WeightRecord)
        .where(
            and_(
                WeightRecord.user_id == goal.user_id,
                WeightRecord.record_date <= goal.created_at.date()
            )
        )
        .order_by(desc(WeightRecord.record_date))
        .limit(1)
    )
    start_record = result.scalar_one_or_none()
    start_weight = start_record.weight if start_record else current_weight
    
    # 计算基础数据
    today = date.today()
    target_date = goal.target_date
    
    if start_weight is None:
        return {
            "current_weight": None,
            "start_weight": None,
            "weight_lost": 0,
            "progress_percent": 0,
            "days_remaining": max(0, (target_date - today).days),
            "daily_rate": 0,
            "expected_rate": goal.weekly_plan / 7,
            "status": "unknown",
            "message": "暂无体重记录，无法计算进度"
        }
    
    # 已减重
    weight_lost = round(start_weight - current_weight, 1) if current_weight else 0
    
    # 进度百分比
    total_to_lose = start_weight - goal.target_weight
    if total_to_lose > 0:
        progress_percent = min(100, round(weight_lost / total_to_lose * 100, 1))
    else:
        progress_percent = 100
    
    # 剩余天数
    days_remaining = max(0, (target_date - today).days)
    
    # 计划每日减重速率
    total_days = (goal.target_date - goal.created_at.date()).days
    expected_rate = round(goal.weekly_plan / 7, 3) if total_days > 0 else 0
    
    # 实际每日减重速率
    days_passed = (today - goal.created_at.date()).days
    daily_rate = round(weight_lost / days_passed, 3) if days_passed > 0 else 0
    
    # 进度状态
    if days_passed == 0:
        status = "just_started"
        message = "刚开始，目标进行中"
    elif days_remaining == 0:
        if progress_percent >= 100:
            status = "completed"
            message = "恭喜！目标已完成！"
        else:
            status = "deadline_passed"
            message = "已过截止日期，请调整目标"
    else:
        expected_lost = expected_rate * days_passed
        if weight_lost >= expected_lost + (goal.weekly_plan * 0.5):
            status = "ahead"
            message = "进度超前！保持得很好！"
        elif weight_lost >= expected_lost - (goal.weekly_plan * 0.5):
            status = "on_track"
            message = "进度正常，继续保持"
        else:
            status = "behind"
            message = "进度稍慢，建议调整计划"
    
    # 预计达成日期
    if daily_rate > 0 and current_weight > goal.target_weight:
        remaining_weight = current_weight - goal.target_weight
        days_to_goal = ceil(remaining_weight / daily_rate)
        expected_completion = today + timedelta(days=days_to_goal)
    else:
        expected_completion = None
    
    return {
        "current_weight": current_weight,
        "start_weight": start_weight,
        "weight_lost": weight_lost,
        "progress_percent": progress_percent,
        "days_remaining": days_remaining,
        "daily_rate": daily_rate,
        "expected_rate": expected_rate,
        "status": status,
        "message": message,
        "expected_completion": expected_completion.isoformat() if expected_completion else None
    }


# ============ API 端点 ============

@router.get("/current")
async def get_current_goal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前进行中的目标
    
    返回当前状态为 active 的目标，如果不存在返回空
    """
    result = await db.execute(
        select(Goal)
        .where(
            and_(
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
        .order_by(desc(Goal.created_at))
        .limit(1)
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        return {
            "success": True,
            "has_goal": False,
            "message": "暂无进行中的目标"
        }
    
    # 计算进度
    progress = await calculate_goal_progress(db, goal)
    
    return {
        "success": True,
        "has_goal": True,
        "goal": {
            "id": goal.id,
            "user_id": goal.user_id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date.isoformat(),
            "weekly_plan": goal.weekly_plan,
            "daily_calorie_target": goal.daily_calorie_target,
            "meal_distribution": goal.meal_distribution,
            "status": goal.status.value,
            "created_at": goal.created_at.isoformat(),
            "progress": progress
        }
    }


@router.post("")
async def create_goal(
    request: CreateGoalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    创建新的减重目标
    
    - **target_weight**: 目标体重（kg）
    - **target_date**: 目标达成日期
    - **weekly_plan**: 每周减重计划（kg），默认0.5
    - **daily_calorie_target**: 每日热量目标，可自动计算
    - **meal_distribution**: 三餐分配比例，如 {"breakfast": 0.3, "lunch": 0.4, "dinner": 0.3}
    """
    # 检查是否已有进行中的目标
    result = await db.execute(
        select(Goal)
        .where(
            and_(
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
    )
    existing_goal = result.scalar_one_or_none()
    
    if existing_goal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已存在进行中的目标，请先完成或放弃当前目标"
        )
    
    # 获取用户当前体重
    result = await db.execute(
        select(WeightRecord)
        .where(WeightRecord.user_id == current_user.id)
        .order_by(desc(WeightRecord.record_date))
        .limit(1)
    )
    current_record = result.scalar_one_or_none()
    
    if not current_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先记录当前体重，再设置目标"
        )
    
    current_weight = current_record.weight
    
    # 验证目标体重
    if request.target_weight >= current_weight:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目标体重应小于当前体重"
        )
    
    # 验证目标日期
    if request.target_date <= date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目标日期应在未来"
        )
    
    # 验证周减重计划（建议0.25-1.0kg/周）
    if request.weekly_plan < 0.25 or request.weekly_plan > 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="周减重计划建议在 0.25-1.0 kg/周 之间"
        )
    
    # 创建目标
    goal = Goal(
        user_id=current_user.id,
        target_weight=request.target_weight,
        target_date=request.target_date,
        weekly_plan=request.weekly_plan,
        daily_calorie_target=request.daily_calorie_target,
        meal_distribution=request.meal_distribution or {"breakfast": 0.3, "lunch": 0.4, "dinner": 0.3},
        status=GoalStatus.ACTIVE
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    
    # 计算初始进度
    progress = await calculate_goal_progress(db, goal)
    
    return {
        "success": True,
        "message": "目标创建成功",
        "goal": {
            "id": goal.id,
            "user_id": goal.user_id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date.isoformat(),
            "weekly_plan": goal.weekly_plan,
            "daily_calorie_target": goal.daily_calorie_target,
            "meal_distribution": goal.meal_distribution,
            "status": goal.status.value,
            "created_at": goal.created_at.isoformat(),
            "progress": progress
        }
    }


@router.get("/{goal_id}")
async def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取指定目标详情
    """
    result = await db.execute(
        select(Goal).where(
            and_(
                Goal.id == goal_id,
                Goal.user_id == current_user.id
            )
        )
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标不存在"
        )
    
    progress = await calculate_goal_progress(db, goal)
    
    return {
        "success": True,
        "goal": {
            "id": goal.id,
            "user_id": goal.user_id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date.isoformat(),
            "weekly_plan": goal.weekly_plan,
            "daily_calorie_target": goal.daily_calorie_target,
            "meal_distribution": goal.meal_distribution,
            "status": goal.status.value,
            "created_at": goal.created_at.isoformat(),
            "progress": progress
        }
    }


@router.put("/{goal_id}")
async def update_goal(
    goal_id: int,
    request: UpdateGoalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新目标（仅限进行中的目标）
    """
    result = await db.execute(
        select(Goal).where(
            and_(
                Goal.id == goal_id,
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标不存在或已完成/已放弃"
        )
    
    # 更新字段
    if request.target_weight is not None:
        goal.target_weight = request.target_weight
    if request.target_date is not None:
        goal.target_date = request.target_date
    if request.weekly_plan is not None:
        goal.weekly_plan = request.weekly_plan
    if request.daily_calorie_target is not None:
        goal.daily_calorie_target = request.daily_calorie_target
    if request.meal_distribution is not None:
        goal.meal_distribution = request.meal_distribution
    
    await db.commit()
    await db.refresh(goal)
    
    progress = await calculate_goal_progress(db, goal)
    
    return {
        "success": True,
        "message": "目标更新成功",
        "goal": {
            "id": goal.id,
            "user_id": goal.user_id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date.isoformat(),
            "weekly_plan": goal.weekly_plan,
            "daily_calorie_target": goal.daily_calorie_target,
            "meal_distribution": goal.meal_distribution,
            "status": goal.status.value,
            "created_at": goal.created_at.isoformat(),
            "progress": progress
        }
    }


@router.post("/{goal_id}/complete")
async def complete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    标记目标为已完成
    """
    result = await db.execute(
        select(Goal).where(
            and_(
                Goal.id == goal_id,
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标不存在或已完成/已放弃"
        )
    
    goal.status = GoalStatus.COMPLETED
    await db.commit()
    
    return {
        "success": True,
        "message": "恭喜！目标已完成！"
    }


@router.post("/{goal_id}/abandon")
async def abandon_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    放弃目标
    """
    result = await db.execute(
        select(Goal).where(
            and_(
                Goal.id == goal_id,
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标不存在或已完成/已放弃"
        )
    
    goal.status = GoalStatus.ABANDONED
    await db.commit()
    
    return {
        "success": True,
        "message": "目标已放弃"
    }


@router.get("/history/list")
async def get_goal_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取历史目标列表（已完成/已放弃）
    """
    result = await db.execute(
        select(Goal)
        .where(
            and_(
                Goal.user_id == current_user.id,
                Goal.status != GoalStatus.ACTIVE
            )
        )
        .order_by(desc(Goal.created_at))
    )
    goals = result.scalars().all()
    
    history = []
    for goal in goals:
        # 计算最终进度
        result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == current_user.id)
            .order_by(desc(WeightRecord.record_date))
            .limit(1)
        )
        current_record = result.scalar_one_or_none()
        current_weight = current_record.weight if current_record else None
        
        start_result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == current_user.id,
                    WeightRecord.record_date <= goal.created_at.date()
                )
            )
            .order_by(desc(WeightRecord.record_date))
            .limit(1)
        )
        start_record = start_result.scalar_one_or_none()
        
        history.append({
            "id": goal.id,
            "target_weight": goal.target_weight,
            "target_date": goal.target_date.isoformat(),
            "weekly_plan": goal.weekly_plan,
            "status": goal.status.value,
            "created_at": goal.created_at.isoformat(),
            "final_weight": current_weight,
            "start_weight": start_record.weight if start_record else None
        })
    
    return {
        "success": True,
        "history": history
    }


@router.get("/progress/stats")
async def get_progress_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取目标进度统计（供仪表盘使用）
    """
    # 获取当前目标
    result = await db.execute(
        select(Goal)
        .where(
            and_(
                Goal.user_id == current_user.id,
                Goal.status == GoalStatus.ACTIVE
            )
        )
        .order_by(desc(Goal.created_at))
        .limit(1)
    )
    goal = result.scalar_one_or_none()
    
    if not goal:
        return {
            "success": True,
            "has_active_goal": False,
            "message": "暂无进行中的目标"
        }
    
    progress = await calculate_goal_progress(db, goal)
    
    return {
        "success": True,
        "has_active_goal": True,
        "goal_id": goal.id,
        "target_weight": goal.target_weight,
        "progress": progress
    }
