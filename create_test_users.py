#!/usr/bin/env python3
"""
创建测试用户脚本
生成多个测试用户，包含基础数据和画像信息
"""
import asyncio
import random
import hashlib
from datetime import datetime, timedelta, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    get_db, User, UserProfile, WeightRecord, MealRecord, ExerciseRecord,
    WaterRecord, SleepRecord, ChatHistory, Goal, AgentConfig,
    MotivationType, PersonalityType, GoalStatus, MealType
)
from config.logging_config import get_module_logger

logger = get_module_logger()

def generate_openid(code: str) -> str:
    """生成与登录API相同的openid"""
    return hashlib.md5(f"{code}:fixed_salt".encode()).hexdigest()[:28]

# 测试用户数据（code用于登录，openid是code的MD5 hash）
TEST_USERS = [
    {
        "code": "test_user_001",
        "nickname": "小明",
        "gender": "男",
        "age": 28,
        "height": 175,
        "personality": PersonalityType.WARM,
        "motivation": MotivationType.GOAL_ORIENTED
    },
    {
        "code": "test_user_002", 
        "nickname": "小红",
        "gender": "女",
        "age": 25,
        "height": 162,
        "personality": PersonalityType.ENERGETIC,
        "motivation": MotivationType.EMOTIONAL_SUPPORT
    },
    {
        "code": "test_user_003",
        "nickname": "大壮",
        "gender": "男", 
        "age": 32,
        "height": 180,
        "personality": PersonalityType.PROFESSIONAL,
        "motivation": MotivationType.DATA_DRIVEN
    },
    {
        "code": "test_user_004",
        "nickname": "小美",
        "gender": "女",
        "age": 26,
        "height": 165,
        "personality": PersonalityType.WARM,
        "motivation": MotivationType.GOAL_ORIENTED
    },
    {
        "code": "test_user_005",
        "nickname": "阿强",
        "gender": "男",
        "age": 30,
        "height": 172,
        "personality": PersonalityType.ENERGETIC,
        "motivation": MotivationType.EMOTIONAL_SUPPORT
    }
]

async def create_test_users():
    """创建测试用户及数据"""
    async for db in get_db():
        try:
            created_users = []
            
            for user_data in TEST_USERS:
                # 生成openid（与登录API一致）
                openid = generate_openid(user_data["code"])
                
                # 检查用户是否已存在
                result = await db.execute(
                    select(User).where(User.openid == openid)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.info(f"用户 {user_data['nickname']} 已存在，跳过")
                    created_users.append(existing)
                    continue
                
                # 创建用户
                user = User(
                    openid=openid,
                    nickname=user_data["nickname"],
                    created_at=datetime.now() - timedelta(days=random.randint(7, 30)),
                    last_login=datetime.now() - timedelta(hours=random.randint(1, 24))
                )
                db.add(user)
                await db.flush()  # 获取user.id
                
                # 创建用户画像
                profile = UserProfile(
                    user_id=user.id,
                    age=user_data["age"],
                    gender=user_data["gender"],
                    height=user_data["height"],
                    bmr=random.randint(1400, 1800),
                    motivation_type=user_data["motivation"],
                    diet_preferences={
                        "food_types": random.choice([["中餐"], ["西餐"], ["混合"]]),
                        "flavor": random.choice(["清淡", "微辣", "偏甜"]),
                        "restrictions": []
                    },
                    exercise_habits={
                        "preferred_types": random.choice([["跑步"], ["游泳"], ["瑜伽"], ["健身"]]),
                        "frequency": random.choice(["每周3次", "每周4次", "每天"]),
                        "available_times": ["晚上"]
                    },
                    decision_mode="balanced",
                    communication_style="friendly",
                    weak_points=random.choice([["饮食控制"], ["运动坚持"], ["作息规律"]]),
                    profiling_batch_day=3,  # 已完成所有画像采集
                    day_1_completed=True,
                    day_2_completed=True,
                    day_3_completed=True,
                    onboarding_completed_at=datetime.now() - timedelta(days=7),
                    points=random.randint(100, 500)
                )
                db.add(profile)
                
                # 创建Agent配置
                agent_config = AgentConfig(
                    user_id=user.id,
                    agent_name=f"{user_data['nickname']}的健康助手",
                    personality_type=user_data["personality"],
                    personality_prompt=f"你是一位{user_data['personality'].value}风格的健康助手",
                    created_at=datetime.now()
                )
                db.add(agent_config)
                
                # 创建目标
                goal = Goal(
                    user_id=user.id,
                    target_weight=random.choice([65.0, 55.0, 70.0, 52.0, 68.0]),
                    target_date=date.today() + timedelta(days=90),
                    daily_calorie_target=random.choice([1500, 1600, 1700, 1400]),
                    status=GoalStatus.ACTIVE,
                    created_at=datetime.now() - timedelta(days=7)
                )
                db.add(goal)
                
                # 生成历史数据
                await generate_weight_records(db, user.id)
                await generate_meal_records(db, user.id)
                await generate_exercise_records(db, user.id)
                await generate_water_records(db, user.id)
                await generate_sleep_records(db, user.id)
                await generate_chat_history(db, user.id)
                
                created_users.append(user)
                logger.info(f"✅ 创建用户: {user_data['nickname']} (ID: {user.id})")
            
            await db.commit()
            
            print(f"\n{'='*50}")
            print(f"✅ 成功创建 {len(created_users)} 个测试用户")
            print(f"{'='*50}")
            for u in created_users:
                print(f"  ID: {u.id} | {u.nickname} | OpenID: {u.openid}")
            print(f"{'='*50}\n")
            
            return created_users
            
        except Exception as e:
            await db.rollback()
            logger.exception("创建测试用户失败: %s", str(e))
            raise
        finally:
            await db.close()

async def generate_weight_records(db: AsyncSession, user_id: int):
    """生成体重记录（最近7天）"""
    base_weight = random.uniform(60.0, 75.0)
    
    for i in range(7):
        record_date = date.today() - timedelta(days=i)
        # 体重略有波动
        weight = base_weight + random.uniform(-0.5, 0.5)
        record_datetime = datetime.combine(record_date, datetime.strptime("08:00", "%H:%M").time())
        
        record = WeightRecord(
            user_id=user_id,
            weight=round(weight, 1),
            record_date=record_date,
            record_time=record_datetime,
            created_at=record_datetime
        )
        db.add(record)

async def generate_meal_records(db: AsyncSession, user_id: int):
    """生成餐食记录（最近3天）"""
    meal_types = [
        (MealType.BREAKFAST, "早餐", 400, "08:00"),
        (MealType.LUNCH, "午餐", 700, "12:30"),
        (MealType.DINNER, "晚餐", 600, "19:00"),
    ]
    
    food_options = {
        "早餐": ["鸡蛋", "牛奶", "面包", "粥", "包子"],
        "午餐": ["米饭", "面条", "鸡胸肉", "蔬菜", "汤"],
        "晚餐": ["沙拉", "鱼", "豆腐", "蔬菜", "粥"]
    }
    
    for i in range(3):
        record_date = date.today() - timedelta(days=i)
        
        for meal_type, meal_name, base_calories, meal_time in meal_types:
            # 不是每餐都记录
            if random.random() > 0.8:  # 20%概率跳过某餐
                continue
                
            foods = random.sample(food_options[meal_name], k=random.randint(2, 3))
            
            record = MealRecord(
                user_id=user_id,
                meal_type=meal_type,
                food_items=[{"name": f, "calories": random.randint(100, 300)} for f in foods],
                total_calories=base_calories + random.randint(-100, 100),
                record_time=datetime.combine(record_date, datetime.strptime(meal_time, "%H:%M").time()),
                created_at=datetime.combine(record_date, datetime.strptime(meal_time, "%H:%M").time())
            )
            db.add(record)

async def generate_exercise_records(db: AsyncSession, user_id: int):
    """生成运动记录（最近7天，间隔1-2天）"""
    exercise_types = ["跑步", "快走", "游泳", "瑜伽", "健身", "骑行"]
    
    for i in range(0, 7, random.choice([1, 2])):
        record_date = date.today() - timedelta(days=i)
        duration = random.choice([30, 45, 60, 90])
        
        record = ExerciseRecord(
            user_id=user_id,
            exercise_type=random.choice(exercise_types),
            duration_minutes=duration,
            calories_burned=duration * random.randint(5, 10),
            record_time=datetime.combine(record_date, datetime.strptime("19:00", "%H:%M").time()),
            created_at=datetime.combine(record_date, datetime.strptime("19:00", "%H:%M").time())
        )
        db.add(record)

async def generate_water_records(db: AsyncSession, user_id: int):
    """生成饮水记录（今天）"""
    times = ["08:00", "10:00", "14:00", "16:00", "20:00"]
    
    for t in times:
        if random.random() > 0.3:  # 70%概率记录
            record_datetime = datetime.combine(date.today(), datetime.strptime(t, "%H:%M").time())
            record = WaterRecord(
                user_id=user_id,
                amount_ml=random.choice([200, 250, 300]),
                record_time=record_datetime,
                created_at=record_datetime
            )
            db.add(record)

async def generate_sleep_records(db: AsyncSession, user_id: int):
    """生成睡眠记录（最近3天）"""
    for i in range(3):
        record_date = date.today() - timedelta(days=i+1)
        duration = random.uniform(6.5, 8.5)
        
        # DateTime 类型需要完整 datetime 对象
        bed_datetime = datetime.combine(record_date, datetime.strptime("23:00", "%H:%M").time())
        wake_datetime = datetime.combine(record_date + timedelta(days=1), datetime.strptime("07:00", "%H:%M").time())
        
        record = SleepRecord(
            user_id=user_id,
            bed_time=bed_datetime,
            wake_time=wake_datetime,
            total_minutes=int(duration * 60),
            quality=random.randint(3, 5),  # 质量是整数 1-5
            created_at=datetime.now()
        )
        db.add(record)

async def generate_chat_history(db: AsyncSession, user_id: int):
    """生成聊天记录（最近3天）"""
    messages = [
        ("user", "今天体重65kg"),
        ("assistant", "很好！继续保持记录习惯"),
        ("user", "晚上吃了沙拉"),
        ("assistant", "健康的选择！记得补充蛋白质"),
        ("user", "明天计划去跑步"),
        ("assistant", "太棒了！建议跑30-45分钟")
    ]
    
    for i, (role, content) in enumerate(messages):
        msg_time = datetime.now() - timedelta(days=random.randint(0, 2), hours=random.randint(0, 23))
        
        record = ChatHistory(
            user_id=user_id,
            role=role,
            content=content,
            created_at=msg_time
        )
        db.add(record)

if __name__ == "__main__":
    print("开始创建测试用户...")
    asyncio.run(create_test_users())
