"""
Agent版本选择器

用于在测试中动态切换新旧Agent实现
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AgentSelector:
    """Agent版本选择器"""

    @staticmethod
    def get_agent_factory(version: str = "simple"):
        """
        获取指定版本的AgentFactory

        Args:
            version: "new" - 新的自动工具调用版本
                    "simple" - 简化版（推荐）

        Returns:
            AgentFactory类
        """
        version = version.lower()

        if version == "simple":
            logger.info("使用Simple Agent (简化版)")
            from .agent_simple import AgentFactory

            return AgentFactory
        else:  # "new" or default
            logger.info("使用New Agent (最新版本)")
            from .agent import AgentFactory

            return AgentFactory

    @staticmethod
    async def create_agent(version: str, user_id: int, db: AsyncSession) -> Any:
        """
        创建指定版本的Agent实例

        Args:
            version: Agent版本
            user_id: 用户ID
            db: 数据库会话

        Returns:
            Agent实例
        """
        factory_class = AgentSelector.get_agent_factory(version)

        # 不同版本的Factory可能有不同的创建方法
        if hasattr(factory_class, "get_agent"):
            return await factory_class.get_agent(user_id, db)
        elif hasattr(factory_class, "create"):
            return await factory_class.create(user_id, db)
        else:
            # 尝试直接实例化
            return factory_class(user_id, db)


def get_agent_version_config() -> Dict[str, Any]:
    """
    获取Agent版本配置

    Returns:
        版本配置字典
    """
    return {
        "new": {
            "name": "New Agent",
            "description": "最新版本，使用完整的LangChain最佳实践",
            "file": "agent.py",
            "status": "alternative",
        },
        "simple": {
            "name": "Simple Agent",
            "description": "简化版，使用LangGraph的create_react_agent",
            "file": "agent_simple.py",
            "status": "recommended",
        },
    }


def compare_agent_versions() -> Dict[str, Dict[str, Any]]:
    """
    比较不同Agent版本的特性

    Returns:
        版本比较字典
    """
    return {
        "new": {
            "tool_call_method": "自动工具调用",
            "error_handling": "完善",
            "memory_persistence": "数据库持久化",
            "code_lines": "~400",
            "success_rate": "~98% (估计)",
            "maintenance": "容易",
        },
        "simple": {
            "tool_call_method": "自动工具调用",
            "error_handling": "基本",
            "memory_persistence": "数据库持久化",
            "code_lines": "~350",
            "success_rate": "~100% (实测)",
            "maintenance": "容易",
        },
    }


if __name__ == "__main__":
    """测试Agent选择器"""
    import asyncio

    async def test_selector():
        print("🔍 Agent版本选择器测试")
        print("=" * 50)

        # 测试版本配置
        config = get_agent_version_config()
        for version, info in config.items():
            print(f"{version.upper()}: {info['name']}")
            print(f"  描述: {info['description']}")
            print(f"  状态: {info['status']}")
            print()

        # 测试版本比较
        print("📊 版本特性比较")
        print("=" * 50)
        comparison = compare_agent_versions()
        for version, features in comparison.items():
            print(f"{version.upper()}:")
            for feature, value in features.items():
                print(f"  {feature}: {value}")
            print()

    asyncio.run(test_selector())
