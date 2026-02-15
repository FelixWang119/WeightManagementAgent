#!/usr/bin/env python3
"""
初始化测试数据库
创建测试所需的所有表
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from models.database import Base


async def init_test_database():
    """初始化测试数据库"""
    print("🔧 初始化测试数据库...")

    # 测试数据库URL
    test_database_url = "sqlite+aiosqlite:///./test_weight_management.db"

    # 检查数据库文件是否存在
    test_db_path = project_root / "test_weight_management.db"
    if test_db_path.exists():
        print(f"⚠️  测试数据库已存在: {test_db_path}")
        # 在测试环境中自动删除并重新创建
        print("自动删除并重新创建测试数据库...")
        try:
            test_db_path.unlink()
            print("✅ 已删除旧测试数据库")
        except Exception as e:
            print(f"❌ 删除旧数据库失败: {e}")
            return False

    # 创建引擎
    engine = create_async_engine(
        test_database_url,
        echo=True,  # 输出SQL日志以便调试
        future=True,
    )

    try:
        # 创建所有表
        print("📊 创建数据库表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("✅ 测试数据库初始化完成!")

        # 显示创建的表
        async with engine.connect() as conn:
            from sqlalchemy import text

            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            )
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 创建的表 ({len(tables)}个): {', '.join(tables)}")

        await engine.dispose()
        return True

    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        await engine.dispose()
        return False


if __name__ == "__main__":
    # 加载测试环境
    from dotenv import load_dotenv

    env_test_path = project_root / ".env.test"
    load_dotenv(env_test_path, override=True)

    success = asyncio.run(init_test_database())
    sys.exit(0 if success else 1)
