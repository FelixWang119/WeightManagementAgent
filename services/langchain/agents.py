"""
Agent入口点 - 兼容现有代码

这个文件作为现有代码的入口点，确保向后兼容。
实际实现已经移动到其他文件：
- agent.py: 主实现（最新版本）
- agent_simple.py: 简化版（推荐使用）

使用环境变量 AGENT_VERSION 控制使用的版本：
- new: 最新版本（默认）
- simple: 简化版（推荐）
"""

import logging
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def get_current_agent_version() -> str:
    """
    获取当前使用的agent版本

    Returns:
        agent版本字符串
    """
    version = os.environ.get("AGENT_VERSION", "simple").lower()
    valid_versions = ["new", "simple"]

    if version not in valid_versions:
        logger.warning(f"无效的AGENT_VERSION: {version}, 使用默认值: simple")
        version = "simple"

    logger.info(f"当前Agent版本: {version}")
    return version


# 根据版本动态导入
def _import_agent_factory(version: str):
    """
    根据版本导入AgentFactory

    Args:
        version: agent版本

    Returns:
        AgentFactory类
    """
    if version == "simple":
        from .agent_simple import AgentFactory

        return AgentFactory
    else:  # "new" or default
        from .agent import AgentFactory

        return AgentFactory


# 动态获取当前版本的AgentFactory
def _get_current_agent_factory():
    """获取当前版本的AgentFactory"""
    version = get_current_agent_version()
    return _import_agent_factory(version)


# 导出当前版本的AgentFactory
AgentFactory = _get_current_agent_factory()


# 兼容性函数
async def get_agent(
    user_id: int, db: AsyncSession, version: Optional[str] = None
) -> Any:
    """
    获取Agent实例（兼容现有代码）

    Args:
        user_id: 用户ID
        db: 数据库会话
        version: 指定版本，如果为None则使用当前版本

    Returns:
        Agent实例
    """
    if version is None:
        version = get_current_agent_version()

    factory_class = _import_agent_factory(version)

    try:
        # 尝试使用get_agent方法
        if hasattr(factory_class, "get_agent"):
            return await factory_class.get_agent(user_id, db)
        else:
            # 尝试其他方式
            logger.warning(f"版本 {version} 没有标准的get_agent方法，尝试其他方式")
            raise ValueError(f"版本 {version} 不支持标准的get_agent方法")
    except Exception as e:
        logger.error(f"创建Agent实例失败 (版本: {version}): {e}")
        raise


# 导出其他兼容函数（如果需要）
async def chat_with_agent(
    user_id: int, message: str, db: AsyncSession, version: Optional[str] = None
) -> Dict[str, Any]:
    """
    与Agent聊天（兼容现有代码）

    Args:
        user_id: 用户ID
        message: 用户消息
        db: 数据库会话
        version: Agent版本

    Returns:
        聊天结果
    """
    agent = await get_agent(user_id, db, version)
    return await agent.chat(message)


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test_agents_module():
        print("🔧 Agent入口点模块测试")
        print("=" * 50)

        # 测试版本获取
        print("测试环境变量:")
        os.environ["AGENT_VERSION"] = "simple"
        print(f"  AGENT_VERSION=simple -> {get_current_agent_version()}")

        os.environ["AGENT_VERSION"] = "new"
        print(f"  AGENT_VERSION=new -> {get_current_agent_version()}")

        os.environ["AGENT_VERSION"] = "invalid"
        print(f"  AGENT_VERSION=invalid -> {get_current_agent_version()}")

        # 测试Factory获取
        print(f"\n当前AgentFactory: {AgentFactory}")

        print("\n✅ Agent入口点模块测试通过")

    asyncio.run(test_agents_module())
