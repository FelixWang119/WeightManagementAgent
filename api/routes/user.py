"""
用户相关 API 路由
包含：微信登录、用户信息、Agent 配置
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import hashlib
import secrets

from models.database import get_db, User, UserProfile, AgentConfig, PersonalityType
from config.settings import fastapi_settings

router = APIRouter()
security = HTTPBearer(auto_error=False)


# ============ 辅助函数 ============

def generate_token(user_id: int) -> str:
    """生成简单的访问令牌（实际生产环境应使用 JWT）"""
    data = f"{user_id}:{fastapi_settings.SECRET_KEY}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前登录用户（用于 Depends）"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌"
        )

    # 从 Authorization header 获取 token
    token = credentials.credentials

    import hashlib
    from config.settings import fastapi_settings

    # 遍历所有用户，找到匹配的 token
    result = await db.execute(select(User))
    all_users = result.scalars().all()

    for user in all_users:
        # 生成期望的token（不包含时间戳，使其永久有效）
        expected_token_data = f"{user.id}:{fastapi_settings.SECRET_KEY}"
        expected_token = hashlib.sha256(expected_token_data.encode()).hexdigest()[:32]

        if token == expected_token:
            # 找到匹配的用户
            return user

    # 没有匹配的用户，抛出认证错误
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效令牌"
    )


# ============ API 路由 ============

@router.post("/login")
async def wechat_login(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    微信登录
    
    - **code**: 微信临时登录凭证（从小程序 wx.login 获取）
    
    返回：
    - token: 访问令牌
    - user: 用户信息
    - is_new: 是否新用户
    """
    # TODO: 实际应调用微信 auth.code2Session 接口
    # 临时模拟返回
    
    # 生成唯一 openid（相同code固定生成相同openid，便于调试）
    openid = hashlib.md5(f"{code}:fixed_salt".encode()).hexdigest()[:28]
    
    # 查询用户是否存在
    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    
    is_new = False
    
    if not user:
        # 创建新用户
        is_new = True
        user = User(
            openid=openid,
            nickname=f"用户{openid[-6:]}",
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # 创建默认 Agent 配置
        agent_config = AgentConfig(
            user_id=user.id,
            agent_name="小助",
            personality_type=PersonalityType.WARM,
            personality_prompt="你是一个温暖、亲切的体重管理助手，像好朋友一样给予用户情感支持。"
        )
        db.add(agent_config)
        await db.commit()
    else:
        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        await db.commit()
    
    # 生成 token
    token = generate_token(user.id)
    
    return {
        "success": True,
        "token": token,
        "is_new": is_new,
        "user": {
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "is_vip": user.is_vip
        }
    }


@router.get("/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户详细资料"""
    # 查询用户画像
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    
    # 查询 Agent 配置
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == current_user.id)
    )
    agent_config = result.scalar_one_or_none()
    
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "nickname": current_user.nickname,
            "avatar_url": current_user.avatar_url,
            "phone": current_user.phone,
            "is_vip": current_user.is_vip,
            "vip_expire": current_user.vip_expire.isoformat() if current_user.vip_expire else None
        },
        "profile": {
            "age": profile.age if profile else None,
            "gender": profile.gender if profile else None,
            "height": profile.height if profile else None,
            "bmr": profile.bmr if profile else None,
            "motivation_type": profile.motivation_type.value if profile and profile.motivation_type else None,
            "diet_preferences": profile.diet_preferences if profile else None,
            "exercise_habits": profile.exercise_habits if profile else None,
        } if profile else None,
        "agent_config": {
            "name": agent_config.agent_name if agent_config else "小助",
            "personality": agent_config.personality_type.value if agent_config else "warm",
        } if agent_config else None
    }


@router.put("/profile")
async def update_user_profile(
    nickname: Optional[str] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    height: Optional[float] = None,
    bmr: Optional[int] = None,
    diet_preferences: Optional[dict] = None,
    exercise_habits: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户资料"""
    # 更新基本信息
    if nickname:
        current_user.nickname = nickname
    
    # 更新或创建用户画像
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
    
    if age is not None:
        profile.age = age
    if gender:
        profile.gender = gender
    if height:
        profile.height = height
    if bmr is not None:
        profile.bmr = bmr
    if diet_preferences is not None:
        profile.diet_preferences = diet_preferences
    if exercise_habits is not None:
        profile.exercise_habits = exercise_habits
    
    profile.updated_at = datetime.utcnow()
    await db.commit()
    
    # 清理用户画像缓存（如果有）
    from services.user_profile_service import UserProfileService
    await UserProfileService.invalidate_cache(current_user.id, db)
    
    return {
        "success": True,
        "message": "资料更新成功"
    }


@router.put("/profile/bmr")
async def update_user_bmr(
    bmr: int = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    专门用于更新BMR的接口
    
    Args:
        bmr: 基础代谢率值（千卡/天）
    """
    # 验证BMR值范围
    if bmr < 500 or bmr > 5000:
        raise HTTPException(
            status_code=400,
            detail="BMR值应在500-5000千卡/天范围内"
        )
    
    # 更新或创建用户画像
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
    
    profile.bmr = bmr
    profile.updated_at = datetime.utcnow()
    await db.commit()
    
    # 清理用户画像缓存
    from services.user_profile_service import UserProfileService
    await UserProfileService.invalidate_cache(current_user.id, db)
    
    return {
        "success": True,
        "message": "BMR更新成功",
        "bmr": bmr
    }


@router.get("/agent/config")
async def get_agent_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取 Agent 配置"""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Agent 配置未找到")
    
    return {
        "success": True,
        "config": {
            "agent_name": config.agent_name,
            "personality_type": config.personality_type.value,
            "personality_prompt": config.personality_prompt
        }
    }


@router.get("/agent/styles")
async def get_agent_styles(db: AsyncSession = Depends(get_db)):
    """获取所有可用的助手风格"""
    from config.assistant_styles import get_all_styles
    
    return {
        "success": True,
        "styles": await get_all_styles(db)
    }


@router.put("/agent/config")
async def update_agent_config(
    agent_name: Optional[str] = Body(default=None),
    personality_type: Optional[str] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新 Agent 配置"""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        config = AgentConfig(user_id=current_user.id)
        db.add(config)
    
    if agent_name:
        config.agent_name = agent_name
    
    if personality_type:
        try:
            from config.assistant_styles import AssistantStyle, get_style_config
            style = AssistantStyle(personality_type)
            style_config = await get_style_config(style, db)
            
            config.personality_type = PersonalityType(personality_type)
            config.personality_prompt = style_config["system_prompt_addition"]
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的性格类型")
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Agent 配置更新成功",
        "config": {
            "agent_name": config.agent_name,
            "personality_type": config.personality_type.value if config.personality_type else None
        }
    }
