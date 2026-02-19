# 成就与积分系统完整集成实施计划

**目标：** 实现成就和积分的自动检查、发放，并与体重、饮食、运动、饮水、睡眠等业务系统集成，同时实现排行榜功能

**架构：** 扩展现有的`AchievementService`和`PointsService`，添加`IntegrationService`用于统一处理业务操作后的成就检查和积分发放，在数据库中添加`PointsHistory`表，并在各个业务API端点中调用集成服务

**技术栈：** Python, FastAPI, SQLAlchemy, AsyncSession

---

## Task 1: 创建积分历史表模型

**Files:**
- Create: `/Users/felix/open_workdspace/models/points_history.py`
- Modify: `/Users/felix/open_workdspace/models/database.py` - 导入PointsHistory
- Test: `/Users/felix/open_workdspace/tests/test_points_history.py`

**Step 1: 创建积分历史表模型**

```python
"""
积分历史记录模型
用于记录用户积分的获取和消费明细
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from models.database import Base
import enum


class PointsType(enum.Enum):
    """积分类型"""
    EARN = "earn"          # 获得积分
    SPEND = "spend"        # 消耗积分


class PointsHistory(Base):
    """积分历史记录表"""
    
    __tablename__ = "points_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    points_type = Column(Enum(PointsType), nullable=False, comment="积分类型")
    amount = Column(Integer, nullable=False, comment="积分数量")
    reason = Column(String(100), nullable=False, comment="原因/来源")
    description = Column(Text, nullable=True, comment="详细描述")
    related_record_id = Column(Integer, nullable=True, comment="关联记录ID")
    related_record_type = Column(String(50), nullable=True, comment="关联记录类型")
    balance_after = Column(Integer, nullable=False, comment="操作后余额")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
```

**Step 2: 修改database.py导入**

在文件末尾添加导入：
```python
# 导入积分历史模型
from models.points_history import PointsHistory
```

**Step 3: 创建数据库迁移（手动）**

提示用户运行：
```bash
alembic revision --autogenerate -m "add points_history table"
alembic upgrade head
```

**Step 4: 提交**

```bash
git add models/points_history.py models/database.py
git commit -m "feat: add PointsHistory model for tracking points transactions"
```

---

## Task 2: 修改成就服务 - 添加缺失成就和自动检查功能

**Files:**
- Modify: `/Users/felix/open_workdspace/services/achievement_service.py`
- Test: `/Users/felix/open_workdspace/tests/test_achievement_service.py`

**Step 1: 添加缺失的成就定义**

在 ACHIEVEMENTS 字典中添加缺失的成就：

```python
    AchievementType.CALORIE_CONTROL.value: Achievement(
        id=AchievementType.CALORIE_CONTROL.value,
        name="热量控制师",
        description="连续7天热量达标",
        category=AchievementCategory.DIET,
        icon="🔥",
        points=150,
        rarity="rare",
        condition={"type": "calorie_streak", "days": 7},
    ),
    AchievementType.SLEEP_MASTER.value: Achievement(
        id=AchievementType.SLEEP_MASTER.value,
        name="睡眠大师",
        description="连续14天睡眠达标",
        category=AchievementCategory.SPECIAL,
        icon="🌙",
        points=250,
        rarity="epic",
        condition={"type": "sleep_streak", "days": 14},
    ),
    AchievementType.SOCIAL_SHARE.value: Achievement(
        id=AchievementType.SOCIAL_SHARE.value,
        name="分享达人",
        description="分享成就10次",
        category=AchievementCategory.SPECIAL,
        icon="📢",
        points=100,
        rarity="common",
        condition={"type": "social_shares", "count": 10},
    ),
```

**Step 2: 添加UnlockReason类型**

```python
class UnlockReason:
    """成就解锁原因/触发点"""
    WEIGHT_RECORD = "weight_record"
    MEAL_RECORD = "meal_record"
    EXERCISE_RECORD = "exercise_record"
    WATER_RECORD = "water_record"
    SLEEP_RECORD = "sleep_record"
    GOAL_ACHIEVED = "goal_achieved"
    DAILY_CHECKIN = "daily_checkin"
```

**Step 3: 修改check_and_unlock方法**

优化成就检查逻辑，添加更多触发类型：

```python
    @staticmethod
    async def check_and_unlock(
        user_id: int, trigger_type: str, value: Any, db: AsyncSession
    ) -> List[Dict]:
        """检查并解锁成就"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        unlocked = []
        if profile and profile.achievements:
            unlocked = (
                json.loads(profile.achievements)
                if isinstance(profile.achievements, str)
                else profile.achievements
            )

        newly_unlocked = []

        for ach_id, ach in ACHIEVEMENTS.items():
            if ach_id in unlocked:
                continue

            should_unlock = False
            condition_type = ach.condition.get("type")

            if condition_type == "streak" and trigger_type == "streak":
                if value >= ach.condition.get("days", 7):
                    should_unlock = True

            elif condition_type == "total_records" and trigger_type == "total_records":
                if value >= ach.condition.get("count", 100):
                    should_unlock = True

            elif condition_type == "total_exercises" and trigger_type == "total_exercises":
                if value >= ach.condition.get("count", 50):
                    should_unlock = True

            elif condition_type == "total_meals" and trigger_type == "total_meals":
                if value >= ach.condition.get("count", 100):
                    should_unlock = True

            elif condition_type == "first_record" and trigger_type == "first_record":
                should_unlock = True

            elif condition_type == "goal_achieved" and trigger_type == "goal_achieved":
                should_unlock = True

            elif condition_type == "water_streak" and trigger_type == "water_streak":
                if value >= ach.condition.get("days", 30):
                    should_unlock = True

            elif condition_type == "calorie_streak" and trigger_type == "calorie_streak":
                if value >= ach.condition.get("days", 7):
                    should_unlock = True

            elif condition_type == "sleep_streak" and trigger_type == "sleep_streak":
                if value >= ach.condition.get("days", 14):
                    should_unlock = True

            elif condition_type == "social_shares" and trigger_type == "social_shares":
                if value >= ach.condition.get("count", 10):
                    should_unlock = True

            elif condition_type == "early_morning_streak" and trigger_type == "early_morning_streak":
                if value >= ach.condition.get("days", 7):
                    should_unlock = True

            if should_unlock:
                unlocked.append(ach_id)
                newly_unlocked.append(
                    {
                        "id": ach.id,
                        "name": ach.name,
                        "icon": ach.icon,
                        "points": ach.points,
                        "rarity": ach.rarity,
                        "unlocked_at": datetime.utcnow().isoformat(),
                    }
                )

        if newly_unlocked and profile:
            profile.achievements = json.dumps(unlocked)
            await db.commit()

        return newly_unlocked
```

**Step 4: 提交**

```bash
git add services/achievement_service.py
git commit -m "feat: add missing achievements and improve check logic"
```

---

## Task 3: 修改积分服务 - 实现历史记录功能

**Files:**
- Modify: `/Users/felix/open_workdspace/services/achievement_service.py`
- Test: `/Users/felix/open_workdspace/tests/test_points_service.py`

**Step 1: 导入PointsHistory模型**

在文件顶部添加：
```python
from models.points_history import PointsHistory, PointsType
```

**Step 2: 修改earn_points方法**

添加历史记录写入：

```python
    @staticmethod
    async def earn_points(
        user_id: int, reason: str, amount: int, db: AsyncSession,
        description: str = None, related_record_id: int = None, related_record_type: str = None
    ) -> Dict[str, Any]:
        """获得积分"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(
                user_id=user_id, points=0, total_points_earned=0, total_points_spent=0
            )
            db.add(profile)

        profile.points = (profile.points or 0) + amount
        profile.total_points_earned = (profile.total_points_earned or 0) + amount

        # 创建积分历史记录
        history = PointsHistory(
            user_id=user_id,
            points_type=PointsType.EARN,
            amount=amount,
            reason=reason,
            description=description,
            related_record_id=related_record_id,
            related_record_type=related_record_type,
            balance_after=profile.points
        )
        db.add(history)

        await db.commit()

        return {
            "success": True,
            "message": f"获得 {amount} 积分",
            "data": {
                "reason": reason,
                "points_earned": amount,
                "current_points": profile.points,
            },
        }
```

**Step 3: 修改spend_points方法**

添加历史记录写入：

```python
    @staticmethod
    async def spend_points(
        user_id: int, reason: str, amount: int, db: AsyncSession,
        description: str = None, related_record_id: int = None, related_record_type: str = None
    ) -> Dict[str, Any]:
        """消费积分"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or (profile.points or 0) < amount:
            return {"success": False, "error": "积分不足"}

        profile.points = profile.points - amount
        profile.total_points_spent = (profile.total_points_spent or 0) + amount

        # 创建积分历史记录
        history = PointsHistory(
            user_id=user_id,
            points_type=PointsType.SPEND,
            amount=amount,
            reason=reason,
            description=description,
            related_record_id=related_record_id,
            related_record_type=related_record_type,
            balance_after=profile.points
        )
        db.add(history)

        await db.commit()

        return {
            "success": True,
            "message": f"消耗 {amount} 积分",
            "data": {
                "reason": reason,
                "points_spent": amount,
                "current_points": profile.points,
            },
        }
```

**Step 4: 修改get_points_history方法**

实现真正的历史记录查询：

```python
    @staticmethod
    async def get_points_history(
        user_id: int, db: AsyncSession, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """获取积分历史"""
        from sqlalchemy import desc
        
        result = await db.execute(
            select(PointsHistory)
            .where(PointsHistory.user_id == user_id)
            .order_by(desc(PointsHistory.created_at))
            .limit(limit)
            .offset(offset)
        )
        
        history_records = result.scalars().all()
        
        history = []
        for record in history_records:
            history.append({
                "id": record.id,
                "type": record.points_type.value,
                "amount": record.amount,
                "reason": record.reason,
                "description": record.description,
                "balance_after": record.balance_after,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            })
        
        # 获取总数
        count_result = await db.execute(
            select(func.count()).where(PointsHistory.user_id == user_id)
        )
        total = count_result.scalar()
        
        return {
            "success": True,
            "data": {
                "history": history,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        }
```

**Step 5: 提交**

```bash
git add services/achievement_service.py
git commit -m "feat: implement points history tracking with database storage"
```

---

## Task 4: 创建业务集成服务

**Files:**
- Create: `/Users/felix/open_workdspace/services/integration_service.py`
- Test: `/Users/felix/open_workdspace/tests/test_integration_service.py`

**Step 1: 创建集成服务**

```python
"""
业务集成服务
处理成就检查和积分发放的自动化集成
"""

from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from models.database import (
    UserProfile, WeightRecord, MealRecord, ExerciseRecord, 
    WaterRecord, SleepRecord, Goal
)
from models.points_history import PointsHistory, PointsType
from services.achievement_service import AchievementService, PointsService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class AchievementIntegrationService:
    """成就集成服务"""
    
    @staticmethod
    async def process_weight_record(user_id: int, record_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理体重记录后的成就检查和积分发放"""
        logger.info("处理体重记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "messages": []
        }
        
        try:
            # 1. 发放体重记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录体重",
                amount=10,
                db=db,
                description="成功记录体重数据",
                related_record_id=record_id,
                related_record_type="weight_record"
            )
            
            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 检查是否是首次记录
            total_records = await AchievementIntegrationService._get_total_weight_records(user_id, db)
            if total_records == 1:
                # 首次记录成就
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                
                # 首次记录积分奖励
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="weight_record"
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"]["points_earned"]
            
            # 3. 检查累计记录数成就
            total_all_records = await AchievementIntegrationService._get_total_all_records(user_id, db)
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            # 4. 检查体重目标成就
            await AchievementIntegrationService._check_weight_goal_achievement(user_id, db, results)
            
        except Exception as e:
            logger.exception("处理体重记录成就时出错: %s", e)
        
        return results
    
    @staticmethod
    async def process_meal_record(user_id: int, record_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理餐食记录后的成就检查和积分发放"""
        logger.info("处理餐食记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "messages": []
        }
        
        try:
            # 1. 发放餐食记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录饮食",
                amount=5,
                db=db,
                description="成功记录餐食数据",
                related_record_id=record_id,
                related_record_type="meal_record"
            )
            
            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 检查是否是首次记录
            total_meals = await AchievementIntegrationService._get_total_meal_records(user_id, db)
            if total_meals == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="meal_record"
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"]["points_earned"]
            
            # 3. 检查餐食累计成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_meals", total_meals, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            # 4. 检查累计记录数成就
            total_all_records = await AchievementIntegrationService._get_total_all_records(user_id, db)
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            # 5. 检查热量控制成就
            await AchievementIntegrationService._check_calorie_streak(user_id, db, results)
            
        except Exception as e:
            logger.exception("处理餐食记录成就时出错: %s", e)
        
        return results
    
    @staticmethod
    async def process_exercise_record(user_id: int, record_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理运动记录后的成就检查和积分发放"""
        logger.info("处理运动记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "messages": []
        }
        
        try:
            # 1. 发放运动记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录运动",
                amount=10,
                db=db,
                description="成功记录运动数据",
                related_record_id=record_id,
                related_record_type="exercise_record"
            )
            
            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 检查是否是首次记录
            total_exercises = await AchievementIntegrationService._get_total_exercise_records(user_id, db)
            if total_exercises == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="exercise_record"
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"]["points_earned"]
            
            # 3. 检查运动累计成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_exercises", total_exercises, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            # 4. 检查累计记录数成就
            total_all_records = await AchievementIntegrationService._get_total_all_records(user_id, db)
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
        except Exception as e:
            logger.exception("处理运动记录成就时出错: %s", e)
        
        return results
    
    @staticmethod
    async def process_water_record(user_id: int, record_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理饮水记录后的成就检查和积分发放"""
        logger.info("处理饮水记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "messages": []
        }
        
        try:
            # 1. 发放饮水记录积分（如果当天饮水达标）
            is_target_met = await AchievementIntegrationService._is_water_target_met(user_id, db)
            
            if is_target_met:
                # 检查今天是否已经发放过积分
                today = date.today()
                has_earned_today = await AchievementIntegrationService._has_earned_points_today(
                    user_id, "饮水达标", db
                )
                
                if not has_earned_today:
                    points_result = await PointsService.earn_points(
                        user_id=user_id,
                        reason="饮水达标",
                        amount=5,
                        db=db,
                        description="今日饮水达到目标",
                        related_record_id=record_id,
                        related_record_type="water_record"
                    )
                    
                    if points_result["success"]:
                        results["points_earned"] += points_result["data"]["points_earned"]
                        results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 检查是否是首次记录
            total_water = await AchievementIntegrationService._get_total_water_records(user_id, db)
            if total_water == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="water_record"
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"]["points_earned"]
            
            # 3. 检查饮水连续达标成就
            await AchievementIntegrationService._check_water_streak(user_id, db, results)
            
            # 4. 检查累计记录数成就
            total_all_records = await AchievementIntegrationService._get_total_all_records(user_id, db)
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
        except Exception as e:
            logger.exception("处理饮水记录成就时出错: %s", e)
        
        return results
    
    @staticmethod
    async def process_sleep_record(user_id: int, record_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理睡眠记录后的成就检查和积分发放"""
        logger.info("处理睡眠记录成就 - 用户ID: %s, 记录ID: %s", user_id, record_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "messages": []
        }
        
        try:
            # 1. 发放睡眠记录积分
            points_result = await PointsService.earn_points(
                user_id=user_id,
                reason="记录睡眠",
                amount=5,
                db=db,
                description="成功记录睡眠数据",
                related_record_id=record_id,
                related_record_type="sleep_record"
            )
            
            if points_result["success"]:
                results["points_earned"] += points_result["data"]["points_earned"]
                results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 检查是否是首次记录
            total_sleep = await AchievementIntegrationService._get_total_sleep_records(user_id, db)
            if total_sleep == 1:
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "first_record", 1, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                
                first_record_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="首次记录",
                    amount=10,
                    db=db,
                    description="完成首次健康记录",
                    related_record_id=record_id,
                    related_record_type="sleep_record"
                )
                if first_record_points["success"]:
                    results["points_earned"] += first_record_points["data"]["points_earned"]
            
            # 3. 检查睡眠连续达标成就
            await AchievementIntegrationService._check_sleep_streak(user_id, db, results)
            
            # 4. 检查累计记录数成就
            total_all_records = await AchievementIntegrationService._get_total_all_records(user_id, db)
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "total_records", total_all_records, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
        except Exception as e:
            logger.exception("处理睡眠记录成就时出错: %s", e)
        
        return results
    
    # ============ 辅助方法 ============
    
    @staticmethod
    async def _get_total_weight_records(user_id: int, db: AsyncSession) -> int:
        """获取用户体重记录总数"""
        result = await db.execute(
            select(func.count()).where(WeightRecord.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_total_meal_records(user_id: int, db: AsyncSession) -> int:
        """获取用户餐食记录总数"""
        result = await db.execute(
            select(func.count()).where(MealRecord.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_total_exercise_records(user_id: int, db: AsyncSession) -> int:
        """获取用户运动记录总数"""
        result = await db.execute(
            select(func.count()).where(ExerciseRecord.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_total_water_records(user_id: int, db: AsyncSession) -> int:
        """获取用户饮水记录总数"""
        result = await db.execute(
            select(func.count()).where(WaterRecord.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_total_sleep_records(user_id: int, db: AsyncSession) -> int:
        """获取用户睡眠记录总数"""
        result = await db.execute(
            select(func.count()).where(SleepRecord.user_id == user_id)
        )
        return result.scalar() or 0
    
    @staticmethod
    async def _get_total_all_records(user_id: int, db: AsyncSession) -> int:
        """获取用户所有健康记录总数"""
        total = 0
        total += await AchievementIntegrationService._get_total_weight_records(user_id, db)
        total += await AchievementIntegrationService._get_total_meal_records(user_id, db)
        total += await AchievementIntegrationService._get_total_exercise_records(user_id, db)
        total += await AchievementIntegrationService._get_total_water_records(user_id, db)
        total += await AchievementIntegrationService._get_total_sleep_records(user_id, db)
        return total
    
    @staticmethod
    async def _is_water_target_met(user_id: int, db: AsyncSession) -> bool:
        """检查用户今日是否饮水达标（简化判断，默认1500ml）"""
        today = date.today()
        result = await db.execute(
            select(func.sum(WaterRecord.amount)).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == today
                )
            )
        )
        total_amount = result.scalar() or 0
        # 默认目标 1500ml
        return total_amount >= 1500
    
    @staticmethod
    async def _check_weight_goal_achievement(user_id: int, db: AsyncSession, results: Dict):
        """检查体重目标达成成就"""
        # 获取当前体重
        weight_result = await db.execute(
            select(WeightRecord).where(
                WeightRecord.user_id == user_id
            ).order_by(WeightRecord.record_time.desc()).limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()
        
        if not latest_weight:
            return
        
        # 获取活跃目标
        goal_result = await db.execute(
            select(Goal).where(
                and_(
                    Goal.user_id == user_id,
                    Goal.status == "active"
                )
            )
        )
        active_goal = goal_result.scalar_one_or_none()
        
        if not active_goal or not active_goal.target_weight:
            return
        
        # 检查是否达成目标
        if latest_weight.weight <= active_goal.target_weight:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "goal_achieved", True, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            if new_achievements:
                # 目标达成额外积分
                goal_points = await PointsService.earn_points(
                    user_id=user_id,
                    reason="达成体重目标",
                    amount=300,
                    db=db,
                    description=f"达成目标体重 {active_goal.target_weight}kg"
                )
                if goal_points["success"]:
                    results["points_earned"] += goal_points["data"]["points_earned"]
    
    @staticmethod
    async def _check_calorie_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查热量连续达标成就"""
        # 获取最近7天的餐食记录
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        
        # 简化实现：这里需要根据实际情况调整
        # 假设每日热量目标为1800kcal
        calorie_target = 1800
        streak_days = 0
        
        for i in range(7):
            check_date = end_date - timedelta(days=i)
            # 查询当天总热量
            result = await db.execute(
                select(func.sum(MealRecord.calories)).where(
                    and_(
                        MealRecord.user_id == user_id,
                        func.date(MealRecord.record_time) == check_date
                    )
                )
            )
            total_calories = result.scalar() or 0
            
            # 假设在合理范围内（1500-2100）算达标
            if 1500 <= total_calories <= 2100:
                streak_days += 1
            else:
                break
        
        if streak_days >= 7:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "calorie_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)
    
    @staticmethod
    async def _check_water_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查饮水连续达标成就"""
        end_date = date.today()
        streak_days = 0
        
        for i in range(30):  # 最多检查30天
            check_date = end_date - timedelta(days=i)
            result = await db.execute(
                select(func.sum(WaterRecord.amount)).where(
                    and_(
                        WaterRecord.user_id == user_id,
                        func.date(WaterRecord.record_time) == check_date
                    )
                )
            )
            total_amount = result.scalar() or 0
            
            if total_amount >= 1500:  # 1500ml达标
                streak_days += 1
            else:
                break
        
        if streak_days >= 30:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "water_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)
    
    @staticmethod
    async def _check_sleep_streak(user_id: int, db: AsyncSession, results: Dict):
        """检查睡眠连续达标成就"""
        end_date = date.today()
        streak_days = 0
        
        for i in range(14):  # 最多检查14天
            check_date = end_date - timedelta(days=i)
            result = await db.execute(
                select(SleepRecord).where(
                    and_(
                        SleepRecord.user_id == user_id,
                        func.date(SleepRecord.sleep_date) == check_date
                    )
                )
            )
            sleep_record = result.scalar_one_or_none()
            
            if sleep_record and sleep_record.duration:
                # 睡眠时长在7-9小时算达标
                hours = sleep_record.duration.total_seconds() / 3600
                if 7 <= hours <= 9:
                    streak_days += 1
                else:
                    break
            else:
                break
        
        if streak_days >= 14:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "sleep_streak", streak_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)
    
    @staticmethod
    async def _has_earned_points_today(user_id: int, reason: str, db: AsyncSession) -> bool:
        """检查今天是否已经获得过某类积分"""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        result = await db.execute(
            select(PointsHistory).where(
                and_(
                    PointsHistory.user_id == user_id,
                    PointsHistory.reason == reason,
                    PointsHistory.points_type == PointsType.EARN,
                    PointsHistory.created_at >= today,
                    PointsHistory.created_at < tomorrow
                )
            )
        )
        return result.scalar_one_or_none() is not None


class DailyCheckinService:
    """每日打卡服务"""
    
    @staticmethod
    async def process_daily_checkin(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理每日打卡"""
        logger.info("处理每日打卡 - 用户ID: %s", user_id)
        
        results = {
            "points_earned": 0,
            "achievements_unlocked": [],
            "streak": 0,
            "messages": []
        }
        
        try:
            # 1. 发放每日登录积分
            today = date.today()
            has_earned_login = await AchievementIntegrationService._has_earned_points_today(
                user_id, "每日登录", db
            )
            
            if not has_earned_login:
                points_result = await PointsService.earn_points(
                    user_id=user_id,
                    reason="每日登录",
                    amount=5,
                    db=db,
                    description="每日首次登录奖励"
                )
                
                if points_result["success"]:
                    results["points_earned"] += points_result["data"]["points_earned"]
                    results["messages"].append(f"获得 {points_result['data']['points_earned']} 积分")
            
            # 2. 计算连续打卡天数
            streak = await DailyCheckinService._calculate_streak(user_id, db)
            results["streak"] = streak
            
            # 3. 检查连续打卡成就
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "streak", streak, db
            )
            results["achievements_unlocked"].extend(new_achievements)
            
            # 4. 连续打卡额外积分
            if streak in [7, 30, 100]:
                streak_bonus = {7: 50, 30: 200, 100: 500}
                bonus_points = streak_bonus.get(streak, 0)
                
                # 检查今天是否已经发放过连续打卡奖励
                has_earned_streak = await AchievementIntegrationService._has_earned_points_today(
                    user_id, f"连续打卡{streak}天", db
                )
                
                if not has_earned_streak:
                    streak_points = await PointsService.earn_points(
                        user_id=user_id,
                        reason=f"连续打卡{streak}天",
                        amount=bonus_points,
                        db=db,
                        description=f"连续打卡 {streak} 天奖励"
                    )
                    if streak_points["success"]:
                        results["points_earned"] += streak_points["data"]["points_earned"]
                        results["messages"].append(f"获得连续打卡奖励 {bonus_points} 积分")
            
            # 5. 检查完美一周成就
            await DailyCheckinService._check_perfect_week(user_id, db, results)
            
            # 6. 检查早起鸟儿成就
            await DailyCheckinService._check_early_bird(user_id, db, results)
            
        except Exception as e:
            logger.exception("处理每日打卡时出错: %s", e)
        
        return results
    
    @staticmethod
    async def _calculate_streak(user_id: int, db: AsyncSession) -> int:
        """计算连续打卡天数"""
        today = date.today()
        streak = 0
        
        for i in range(365):  # 最多检查一年
            check_date = today - timedelta(days=i)
            
            # 检查当天是否有任何健康记录
            has_record = await DailyCheckinService._has_any_record_on_date(user_id, check_date, db)
            
            if has_record:
                streak += 1
            else:
                break
        
        return streak
    
    @staticmethod
    async def _has_any_record_on_date(user_id: int, check_date: date, db: AsyncSession) -> bool:
        """检查某天是否有任何健康记录"""
        # 检查体重记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WeightRecord.user_id == user_id,
                    func.date(WeightRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            return True
        
        # 检查餐食记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            return True
        
        # 检查运动记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.date(ExerciseRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            return True
        
        # 检查饮水记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            return True
        
        # 检查睡眠记录
        result = await db.execute(
            select(func.count()).where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.sleep_date) == check_date
                )
            )
        )
        if result.scalar() > 0:
            return True
        
        return False
    
    @staticmethod
    async def _check_perfect_week(user_id: int, db: AsyncSession, results: Dict):
        """检查完美一周成就（7天内每天有至少3种类型的记录）"""
        end_date = date.today()
        
        # 检查最近7天
        for week_start in range(6, -1, -1):
            week_end = end_date - timedelta(days=week_start)
            week_begin = week_end - timedelta(days=6)
            
            perfect_days = 0
            for day_offset in range(7):
                check_date = week_begin + timedelta(days=day_offset)
                
                # 统计当天记录类型数量
                record_types = await DailyCheckinService._count_record_types_on_date(user_id, check_date, db)
                if record_types >= 3:  # 至少有3种类型算完美
                    perfect_days += 1
            
            if perfect_days >= 7:  # 7天都完美
                new_achievements = await AchievementService.check_and_unlock(
                    user_id, "perfect_week", True, db
                )
                results["achievements_unlocked"].extend(new_achievements)
                break
    
    @staticmethod
    async def _count_record_types_on_date(user_id: int, check_date: date, db: AsyncSession) -> int:
        """统计某天有多少种类型的健康记录"""
        types = 0
        
        # 体重
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WeightRecord.user_id == user_id,
                    func.date(WeightRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            types += 1
        
        # 餐食
        result = await db.execute(
            select(func.count()).where(
                and_(
                    MealRecord.user_id == user_id,
                    func.date(MealRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            types += 1
        
        # 运动
        result = await db.execute(
            select(func.count()).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    func.date(ExerciseRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            types += 1
        
        # 饮水
        result = await db.execute(
            select(func.count()).where(
                and_(
                    WaterRecord.user_id == user_id,
                    func.date(WaterRecord.record_time) == check_date
                )
            )
        )
        if result.scalar() > 0:
            types += 1
        
        # 睡眠
        result = await db.execute(
            select(func.count()).where(
                and_(
                    SleepRecord.user_id == user_id,
                    func.date(SleepRecord.sleep_date) == check_date
                )
            )
        )
        if result.scalar() > 0:
            types += 1
        
        return types
    
    @staticmethod
    async def _check_early_bird(user_id: int, db: AsyncSession, results: Dict):
        """检查早起鸟儿成就（连续7天早上8点前记录）"""
        # 简化实现：检查最近7天是否有早上的记录
        # 实际实现需要记录每个记录的时间戳
        end_date = date.today()
        early_days = 0
        
        for i in range(7):
            check_date = end_date - timedelta(days=i)
            
            # 检查当天是否有早上8点前的记录
            result = await db.execute(
                select(func.count()).where(
                    and_(
                        WeightRecord.user_id == user_id,
                        func.date(WeightRecord.record_time) == check_date,
                        func.time(WeightRecord.record_time) < "08:00:00"
                    )
                )
            )
            if result.scalar() > 0:
                early_days += 1
            else:
                break
        
        if early_days >= 7:
            new_achievements = await AchievementService.check_and_unlock(
                user_id, "early_morning_streak", early_days, db
            )
            results["achievements_unlocked"].extend(new_achievements)
```

**Step 2: 提交**

```bash
git add services/integration_service.py
git commit -m "feat: add integration service for automatic achievement and points processing"
```

---

## Task 5: 修改体重记录API集成成就和积分

**Files:**
- Modify: `/Users/felix/open_workdspace/api/routes/weight.py`

**Step 1: 导入集成服务**

在文件顶部添加：
```python
from services.integration_service import AchievementIntegrationService
```

**Step 2: 修改体重记录接口**

找到体重记录POST接口，在保存记录后添加成就处理：

```python
@router.post("/record")
async def record_weight(
    data: WeightRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录体重（同一天自动覆盖）"""
    try:
        # 检查今天是否已有记录
        today = date.today()
        result = await db.execute(
            select(WeightRecord).where(
                and_(
                    WeightRecord.user_id == current_user.id,
                    func.date(WeightRecord.record_time) == today,
                )
            )
        )
        existing_record = result.scalar_one_or_none()
        
        if existing_record:
            # 更新现有记录
            existing_record.weight = data.weight
            existing_record.note = data.note
            existing_record.record_time = datetime.utcnow()
            await db.commit()
            
            record_id = existing_record.id
            is_new_record = False
        else:
            # 创建新记录
            new_record = WeightRecord(
                user_id=current_user.id,
                weight=data.weight,
                note=data.note,
            )
            db.add(new_record)
            await db.commit()
            await db.refresh(new_record)
            
            record_id = new_record.id
            is_new_record = True
        
        # 处理成就和积分
        achievement_results = await AchievementIntegrationService.process_weight_record(
            current_user.id, record_id, db
        )
        
        response_data = {
            "success": True,
            "message": "体重记录成功",
            "data": {
                "id": record_id,
                "weight": data.weight,
                "record_time": datetime.utcnow(),
                "is_new_record": is_new_record,
            }
        }
        
        # 添加成就和积分信息
        if achievement_results["points_earned"] > 0:
            response_data["data"]["points_earned"] = achievement_results["points_earned"]
        
        if achievement_results["achievements_unlocked"]:
            response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]
        
        return response_data
        
    except Exception as e:
        logger.exception("记录体重失败: %s", e)
        raise HTTPException(status_code=500, detail="记录体重失败")
```

**Step 3: 提交**

```bash
git add api/routes/weight.py
git commit -m "feat: integrate achievement and points into weight record API"
```

---

## Task 6: 修改饮食记录API集成成就和积分

**Files:**
- Modify: `/Users/felix/open_workdspace/api/routes/meal.py`

**Step 1: 导入集成服务**

在文件顶部添加：
```python
from services.integration_service import AchievementIntegrationService
```

**Step 2: 修改餐食记录接口**

找到餐食记录POST接口，在保存记录后添加成就处理：

```python
@router.post("/record")
async def record_meal(
    data: MealRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录餐食"""
    try:
        # 创建餐食记录
        new_record = MealRecord(
            user_id=current_user.id,
            meal_type=data.meal_type,
            food_name=data.food_name,
            calories=data.calories,
            portion=data.portion,
            record_time=data.record_time or datetime.utcnow(),
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
        
        # 处理成就和积分
        achievement_results = await AchievementIntegrationService.process_meal_record(
            current_user.id, new_record.id, db
        )
        
        response_data = {
            "success": True,
            "message": "餐食记录成功",
            "data": {
                "id": new_record.id,
                "meal_type": new_record.meal_type,
                "food_name": new_record.food_name,
                "calories": new_record.calories,
                "record_time": new_record.record_time,
            }
        }
        
        # 添加成就和积分信息
        if achievement_results["points_earned"] > 0:
            response_data["data"]["points_earned"] = achievement_results["points_earned"]
        
        if achievement_results["achievements_unlocked"]:
            response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]
        
        return response_data
        
    except Exception as e:
        logger.exception("记录餐食失败: %s", e)
        raise HTTPException(status_code=500, detail="记录餐食失败")
```

**Step 3: 提交**

```bash
git add api/routes/meal.py
git commit -m "feat: integrate achievement and points into meal record API"
```

---

## Task 7: 修改运动记录API集成成就和积分

**Files:**
- Modify: `/Users/felix/open_workdspace/api/routes/exercise.py`

**Step 1: 导入集成服务**

在文件顶部添加：
```python
from services.integration_service import AchievementIntegrationService
```

**Step 2: 修改运动记录接口**

```python
@router.post("/record")
async def record_exercise(
    data: ExerciseRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录运动"""
    try:
        # 创建运动记录
        new_record = ExerciseRecord(
            user_id=current_user.id,
            exercise_type=data.exercise_type,
            duration=data.duration,
            calories_burned=data.calories_burned,
            record_time=data.record_time or datetime.utcnow(),
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
        
        # 处理成就和积分
        achievement_results = await AchievementIntegrationService.process_exercise_record(
            current_user.id, new_record.id, db
        )
        
        response_data = {
            "success": True,
            "message": "运动记录成功",
            "data": {
                "id": new_record.id,
                "exercise_type": new_record.exercise_type,
                "duration": new_record.duration,
                "calories_burned": new_record.calories_burned,
                "record_time": new_record.record_time,
            }
        }
        
        # 添加成就和积分信息
        if achievement_results["points_earned"] > 0:
            response_data["data"]["points_earned"] = achievement_results["points_earned"]
        
        if achievement_results["achievements_unlocked"]:
            response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]
        
        return response_data
        
    except Exception as e:
        logger.exception("记录运动失败: %s", e)
        raise HTTPException(status_code=500, detail="记录运动失败")
```

**Step 3: 提交**

```bash
git add api/routes/exercise.py
git commit -m "feat: integrate achievement and points into exercise record API"
```

---

## Task 8: 修改饮水记录API集成成就和积分

**Files:**
- Modify: `/Users/felix/open_workdspace/api/routes/water.py`

**Step 1: 导入集成服务**

```python
from services.integration_service import AchievementIntegrationService
```

**Step 2: 修改饮水记录接口**

```python
@router.post("/record")
async def record_water(
    data: WaterRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录饮水"""
    try:
        # 创建饮水记录
        new_record = WaterRecord(
            user_id=current_user.id,
            amount=data.amount,
            record_time=data.record_time or datetime.utcnow(),
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
        
        # 处理成就和积分
        achievement_results = await AchievementIntegrationService.process_water_record(
            current_user.id, new_record.id, db
        )
        
        response_data = {
            "success": True,
            "message": "饮水记录成功",
            "data": {
                "id": new_record.id,
                "amount": new_record.amount,
                "record_time": new_record.record_time,
            }
        }
        
        # 添加成就和积分信息
        if achievement_results["points_earned"] > 0:
            response_data["data"]["points_earned"] = achievement_results["points_earned"]
        
        if achievement_results["achievements_unlocked"]:
            response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]
        
        return response_data
        
    except Exception as e:
        logger.exception("记录饮水失败: %s", e)
        raise HTTPException(status_code=500, detail="记录饮水失败")
```

**Step 3: 提交**

```bash
git add api/routes/water.py
git commit -m "feat: integrate achievement and points into water record API"
```

---

## Task 9: 修改睡眠记录API集成成就和积分

**Files:**
- Modify: `/Users/felix/open_workdspace/api/routes/sleep.py`

**Step 1: 导入集成服务**

```python
from services.integration_service import AchievementIntegrationService
```

**Step 2: 修改睡眠记录接口**

```python
@router.post("/record")
async def record_sleep(
    data: SleepRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录睡眠"""
    try:
        # 创建睡眠记录
        new_record = SleepRecord(
            user_id=current_user.id,
            sleep_date=data.sleep_date,
            bed_time=data.bed_time,
            wake_time=data.wake_time,
            quality=data.quality,
            note=data.note,
        )
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
        
        # 处理成就和积分
        achievement_results = await AchievementIntegrationService.process_sleep_record(
            current_user.id, new_record.id, db
        )
        
        response_data = {
            "success": True,
            "message": "睡眠记录成功",
            "data": {
                "id": new_record.id,
                "sleep_date": new_record.sleep_date,
                "duration": str(new_record.duration) if new_record.duration else None,
                "quality": new_record.quality,
            }
        }
        
        # 添加成就和积分信息
        if achievement_results["points_earned"] > 0:
            response_data["data"]["points_earned"] = achievement_results["points_earned"]
        
        if achievement_results["achievements_unlocked"]:
            response_data["data"]["achievements_unlocked"] = achievement_results["achievements_unlocked"]
        
        return response_data
        
    except Exception as e:
        logger.exception("记录睡眠失败: %s", e)
        raise HTTPException(status_code=500, detail="记录睡眠失败")
```

**Step 3: 提交**

```bash
git add api/routes/sleep.py
git commit -m "feat: integrate achievement and points into sleep record API"
```

---

## Task 10: 实现排行榜功能

**Files:**
- Create: `/Users/felix/open_workdspace/services/leaderboard_service.py`
- Modify: `/Users/felix/open_workdspace/api/routes/achievements.py`
- Test: `/Users/felix/open_workdspace/tests/test_leaderboard.py`

**Step 1: 创建排行榜服务**

```python
"""
排行榜服务
提供用户积分、成就、连续打卡等排行榜功能
"""

from typing import Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from models.database import User, UserProfile
from models.points_history import PointsHistory, PointsType
from services.achievement_service import ACHIEVEMENTS, AchievementService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class LeaderboardService:
    """排行榜服务"""
    
    @staticmethod
    async def get_points_leaderboard(
        db: AsyncSession, 
        period: str = "total",  # total, week, month
        limit: int = 10
    ) -> Dict[str, Any]:
        """获取积分排行榜"""
        logger.info("获取积分排行榜 - 周期: %s, 限制: %s", period, limit)
        
        try:
            if period == "total":
                # 总积分排行榜
                result = await db.execute(
                    select(
                        User.id,
                        User.username,
                        UserProfile.total_points_earned
                    )
                    .join(UserProfile, User.id == UserProfile.user_id)
                    .where(UserProfile.total_points_earned > 0)
                    .order_by(desc(UserProfile.total_points_earned))
                    .limit(limit)
                )
                
                rankings = []
                rank = 1
                for row in result:
                    rankings.append({
                        "rank": rank,
                        "user_id": row.id,
                        "username": row.username,
                        "points": row.total_points_earned
                    })
                    rank += 1
                
            elif period == "week":
                # 本周积分排行榜
                week_start = date.today() - timedelta(days=date.today().weekday())
                rankings = await LeaderboardService._get_period_points_leaderboard(
                    db, week_start, limit
                )
                
            elif period == "month":
                # 本月积分排行榜
                month_start = date.today().replace(day=1)
                rankings = await LeaderboardService._get_period_points_leaderboard(
                    db, month_start, limit
                )
            else:
                return {"success": False, "error": "无效的周期参数"}
            
            return {
                "success": True,
                "data": {
                    "period": period,
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.exception("获取积分排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}
    
    @staticmethod
    async def _get_period_points_leaderboard(
        db: AsyncSession, start_date: date, limit: int
    ) -> List[Dict]:
        """获取指定周期内的积分排行榜"""
        from sqlalchemy import text
        
        # 使用原生SQL查询积分历史
        query = """
            SELECT 
                ph.user_id,
                u.username,
                SUM(ph.amount) as period_points
            FROM points_history ph
            JOIN users u ON ph.user_id = u.id
            WHERE ph.points_type = 'earn'
            AND ph.created_at >= :start_date
            GROUP BY ph.user_id, u.username
            ORDER BY period_points DESC
            LIMIT :limit
        """
        
        result = await db.execute(
            text(query),
            {"start_date": start_date, "limit": limit}
        )
        
        rankings = []
        rank = 1
        for row in result:
            rankings.append({
                "rank": rank,
                "user_id": row.user_id,
                "username": row.username,
                "points": row.period_points
            })
            rank += 1
        
        return rankings
    
    @staticmethod
    async def get_achievement_leaderboard(
        db: AsyncSession,
        category: str = "count",  # count, rare
        limit: int = 10
    ) -> Dict[str, Any]:
        """获取成就排行榜"""
        logger.info("获取成就排行榜 - 类别: %s, 限制: %s", category, limit)
        
        try:
            # 获取所有用户的成就数据
            result = await db.execute(
                select(User.id, User.username, UserProfile.achievements)
                .join(UserProfile, User.id == UserProfile.user_id)
                .where(UserProfile.achievements != None)
            )
            
            user_achievements = []
            for row in result:
                import json
                achievements = row.achievements
                if isinstance(achievements, str):
                    achievements = json.loads(achievements)
                
                if not achievements:
                    continue
                
                achievement_count = len(achievements)
                
                # 计算稀有成就数量
                rare_count = 0
                epic_count = 0
                legendary_count = 0
                
                for ach_id in achievements:
                    if ach_id in ACHIEVEMENTS:
                        rarity = ACHIEVEMENTS[ach_id].rarity
                        if rarity == "rare":
                            rare_count += 1
                        elif rarity == "epic":
                            epic_count += 1
                        elif rarity == "legendary":
                            legendary_count += 1
                
                # 计算成就积分
                total_achievement_points = sum(
                    ACHIEVEMENTS[ach_id].points 
                    for ach_id in achievements 
                    if ach_id in ACHIEVEMENTS
                )
                
                user_achievements.append({
                    "user_id": row.id,
                    "username": row.username,
                    "achievement_count": achievement_count,
                    "rare_count": rare_count,
                    "epic_count": epic_count,
                    "legendary_count": legendary_count,
                    "total_points": total_achievement_points,
                    "score": achievement_count + rare_count * 2 + epic_count * 5 + legendary_count * 10
                })
            
            # 根据类别排序
            if category == "count":
                user_achievements.sort(key=lambda x: x["achievement_count"], reverse=True)
            elif category == "rare":
                user_achievements.sort(key=lambda x: x["score"], reverse=True)
            
            # 生成排名
            rankings = []
            for i, user in enumerate(user_achievements[:limit]):
                rankings.append({
                    "rank": i + 1,
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "achievement_count": user["achievement_count"],
                    "rare_count": user["rare_count"],
                    "epic_count": user["epic_count"],
                    "legendary_count": user["legendary_count"],
                    "total_points": user["total_points"]
                })
            
            return {
                "success": True,
                "data": {
                    "category": category,
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.exception("获取成就排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}
    
    @staticmethod
    async def get_streak_leaderboard(
        db: AsyncSession,
        limit: int = 10
    ) -> Dict[str, Any]:
        """获取连续打卡排行榜"""
        logger.info("获取连续打卡排行榜 - 限制: %s", limit)
        
        try:
            # 获取所有用户的连续打卡数据
            # 这里需要从每日打卡记录中计算
            # 简化实现：从UserProfile中获取连续打卡天数（需要添加字段）
            
            result = await db.execute(
                select(User.id, User.username)
                .join(UserProfile, User.id == UserProfile.user_id)
                .limit(100)  # 限制查询数量
            )
            
            user_streaks = []
            for row in result:
                # 计算连续打卡天数
                from services.integration_service import DailyCheckinService
                streak = await DailyCheckinService._calculate_streak(row.id, db)
                
                if streak > 0:
                    user_streaks.append({
                        "user_id": row.id,
                        "username": row.username,
                        "streak_days": streak
                    })
            
            # 按连续天数排序
            user_streaks.sort(key=lambda x: x["streak_days"], reverse=True)
            
            # 生成排名
            rankings = []
            for i, user in enumerate(user_streaks[:limit]):
                rankings.append({
                    "rank": i + 1,
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "streak_days": user["streak_days"]
                })
            
            return {
                "success": True,
                "data": {
                    "rankings": rankings,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.exception("获取连续打卡排行榜失败: %s", e)
            return {"success": False, "error": "获取排行榜失败"}
    
    @staticmethod
    async def get_user_rank(
        user_id: int,
        db: AsyncSession,
        leaderboard_type: str = "points"
    ) -> Dict[str, Any]:
        """获取用户排名"""
        logger.info("获取用户排名 - 用户ID: %s, 类型: %s", user_id, leaderboard_type)
        
        try:
            if leaderboard_type == "points":
                # 获取总积分排名
                result = await db.execute(
                    select(UserProfile.total_points_earned)
                    .where(UserProfile.user_id == user_id)
                )
                user_points = result.scalar() or 0
                
                # 计算排名
                rank_result = await db.execute(
                    select(func.count())
                    .select_from(UserProfile)
                    .where(UserProfile.total_points_earned > user_points)
                )
                rank = rank_result.scalar() + 1
                
                # 获取总人数
                total_result = await db.execute(
                    select(func.count())
                    .select_from(UserProfile)
                    .where(UserProfile.total_points_earned > 0)
                )
                total_users = total_result.scalar()
                
                return {
                    "success": True,
                    "data": {
                        "user_id": user_id,
                        "rank": rank,
                        "total_users": total_users,
                        "score": user_points,
                        "percentile": round((1 - rank / total_users) * 100, 1) if total_users > 0 else 0
                    }
                }
            
            elif leaderboard_type == "achievements":
                # 获取成就数量排名
                result = await db.execute(
                    select(UserProfile.achievements)
                    .where(UserProfile.user_id == user_id)
                )
                achievements = result.scalar()
                
                import json
                if isinstance(achievements, str):
                    achievements = json.loads(achievements)
                
                achievement_count = len(achievements) if achievements else 0
                
                # 获取所有用户的成就数量并排序
                all_result = await db.execute(
                    select(UserProfile.user_id, UserProfile.achievements)
                    .where(UserProfile.achievements != None)
                )
                
                all_counts = []
                for row in all_result:
                    ach = row.achievements
                    if isinstance(ach, str):
                        ach = json.loads(ach)
                    all_counts.append(len(ach) if ach else 0)
                
                # 计算排名
                rank = sum(1 for count in all_counts if count > achievement_count) + 1
                total_users = len(all_counts)
                
                return {
                    "success": True,
                    "data": {
                        "user_id": user_id,
                        "rank": rank,
                        "total_users": total_users,
                        "score": achievement_count,
                        "percentile": round((1 - rank / total_users) * 100, 1) if total_users > 0 else 0
                    }
                }
            
            else:
                return {"success": False, "error": "无效的排行榜类型"}
                
        except Exception as e:
            logger.exception("获取用户排名失败: %s", e)
            return {"success": False, "error": "获取排名失败"}
```

**Step 2: 修改achievements.py添加排行榜API**

在文件末尾添加排行榜路由：

```python
@router.get("/leaderboard/points")
async def get_points_leaderboard(
    period: str = "total",  # total, week, month
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取积分排行榜"""
    from services.leaderboard_service import LeaderboardService
    return await LeaderboardService.get_points_leaderboard(db, period, limit)


@router.get("/leaderboard/achievements")
async def get_achievement_leaderboard(
    category: str = "count",  # count, rare
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取成就排行榜"""
    from services.leaderboard_service import LeaderboardService
    return await LeaderboardService.get_achievement_leaderboard(db, category, limit)


@router.get("/leaderboard/streak")
async def get_streak_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """获取连续打卡排行榜"""
    from services.leaderboard_service import LeaderboardService
    return await LeaderboardService.get_streak_leaderboard(db, limit)


@router.get("/leaderboard/my-rank")
async def get_my_rank(
    type: str = "points",  # points, achievements
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的排名"""
    from services.leaderboard_service import LeaderboardService
    return await LeaderboardService.get_user_rank(current_user.id, db, type)
```

**Step 3: 提交**

```bash
git add services/leaderboard_service.py api/routes/achievements.py
git commit -m "feat: implement leaderboard functionality with points, achievement and streak rankings"
```

---

## Task 11: 创建每日汇总任务

**Files:**
- Create: `/Users/felix/open_workdspace/tasks/daily_summary.py`
- Create: `/Users/felix/open_workdspace/api/routes/tasks.py` (如果不存在)
- Modify: `/Users/felix/open_workdspace/main.py` - 注册任务路由

**Step 1: 创建每日汇总任务**

```python
"""
每日汇总任务
定时检查用户的连续打卡、完美一周等成就
"""

from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List

from models.database import User, UserProfile
from services.integration_service import DailyCheckinService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class DailySummaryTask:
    """每日汇总任务"""
    
    @staticmethod
    async def process_all_users(db: AsyncSession) -> Dict[str, Any]:
        """处理所有用户的每日汇总"""
        logger.info("开始执行每日汇总任务")
        
        try:
            # 获取所有用户
            result = await db.execute(select(User.id, User.username))
            users = result.fetchall()
            
            processed_count = 0
            total_points_issued = 0
            achievements_unlocked = []
            
            for user in users:
                try:
                    logger.debug("处理用户每日汇总: %s (%s)", user.username, user.id)
                    
                    # 执行每日打卡处理
                    result = await DailyCheckinService.process_daily_checkin(user.id, db)
                    
                    processed_count += 1
                    total_points_issued += result.get("points_earned", 0)
                    
                    if result.get("achievements_unlocked"):
                        achievements_unlocked.extend(result["achievements_unlocked"])
                    
                except Exception as e:
                    logger.exception("处理用户 %s 每日汇总时出错: %s", user.id, e)
                    continue
            
            summary = {
                "processed_users": processed_count,
                "total_points_issued": total_points_issued,
                "achievements_unlocked_count": len(achievements_unlocked),
                "completed_at": datetime.utcnow().isoformat()
            }
            
            logger.info("每日汇总任务完成: %s", summary)
            
            return {
                "success": True,
                "data": summary
            }
            
        except Exception as e:
            logger.exception("执行每日汇总任务失败: %s", e)
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def process_single_user(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理单个用户的每日汇总"""
        logger.info("处理用户 %s 的每日汇总", user_id)
        
        try:
            result = await DailyCheckinService.process_daily_checkin(user_id, db)
            
            return {
                "success": True,
                "data": result
            }
            
        except Exception as e:
            logger.exception("处理用户 %s 每日汇总失败: %s", user_id, e)
            return {
                "success": False,
                "error": str(e)
            }
```

**Step 2: 创建任务API路由**

```python
"""
任务管理路由
用于手动触发定时任务
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from models.database import get_db, User
from api.dependencies import get_current_user
from tasks.daily_summary import DailySummaryTask
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.post("/daily-summary")
async def run_daily_summary(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动触发每日汇总任务（仅当前用户）"""
    logger.info("用户 %s 手动触发每日汇总", current_user.id)
    
    try:
        result = await DailySummaryTask.process_single_user(current_user.id, db)
        
        if result["success"]:
            return {
                "success": True,
                "message": "每日汇总处理完成",
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))
            
    except Exception as e:
        logger.exception("每日汇总任务失败: %s", e)
        raise HTTPException(status_code=500, detail="处理失败")


@router.post("/daily-summary/all")
async def run_daily_summary_all(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发所有用户的每日汇总任务
    注意：这应该是管理员功能，需要添加权限检查
    """
    # TODO: 添加管理员权限检查
    logger.info("管理员手动触发全量每日汇总")
    
    try:
        result = await DailySummaryTask.process_all_users(db)
        
        if result["success"]:
            return {
                "success": True,
                "message": "全量每日汇总处理完成",
                "data": result["data"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))
            
    except Exception as e:
        logger.exception("全量每日汇总任务失败: %s", e)
        raise HTTPException(status_code=500, detail="处理失败")
```

**Step 3: 注册任务路由**

在main.py中添加：
```python
from api.routes import tasks

# ... 其他路由注册
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"])
```

**Step 4: 提交**

```bash
git add tasks/daily_summary.py api/routes/tasks.py main.py
git commit -m "feat: add daily summary task for automated achievement checking"
```

---

## Task 12: 运行测试验证

**Step 1: 运行单元测试**

```bash
# 运行所有相关测试
pytest tests/test_achievement_service.py tests/test_points_service.py tests/test_integration_service.py tests/test_leaderboard.py -v
```

**Step 2: 验证API接口**

```bash
# 启动服务并测试
uvicorn main:app --reload

# 测试端点
curl -X POST http://localhost:8000/api/weight/record \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"weight": 70.5}'
```

**Step 3: 验证数据库迁移**

确保PointsHistory表已创建：
```sql
SELECT * FROM points_history LIMIT 5;
```

**Step 4: 提交**

```bash
git commit -m "test: verify achievement and points integration works correctly"
```

---

## 实施检查清单

- [ ] Task 1: 创建积分历史表模型
- [ ] Task 2: 修改成就服务 - 添加缺失成就
- [ ] Task 3: 修改积分服务 - 实现历史记录功能
- [ ] Task 4: 创建业务集成服务
- [ ] Task 5: 修改体重记录API集成
- [ ] Task 6: 修改饮食记录API集成
- [ ] Task 7: 修改运动记录API集成
- [ ] Task 8: 修改饮水记录API集成
- [ ] Task 9: 修改睡眠记录API集成
- [ ] Task 10: 实现排行榜功能
- [ ] Task 11: 创建每日汇总任务
- [ ] Task 12: 运行测试验证

---

## 注意事项

1. **数据库迁移**：创建PointsHistory表后需要运行Alembic迁移
2. **性能考虑**：排行榜查询可能需要优化（添加索引）
3. **并发处理**：成就检查和积分发放需要考虑并发情况
4. **错误处理**：所有集成点都有try-except包裹，确保不影响主流程
5. **日志记录**：所有关键操作都有日志记录，便于调试
