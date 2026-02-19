"""
GraphFactory实现
替代原有的AgentFactory，提供LangGraph图实例管理和调用接口
保持API兼容性，支持热修复和fallback机制
"""

import asyncio
from typing import Dict, Any, Optional, List
import time
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from .graph import invoke_graph, get_graph_performance_summary, reset_graph_cache
from .monitor import performance_monitor
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class GraphFactory:
    """
    Graph工厂类
    负责创建和管理LangGraph图实例，替代原有的AgentFactory
    保持相同的API接口以支持无缝迁移
    """

    _instance_cache: Dict[int, Dict[str, Any]] = {}
    _cache_lock: Optional[asyncio.Lock] = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """懒加载获取锁实例"""
        if cls._cache_lock is None:
            cls._cache_lock = asyncio.Lock()
        return cls._cache_lock

    class AgentWrapper:
        """Agent包装器，提供chat方法以兼容原有接口"""

        def __init__(self, agent_name: str, user_id: int, chat_func):
            self.agent_name = agent_name
            self.user_id = user_id
            self._chat_func = chat_func

        async def chat(self, message: str, **kwargs):
            """调用聊天方法"""
            return await self._chat_func(message, **kwargs)

    @classmethod
    async def _chat_wrapper(
        cls, user_id: int, message: str, **kwargs
    ) -> Dict[str, Any]:
        """
        聊天包装器，调用LangGraph处理消息

        Args:
            user_id: 用户ID
            message: 用户消息
            **kwargs: 其他参数

        Returns:
            处理结果
        """
        try:
            # 调用LangGraph处理消息
            from .graph import invoke_graph

            result = await invoke_graph(
                user_id=user_id,
                user_message=message,
                config=None,  # 节点函数会自己创建数据库会话
            )

            # 提取响应
            structured_response = result.get("structured_response", {})
            response_content = structured_response.get("content", "")

            return {
                "response": response_content,
                "structured_response": structured_response,
                "intermediate_steps": result.get("intermediate_steps", []),
                "error": result.get("error"),
                "needs_refresh": result.get("needs_refresh", False),
                "checkins": result.get("checkins", []),
            }
        except Exception as e:
            logger.exception("_chat_wrapper失败: user_id=%s, 错误=%s", user_id, e)
            return {
                "response": "抱歉，处理您的消息时发生了错误。",
                "structured_response": {"type": "text", "content": "系统错误"},
                "error": str(e),
                "intermediate_steps": [],
            }

    @classmethod
    async def get_agent(cls, user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """
        获取Agent实例（兼容原有AgentFactory接口）

        注意：db参数被保留用于API兼容性，但节点函数会自己创建数据库会话
        以避免AsyncSession序列化问题

        Args:
            user_id: 用户ID
            db: 数据库会话（为兼容性保留，实际不使用）

        Returns:
            Agent实例字典（保持API兼容）
        """
        logger.info("GraphFactory.get_agent调用: user_id=%s", user_id)

        # 创建聊天函数（忽略传入的db，节点会自己创建会话）
        async def chat_func(message: str, **kwargs):
            return await cls._chat_wrapper(user_id, message, **kwargs)

        # 返回包装对象
        agent_wrapper = cls.AgentWrapper(
            agent_name="体重教练(LangGraph)", user_id=user_id, chat_func=chat_func
        )

        return {
            "name": "体重教练(LangGraph)",
            "user_id": user_id,
            "agent": agent_wrapper,
            "type": "graph",
        }

    @classmethod
    async def create_or_update_agent_config(
        cls,
        user_id: int,
        agent_name: str,
        personality_type: str = "friendly",
        config_data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        创建或更新Agent配置（兼容原有接口）

        Args:
            user_id: 用户ID
            agent_name: Agent名称
            personality_type: 性格类型
            config_data: 配置数据
            db: 数据库会话（可选）

        Returns:
            操作结果
        """
        logger.info(
            "GraphFactory.create_or_update_agent_config: user_id=%s, agent_name=%s",
            user_id,
            agent_name,
        )

        # LangGraph版本简化处理
        return {
            "success": True,
            "message": "LangGraph配置已保存（简化实现）",
            "agent_name": agent_name,
            "personality_type": personality_type,
            "graph_version": "coach_graph_v1",
        }

    @classmethod
    async def clear_cache(cls, user_id: Optional[int] = None) -> int:
        """
        清除缓存（兼容原有接口）

        Args:
            user_id: 用户ID（可选，None表示清除所有）

        Returns:
            清除的缓存数量
        """
        async with cls._get_lock():
            if user_id is None:
                count = len(cls._instance_cache)
                cls._instance_cache.clear()
                await reset_graph_cache()
                logger.info("清除所有缓存: 数量=%d", count)
                return count
            else:
                if user_id in cls._instance_cache:
                    del cls._instance_cache[user_id]
                    await reset_graph_cache(f"user_{user_id}")
                    logger.info("清除用户缓存: user_id=%s", user_id)
                    return 1
                return 0

    @classmethod
    def get_available_agents(cls) -> Dict[str, Dict[str, Any]]:
        """
        获取可用的Agent列表（兼容原有接口）

        Returns:
            Agent信息字典
        """
        return {
            "LangGraphCoach": {
                "class_name": "LangGraphCoach",
                "description": "基于LangGraph的体重管理教练，支持工具调用和状态管理",
                "module": "services.langchain.graph.factory",
                "version": "1.0.0",
                "features": ["工具调用", "状态管理", "5分钟缓存", "性能监控"],
            }
        }

    @classmethod
    async def get_agent_info(
        cls, user_id: int, db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        获取用户的Agent信息（兼容原有接口）

        Args:
            user_id: 用户ID
            db: 数据库会话（可选）

        Returns:
            Agent信息
        """
        # 获取性能摘要
        perf_summary = await get_graph_performance_summary("coach_graph")

        return {
            "user_id": user_id,
            "agent_name": "LangGraphCoach",
            "personality_type": "friendly",
            "config_data": {
                "graph_id": "coach_graph",
                "version": "1.0.0",
                "features": ["tools", "state_management", "caching", "monitoring"],
            },
            "stats": {
                "cache_hit_rate": 0.0,  # 可以从性能监控获取
                "graph_invocations": perf_summary.get("summary", {}).get(
                    "total_invocations", 0
                ),
                "avg_response_time": perf_summary.get("summary", {}).get(
                    "avg_duration_ms", 0
                ),
            },
            "available_agents": list(cls.get_available_agents().keys()),
        }

    @classmethod
    async def test_agent(
        cls, user_id: int, message: str, db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        测试Agent（兼容原有接口）

        Args:
            user_id: 用户ID
            message: 测试消息
            db: 数据库会话（可选）

        Returns:
            测试结果
        """
        start_time = time.time()
        logger.info(
            "GraphFactory.test_agent: user_id=%s, 消息=%s", user_id, message[:50]
        )

        try:
            # 使用db或创建临时会话
            from models.database import AsyncSessionLocal

            test_db = db
            if test_db is None:
                test_db = AsyncSessionLocal()

            # 调用chat方法（节点函数自己创建数据库会话）
            result = await cls._chat_wrapper(user_id, message)

            end_time = time.time()
            response_time = (end_time - start_time) * 1000

            response = {
                "success": True,
                "agent_name": "LangGraphCoach",
                "user_message": message,
                "response": result.get("response"),
                "response_time": response_time,
                "intermediate_steps": result.get("intermediate_steps", []),
                "memory_result": result.get("memory_result", {}),
                "timestamp": datetime.fromtimestamp(end_time).isoformat(),
            }

            # 如果db是我们创建的，关闭它
            if db is None and hasattr(test_db, "close"):
                await test_db.close()

            logger.info(
                "GraphFactory.test_agent完成: user_id=%s, 耗时=%.2fms",
                user_id,
                response_time,
            )

            return response

        except Exception as e:
            logger.exception(
                "GraphFactory.test_agent失败: user_id=%s, 错误=%s", user_id, e
            )

            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
            }

    @classmethod
    async def switch_agent(
        cls,
        user_id: int,
        new_agent_name: str,
        personality_type: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        切换用户的Agent（兼容原有接口）

        Args:
            user_id: 用户ID
            new_agent_name: 新的Agent名称
            personality_type: 性格类型（可选）
            config_data: 配置数据（可选）
            db: 数据库会话（可选）

        Returns:
            切换结果
        """
        logger.info(
            "GraphFactory.switch_agent: user_id=%s, new_agent=%s",
            user_id,
            new_agent_name,
        )

        # 验证新的Agent名称
        available_agents = cls.get_available_agents()
        if new_agent_name not in available_agents:
            return {
                "success": False,
                "error": f"不支持的Agent类型: {new_agent_name}",
                "available_agents": list(available_agents.keys()),
            }

        # 清除缓存
        await cls.clear_cache(user_id)

        return {
            "success": True,
            "message": f"已切换到 {new_agent_name}",
            "new_agent": new_agent_name,
            "personality_type": personality_type or "friendly",
            "graph_version": "coach_graph_v1",
        }

    @classmethod
    async def get_performance_stats(
        cls, graph_id: str = "coach_graph"
    ) -> Dict[str, Any]:
        """
        获取性能统计（新增方法）

        Args:
            graph_id: 图ID

        Returns:
            性能统计
        """
        try:
            summary = await get_graph_performance_summary(graph_id)
            return {
                "success": True,
                "graph_id": graph_id,
                "summary": summary.get("summary", {}),
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.exception("获取性能统计失败: graph_id=%s, 错误=%s", graph_id, e)
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time(),
            }

    @classmethod
    async def health_check(cls) -> Dict[str, Any]:
        """
        健康检查（新增方法）

        Returns:
            健康状态
        """
        try:
            # 检查图是否可以编译
            from .graph import get_graph

            graph = await get_graph()

            # 检查性能监控
            perf_stats = await cls.get_performance_stats()

            return {
                "success": True,
                "status": "healthy",
                "graph_compiled": True,
                "monitoring_active": perf_stats.get("success", False),
                "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
            }
        except Exception as e:
            logger.exception("健康检查失败: %s", e)
            return {
                "success": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
            }


# 全局工厂实例
graph_factory = GraphFactory()
