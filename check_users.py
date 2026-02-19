#!/usr/bin/env python3
"""检查并清理测试用户"""
import asyncio
from sqlalchemy import select, delete
from models.database import get_db, User, UserProfile, WeightRecord, MealRecord, ExerciseRecord, WaterRecord, SleepRecord, ChatHistory, Goal

async def check_users():
    async for db in get_db():
        try:
            # 查询所有用户
            result = await db.execute(select(User))
            users = result.scalars().all()
            
            print(f"=== 数据库用户统计 ===")
            print(f"总用户数: {len(users)}\n")
            
            if users:
                print("用户列表:")
                for u in users[:20]:  # 只显示前20个
                    nickname = u.nickname or '未设置'
                    created = u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else 'N/A'
                    last_login = u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else 'N/A'
                    print(f"  ID:{u.id} | {nickname} | 创建:{created} | 登录:{last_login}")
                
                if len(users) > 20:
                    print(f"  ... 还有 {len(users)-20} 个用户")
            
            # 统计各类记录数
            tables = [
                (UserProfile, "用户画像"),
                (WeightRecord, "体重记录"),
                (MealRecord, "餐食记录"),
                (ExerciseRecord, "运动记录"),
                (WaterRecord, "饮水记录"),
                (SleepRecord, "睡眠记录"),
                (ChatHistory, "聊天记录"),
                (Goal, "目标记录"),
            ]
            
            print("\n=== 数据记录统计 ===")
            for model, name in tables:
                result = await db.execute(select(model))
                count = len(result.scalars().all())
                print(f"  {name}: {count} 条")
            
            return users
            
        finally:
            await db.close()

async def clean_test_users():
    """清理测试用户（昵称包含test、测试、或特定前缀的用户）"""
    async for db in get_db():
        try:
            result = await db.execute(select(User))
            users = result.scalars().all()
            
            test_users = []
            for u in users:
                nickname = (u.nickname or "").lower()
                # 识别测试用户
                if any(keyword in nickname for keyword in ['test', '测试', 'demo', 'user', '用户']):
                    test_users.append(u)
            
            if test_users:
                print(f"\n找到 {len(test_users)} 个测试用户，准备清理...")
                for u in test_users:
                    print(f"  删除用户: ID:{u.id} {u.nickname}")
                    # 由于外键约束，用户记录会自动级联删除关联数据
                    await db.execute(delete(User).where(User.id == u.id))
                
                await db.commit()
                print(f"✅ 已清理 {len(test_users)} 个测试用户")
            else:
                print("\n没有找到需要清理的测试用户")
                
        finally:
            await db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        print("=== 清理测试用户模式 ===")
        asyncio.run(clean_test_users())
    else:
        print("=== 查看用户模式 ===")
        print("提示: 使用 'python check_users.py clean' 清理测试用户\n")
        asyncio.run(check_users())
