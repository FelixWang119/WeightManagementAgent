"""
热量计算 API 路由
提供基础代谢率(BMR)、每日总能量消耗(TDEE)计算服务
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from pydantic import BaseModel

from models.database import get_db, User
from api.routes.user import get_current_user
from services.calorie_calculator import CalorieCalculator
from services.calorie_balance_service import CalorieBalanceService

router = APIRouter()


# ============ 请求/响应模型 ============

class CalculateBmrRequest(BaseModel):
    """BMR计算请求"""
    age: Optional[int] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    activity_level: Optional[str] = "light"
    use_user_bmr: Optional[int] = None


class CalorieBalanceRequest(BaseModel):
    """热量平衡计算请求"""
    tdee: float
    intake_calories: float
    burned_exercise_calories: float = 0.0


class WeightLossTargetRequest(BaseModel):
    """减重目标计算请求"""
    tdee: float
    target_weekly_loss_kg: Optional[float] = 0.5


# ============ API 端点 ============

@router.post("/calculate")
async def calculate_calories(
    request: CalculateBmrRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    计算基础代谢率(BMR)和每日总能量消耗(TDEE)
    
    优先使用用户提供的BMR值，否则根据年龄、性别、身高、体重计算
    如果用户profile中有数据，优先使用profile中的数据
    """
    try:
        # 优先从用户profile中获取数据
        from sqlalchemy import select
        from models.database import UserProfile
        
        # 查询用户profile
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        
        # 使用优先级：用户提供的BMR > profile中的BMR > 计算BMR
        use_user_bmr = request.use_user_bmr
        
        # 如果用户没有提供BMR，但profile中有BMR，使用profile的BMR
        if use_user_bmr is None and profile and profile.bmr:
            use_user_bmr = profile.bmr
        
        # 如果用户没有提供年龄/性别/身高/体重，尝试从profile获取
        age = request.age
        gender = request.gender
        height = request.height
        weight = request.weight
        
        if profile:
            if age is None and profile.age:
                age = profile.age
            if gender is None and profile.gender:
                gender = profile.gender
            if height is None and profile.height:
                height = profile.height
        
        # 计算BMR（优先使用用户提供的值）
        bmr = CalorieCalculator.calculate_bmr(
            age=age,
            gender=gender,
            height_cm=height,
            weight_kg=weight,
            use_user_bmr=use_user_bmr
        )
        
        if bmr is None:
            raise HTTPException(
                status_code=400,
                detail="无法计算BMR：请提供年龄、性别、身高、体重，或直接提供BMR值"
            )
        
        # 计算TDEE
        tdee = CalorieCalculator.calculate_tdee(
            bmr=bmr,
            activity_level=request.activity_level or "light"
        )
        
        # 返回详细的数据来源信息
        response_data = {
            "success": True,
            "bmr": round(bmr, 1),
            "tdee": round(tdee, 1),
            "activity_level": request.activity_level or "light",
            "activity_factor": CalorieCalculator.ACTIVITY_FACTORS.get(
                request.activity_level or "light", 
                1.375
            ),
            "formula_used": "harris_benedict",
            "data_sources": {
                "bmr_used": "user_provided" if request.use_user_bmr else (
                    "profile" if profile and profile.bmr else "calculated"
                ),
                "age_used": "user_provided" if request.age else (
                    "profile" if profile and profile.age else "not_provided"
                ),
                "gender_used": "user_provided" if request.gender else (
                    "profile" if profile and profile.gender else "not_provided"
                ),
                "height_used": "user_provided" if request.height else (
                    "profile" if profile and profile.height else "not_provided"
                ),
                "weight_used": "user_provided" if request.weight else "not_provided"
            }
        }
        
        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/balance")
async def calculate_calorie_balance(
    request: CalorieBalanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    计算每日热量平衡
    """
    try:
        balance_data = CalorieCalculator.calculate_calorie_balance(
            tdee=request.tdee,
            intake_calories=request.intake_calories,
            burned_exercise_calories=request.burned_exercise_calories
        )
        
        # 添加格式化摘要
        summary = CalorieCalculator.format_calorie_summary(balance_data)
        
        return {
            "success": True,
            "balance": balance_data,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/weight-loss-target")
async def calculate_weight_loss_target(
    request: WeightLossTargetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    根据减重目标计算热量摄入目标
    """
    try:
        target_data = CalorieCalculator.get_calorie_target_for_weight_loss(
            tdee=request.tdee,
            target_weekly_loss_kg=request.target_weekly_loss_kg or 0.5
        )
        
        return {
            "success": True,
            "target": target_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.get("/activity-levels")
async def get_activity_levels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取活动级别定义和对应系数
    """
    levels = {
        "sedentary": {
            "name": "久坐",
            "description": "办公室工作，很少或没有运动",
            "factor": 1.2
        },
        "light": {
            "name": "轻度活动", 
            "description": "每周1-3天轻度运动",
            "factor": 1.375
        },
        "moderate": {
            "name": "中度活动",
            "description": "每周3-5天中度运动", 
            "factor": 1.55
        },
        "active": {
            "name": "高度活动",
            "description": "每天运动或体力劳动",
            "factor": 1.725
        },
        "very_active": {
            "name": "极高度活动",
            "description": "专业运动员或重体力劳动者",
            "factor": 1.9
        }
    }
    
    return {
        "success": True,
        "levels": levels,
        "default": "light"
    }


# ============ 热量平衡图表API ============

@router.get("/balance/daily")
async def get_daily_calorie_balance(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取每日热量平衡数据
    
    Args:
        days: 获取最近多少天的数据（默认7天）
    """
    try:
        data = await CalorieBalanceService.get_daily_calorie_data(
            user_id=current_user.id,
            days=days,
            db=db
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/balance/chart")
async def get_calorie_balance_chart(
    chart_type: str = "daily",  # daily, weekly, monthly
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取图表格式的热量平衡数据
    
    Args:
        chart_type: 图表类型 (daily, weekly, monthly)
    """
    try:
        data = await CalorieBalanceService.get_calorie_balance_chart_data(
            user_id=current_user.id,
            chart_type=chart_type,
            db=db
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图表数据失败: {str(e)}")


@router.get("/balance/distribution")
async def get_calorie_distribution(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取热量来源分布数据
    
    Args:
        days: 获取最近多少天的数据（默认7天）
    """
    try:
        data = await CalorieBalanceService.get_calorie_distribution(
            user_id=current_user.id,
            days=days,
            db=db
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分布数据失败: {str(e)}")