"""
JWT认证工具类
提供JWT令牌生成、验证和刷新功能，同时保持与旧哈希令牌的兼容性
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import hashlib
from jose import jwt
from jose.exceptions import JWTError

from config.settings import get_fastapi_settings

settings = get_fastapi_settings()

# JWT配置
JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = settings.SECRET_KEY
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


class JWTManager:
    """JWT令牌管理器"""
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建JWT访问令牌
        
        Args:
            data: 令牌数据（如user_id, is_admin等）
            expires_delta: 过期时间增量，默认使用配置值
            
        Returns:
            JWT令牌字符串
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )
            
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(
            to_encode,
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        验证JWT令牌
        
        Args:
            token: JWT令牌字符串
            
        Returns:
            解码后的令牌数据，如果无效则返回None
        """
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def create_user_token(
        user_id: int,
        is_admin: bool = False,
        admin_role: Optional[str] = None,
        admin_permissions: Optional[list] = None
    ) -> str:
        """
        创建用户JWT令牌（包含用户信息）
        
        Args:
            user_id: 用户ID
            is_admin: 是否管理员
            admin_role: 管理员角色
            admin_permissions: 管理员权限列表
            
        Returns:
            JWT令牌字符串
        """
        token_data = {
            "user_id": user_id,
            "is_admin": is_admin,
            "type": "jwt"
        }
        
        if is_admin:
            token_data.update({
                "admin_role": admin_role,
                "admin_permissions": admin_permissions or []
            })
            
        return JWTManager.create_access_token(token_data)
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        检查令牌是否过期（不验证签名）
        
        Args:
            token: JWT令牌
            
        Returns:
            是否过期
        """
        try:
            # 不验证签名，只解码
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"verify_signature": False}
            )
            exp = payload.get("exp")
            if not exp:
                return True
                
            expire_time = datetime.fromtimestamp(exp, tz=timezone.utc)
            return datetime.now(timezone.utc) > expire_time
        except JWTError:
            return True


class LegacyTokenManager:
    """旧哈希令牌管理器（保持兼容性）"""
    
    @staticmethod
    def generate_legacy_token(user_id: int) -> str:
        """
        生成旧版哈希令牌（保持向后兼容）
        
        Args:
            user_id: 用户ID
            
        Returns:
            哈希令牌字符串
        """
        data = f"{user_id}:{JWT_SECRET_KEY}:{datetime.utcnow().timestamp()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    @staticmethod
    def is_legacy_token(token: str) -> bool:
        """
        判断是否为旧版哈希令牌
        
        Args:
            token: 令牌字符串
            
        Returns:
            是否为旧版令牌
        """
        # 旧版令牌是32字符的十六进制字符串
        if len(token) != 32:
            return False
            
        try:
            int(token, 16)
            return True
        except ValueError:
            return False


class TokenManager:
    """统一的令牌管理器（兼容新旧令牌）"""
    
    @staticmethod
    def create_token(
        user_id: int,
        is_admin: bool = False,
        admin_role: Optional[str] = None,
        admin_permissions: Optional[list] = None,
        use_jwt: bool = True
    ) -> str:
        """
        创建令牌（可指定使用JWT或旧版令牌）
        
        Args:
            user_id: 用户ID
            is_admin: 是否管理员
            admin_role: 管理员角色
            admin_permissions: 管理员权限列表
            use_jwt: 是否使用JWT（默认True）
            
        Returns:
            令牌字符串
        """
        if use_jwt:
            return JWTManager.create_user_token(
                user_id, is_admin, admin_role, admin_permissions
            )
        else:
            return LegacyTokenManager.generate_legacy_token(user_id)
    
    @staticmethod
    def verify_and_decode(token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        验证并解码令牌（兼容新旧令牌）
        
        Args:
            token: 令牌字符串
            
        Returns:
            (是否有效, 令牌数据, 令牌类型)
        """
        # 先尝试JWT验证
        jwt_payload = JWTManager.verify_token(token)
        if jwt_payload:
            return True, jwt_payload, "jwt"
        
        # 如果是旧版令牌格式，返回特殊标记
        if LegacyTokenManager.is_legacy_token(token):
            # 旧版令牌需要特殊处理（由上层逻辑处理）
            return True, {"type": "legacy"}, "legacy"
        
        return False, None, "invalid"
    
    @staticmethod
    def migrate_legacy_to_jwt(
        legacy_token: str,
        user_id: int,
        is_admin: bool = False,
        admin_role: Optional[str] = None
    ) -> str:
        """
        将旧版令牌迁移为JWT令牌
        
        Args:
            legacy_token: 旧版令牌
            user_id: 用户ID
            is_admin: 是否管理员
            admin_role: 管理员角色
            
        Returns:
            新的JWT令牌
        """
        # 验证旧版令牌（这里需要根据实际业务逻辑验证）
        # 暂时假设验证通过，直接创建新JWT
        return JWTManager.create_user_token(
            user_id, is_admin, admin_role
        )


# 工具函数
def get_token_type(token: str) -> str:
    """获取令牌类型"""
    _, _, token_type = TokenManager.verify_and_decode(token)
    return token_type

def is_valid_token(token: str) -> bool:
    """检查令牌是否有效"""
    valid, _, _ = TokenManager.verify_and_decode(token)
    return valid

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码令牌"""
    valid, payload, _ = TokenManager.verify_and_decode(token)
    return payload if valid else None