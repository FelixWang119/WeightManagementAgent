"""
对话集成模块
提供与现有对话系统的集成接口
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from .factory import AgentFactory
from services.langchain.memory import MemoryManager, CheckinSyncService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


async def chat_with_agent(
    user_id: int, message: str, db=None, **kwargs
) -> Dict[str, Any]:
    """
    与Agent对话（主入口函数）

    Args:
        user_id: 用户ID
        message: 用户消息
        db: 数据库会话（可选）
        **kwargs: 额外参数

    Returns:
        对话结果
    """
    try:
        # 1. 获取Agent实例
        agent = await AgentFactory.get_agent(user_id, db)

        # 2. 可选：同步最近的打卡记录
        if kwargs.get("sync_checkins_before_chat", True):
            try:
                sync_service = CheckinSyncService()
                sync_result = await sync_service.sync_recent_checkins(user_id, hours=24)
                if sync_result.get("status") == "success":
                    logger.info(
                        f"对话前同步了{sync_result.get('synced_records', 0)}条打卡记录"
                    )
            except Exception as sync_error:
                logger.warning(f"对话前同步打卡记录失败: {sync_error}")
                # 不中断对话流程

        # 3. 调用Agent聊天
        start_time = datetime.now()
        result = await agent.chat(message, **kwargs)
        end_time = datetime.now()

        response_time = (end_time - start_time).total_seconds()

        # 4. 构建标准化的响应
        response = {
            "response": result.get("response", "抱歉，我现在有点忙。"),
            "structured_response": result.get(
                "structured_response",
                {
                    "type": "text",
                    "content": result.get("response", "抱歉，我现在有点忙。"),
                    "actions": [],
                },
            ),
            "intermediate_steps": result.get("intermediate_steps", []),
            "agent_name": result.get("agent_name", agent.agent_name),
            "response_time": response_time,
            "memory_result": result.get("memory_result"),
            "timestamp": end_time.isoformat(),
        }

        # 5. 添加额外的分析结果（如果有）
        if "weight_analysis" in result:
            response["weight_analysis"] = result["weight_analysis"]

        logger.info(
            f"Agent对话完成 - 用户: {user_id}, "
            f"Agent: {response['agent_name']}, "
            f"响应时间: {response_time:.2f}秒"
        )

        return response

    except Exception as e:
        logger.error(f"Agent对话失败: {e}", exc_info=True)

        # 返回错误响应
        return {
            "response": "抱歉，我在处理您的请求时遇到了问题。请稍后再试或联系技术支持。",
            "structured_response": {
                "type": "text",
                "content": "抱歉，我在处理您的请求时遇到了问题。请稍后再试或联系技术支持。",
                "actions": [],
            },
            "intermediate_steps": [{"step": "error", "data": {"error": str(e)}}],
            "agent_name": "ErrorAgent",
            "response_time": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def save_to_memory(
    user_id: int,
    user_message: str,
    assistant_response: str,
    memory_type: str = "conversation",
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    保存对话到记忆系统

    Args:
        user_id: 用户ID
        user_message: 用户消息
        assistant_response: 助手回复
        memory_type: 记忆类型（conversation/checkin/summary）
        metadata: 附加元数据
        **kwargs: 额外参数

    Returns:
        保存结果
    """
    try:
        # 创建记忆管理器
        memory_manager = MemoryManager(user_id)

        # 导入必要的模块
        from services.langchain.memory.manager import HumanMessage, AIMessage
        from services.langchain.memory.typed_buffer import MemoryType

        # 确定记忆类型
        if memory_type == "checkin":
            mem_type = MemoryType.CHECKIN
        elif memory_type == "summary":
            mem_type = MemoryType.SUMMARY
        else:
            mem_type = MemoryType.CONVERSATION

        # 保存用户消息
        user_msg = HumanMessage(content=user_message)
        user_metadata = metadata or {}
        if memory_type == "checkin":
            user_metadata["checkin_type"] = kwargs.get("checkin_type", "unknown")

        user_result = memory_manager.add_message(
            message=user_msg,
            memory_type=mem_type,
            metadata=user_metadata,
            sync_to_long_term=kwargs.get("sync_to_long_term", True),
        )

        # 保存助手回复（如果是对话类型）
        if memory_type == "conversation":
            assistant_msg = AIMessage(content=assistant_response)
            assistant_metadata = {
                "agent": kwargs.get("agent_name", "unknown"),
                "role": "assistant",
            }
            if metadata:
                assistant_metadata.update(metadata)

            assistant_result = memory_manager.add_message(
                message=assistant_msg,
                memory_type=mem_type,
                metadata=assistant_metadata,
                sync_to_long_term=kwargs.get("sync_to_long_term", True),
            )
        else:
            assistant_result = {"skipped": "not_conversation"}

        return {
            "success": True,
            "user_message_saved": user_result,
            "assistant_response_saved": assistant_result,
            "memory_type": memory_type,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"保存到记忆失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def get_memory_context(
    user_id: int, query: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """
    获取记忆上下文

    Args:
        user_id: 用户ID
        query: 查询文本（用于检索长期记忆）
        **kwargs: 额外参数

    Returns:
        上下文信息
    """
    try:
        memory_manager = MemoryManager(user_id)

        # 获取组合上下文
        context = memory_manager.get_context(
            checkin_limit=kwargs.get("checkin_limit", 10),
            conversation_limit=kwargs.get("conversation_limit", 10),
            include_long_term=kwargs.get("include_long_term", True),
            query=query,
        )

        # 获取用户画像
        user_profile = memory_manager.get_user_profile(
            force_refresh=kwargs.get("force_refresh_profile", False)
        )

        # 获取记忆统计
        stats = memory_manager.get_stats()

        return {
            "success": True,
            "context": context,
            "context_length": len(context),
            "user_profile": user_profile,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取记忆上下文失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def search_memories(user_id: int, query: str, **kwargs) -> Dict[str, Any]:
    """
    搜索记忆

    Args:
        user_id: 用户ID
        query: 搜索查询
        **kwargs: 额外参数

    Returns:
        搜索结果
    """
    try:
        memory_manager = MemoryManager(user_id)

        # 导入记忆类型
        from services.langchain.memory.typed_buffer import MemoryType

        # 确定记忆类型
        memory_type = kwargs.get("memory_type")
        if memory_type == "checkin":
            mem_type = MemoryType.CHECKIN
        elif memory_type == "conversation":
            mem_type = MemoryType.CONVERSATION
        else:
            mem_type = None

        # 执行搜索
        results = memory_manager.search_memories(
            query=query,
            memory_type=mem_type,
            limit=kwargs.get("limit", 10),
            include_short_term=kwargs.get("include_short_term", True),
            include_long_term=kwargs.get("include_long_term", True),
        )

        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results.get("short_term", []))
            + len(results.get("long_term", [])),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"搜索记忆失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def clear_memories(user_id: int, **kwargs) -> Dict[str, Any]:
    """
    清理记忆

    Args:
        user_id: 用户ID
        **kwargs: 额外参数

    Returns:
        清理结果
    """
    try:
        memory_manager = MemoryManager(user_id)

        # 导入记忆类型
        from services.langchain.memory.typed_buffer import MemoryType

        # 确定记忆类型
        memory_type = kwargs.get("memory_type")
        if memory_type == "checkin":
            mem_type = MemoryType.CHECKIN
        elif memory_type == "conversation":
            mem_type = MemoryType.CONVERSATION
        else:
            mem_type = None

        # 执行清理
        result = memory_manager.clear_memories(
            memory_type=mem_type,
            clear_short_term=kwargs.get("clear_short_term", True),
            clear_long_term=kwargs.get("clear_long_term", False),
        )

        # 清除Agent缓存
        if kwargs.get("clear_agent_cache", True):
            await AgentFactory.clear_cache(user_id)

        return {
            "success": True,
            "cleared_counts": result,
            "memory_type": memory_type,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"清理记忆失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


async def export_memories(user_id: int, **kwargs) -> Dict[str, Any]:
    """
    导出记忆数据

    Args:
        user_id: 用户ID
        **kwargs: 额外参数

    Returns:
        导出的记忆数据
    """
    try:
        memory_manager = MemoryManager(user_id)

        # 导出记忆
        export_data = memory_manager.export_memories(
            format=kwargs.get("format", "json")
        )

        return {
            "success": True,
            "export_data": export_data,
            "export_format": kwargs.get("format", "json"),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"导出记忆失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
