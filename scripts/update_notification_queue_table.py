#!/usr/bin/env python3
"""
更新notification_queue表结构，添加content_type和content_data字段
"""

import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_notification_queue_table():
    """更新notification_queue表结构"""
    db_path = "weight_management.db"

    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notification_queue'"
        )
        if not cursor.fetchone():
            print("❌ notification_queue表不存在")
            return False

        # 检查是否已有content_type字段
        cursor.execute("PRAGMA table_info(notification_queue)")
        columns = [col[1] for col in cursor.fetchall()]

        print("当前表结构:")
        for col in columns:
            print(f"  - {col}")

        # 添加缺失的字段
        if "content_type" not in columns:
            print("\n添加content_type字段...")
            cursor.execute(
                "ALTER TABLE notification_queue ADD COLUMN content_type TEXT"
            )
            print("✅ content_type字段已添加")

        if "content_data" not in columns:
            print("\n添加content_data字段...")
            cursor.execute(
                "ALTER TABLE notification_queue ADD COLUMN content_data TEXT"
            )
            print("✅ content_data字段已添加")

        conn.commit()
        conn.close()

        print("\n✅ 表结构更新完成")
        return True

    except Exception as e:
        print(f"❌ 更新表结构时发生错误: {e}")
        return False


if __name__ == "__main__":
    print("开始更新notification_queue表结构...")
    print("=" * 50)

    success = update_notification_queue_table()

    if success:
        print("\n" + "=" * 50)
        print("✅ 更新成功")
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ 更新失败")
        sys.exit(1)
