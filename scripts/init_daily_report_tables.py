#!/usr/bin/env python3
"""
初始化日报相关数据库表
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from models.database import AsyncSessionLocal
from config.settings import fastapi_settings


async def init_daily_report_tables():
    """初始化日报相关数据库表"""
    print("开始初始化日报相关数据库表...")

    async with AsyncSessionLocal() as db:
        try:
            # 检查 daily_reports 表是否存在
            check_table_sql = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='daily_reports'
            """

            result = await db.execute(text(check_table_sql))
            table_exists = result.scalar() is not None

            if table_exists:
                print("daily_reports 表已存在，跳过创建")
            else:
                # 创建 daily_reports 表
                create_table_sql = """
                CREATE TABLE daily_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    report_date DATE NOT NULL,
                    summary_text TEXT,
                    weight REAL,
                    calories_in INTEGER,
                    calories_out INTEGER,
                    calorie_deficit INTEGER,
                    water_intake INTEGER,
                    sleep_hours REAL,
                    exercise_minutes INTEGER,
                    highlights TEXT,
                    tips TEXT,
                    suggestions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(user_id, report_date)
                )
                """

                await db.execute(text(create_table_sql))
                print("daily_reports 表创建成功")

                # 创建索引
                create_index_sql = """
                CREATE INDEX idx_daily_reports_user_date 
                ON daily_reports (user_id, report_date DESC)
                """
                await db.execute(text(create_index_sql))
                print("日报索引创建成功")

            # 检查 reminder_settings 表中是否有日报配置
            check_reminder_sql = """
            SELECT COUNT(*) FROM reminder_settings 
            WHERE reminder_type = 'daily'
            """

            result = await db.execute(text(check_reminder_sql))
            daily_reminder_count = result.scalar() or 0

            if daily_reminder_count == 0:
                print("提醒设置中没有日报配置，需要为用户添加默认配置")
                # 这里可以在后续步骤中为用户添加默认配置
            else:
                print(f"提醒设置中已有 {daily_reminder_count} 条日报配置")

            await db.commit()
            print("日报表初始化完成")

        except Exception as e:
            await db.rollback()
            print(f"初始化失败: {e}")
            raise


async def add_default_daily_reminders():
    """为用户添加默认日报提醒设置"""
    print("开始为用户添加默认日报提醒设置...")

    async with AsyncSessionLocal() as db:
        try:
            # 获取所有用户
            get_users_sql = "SELECT id FROM users"
            result = await db.execute(text(get_users_sql))
            users = result.fetchall()

            added_count = 0
            for user in users:
                user_id = user[0]

                # 检查是否已有日报设置
                check_sql = """
                SELECT COUNT(*) FROM reminder_settings 
                WHERE user_id = :user_id AND reminder_type = 'daily'
                """
                result = await db.execute(text(check_sql), {"user_id": user_id})
                exists = result.scalar() or 0

                if exists == 0:
                    # 添加默认日报设置（晚上9点）
                    insert_sql = """
                    INSERT INTO reminder_settings 
                    (user_id, reminder_type, enabled, reminder_time, weekdays_only)
                    VALUES 
                    (:user_id, 'daily', 1, '21:00:00', 0)
                    """
                    await db.execute(text(insert_sql), {"user_id": user_id})
                    added_count += 1

            await db.commit()
            print(f"为 {added_count} 个用户添加了默认日报提醒设置")

        except Exception as e:
            await db.rollback()
            print(f"添加默认提醒设置失败: {e}")
            raise


async def main():
    """主函数"""
    try:
        await init_daily_report_tables()
        await add_default_daily_reminders()
        print("所有初始化任务完成")
    except Exception as e:
        print(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
