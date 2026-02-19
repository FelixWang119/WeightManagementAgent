"""
Agent工厂
根据用户配置创建和管理Agent实例（简化实现）
"""

from typing import Dict, Any, Optional, Type
import asyncio
from datetime import datetime

from .base import BaseAgent
from .simple import SimpleWeightAgent


class AgentFactory:
    """
    Agent工厂类
    负责创建和管理Agent实例（简化实现）
    """

    _agent_classes: Dict[str, Type[BaseAgent]] = {
        "SimpleWeightAgent": SimpleWeightAgent,
    }

    _agent_cache: Dict[int, BaseAgent] = {}
    _cache_lock: Optional[asyncio.Lock] = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """懒加载获取锁实例"""
        if cls._cache_lock is None:
            cls._cache_lock = asyncio.Lock()
        return cls._cache_lock

    @classmethod
    async def get_agent(cls, user_id: int, db=None) -> BaseAgent:
        async with cls._get_lock():
            if user_id in cls._agent_cache:
                return cls._agent_cache[user_id]

        agent = cls._create_agent(user_id)

        async with cls._get_lock():
            cls._agent_cache[user_id] = agent

        return agent

    @classmethod
    def _create_agent(cls, user_id: int) -> BaseAgent:
        """
        创建Agent实例

        Args:
            user_id: 用户ID

        Returns:
            Agent实例
        """
        # 使用默认的SimpleWeightAgent
        agent_class = SimpleWeightAgent

        # 创建Agent实例
        agent = agent_class(user_id=user_id)

        return agent

    @classmethod
    async def create_or_update_agent_config(
        cls,
        user_id: int,
        agent_name: str,
        personality_type: str = "friendly",
        config_data: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        创建或更新Agent配置（简化实现）

        Args:
            user_id: 用户ID
            agent_name: Agent名称
            personality_type: 性格类型
            config_data: 配置数据
            db: 数据库会话（可选）

        Returns:
            操作结果
        """
        # 简化实现：直接返回成功
        # 在实际应用中，这里应该保存到数据库
        return {
            "success": True,
            "message": "Agent配置已保存（简化实现）",
            "agent_name": agent_name,
            "personality_type": personality_type,
        }

    @classmethod
    async def clear_cache(cls, user_id: Optional[int] = None) -> int:
        async with cls._get_lock():
            if user_id is None:
                count = len(cls._agent_cache)
                cls._agent_cache.clear()
                return count
            else:
                if user_id in cls._agent_cache:
                    del cls._agent_cache[user_id]
                    return 1
                return 0

    @classmethod
    def get_available_agents(cls) -> Dict[str, Dict[str, Any]]:
        """
        获取可用的Agent列表

        Returns:
            Agent信息字典
        """
        agents = {}

        for agent_name, agent_class in cls._agent_classes.items():
            agents[agent_name] = {
                "class_name": agent_class.__name__,
                "description": agent_class.__doc__ or "无描述",
                "module": agent_class.__module__,
            }

        return agents

    @classmethod
    async def get_agent_info(cls, user_id: int, db=None) -> Dict[str, Any]:
        """
        获取用户的Agent信息

        Args:
            user_id: 用户ID
            db: 数据库会话（可选）

        Returns:
            Agent信息
        """
        # 获取Agent实例
        agent = await cls.get_agent(user_id, db)

        # 获取Agent统计信息
        stats = agent.get_stats()

        return {
            "user_id": user_id,
            "agent_name": agent.agent_name,
            "personality_type": "friendly",  # 简化处理
            "config_data": {},
            "stats": stats,
            "available_agents": list(cls._agent_classes.keys()),
        }

    @classmethod
    async def test_agent(cls, user_id: int, message: str, db=None) -> Dict[str, Any]:
        """
        测试Agent

        Args:
            user_id: 用户ID
            message: 测试消息
            db: 数据库会话（可选）

        Returns:
            测试结果
        """
        try:
            # 获取Agent实例
            agent = await cls.get_agent(user_id, db)

            # 测试聊天
            start_time = datetime.now()
            result = await agent.chat(message)
            end_time = datetime.now()

            response_time = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "agent_name": agent.agent_name,
                "user_message": message,
                "response": result.get("response"),
                "response_time": response_time,
                "intermediate_steps": result.get("intermediate_steps", []),
                "memory_result": result.get("memory_result"),
                "timestamp": end_time.isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    @classmethod
    async def switch_agent(
        cls,
        user_id: int,
        new_agent_name: str,
        personality_type: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        切换用户的Agent（简化实现）

        Args:
            user_id: 用户ID
            new_agent_name: 新的Agent名称
            personality_type: 性格类型（可选）
            config_data: 配置数据（可选）
            db: 数据库会话（可选）

        Returns:
            切换结果
        """
        # 验证新的Agent名称
        if new_agent_name not in cls._agent_classes:
            return {
                "success": False,
                "error": f"不支持的Agent类型: {new_agent_name}",
                "available_agents": list(cls._agent_classes.keys()),
            }

        # 清除缓存
        await cls.clear_cache(user_id)

        return {
            "success": True,
            "message": f"已切换到 {new_agent_name}",
            "new_agent": new_agent_name,
            "personality_type": personality_type or "friendly",
        }
