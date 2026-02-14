#!/usr/bin/env python3
"""
创建测试用户脚本
用于为API集成测试创建测试用户
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import select

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试用户配置
TEST_USER_CONFIG = {
    "nickname": "测试用户",
    "code": "test_api_code",  # 模拟微信登录code
    "is_admin": False
}


async def create_test_user():
    """创建测试用户"""
    
    logger.info("🚀 开始创建测试用户...")
    
    try:
        # 导入数据库相关模块
        from models.database import AsyncSessionLocal, User
        from api.routes.user import get_password_hash
        
        async with AsyncSessionLocal() as db:
            # 检查用户是否已存在
            result = await db.execute(
                select(User).where(User.nickname == TEST_USER_CONFIG["nickname"])
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"✅ 测试用户已存在 - ID: {existing_user.id}, 昵称: {existing_user.nickname}")
                return existing_user
            
            # 创建新用户
            new_user = User(
                nickname=TEST_USER_CONFIG["nickname"],
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
                is_admin=TEST_USER_CONFIG["is_admin"]
            )
            
            # 设置openid（基于微信登录code生成）
            import hashlib
            openid = hashlib.md5(f"{TEST_USER_CONFIG['code']}:fixed_salt".encode()).hexdigest()[:28]
            new_user.openid = openid
            
            db.add(new_user)
            await db.commit()
            
            # 获取用户ID
            await db.refresh(new_user)
            
            logger.info(f"✅ 测试用户创建成功 - ID: {new_user.id}, 昵称: {new_user.nickname}")
            
            # 创建用户画像
            await create_user_profile(new_user.id, db)
            
            # 创建Agent配置
            await create_agent_config(new_user.id, db)
            
            return new_user
            
    except Exception as e:
        logger.error(f"❌ 创建测试用户失败: {e}")
        return None


async def create_user_profile(user_id: int, db):
    """创建用户画像"""
    
    try:
        from models.database import UserProfile
        
        # 检查是否已存在画像
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        existing_profile = result.scalar_one_or_none()
        
        if existing_profile:
            logger.info("✅ 用户画像已存在")
            return existing_profile
        
        # 创建新画像
        profile = UserProfile(
            user_id=user_id,
            age=28,
            gender="male",
            height=175,
            weight=70,
            bmr=1650,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(profile)
        await db.commit()
        
        logger.info("✅ 用户画像创建成功")
        return profile
        
    except Exception as e:
        logger.error(f"❌ 创建用户画像失败: {e}")
        return None


async def create_agent_config(user_id: int, db):
    """创建Agent配置"""
    
    try:
        from models.database import AgentConfig, PersonalityType
        
        # 检查是否已存在配置
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.user_id == user_id)
        )
        existing_config = result.scalar_one_or_none()
        
        if existing_config:
            logger.info("✅ Agent配置已存在")
            return existing_config
        
        # 创建新配置
        agent_config = AgentConfig(
            user_id=user_id,
            agent_name="小助",
            personality_type=PersonalityType.WARM,
            personality_prompt="你是一个温暖、亲切的体重管理助手。",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(agent_config)
        await db.commit()
        
        logger.info("✅ Agent配置创建成功")
        return agent_config
        
    except Exception as e:
        logger.error(f"❌ 创建Agent配置失败: {e}")
        return None


async def check_user_auth_table():
    """检查用户认证表结构"""
    
    try:
        from models.database import Base, User
        from sqlalchemy import inspect
        
        async with AsyncSessionLocal() as db:
            # 检查users表是否存在
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            
            if "users" in tables:
                logger.info("✅ users表存在")
                
                # 检查是否有测试用户
                import hashlib
                openid = hashlib.md5(f"{TEST_USER_CONFIG['code']}:fixed_salt".encode()).hexdigest()[:28]
                
                result = await db.execute(
                    select(User).where(User.openid == openid)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    logger.info(f"✅ 测试用户已存在 - ID: {existing_user.id}")
                    return existing_user
                else:
                    logger.info("❌ 测试用户不存在")
                    return None
            else:
                logger.warning("⚠️ users表不存在")
                return None
                
    except Exception as e:
        logger.error(f"❌ 检查用户表失败: {e}")
        return None


async def setup_test_environment():
    """设置测试环境"""
    
    logger.info("🔧 设置测试环境...")
    
    # 检查数据库连接
    try:
        from models.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # 简单查询测试连接
            await db.execute("SELECT 1")
            logger.info("✅ 数据库连接正常")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return False
    
    # 检查用户认证表
    auth_info = await check_user_auth_table()
    
    if auth_info:
        logger.info("✅ 用户认证系统就绪")
    else:
        logger.warning("⚠️ 用户认证系统可能未完全配置")
    
    # 创建测试用户
    user = await create_test_user()
    
    if user:
        logger.info("✅ 测试环境设置完成")
        return True
    else:
        logger.error("❌ 测试环境设置失败")
        return False


async def main():
    """主函数"""
    
    logger.info("🚀 开始设置测试环境...")
    
    success = await setup_test_environment()
    
    if success:
        logger.info("\n🎉 测试环境设置完成！")
        logger.info(f"📋 测试用户信息：")
        logger.info(f"   登录code: {TEST_USER_CONFIG['code']}")
        logger.info(f"   昵称: {TEST_USER_CONFIG['nickname']}")
        logger.info("\n💡 现在可以运行API集成测试了:")
        logger.info("   python test_api_integration.py")
    else:
        logger.error("\n💥 测试环境设置失败！")
        logger.info("💡 请检查数据库连接和服务器状态")


if __name__ == "__main__":
    asyncio.run(main())