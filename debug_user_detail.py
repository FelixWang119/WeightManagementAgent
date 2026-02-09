#!/usr/bin/env python3
"""
调试用户详情API错误
"""
import asyncio
import sys
sys.path.insert(0, '.')

from api.routes.admin.users import get_user, list_users, get_user_stats_summary
from models.database import get_db
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
import logging

logging.basicConfig(level=logging.DEBUG)

# 使用测试数据库
DATABASE_URL = "sqlite+aiosqlite:///./weight_management.db"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("测试用户列表...")
        try:
            # 模拟管理员用户（跳过认证）
            from models.database import User
            admin_user = User(id=1, is_admin=True, admin_role="super")
            
            # 获取第一个用户ID
            result = await db.execute("SELECT id FROM users LIMIT 1")
            user_id = result.scalar_one()
            print(f"测试用户ID: {user_id}")
            
            # 测试get_user_with_profile
            from api.routes.admin.users import get_user_with_profile
            user_obj = await get_user_with_profile(db, user_id)
            print(f"用户对象: {user_obj}")
            
            # 测试get_user_stats
            from api.routes.admin.users import get_user_stats
            stats = await get_user_stats(db, user_id)
            print(f"用户统计: {stats}")
            
            # 测试get_current_goal
            from api.routes.admin.users import get_current_goal
            goal = await get_current_goal(db, user_id)
            print(f"当前目标: {goal}")
            
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())