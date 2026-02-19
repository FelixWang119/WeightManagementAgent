"""
SSE连接管理器
管理Server-Sent Events连接的生命周期和消息广播
"""

import asyncio
import json
import logging
import time
from typing import Dict, Set, Optional, AsyncGenerator, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    User,
    CoachingPrompt,
    PromptState,
    PromptInteractionHistory,
    ActionType,
    AsyncSessionLocal,
)

logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """SSE连接信息"""

    user_id: int
    connection_id: str
    created_at: float
    last_activity: float
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    active: bool = True

    def is_alive(self, timeout_seconds: int = 30) -> bool:
        """检查连接是否存活"""
        if not self.active:
            return False
        return (time.time() - self.last_activity) < timeout_seconds

    def update_activity(self):
        """更新活动时间"""
        self.last_activity = time.time()


class SSEConnectionManager:
    """SSE连接管理器"""

    def __init__(self):
        # 用户ID -> 连接ID -> SSEConnection
        self._connections: Dict[int, Dict[str, SSEConnection]] = {}
        # 连接ID -> (用户ID, 连接)
        self._connection_index: Dict[str, tuple[int, SSEConnection]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = 60  # 清理间隔（秒）
        self._connection_timeout = 300  # 连接超时时间（秒）
        self._cleanup_task = None  # 清理任务引用

    async def register_connection(
        self, user_id: int, connection_id: str
    ) -> SSEConnection:
        """注册新的SSE连接"""
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = {}

            connection = SSEConnection(
                user_id=user_id,
                connection_id=connection_id,
                created_at=time.time(),
                last_activity=time.time(),
            )

            self._connections[user_id][connection_id] = connection
            self._connection_index[connection_id] = (user_id, connection)

            logger.info(
                "注册SSE连接: user_id=%d, connection_id=%s", user_id, connection_id
            )
            return connection

    async def unregister_connection(self, connection_id: str):
        """注销SSE连接"""
        async with self._lock:
            if connection_id in self._connection_index:
                user_id, connection = self._connection_index[connection_id]
                connection.active = False

                if user_id in self._connections:
                    if connection_id in self._connections[user_id]:
                        del self._connections[user_id][connection_id]

                    # 如果用户没有其他连接，删除用户条目
                    if not self._connections[user_id]:
                        del self._connections[user_id]

                del self._connection_index[connection_id]

                logger.info(
                    "注销SSE连接: user_id=%d, connection_id=%s", user_id, connection_id
                )

    async def send_message(self, user_id: int, event_type: str, data: Any):
        """向指定用户的所有连接发送消息"""
        async with self._lock:
            if user_id not in self._connections:
                logger.debug("用户 %d 没有活跃的SSE连接", user_id)
                return 0

            sent_count = 0
            message = self._format_sse_message(event_type, data)

            for connection_id, connection in list(self._connections[user_id].items()):
                if connection.is_alive():
                    try:
                        await connection.queue.put(message)
                        sent_count += 1
                        logger.debug(
                            "向连接 %s 发送消息: %s", connection_id, event_type
                        )
                    except Exception as e:
                        logger.error(
                            "向连接 %s 发送消息失败: %s", connection_id, str(e)
                        )
                        connection.active = False

            return sent_count

    async def broadcast_message(
        self, event_type: str, data: Any, exclude_user_ids: Optional[Set[int]] = None
    ):
        """向所有连接广播消息（排除指定用户）"""
        if exclude_user_ids is None:
            exclude_user_ids = set()

        async with self._lock:
            sent_count = 0
            message = self._format_sse_message(event_type, data)

            for user_id, connections in list(self._connections.items()):
                if user_id in exclude_user_ids:
                    continue

                for connection_id, connection in list(connections.items()):
                    if connection.is_alive():
                        try:
                            await connection.queue.put(message)
                            sent_count += 1
                        except Exception as e:
                            logger.error(
                                "广播消息到连接 %s 失败: %s", connection_id, str(e)
                            )
                            connection.active = False

            logger.debug("广播消息 %s 到 %d 个连接", event_type, sent_count)
            return sent_count

    async def get_connection_stream(
        self, connection_id: str
    ) -> Optional[AsyncGenerator[str, None]]:
        """获取连接的SSE事件流"""
        if connection_id not in self._connection_index:
            return None

        user_id, connection = self._connection_index[connection_id]

        async def event_stream():
            try:
                while connection.is_alive():
                    try:
                        # 等待消息，最多30秒
                        message = await asyncio.wait_for(
                            connection.queue.get(), timeout=30
                        )
                        connection.update_activity()
                        yield message

                        # 发送心跳保持连接
                        yield self._format_sse_message(
                            "heartbeat", {"timestamp": datetime.utcnow().isoformat()}
                        )

                    except asyncio.TimeoutError:
                        # 发送心跳保持连接
                        yield self._format_sse_message(
                            "heartbeat", {"timestamp": datetime.utcnow().isoformat()}
                        )
                        connection.update_activity()

                    except Exception as e:
                        logger.error("连接 %s 事件流错误: %s", connection_id, str(e))
                        break
            finally:
                await self.unregister_connection(connection_id)

        return event_stream()

    async def get_user_connections(self, user_id: int) -> Dict[str, SSEConnection]:
        """获取用户的所有连接"""
        async with self._lock:
            return self._connections.get(user_id, {}).copy()

    async def get_connection_count(self, user_id: Optional[int] = None) -> int:
        """获取连接数量"""
        async with self._lock:
            if user_id is not None:
                return len(self._connections.get(user_id, {}))
            else:
                return len(self._connection_index)

    async def start_cleanup_task(self):
        """启动清理任务（在应用启动后调用）"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
            logger.info("SSE连接清理任务已启动")

    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("SSE连接清理任务已停止")

    async def _cleanup_stale_connections(self):
        """定期清理失效的连接"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)

                async with self._lock:
                    stale_count = 0
                    current_time = time.time()

                    for connection_id, (user_id, connection) in list(
                        self._connection_index.items()
                    ):
                        if not connection.is_alive(self._connection_timeout):
                            connection.active = False

                            if user_id in self._connections:
                                if connection_id in self._connections[user_id]:
                                    del self._connections[user_id][connection_id]

                                if not self._connections[user_id]:
                                    del self._connections[user_id]

                            del self._connection_index[connection_id]
                            stale_count += 1

                    if stale_count > 0:
                        logger.info("清理了 %d 个失效的SSE连接", stale_count)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("清理过期连接时发生错误: %s", e)

    def _format_sse_message(self, event_type: str, data: Any) -> str:
        """格式化SSE消息"""
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)

        return f"event: {event_type}\ndata: {data_str}\n\n"

    async def send_coaching_prompt(self, user_id: int, prompt_data: dict):
        """发送教练提示消息"""
        # 首先保存到数据库
        async with AsyncSessionLocal() as session:
            try:
                # 创建教练提示记录
                prompt = CoachingPrompt(
                    user_id=user_id,
                    timing_type=prompt_data.get("timing_type"),
                    priority=prompt_data.get("priority"),
                    state="pending",  # PromptState.PENDING.value
                    title=prompt_data.get("title", ""),
                    message=prompt_data.get("message", ""),
                    suggested_actions=prompt_data.get("suggested_actions"),
                    quick_replies=prompt_data.get("quick_replies"),
                    delivery_channels=["in_app_chat"],
                    scheduled_for=datetime.utcnow(),
                    context_data=prompt_data.get("context_data"),
                    trigger_conditions=prompt_data.get("trigger_conditions"),
                    prompt_metadata=prompt_data.get("metadata"),
                )

                session.add(prompt)
                await session.commit()
                await session.refresh(prompt)

                # 发送SSE消息
                sse_data = {
                    "prompt_id": prompt.id,
                    "type": "coaching_prompt",
                    "title": prompt.title,
                    "message": prompt.message,
                    "suggested_actions": prompt.suggested_actions,
                    "quick_replies": prompt.quick_replies,
                    "priority": prompt.priority.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                sent_count = await self.send_message(
                    user_id, "coaching_prompt", sse_data
                )

                if sent_count > 0:
                    # 更新提示状态为已发送
                    prompt.state = "delivered"  # PromptState.DELIVERED.value
                    prompt.delivered_at = datetime.utcnow()
                    await session.commit()

                    logger.info(
                        "教练提示已发送: user_id=%d, prompt_id=%d, sent_to=%d",
                        user_id,
                        prompt.id,
                        sent_count,
                    )
                else:
                    # 保持PENDING状态，等待有连接时再发送
                    logger.warning(
                        "教练提示暂未发送: user_id=%d, prompt_id=%d (无活跃连接)",
                        user_id,
                        prompt.id,
                    )

                return prompt

            except Exception as e:
                logger.error("发送教练提示失败: user_id=%d, error=%s", user_id, str(e))
                await session.rollback()
                raise

    async def record_prompt_interaction(
        self,
        prompt_id: int,
        user_id: int,
        action_type: ActionType,
        action_value: Optional[str] = None,
        response_text: Optional[str] = None,
    ):
        """记录提示交互历史"""
        async with AsyncSessionLocal() as session:
            try:
                # 查找提示
                from sqlalchemy import select

                stmt = select(CoachingPrompt).where(
                    CoachingPrompt.id == prompt_id, CoachingPrompt.user_id == user_id
                )
                result = await session.execute(stmt)
                prompt = result.scalar_one_or_none()

                if not prompt:
                    logger.error(
                        "提示不存在: prompt_id=%d, user_id=%d", prompt_id, user_id
                    )
                    return None

                # 创建交互记录
                interaction = PromptInteractionHistory(
                    prompt_id=prompt_id,
                    user_id=user_id,
                    action_type=action_type,
                    action_value=action_value,
                    response_text=response_text,
                    success=True,
                )

                session.add(interaction)

                # 更新提示状态
                prompt.state = "responded"  # PromptState.RESPONDED.value
                prompt.responded_at = datetime.utcnow()

                await session.commit()

                logger.info(
                    "记录提示交互: prompt_id=%d, action=%s",
                    prompt_id,
                    action_type.value,
                )
                return interaction

            except Exception as e:
                logger.error(
                    "记录提示交互失败: prompt_id=%d, error=%s", prompt_id, str(e)
                )
                await session.rollback()
                raise


# 全局SSE连接管理器实例
sse_manager = SSEConnectionManager()
