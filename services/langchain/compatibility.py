"""
兼容性模块

确保现有代码可以继续工作，同时支持新的agent版本切换
"""

import logging
import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def get_agent_version_from_env() -> str:
    """
    从环境变量获取agent版本

    Returns:
        agent版本: "legacy", "new", "v2", "simple"
    """
    version = os.environ.get("AGENT_VERSION", "new").lower()

    valid_versions = ["legacy", "new", "v2", "simple"]
    if version not in valid_versions:
        logger.warning(f"无效的AGENT_VERSION: {version}, 使用默认值: new")
        version = "new"

    logger.info(f"使用Agent版本: {version} (来自环境变量)")
    return version


class CompatibilityLayer:
    """兼容性层，确保现有代码可以继续工作"""

    @staticmethod
    async def get_agent(user_id: int, db: AsyncSession, version: Optional[str] = None):
        """
        获取Agent实例（兼容现有代码）

        Args:
            user_id: 用户ID
            db: 数据库会话
            version: 指定版本，如果为None则从环境变量读取

        Returns:
            Agent实例
        """
        from .agent_selector import AgentSelector

        if version is None:
            version = get_agent_version_from_env()

        return await AgentSelector.create_agent(version, user_id, db)

    @staticmethod
    def get_agent_factory(version: Optional[str] = None):
        """
        获取AgentFactory（兼容现有代码）

        Args:
            version: 指定版本，如果为None则从环境变量读取

        Returns:
            AgentFactory类
        """
        from .agent_selector import AgentSelector

        if version is None:
            version = get_agent_version_from_env()

        return AgentSelector.get_agent_factory(version)


# 导出兼容的AgentFactory，默认使用新版本
AgentFactory = CompatibilityLayer.get_agent_factory("new")


async def get_agent(user_id: int, db: AsyncSession, version: Optional[str] = None):
    """
    兼容函数：获取Agent实例

    Args:
        user_id: 用户ID
        db: 数据库会话
        version: Agent版本

    Returns:
        Agent实例
    """
    return await CompatibilityLayer.get_agent(user_id, db, version)


def get_agent_factory(version: Optional[str] = None):
    """
    兼容函数：获取AgentFactory

    Args:
        version: Agent版本

    Returns:
        AgentFactory类
    """
    return CompatibilityLayer.get_agent_factory(version)


# 测试兼容性
if __name__ == "__main__":
    import asyncio

    async def test_compatibility():
        print("🔧 兼容性模块测试")
        print("=" * 50)

        # 测试环境变量读取
        os.environ["AGENT_VERSION"] = "legacy"
        print(f"环境变量 AGENT_VERSION = legacy")
        print(f"获取的版本: {get_agent_version_from_env()}")

        os.environ["AGENT_VERSION"] = "new"
        print(f"\n环境变量 AGENT_VERSION = new")
        print(f"获取的版本: {get_agent_version_from_env()}")

        # 测试AgentFactory获取
        print(f"\n默认AgentFactory: {AgentFactory}")

        # 测试版本切换
        legacy_factory = get_agent_factory("legacy")
        new_factory = get_agent_factory("new")

        print(f"Legacy AgentFactory: {legacy_factory}")
        print(f"New AgentFactory: {new_factory}")

        print("\n✅ 兼容性模块测试通过")

    asyncio.run(test_compatibility())
