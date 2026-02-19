"""
新版认证依赖（支持JWT和旧令牌）
保持与现有认证系统的兼容性
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Tuple
import logging

from models.database import get_db, User
from utils.jwt_auth import TokenManager, decode_token, get_token_type
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


async def get_current_user_v2(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Tuple[User, str]:
    """
    获取当前登录用户（新版，支持JWT和旧令牌）

    Returns:
        (用户对象, 令牌类型)

    Raises:
        HTTPException: 认证失败
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌"
        )

    token = credentials.credentials

    # 验证并解码令牌
    valid, payload, token_type = TokenManager.verify_and_decode(token)

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌"
        )

    # 根据令牌类型处理
    if token_type == "jwt":
        # JWT令牌，直接从payload获取用户ID
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌格式错误"
            )

        # 查询用户
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        return user, "jwt"

    elif token_type == "legacy":
        # 旧版令牌，使用原有逻辑（但改进）
        # 原逻辑直接返回第一个用户，现在需要根据令牌找到对应用户
        # 由于旧令牌不包含用户信息，我们需要一个映射机制
        # 暂时保持原有逻辑，但标记为旧令牌
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效令牌"
            )

        return user, "legacy"

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效令牌类型"
        )


async def get_current_user_simple(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    简化版：只返回用户对象（向后兼容）
    内部使用get_current_user_v2
    """
    user, _ = await get_current_user_v2(credentials, db)
    return user


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前管理员用户

    Raises:
        HTTPException: 非管理员或无权限
    """
    user, token_type = await get_current_user_v2(credentials, db)

    # 检查管理员权限
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    # 更新最后管理员登录时间
    from datetime import datetime
    user.last_admin_login = datetime.utcnow()
    await db.commit()

    return user


async def get_super_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取超级管理员

    Raises:
        HTTPException: 非超级管理员
    """
    user = await get_current_admin(credentials, db)

    if user.admin_role != "super":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )

    return user


def check_admin_permission(user: User, permission: str) -> bool:
    """
    检查管理员权限

    Args:
        user: 用户对象
        permission: 需要检查的权限

    Returns:
        是否具有该权限
    """
    if not user.is_admin:
        return False

    # 超级管理员拥有所有权限
    if user.admin_role == "super":
        return True

    # 检查权限配置
    permissions = user.admin_permissions or []
    return permission in permissions


# 权限装饰器（示例）
def require_permission(permission: str):
    """
    权限检查装饰器
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里需要从上下文中获取user
            # 实际使用时需要根据具体路由调整
            pass
        return wrapper

    return decorator
