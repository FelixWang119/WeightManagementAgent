#!/usr/bin/env python3
"""
数据库迁移脚本 - 创建提示词管理相关表
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from models.database import Base, SystemPrompt, PromptVersion
from config.settings import get_fastapi_settings

settings = get_fastapi_settings()


async def migrate_prompt_tables():
    """创建提示词相关表"""
    print("🚀 开始创建提示词管理表...")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG
    )
    
    async with engine.begin() as conn:
        # 创建表
        print("📊 创建表: system_prompts")
        await conn.run_sync(Base.metadata.create_all, tables=[SystemPrompt.__table__])
        
        print("📊 创建表: prompt_versions")
        await conn.run_sync(Base.metadata.create_all, tables=[PromptVersion.__table__])
    
    print("✅ 提示词管理表创建完成!")
    
    # 验证表结构
    await verify_tables(engine)


async def verify_tables(engine):
    """验证表结构"""
    import sqlite3
    
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///./", "")
    print(f"\n🔍 验证数据库: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    tables = ["system_prompts", "prompt_versions"]
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if cursor.fetchone():
            print(f"✅ 表存在: {table}")
            
            # 显示表结构
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print(f"   列结构:")
            for col in columns:
                print(f"     {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULLABLE'}")
        else:
            print(f"❌ 表不存在: {table}")
    
    conn.close()


async def main():
    """主函数"""
    print("=" * 50)
    print("提示词管理表迁移工具")
    print("=" * 50)
    
    await migrate_prompt_tables()
    
    print("\n📋 迁移完成!")
    print("   提示词管理API端点:")
    print("   - GET    /admin/prompts         # 列表")
    print("   - POST   /admin/prompts         # 创建")
    print("   - GET    /admin/prompts/{id}    # 详情")
    print("   - PUT    /admin/prompts/{id}    # 更新")
    print("   - DELETE /admin/prompts/{id}    # 删除")
    print("   - POST   /admin/prompts/{id}/test    # 测试")
    print("   - GET    /admin/prompts/{id}/versions    # 版本历史")
    print("   - POST   /admin/prompts/{id}/publish    # 发布")
    print("   - POST   /admin/prompts/{id}/rollback/{version}    # 回滚")


if __name__ == "__main__":
    asyncio.run(main())