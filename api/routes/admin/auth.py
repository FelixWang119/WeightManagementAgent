"""
管理员认证路由
提供管理员登录、令牌刷新、登出和个人信息功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import logging

from models.database import get_db, User
from api.dependencies.auth_v2 import get_current_admin, get_current_user_v2
from utils.jwt_auth import TokenManager, JWTManager

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


# ============ 请求/响应模型 ============

class AdminLoginRequest(BaseModel):
    """管理员登录请求"""
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    """管理员登录响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 过期时间（秒）
    user_info: Dict[str, Any]
    
class AdminProfileResponse(BaseModel):
    """管理员个人信息响应"""
    user_id: int
    username: str
    nickname: str
    is_admin: bool
    admin_role: Optional[str]
    admin_permissions: Optional[list]
    last_admin_login: Optional[datetime]
    
class TokenRefreshRequest(BaseModel):
    """令牌刷新请求"""
    refresh_token: Optional[str] = None
    
class TokenRefreshResponse(BaseModel):
    """令牌刷新响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============ 辅助函数 ============

def hash_password(password: str, salt: str = "") -> str:
    """
    密码哈希函数
    
    Args:
        password: 原始密码
        salt: 盐值
        
    Returns:
        哈希后的密码字符串
    """
    # 简单哈希实现，生产环境应使用bcrypt或argon2
    data = f"{password}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


async def authenticate_admin(
    db: AsyncSession, 
    username: str, 
    password: str
) -> Optional[User]:
    """
    管理员身份验证
    
    Args:
        db: 数据库会话
        username: 用户名
        password: 密码
        
    Returns:
        验证成功的用户对象，失败返回None
    """
    # 临时实现：查找第一个管理员用户
    # 后续应添加admin_username和admin_password_hash字段
    result = await db.execute(
        select(User).where(User.is_admin == True).limit(1)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning("未找到管理员用户")
        return None
    
    # 临时密码验证：使用配置中的管理员密码
    # 生产环境应使用数据库存储的哈希密码
    from config.settings import get_fastapi_settings
    settings = get_fastapi_settings()
    
    if password == settings.ADMIN_PASSWORD and username == "admin":
        # 更新最后管理员登录时间
        user.last_admin_login = datetime.utcnow()
        await db.commit()
        return user
    
    return None


# ============ API 路由 ============

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    login_data: AdminLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    管理员登录
    
    - **username**: 管理员用户名
    - **password**: 管理员密码
    
    返回JWT访问令牌和管理员信息
    """
    logger.info(f"管理员登录尝试: {login_data.username}")
    
    # 身份验证
    user = await authenticate_admin(db, login_data.username, login_data.password)
    if not user:
        logger.warning(f"管理员登录失败: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 创建JWT令牌
    access_token = TokenManager.create_token(
        user_id=user.id,
        is_admin=True,
        admin_role=user.admin_role,
        admin_permissions=user.admin_permissions
    )
    
    # 计算过期时间（默认30分钟）
    expires_in = 30 * 60  # 秒
    
    logger.info(f"管理员登录成功: {login_data.username}, 用户ID: {user.id}")
    
    return AdminLoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        user_info={
            "user_id": user.id,
            "username": login_data.username,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
            "admin_role": user.admin_role,
            "admin_permissions": user.admin_permissions,
            "last_admin_login": user.last_admin_login
        }
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    refresh_data: TokenRefreshRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    刷新访问令牌
    
    - **refresh_token**: 刷新令牌（可选，当前使用访问令牌刷新）
    
    返回新的访问令牌
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌"
        )
    
    token = credentials.credentials
    
    # 验证当前令牌
    valid, payload, token_type = TokenManager.verify_and_decode(token)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌"
        )
    
    # 检查是否为JWT令牌
    if token_type != "jwt":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持JWT令牌刷新"
        )
    
    # 检查令牌是否即将过期（剩余时间小于5分钟）
    from utils.jwt_auth import JWTManager
    if not JWTManager.is_token_expired(token):
        # 令牌未过期，可以刷新
        user_id = payload.get("user_id")
        is_admin = payload.get("is_admin", False)
        admin_role = payload.get("admin_role")
        admin_permissions = payload.get("admin_permissions")
        
        # 创建新令牌
        new_token = TokenManager.create_token(
            user_id=user_id,
            is_admin=is_admin,
            admin_role=admin_role,
            admin_permissions=admin_permissions
        )
        
        expires_in = 30 * 60  # 秒
        
        return TokenRefreshResponse(
            access_token=new_token,
            expires_in=expires_in
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录"
        )


@router.post("/logout")
async def admin_logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    管理员登出
    
    使当前令牌失效（客户端应删除令牌）
    """
    # JWT是无状态的，客户端只需删除令牌即可
    # 这里可以记录登出日志或将令牌加入黑名单（如果需要）
    
    logger.info("管理员登出")
    
    return {"message": "登出成功"}


@router.get("/profile", response_model=AdminProfileResponse)
async def get_admin_profile(
    user: User = Depends(get_current_admin)
):
    """
    获取管理员个人信息
    
    需要管理员权限
    """
    # 用户名暂时使用固定值，后续应从数据库读取
    username = "admin"
    
    return AdminProfileResponse(
        user_id=user.id,
        username=username,
        nickname=user.nickname,
        is_admin=user.is_admin,
        admin_role=user.admin_role,
        admin_permissions=user.admin_permissions,
        last_admin_login=user.last_admin_login
    )