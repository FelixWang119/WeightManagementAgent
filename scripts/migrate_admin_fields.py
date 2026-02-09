#!/usr/bin/env python3
"""
数据库迁移脚本 - 添加管理员字段到User表
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from config.settings import get_fastapi_settings

settings = get_fastapi_settings()

# 同步引擎（用于执行DDL）
import sqlite3


def migrate_sqlite():
    """SQLite数据库迁移"""
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///./", "")
    print(f"📊 数据库文件: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表结构
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"现有列: {columns}")
    
    # 需要添加的字段
    new_columns = [
        ("is_admin", "BOOLEAN DEFAULT 0"),
        ("admin_role", "VARCHAR(20)"),
        ("admin_permissions", "TEXT"),  # JSON存储为TEXT
        ("last_admin_login", "DATETIME")
    ]
    
    added_count = 0
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"添加列: {col_name} {col_type}")
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"  错误: {e}")
        else:
            print(f"列已存在: {col_name}")
    
    if added_count > 0:
        conn.commit()
        print(f"✅ 成功添加 {added_count} 个列")
    else:
        print("✅ 所有列已存在")
    
    # 验证
    cursor.execute("PRAGMA table_info(users)")
    print("\n📋 最终表结构:")
    for row in cursor.fetchall():
        print(f"  {row[1]} ({row[2]}) {'NOT NULL' if row[3] else 'NULLABLE'} DEFAULT={row[4]}")
    
    conn.close()
    
    # 如果有用户，将第一个用户设为管理员
    if added_count > 0:
        set_first_user_as_admin(db_path)


def set_first_user_as_admin(db_path: str):
    """将第一个用户设为管理员（如果还没有管理员）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查是否有管理员
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    admin_count = cursor.fetchone()[0]
    
    if admin_count == 0:
        # 获取第一个用户
        cursor.execute("SELECT id, nickname FROM users ORDER BY id LIMIT 1")
        user = cursor.fetchone()
        
        if user:
            user_id, nickname = user
            print(f"\n👤 找到用户: {nickname} (ID: {user_id})")
            
            # 设为超级管理员
            cursor.execute("""
                UPDATE users 
                SET is_admin = 1, 
                    admin_role = 'super', 
                    admin_permissions = '["*"]',
                    last_admin_login = datetime('now')
                WHERE id = ?
            """, (user_id,))
            
            conn.commit()
            print(f"✅ 已将用户 '{nickname}' 设为超级管理员")
            print(f"   默认管理员密码: admin123 (通过环境变量 ADMIN_PASSWORD 设置)")
    
    conn.close()


async def main():
    print("🚀 开始数据库迁移...")
    
    if "sqlite" in settings.DATABASE_URL:
        migrate_sqlite()
    else:
        print("❌ 目前仅支持SQLite数据库迁移")
        print(f"   数据库URL: {settings.DATABASE_URL}")
    
    print("\n📋 迁移完成!")
    print("   请设置环境变量 ADMIN_PASSWORD 以启用管理员登录")
    print("   访问管理后台: http://localhost:8000/admin/login.html")


if __name__ == "__main__":
    asyncio.run(main())