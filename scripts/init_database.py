#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表结构和初始数据
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.database import init_db, get_async_engine, async_session
from config.settings import fastapi_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    """创建数据库表"""
    logger.info("正在创建数据库表...")
    try:
        await init_db()
        logger.info("✅ 数据库表创建成功")
    except Exception as e:
        logger.error(f"❌ 创建数据库表失败: {e}")
        raise


async def create_initial_data():
    """创建初始数据"""
    logger.info("正在创建初始数据...")
    
    async with async_session() as session:
        try:
            # 这里可以添加初始数据的创建逻辑
            # 例如：创建默认的系统配置、助手风格等
            
            await session.commit()
            logger.info("✅ 初始数据创建成功")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ 创建初始数据失败: {e}")
            raise


async def check_database():
    """检查数据库连接和表结构"""
    logger.info("正在检查数据库...")
    
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            # 测试连接
            result = await conn.execute("SELECT 1")
            test = result.scalar()
            if test == 1:
                logger.info("✅ 数据库连接正常")
            else:
                logger.error("❌ 数据库连接测试失败")
                return False
                
        # 检查表是否存在（通过查询系统表）
        async with async_session() as session:
            try:
                # 尝试查询一个表
                result = await session.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = result.fetchall()
                logger.info(f"📊 数据库中有 {len(tables)} 个表")
                for table in tables[:10]:  # 只显示前10个表
                    logger.info(f"  - {table[0]}")
                if len(tables) > 10:
                    logger.info(f"  ... 还有 {len(tables) - 10} 个表")
            except Exception as e:
                logger.warning(f"⚠️  无法查询表信息: {e}")
                
        return True
    except Exception as e:
        logger.error(f"❌ 数据库检查失败: {e}")
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("体重管理助手 - 数据库初始化工具")
    print("=" * 60)
    
    # 检查数据库
    if not await check_database():
        print("\n❌ 数据库检查失败，请检查配置")
        return
    
    # 创建表
    try:
        await create_tables()
    except Exception as e:
        print(f"\n❌ 创建表失败: {e}")
        return
    
    # 创建初始数据
    try:
        await create_initial_data()
    except Exception as e:
        print(f"\n⚠️  创建初始数据失败（可忽略）: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 数据库初始化完成！")
    print(f"📁 数据库文件: {fastapi_settings.DATABASE_URL.replace('sqlite+aiosqlite:///', '')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())