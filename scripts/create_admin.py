#!/usr/bin/env python3
"""
创建管理员用户脚本
用法：python scripts/create_admin.py [--username admin] [--password admin123]
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime
import hashlib
import secrets

from models.database import User, Base
from config.settings import get_fastapi_settings

settings = get_fastapi_settings()

# 数据库引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def hash_password(password: str, salt: str = "") -> str:
    """简单的密码哈希函数"""
    data = f"{password}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


async def create_admin_user(username: str, password: str):
    """
    创建管理员用户
    
    策略：
    1. 如果已有用户，将第一个用户设为管理员
    2. 如果没有用户，创建新用户并设为管理员
    """
    async with AsyncSessionLocal() as db:
        # 检查是否已有用户
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if users:
            # 使用第一个用户作为管理员
            user = users[0]
            print(f"📝 找到现有用户: {user.nickname} (ID: {user.id})")
            
            # 更新为管理员
            user.is_admin = True
            user.admin_role = "super"
            user.admin_permissions = ["*"]  # 所有权限
            user.last_admin_login = datetime.utcnow()
            
            print(f"✅ 已将用户 '{user.nickname}' 设为超级管理员")
            print(f"   用户名: {username}")
            print(f"   密码: {password}")
            print(f"   角色: super")
            print(f"   权限: 所有权限")
            
        else:
            # 创建新管理员用户
            # 生成虚拟openid（管理员不使用微信登录）
            openid = hashlib.md5(f"admin_{secrets.token_hex(8)}".encode()).hexdigest()[:28]
            
            user = User(
                openid=openid,
                nickname="系统管理员",
                avatar_url="",
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
                is_admin=True,
                admin_role="super",
                admin_permissions=["*"],
                last_admin_login=datetime.utcnow()
            )
            
            db.add(user)
            print(f"✅ 创建新管理员用户")
            print(f"   用户名: {username}")
            print(f"   密码: {password}")
            print(f"   角色: super")
            print(f"   权限: 所有权限")
        
        await db.commit()
        
        # 显示环境变量设置提示
        print("\n📋 重要提示:")
        print("1. 请设置环境变量 ADMIN_PASSWORD 以启用密码验证:")
        print(f"   export ADMIN_PASSWORD='{password}'")
        print("2. 或修改 .env 文件添加:")
        print(f"   ADMIN_PASSWORD={password}")
        print("\n3. 登录信息:")
        print(f"   访问地址: http://{settings.HOST}:{settings.PORT}/admin/login.html")
        print(f"   用户名: {username}")
        print(f"   密码: {password}")
        
        return user


async def list_admin_users():
    """列出所有管理员用户"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.is_admin == True)
        )
        admins = result.scalars().all()
        
        if not admins:
            print("❌ 未找到管理员用户")
            return
        
        print(f"📊 管理员用户列表 ({len(admins)} 个):")
        for admin in admins:
            print(f"\n  ID: {admin.id}")
            print(f"  昵称: {admin.nickname}")
            print(f"  角色: {admin.admin_role or '未设置'}")
            print(f"  最后登录: {admin.last_login}")
            print(f"  最后管理登录: {admin.last_admin_login}")


async def main():
    parser = argparse.ArgumentParser(description="创建管理员用户")
    parser.add_argument("--username", default="admin", help="管理员用户名")
    parser.add_argument("--password", default="admin123", help="管理员密码")
    parser.add_argument("--list", action="store_true", help="列出所有管理员")
    
    args = parser.parse_args()
    
    if args.list:
        await list_admin_users()
    else:
        print("🚀 正在创建管理员用户...")
        await create_admin_user(args.username, args.password)


if __name__ == "__main__":
    asyncio.run(main())