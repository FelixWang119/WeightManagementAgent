"""
记忆管理器
统一管理短期记忆和长期记忆，提供高层API
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .typed_buffer import (
    TypedConversationBufferMemory,
    MemoryType,
    BaseMessage,
    HumanMessage,
    AIMessage,
)
from .vector_memory import EnhancedVectorStoreRetrieverMemory
from utils.performance import monitor_critical_path

# 数据库相关导入（可选）
try:
    from sqlalchemy import select, desc
    from sqlalchemy.ext.asyncio import AsyncSession
    from models.database import AsyncSessionLocal, MealRecord, ExerciseRecord

    HAS_ASYNC_DB = True
except ImportError:
    HAS_ASYNC_DB = False


class MemoryManager:
    """
    记忆管理器
    统一管理短期记忆（缓冲）和长期记忆（向量存储）
    """

    def __init__(self, user_id: int):
        """
        初始化记忆管理器

        Args:
            user_id: 用户ID
        """
        self.user_id = user_id

        # 添加调试日志
        import logging

        self.logger = logging.getLogger(f"memory.{user_id}")
        self.logger.info(f"初始化MemoryManager，用户ID: {user_id}")

        # 初始化短期记忆
        self.short_term_memory = TypedConversationBufferMemory(
            checkin_capacity=30,  # 30条打卡记录
            conversation_capacity=200,  # 200条对话记录
        )

        # 从数据库加载最近的打卡记录到短期记忆（后台异步加载，不阻塞事件循环）
        self._start_background_checkins_load()

        # 记录短期记忆状态（初始为空，后台加载后会更新）
        self.logger.info(
            f"短期记忆初始化完成 - 打卡记录: {len(self.short_term_memory.checkin_messages)}条, 对话记录: {len(self.short_term_memory.conversation_messages)}条"
        )

        # 初始化长期记忆
        self.long_term_memory = EnhancedVectorStoreRetrieverMemory(user_id=user_id)
        self.logger.info("长期记忆初始化完成")

    def _start_background_checkins_load(self):
        """启动后台异步加载打卡记录"""
        try:
            import asyncio

            # 检查是否在事件循环中
            loop = asyncio.get_event_loop()
            # 创建后台任务，不等待完成
            task = asyncio.create_task(self._load_recent_checkins_async())
            # 可选：存储任务引用以防止垃圾回收
            self._load_task = task
        except RuntimeError:
            # 没有事件循环，同步执行（回退）
            self.logger.warning("没有事件循环，同步加载打卡记录")
            self._load_recent_checkins_sync()

    async def _load_recent_checkins_async(self):
        """异步加载打卡记录（优先使用异步数据库查询，失败时回退到同步版本）"""
        try:
            if HAS_ASYNC_DB:
                await self._load_recent_checkins_from_db_async()
            else:
                import asyncio

                await asyncio.to_thread(self._load_recent_checkins_sync)
            self.logger.info("后台打卡记录加载完成")
        except Exception as e:
            self.logger.error(f"后台加载打卡记录失败: {e}")

    async def _load_recent_checkins_from_db_async(self):
        """使用SQLAlchemy异步查询加载打卡记录"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)

            async with AsyncSessionLocal() as session:
                # 查询最近24小时的餐食记录
                meal_stmt = (
                    select(MealRecord)
                    .where(
                        MealRecord.user_id == self.user_id,
                        MealRecord.record_time >= cutoff_time,
                    )
                    .order_by(desc(MealRecord.record_time))
                    .limit(10)
                )
                meal_result = await session.execute(meal_stmt)
                meal_records = meal_result.scalars().all()

                # 查询最近24小时的运动记录
                exercise_stmt = (
                    select(ExerciseRecord)
                    .where(
                        ExerciseRecord.user_id == self.user_id,
                        ExerciseRecord.record_time >= cutoff_time,
                    )
                    .order_by(desc(ExerciseRecord.record_time))
                    .limit(10)
                )
                exercise_result = await session.execute(exercise_stmt)
                exercise_records = exercise_result.scalars().all()

                # 处理餐食记录
                for record in meal_records:
                    try:
                        food_items = record.food_items or []
                        if isinstance(food_items, str):
                            import json

                            food_items = json.loads(food_items) if food_items else []

                        food_names = [item.get("name", "未知") for item in food_items]
                        content = f"【{record.meal_type}打卡】吃了：{', '.join(food_names)}，总热量：{record.total_calories}千卡"

                        self.short_term_memory.add_message(
                            message=HumanMessage(content=content),
                            memory_type=MemoryType.CHECKIN,
                        )
                    except Exception as e:
                        self.logger.warning(f"解析餐食记录失败: {e}")

                # 处理运动记录
                for record in exercise_records:
                    intensity_name = {
                        "low": "低强度",
                        "medium": "中等强度",
                        "high": "高强度",
                    }.get(record.intensity, record.intensity)
                    content = f"【运动打卡】{record.exercise_type} {record.duration_minutes}分钟（{intensity_name}），消耗{record.calories_burned}卡路里"

                    self.short_term_memory.add_message(
                        message=HumanMessage(content=content),
                        memory_type=MemoryType.CHECKIN,
                    )

                self.logger.info(
                    f"通过异步查询加载了 {len(meal_records)} 条餐食记录和 {len(exercise_records)} 条运动记录到短期记忆"
                )

        except Exception as e:
            self.logger.error(f"异步数据库查询失败: {e}")
            # 抛出异常，让上层决定是否回退
            raise

    def _load_recent_checkins_sync(self):
        """从数据库加载最近的打卡记录到短期记忆（同步版本，在后台线程中运行）"""
        try:
            import sqlite3
            import json
            from datetime import datetime, timedelta
            from config.settings import fastapi_settings
            import re

            # 从DATABASE_URL提取SQLite文件路径
            # 支持格式：sqlite+aiosqlite:///./weight_management.db
            # 或 sqlite:///./weight_management.db
            db_url = fastapi_settings.DATABASE_URL
            match = re.search(r"sqlite(?:\+aiosqlite)?:///\./([\w\.]+)", db_url)
            if match:
                db_file = match.group(1)
            else:
                # 默认回退
                db_file = "weight_management.db"

            # 直接使用SQLite连接
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            # 计算24小时前的时间
            cutoff_time = (datetime.now() - timedelta(hours=24)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # 查询最近24小时的餐食记录
            cursor.execute(
                """
                SELECT meal_type, food_items, total_calories, record_time 
                FROM meal_records 
                WHERE user_id = ? AND record_time >= ?
                ORDER BY record_time DESC 
                LIMIT 10
            """,
                (self.user_id, cutoff_time),
            )

            meal_records = cursor.fetchall()

            for record in meal_records:
                meal_type, food_items_json, total_calories, record_time = record

                # 解析食物项目
                try:
                    food_items = json.loads(food_items_json) if food_items_json else []
                    food_names = [item.get("name", "未知") for item in food_items]
                    content = f"【{meal_type}打卡】吃了：{', '.join(food_names)}，总热量：{total_calories}千卡"

                    from .typed_buffer import HumanMessage

                    self.short_term_memory.add_message(
                        message=HumanMessage(content=content),
                        memory_type=MemoryType.CHECKIN,
                    )
                except Exception as e:
                    print(f"解析餐食记录失败: {e}")

            # 查询最近24小时的运动记录
            cursor.execute(
                """
                SELECT exercise_type, duration_minutes, calories_burned, intensity, record_time 
                FROM exercise_records 
                WHERE user_id = ? AND record_time >= ?
                ORDER BY record_time DESC 
                LIMIT 10
            """,
                (self.user_id, cutoff_time),
            )

            exercise_records = cursor.fetchall()

            for record in exercise_records:
                (
                    exercise_type,
                    duration_minutes,
                    calories_burned,
                    intensity,
                    record_time,
                ) = record

                # 构建运动记录内容
                intensity_name = {
                    "low": "低强度",
                    "medium": "中等强度",
                    "high": "高强度",
                }.get(intensity, intensity)
                content = f"【运动打卡】{exercise_type} {duration_minutes}分钟（{intensity_name}），消耗{calories_burned}卡路里"

                from .typed_buffer import HumanMessage

                self.short_term_memory.add_message(
                    message=HumanMessage(content=content),
                    memory_type=MemoryType.CHECKIN,
                )

            conn.close()
            self.logger.info(
                f"从数据库加载了 {len(meal_records)} 条餐食记录和 {len(exercise_records)} 条运动记录到短期记忆"
            )

        except Exception as e:
            self.logger.error(f"加载打卡记录到短期记忆失败: {e}")
            # 不抛出异常，继续使用空记忆

        # 缓存用户画像
        self.user_profile_cache: Optional[Dict[str, Any]] = None
        self.profile_cache_time: Optional[datetime] = None
        self.profile_cache_ttl = timedelta(minutes=30)  # 30分钟缓存

    @monitor_critical_path("memory_manager.add_message")
    async def add_message(
        self,
        message: BaseMessage,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        metadata: Optional[Dict[str, Any]] = None,
        sync_to_long_term: bool = True,
    ) -> Dict[str, Any]:
        """
        添加消息到记忆系统

        Args:
            message: 消息对象
            memory_type: 记忆类型
            metadata: 附加元数据
            sync_to_long_term: 是否同步到长期记忆

        Returns:
            操作结果
        """
        # 添加调试日志
        self.logger.info(
            f"添加消息到记忆系统 - 类型: {memory_type.value}, 内容长度: {len(message.content)}"
        )

        result = {
            "short_term_added": False,
            "long_term_added": False,
            "short_term_id": None,
            "long_term_id": None,
        }

        # 添加到短期记忆
        try:
            self.short_term_memory.add_message(message, memory_type)
            result["short_term_added"] = True
            self.logger.info(
                f"短期记忆添加成功 - 当前打卡记录数: {len(self.short_term_memory.checkin_messages)}"
            )
        except Exception as e:
            self.logger.error(f"短期记忆添加失败: {e}")
            result["short_term_error"] = str(e)

        # 如果需要，同步到长期记忆
        if sync_to_long_term:
            try:
                long_term_id = await self.long_term_memory.add_message(
                    message, memory_type, metadata
                )
                result["long_term_added"] = True
                result["long_term_id"] = long_term_id
                self.logger.info("长期记忆添加成功")
            except Exception as e:
                # 记录错误但不中断流程
                result["long_term_error"] = str(e)
                self.logger.warning(f"长期记忆添加失败: {e}")

        return result

    async def add_checkin_record(
        self, checkin_type: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加打卡记录

        Args:
            checkin_type: 打卡类型（weight/meal/exercise/water/sleep）
            content: 打卡内容
            metadata: 附加元数据

        Returns:
            操作结果
        """
        # 添加调试日志
        self.logger.info(
            f"添加打卡记录 - 类型: {checkin_type}, 内容: {content[:50]}..."
        )

        # 创建消息
        message = HumanMessage(content=content)

        # 构建元数据
        checkin_metadata = {
            "checkin_type": checkin_type,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            checkin_metadata.update(metadata)

        # 添加到记忆系统
        result = await self.add_message(
            message=message,
            memory_type=MemoryType.CHECKIN,
            metadata=checkin_metadata,
            sync_to_long_term=True,
        )

        # 记录添加结果
        self.logger.info(
            f"打卡记录添加完成 - 短期记忆: {result.get('short_term_added', False)}, 长期记忆: {result.get('long_term_added', False)}"
        )
        if result.get("long_term_error"):
            self.logger.warning(f"长期记忆添加失败: {result.get('long_term_error')}")

        return result

    @monitor_critical_path("memory_manager.get_context")
    def get_context(
        self,
        checkin_limit: int = 10,
        conversation_limit: int = 10,
        include_long_term: bool = True,
        query: Optional[str] = None,
    ) -> str:
        """
        获取组合上下文

        Args:
            checkin_limit: 打卡记录限制
            conversation_limit: 对话记录限制
            include_long_term: 是否包含长期记忆
            query: 查询文本（用于检索长期记忆）

        Returns:
            组合上下文文本
        """
        # 添加调试日志
        self.logger.info(
            f"获取上下文 - 打卡限制: {checkin_limit}, 对话限制: {conversation_limit}, 查询: {query}"
        )

        context_parts = []

        # 1. 获取短期记忆上下文
        short_term_context = self.short_term_memory.get_combined_context(
            checkin_limit=checkin_limit, conversation_limit=conversation_limit
        )
        if short_term_context:
            context_parts.append(short_term_context)
            self.logger.info(f"短期记忆上下文长度: {len(short_term_context)}字符")

        # 2. 获取长期记忆上下文（如果启用）
        if include_long_term and query:
            try:
                long_term_memories = self.long_term_memory.get_relevant_memories(
                    query, memory_type=MemoryType.CONVERSATION
                )
                if long_term_memories:
                    context_parts.append("\n=== 相关历史对话 ===")
                    for i, memory in enumerate(long_term_memories, 1):
                        context_parts.append(f"{i}. {memory}")

                # 获取相关打卡记录
                checkin_memories = self.long_term_memory.get_relevant_memories(
                    query, memory_type=MemoryType.CHECKIN
                )
                if checkin_memories:
                    context_parts.append("\n=== 相关打卡记录 ===")
                    for i, memory in enumerate(checkin_memories, 1):
                        context_parts.append(f"{i}. {memory}")
            except Exception as e:
                # 长期记忆检索失败不影响主流程
                context_parts.append(f"\n[长期记忆检索失败: {str(e)}]")

        # 3. 获取用户画像
        user_profile = self.get_user_profile()
        if user_profile:
            context_parts.append("\n=== 用户画像 ===")
            for key, value in user_profile.items():
                if value:  # 只显示非空值
                    context_parts.append(f"{key}: {value}")

        return "\n".join(context_parts)

    def get_user_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取用户画像

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            用户画像字典
        """
        # 检查缓存
        if not force_refresh and self.user_profile_cache and self.profile_cache_time:
            if datetime.now() - self.profile_cache_time < self.profile_cache_ttl:
                return self.user_profile_cache.copy()

        # 从数据库获取用户画像（同步版本）
        try:
            import sqlite3
            from config.settings import fastapi_settings
            import re

            # 从DATABASE_URL提取SQLite文件路径
            db_url = fastapi_settings.DATABASE_URL
            match = re.search(r"sqlite(?:\+aiosqlite)?:///\./([\w\.]+)", db_url)
            if match:
                db_file = match.group(1)
            else:
                db_file = "weight_management.db"

            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            # 查询用户画像
            cursor.execute(
                """
                SELECT nickname, age, gender, height, bmr, diet_preferences, exercise_habits
                FROM user_profiles 
                WHERE user_id = ?
                """,
                (self.user_id,),
            )

            profile = cursor.fetchone()
            conn.close()

            if profile:
                (
                    nickname,
                    age,
                    gender,
                    height,
                    bmr,
                    diet_preferences,
                    exercise_habits,
                ) = profile
                user_profile = {
                    "昵称": nickname or "未设置",
                    "年龄": age or "未设置",
                    "性别": gender or "未设置",
                    "身高": f"{height}厘米" if height else "未设置",
                    "基础代谢率": f"{bmr}千卡/天" if bmr else "未设置",
                    "饮食偏好": str(diet_preferences) if diet_preferences else "无",
                    "运动习惯": str(exercise_habits) if exercise_habits else "无",
                }
            else:
                user_profile = {"状态": "未设置用户画像"}

        except Exception as e:
            # 数据库查询失败
            self.logger.error(f"获取用户画像失败: {e}")
            user_profile = {"状态": f"获取用户画像失败: {str(e)}"}

        # 更新缓存
        self.user_profile_cache = user_profile
        self.profile_cache_time = datetime.now()

        return user_profile.copy()

    def search_memories(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
        include_short_term: bool = True,
        include_long_term: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            memory_type: 记忆类型过滤
            limit: 返回结果数量
            include_short_term: 是否包含短期记忆
            include_long_term: 是否包含长期记忆

        Returns:
            搜索结果字典
        """
        results = {"short_term": [], "long_term": []}

        # 搜索短期记忆
        if include_short_term:
            if memory_type == MemoryType.CHECKIN or memory_type is None:
                checkins = self.short_term_memory.get_recent_checkins(limit)
                for checkin in checkins:
                    results["short_term"].append(
                        {
                            "type": "checkin",
                            "content": checkin["content"],
                            "timestamp": checkin["timestamp"],
                            "source": "short_term",
                        }
                    )

            if memory_type == MemoryType.CONVERSATION or memory_type is None:
                conversations = self.short_term_memory.get_recent_conversations(limit)
                for conv in conversations:
                    results["short_term"].append(
                        {
                            "type": "conversation",
                            "content": conv["content"],
                            "timestamp": conv["timestamp"],
                            "role": conv["role"],
                            "source": "short_term",
                        }
                    )

        # 搜索长期记忆
        if include_long_term:
            try:
                long_term_results = self.long_term_memory.search_memories(
                    query=query, memory_type=memory_type, limit=limit
                )
                for result in long_term_results:
                    results["long_term"].append(
                        {
                            "type": result["metadata"].get("type", "unknown"),
                            "content": result["content"],
                            "timestamp": result["metadata"].get("timestamp"),
                            "metadata": result["metadata"],
                            "distance": result["distance"],
                            "source": "long_term",
                        }
                    )
            except Exception as e:
                results["long_term_error"] = str(e)

        return results

    def get_checkin_history(
        self,
        checkin_type: Optional[str] = None,
        limit: int = 20,
        include_short_term: bool = True,
        include_long_term: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取打卡历史

        Args:
            checkin_type: 打卡类型过滤
            limit: 返回数量
            include_short_term: 是否包含短期记忆
            include_long_term: 是否包含长期记忆

        Returns:
            打卡记录列表
        """
        all_checkins = []

        # 获取短期记忆中的打卡记录
        if include_short_term:
            short_term_checkins = self.short_term_memory.get_recent_checkins(limit)
            for checkin in short_term_checkins:
                all_checkins.append(
                    {
                        "content": checkin["content"],
                        "timestamp": checkin["timestamp"],
                        "source": "short_term",
                        "type": "checkin",
                    }
                )

        # 获取长期记忆中的打卡记录
        if include_long_term:
            try:
                long_term_checkins = self.long_term_memory.get_checkin_history(
                    checkin_type=checkin_type, limit=limit
                )
                for checkin in long_term_checkins:
                    all_checkins.append(
                        {
                            "content": checkin["content"],
                            "timestamp": checkin["timestamp"],
                            "source": "long_term",
                            "type": checkin["type"],
                            "metadata": checkin["metadata"],
                        }
                    )
            except Exception as e:
                # 记录错误但不中断流程
                all_checkins.append(
                    {
                        "content": f"[获取长期打卡记录失败: {str(e)}]",
                        "timestamp": datetime.now().isoformat(),
                        "source": "error",
                        "type": "error",
                    }
                )

        # 按时间排序（最新的在前）
        all_checkins.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # 限制返回数量
        return all_checkins[:limit]

    def clear_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        clear_short_term: bool = True,
        clear_long_term: bool = False,
    ) -> Dict[str, int]:
        """
        清理记忆

        Args:
            memory_type: 记忆类型，如果为None则清理所有
            clear_short_term: 是否清理短期记忆
            clear_long_term: 是否清理长期记忆

        Returns:
            清理结果统计
        """
        result = {"short_term_cleared": 0, "long_term_cleared": 0}

        # 清理短期记忆
        if clear_short_term:
            if memory_type:
                self.short_term_memory.clear_memory_by_type(memory_type)
                stats = self.short_term_memory.get_stats()
                if memory_type == MemoryType.CHECKIN:
                    result["short_term_cleared"] = stats["checkin_count"]
                else:
                    result["short_term_cleared"] = stats["conversation_count"]
            else:
                # 清理所有短期记忆
                self.short_term_memory.clear()
                stats = self.short_term_memory.get_stats()
                result["short_term_cleared"] = stats["total_count"]

        # 清理长期记忆
        if clear_long_term:
            try:
                cleared = self.long_term_memory.clear_memories(memory_type)
                result["long_term_cleared"] = cleared
            except Exception as e:
                result["long_term_error"] = str(e)

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆系统统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "user_id": self.user_id,
            "short_term": {},
            "long_term": {},
            "profile": {},
        }

        # 短期记忆统计
        short_term_stats = self.short_term_memory.get_stats()
        stats["short_term"] = short_term_stats

        # 长期记忆统计
        try:
            long_term_stats = self.long_term_memory.get_stats()
            stats["long_term"] = long_term_stats
        except Exception as e:
            stats["long_term_error"] = str(e)

        # 用户画像信息
        user_profile = self.get_user_profile()
        stats["profile"] = {
            "has_profile": bool(user_profile and len(user_profile) > 1),
            "cached": self.user_profile_cache is not None,
            "cache_age": (datetime.now() - self.profile_cache_time).total_seconds()
            if self.profile_cache_time
            else None,
        }

        return stats

    def export_memories(self, format: str = "json") -> Dict[str, Any]:
        """
        导出记忆数据

        Args:
            format: 导出格式（目前只支持json）

        Returns:
            导出的记忆数据
        """
        export_data = {
            "user_id": self.user_id,
            "export_time": datetime.now().isoformat(),
            "short_term_memories": {
                "checkins": self.short_term_memory.get_recent_checkins(limit=30),
                "conversations": self.short_term_memory.get_recent_conversations(
                    limit=200
                ),
            },
            "user_profile": self.get_user_profile(),
            "stats": self.get_stats(),
        }

        return export_data
