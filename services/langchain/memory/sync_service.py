"""
打卡同步服务
将数据库中的打卡记录同步到LangChain记忆系统
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import threading
import asyncio

from sqlalchemy import select, desc
from models.database import (
    get_db,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    ChatHistory,
)
from .manager import MemoryManager, HumanMessage, AIMessage
from .typed_buffer import MemoryType


class CheckinSyncService:
    """
    打卡同步服务
    负责将数据库中的打卡记录同步到LangChain记忆系统
    """

    _semaphore: Optional[asyncio.Semaphore] = None

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self._sync_lock = threading.Lock()
        self._last_sync_time: Dict[int, datetime] = {}
        self._sync_interval = timedelta(minutes=5)

    def _get_semaphore(self) -> asyncio.Semaphore:
        if CheckinSyncService._semaphore is None:
            CheckinSyncService._semaphore = asyncio.Semaphore(self.max_workers)
        return CheckinSyncService._semaphore

    async def sync_user_checkins(
        self, user_id: int, force: bool = False
    ) -> Dict[str, Any]:
        """
        同步用户的打卡记录

        Args:
            user_id: 用户ID
            force: 是否强制同步（忽略时间间隔）

        Returns:
            同步结果统计
        """
        # 检查是否需要同步
        if not force:
            last_sync = self._last_sync_time.get(user_id)
            if last_sync and datetime.now() - last_sync < self._sync_interval:
                return {
                    "user_id": user_id,
                    "status": "skipped",
                    "reason": "最近已同步",
                    "last_sync": last_sync.isoformat(),
                }

        # 获取记忆管理器
        memory_manager = MemoryManager(user_id)

        results = {
            "user_id": user_id,
            "status": "success",
            "sync_time": datetime.now().isoformat(),
            "weight_records": 0,
            "meal_records": 0,
            "exercise_records": 0,
            "water_records": 0,
            "sleep_records": 0,
            "chat_history": 0,
            "errors": [],
        }

        async with self._get_semaphore():
            try:
                # 获取数据库会话
                async for db in get_db():
                    # 同步体重记录
                    weight_stmt = (
                        select(WeightRecord)
                        .where(WeightRecord.user_id == user_id)
                        .order_by(desc(WeightRecord.record_time))
                        .limit(100)
                    )
                weight_result = await db.execute(weight_stmt)
                weight_records = weight_result.scalars().all()

                for record in weight_records:
                    try:
                        content = f"【体重打卡】记录了体重：{record.weight}公斤"
                        metadata = {
                            "checkin_type": "weight",
                            "record_id": record.id,
                            "weight": record.weight,
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "weight", content, metadata
                        )
                        results["weight_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"体重记录 {record.id}: {str(e)}")

                # 同步餐食记录
                meal_stmt = (
                    select(MealRecord)
                    .where(MealRecord.user_id == user_id)
                    .order_by(desc(MealRecord.record_time))
                    .limit(100)
                )
                meal_result = await db.execute(meal_stmt)
                meal_records = meal_result.scalars().all()

                for record in meal_records:
                    try:
                        food_items = record.food_items or []
                        food_names = [item.get("name", "未知") for item in food_items]
                        content = f"【餐食打卡】吃了：{', '.join(food_names)}，总热量：{record.total_calories}千卡"
                        metadata = {
                            "checkin_type": "meal",
                            "record_id": record.id,
                            "total_calories": record.total_calories,
                            "food_count": len(food_items),
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "meal", content, metadata
                        )
                        results["meal_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"餐食记录 {record.id}: {str(e)}")

                # 同步运动记录
                exercise_stmt = (
                    select(ExerciseRecord)
                    .where(ExerciseRecord.user_id == user_id)
                    .order_by(desc(ExerciseRecord.record_time))
                    .limit(100)
                )
                exercise_result = await db.execute(exercise_stmt)
                exercise_records = exercise_result.scalars().all()

                for record in exercise_records:
                    try:
                        content = f"【运动打卡】{record.exercise_type}运动{record.duration_minutes}分钟，消耗{record.calories_burned}千卡"
                        metadata = {
                            "checkin_type": "exercise",
                            "record_id": record.id,
                            "exercise_type": record.exercise_type,
                            "duration": record.duration_minutes,
                            "calories_burned": record.calories_burned,
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "exercise", content, metadata
                        )
                        results["exercise_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"运动记录 {record.id}: {str(e)}")

                # 同步饮水记录
                water_stmt = (
                    select(WaterRecord)
                    .where(WaterRecord.user_id == user_id)
                    .order_by(desc(WaterRecord.record_time))
                    .limit(100)
                )
                water_result = await db.execute(water_stmt)
                water_records = water_result.scalars().all()

                for record in water_records:
                    try:
                        content = f"【饮水打卡】喝了{record.amount_ml}毫升水"
                        metadata = {
                            "checkin_type": "water",
                            "record_id": record.id,
                            "amount": record.amount_ml,
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "water", content, metadata
                        )
                        results["water_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"饮水记录 {record.id}: {str(e)}")

                # 同步睡眠记录
                sleep_stmt = (
                    select(SleepRecord)
                    .where(SleepRecord.user_id == user_id)
                    .order_by(desc(SleepRecord.record_time))
                    .limit(100)
                )
                sleep_result = await db.execute(sleep_stmt)
                sleep_records = sleep_result.scalars().all()

                for record in sleep_records:
                    try:
                        total_hours = (
                            record.total_minutes / 60 if record.total_minutes else 0
                        )
                        content = f"【睡眠打卡】睡了{total_hours:.1f}小时，质量：{record.quality or '未知'}/10"
                        metadata = {
                            "checkin_type": "sleep",
                            "record_id": record.id,
                            "duration": record.total_minutes,
                            "quality": record.quality,
                            "bed_time": record.bed_time.isoformat()
                            if record.bed_time
                            else None,
                            "wake_time": record.wake_time.isoformat()
                            if record.wake_time
                            else None,
                            "record_time": record.bed_time.isoformat()
                            if record.bed_time
                            else record.created_at.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "sleep", content, metadata
                        )
                        results["sleep_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"睡眠记录 {record.id}: {str(e)}")

                # 同步对话历史
                chat_stmt = (
                    select(ChatHistory)
                    .where(ChatHistory.user_id == user_id)
                    .order_by(desc(ChatHistory.created_at))
                    .limit(200)
                )
                chat_result = await db.execute(chat_stmt)
                chat_history = chat_result.scalars().all()

                for chat in chat_history:
                    try:
                        # 简化实现，不使用LangChain消息类
                        content = chat.content
                        metadata = {
                            "chat_id": chat.id,
                            "role": chat.role.value
                            if hasattr(chat.role, "value")
                            else str(chat.role),
                            "created_at": chat.created_at.isoformat(),
                        }

                        # 根据角色创建消息对象
                        if chat.role == "USER" or chat.role == "user":
                            message_obj = HumanMessage(content=content)
                        else:
                            message_obj = AIMessage(content=content)

                        await memory_manager.add_message(
                            message=message_obj,
                            memory_type=MemoryType.CONVERSATION,
                            metadata=metadata,
                            sync_to_long_term=True,
                        )
                        results["chat_history"] += 1
                    except Exception as e:
                        results["errors"].append(f"对话历史 {chat.id}: {str(e)}")

                        break  # 只取第一个会话

            except Exception as e:
                results["status"] = "error"
                results["error"] = str(e)

        # 更新最后同步时间
        with self._sync_lock:
            self._last_sync_time[user_id] = datetime.now()

        return results

    async def sync_recent_checkins(
        self, user_id: int, hours: int = 24
    ) -> Dict[str, Any]:
        """
        同步最近指定小时内的打卡记录

        Args:
            user_id: 用户ID
            hours: 小时数

        Returns:
            同步结果统计
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        memory_manager = MemoryManager(user_id)

        results = {
            "user_id": user_id,
            "status": "success",
            "cutoff_time": cutoff_time.isoformat(),
            "synced_records": 0,
            "errors": [],
        }

        try:
            # 获取数据库会话
            async for db in get_db():
                # 同步最近体重记录
                weight_stmt = select(WeightRecord).where(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_time >= cutoff_time,
                )
                weight_result = await db.execute(weight_stmt)
                weight_records = weight_result.scalars().all()

                for record in weight_records:
                    try:
                        content = f"【体重打卡】记录了体重：{record.weight}公斤"
                        metadata = {
                            "checkin_type": "weight",
                            "record_id": record.id,
                            "weight": record.weight,
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "weight", content, metadata
                        )
                        results["synced_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"体重记录 {record.id}: {str(e)}")

                # 同步最近餐食记录
                meal_stmt = select(MealRecord).where(
                    MealRecord.user_id == user_id,
                    MealRecord.record_time >= cutoff_time,
                )
                meal_result = await db.execute(meal_stmt)
                meal_records = meal_result.scalars().all()

                for record in meal_records:
                    try:
                        food_items = record.food_items or []
                        food_names = [item.get("name", "未知") for item in food_items]
                        content = f"【餐食打卡】吃了：{', '.join(food_names)}，总热量：{record.total_calories}千卡"
                        metadata = {
                            "checkin_type": "meal",
                            "record_id": record.id,
                            "total_calories": record.total_calories,
                            "food_count": len(food_items),
                            "record_time": record.record_time.isoformat(),
                        }
                        await memory_manager.add_checkin_record(
                            "meal", content, metadata
                        )
                        results["synced_records"] += 1
                    except Exception as e:
                        results["errors"].append(f"餐食记录 {record.id}: {str(e)}")

                break  # 只取第一个会话

        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)

        return results

    async def sync_multiple_users(
        self, user_ids: List[int], force: bool = False
    ) -> Dict[int, Dict[str, Any]]:
        """
        同步多个用户的打卡记录

        Args:
            user_ids: 用户ID列表
            force: 是否强制同步

        Returns:
            用户ID -> 同步结果的映射
        """
        results = {}

        # 使用asyncio并发执行
        tasks = []
        for user_id in user_ids:
            task = asyncio.create_task(self.sync_user_checkins(user_id, force))
            tasks.append((user_id, task))

        # 收集结果
        for user_id, task in tasks:
            try:
                result = await task
                results[user_id] = result
            except Exception as e:
                results[user_id] = {
                    "user_id": user_id,
                    "status": "error",
                    "error": str(e),
                }

        return results

    def get_sync_status(self, user_id: int) -> Dict[str, Any]:
        """
        获取同步状态

        Args:
            user_id: 用户ID

        Returns:
            同步状态信息
        """
        last_sync = self._last_sync_time.get(user_id)

        return {
            "user_id": user_id,
            "last_sync_time": last_sync.isoformat() if last_sync else None,
            "needs_sync": self._needs_sync(user_id),
            "sync_interval_seconds": self._sync_interval.total_seconds(),
        }

    def _needs_sync(self, user_id: int) -> bool:
        """
        检查是否需要同步

        Args:
            user_id: 用户ID

        Returns:
            是否需要同步
        """
        last_sync = self._last_sync_time.get(user_id)
        if not last_sync:
            return True

        return datetime.now() - last_sync >= self._sync_interval

    def clear_sync_cache(self, user_id: Optional[int] = None) -> int:
        """
        清理同步缓存

        Args:
            user_id: 用户ID，如果为None则清理所有

        Returns:
            清理的用户数量
        """
        with self._sync_lock:
            if user_id is None:
                count = len(self._last_sync_time)
                self._last_sync_time.clear()
                return count
            else:
                if user_id in self._last_sync_time:
                    del self._last_sync_time[user_id]
                    return 1
                return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取同步服务统计信息

        Returns:
            统计信息
        """
        return {
            "max_workers": self.max_workers,
            "sync_interval_seconds": self._sync_interval.total_seconds(),
            "total_users_synced": len(self._last_sync_time),
            "last_sync_times": {
                user_id: time.isoformat()
                for user_id, time in list(self._last_sync_time.items())[
                    :10
                ]  # 只显示前10个
            },
        }
