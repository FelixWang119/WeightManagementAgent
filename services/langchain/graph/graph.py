"""
LangGraph Graph构建
定义对话流程图、边、条件流转和持久化检查点
简化版本：使用内存检查点，避免复杂的导入问题
"""

from typing import Dict, Any, Optional, Literal
import asyncio
import time

from langgraph.graph import StateGraph, END
from .state import CoachState
from .nodes import (
    load_profile_node,
    refresh_checkins_node,
    coach_node,
    tools_node,
    finalize_node,
)
from .monitor import performance_monitor, get_performance_summary
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


def create_coach_graph(
    use_checkpoint: bool = True,
    graph_id: str = "coach_graph",
) -> StateGraph:
    """
    创建教练对话图（简化版本）

    Args:
        use_checkpoint: 是否使用检查点（内存检查点）
        graph_id: 图ID，用于监控

    Returns:
        配置好的StateGraph
    """
    logger.info(
        "创建教练对话图: graph_id=%s, use_checkpoint=%s", graph_id, use_checkpoint
    )
    start_time = time.time()

    try:
        # 1. 创建图
        workflow = StateGraph(CoachState)

        # 2. 添加节点
        workflow.add_node("load_profile", load_profile_node)
        workflow.add_node("refresh_checkins", refresh_checkins_node)
        workflow.add_node("coach", coach_node)
        workflow.add_node("tools", tools_node)
        workflow.add_node("finalize", finalize_node)

        # 3. 设置入口点
        workflow.set_entry_point("load_profile")

        # 4. 定义边和条件流转
        # 4.1 load_profile -> refresh_checkins
        workflow.add_edge("load_profile", "refresh_checkins")

        # 4.2 refresh_checkins -> coach
        workflow.add_edge("refresh_checkins", "coach")

        # 4.3 coach -> tools 或 finalize（条件流转）
        def should_use_tools(state: CoachState) -> Literal["tools", "finalize"]:
            """判断是否需要调用工具"""
            tool_calls = state.get("current_tools", [])
            error = state.get("error")

            if error:
                logger.warning("检测到错误，跳过工具调用: error=%s", error)
                return "finalize"

            if tool_calls:
                logger.info("需要调用工具: tools=%s", tool_calls)
                return "tools"
            else:
                logger.debug("无需工具调用，直接结束")
                return "finalize"

        workflow.add_conditional_edges(
            "coach",
            should_use_tools,
            {
                "tools": "tools",
                "finalize": "finalize",
            },
        )

        # 4.4 tools -> finalize
        workflow.add_edge("tools", "finalize")

        # 4.5 finalize -> END
        workflow.add_edge("finalize", END)

        # 5. 编译图
        if use_checkpoint:
            try:
                from langgraph.checkpoint.memory import MemorySaver

                checkpointer = MemorySaver()
                workflow = workflow.compile(checkpointer=checkpointer)
                logger.info("已配置内存检查点保存器")
            except ImportError as e:
                logger.warning("无法导入MemorySaver，不使用检查点: %s", e)
                workflow = workflow.compile()
                logger.info("使用无检查点模式")
        else:
            workflow = workflow.compile()
            logger.info("使用无检查点模式")

        # 6. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_graph_invocation(
            graph_id,
            duration_ms,
            nodes_count=5,
            has_checkpointer=use_checkpoint,
        )

        logger.info(
            "教练对话图创建完成: graph_id=%s, 耗时=%.2fms", graph_id, duration_ms
        )

        return workflow

    except Exception as e:
        logger.exception("创建教练对话图失败: graph_id=%s, 错误=%s", graph_id, e)
        raise


# 全局图实例缓存
_graph_cache: Dict[str, StateGraph] = {}
_graph_cache_lock = asyncio.Lock()


async def get_graph(
    graph_id: str = "coach_graph",
    use_checkpoint: bool = True,
) -> StateGraph:
    """
    获取图实例（带缓存）

    Args:
        graph_id: 图ID
        use_checkpoint: 是否使用检查点

    Returns:
        图实例
    """
    async with _graph_cache_lock:
        cache_key = f"{graph_id}_{use_checkpoint}"

        if cache_key in _graph_cache:
            logger.debug("从缓存获取图实例: cache_key=%s", cache_key)
            return _graph_cache[cache_key]

        # 创建图
        graph = create_coach_graph(use_checkpoint, graph_id)

        # 缓存图实例
        _graph_cache[cache_key] = graph
        logger.info("创建并缓存图实例: cache_key=%s", cache_key)

        return graph


async def invoke_graph(
    user_id: int,
    user_message: str,
    db=None,
    graph_id: str = "coach_graph",
    thread_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    调用图处理用户消息

    Args:
        user_id: 用户ID
        user_message: 用户消息
        db: 数据库会话（已废弃，保留参数以保持兼容）
        graph_id: 图ID
        thread_id: 线程ID（用于检查点）
        config: 额外配置

    Returns:
        处理结果
    """
    start_time = time.time()
    logger.info(
        "调用图处理消息: user_id=%s, thread_id=%s, 消息长度=%d",
        user_id,
        thread_id,
        len(user_message),
    )

    try:
        # 1. 获取图实例
        graph = await get_graph(graph_id, use_checkpoint=True)

        # 2. 准备初始状态
        initial_state: CoachState = {
            "user_id": user_id,
            "user_message": user_message,
            "assistant_response": "",
            "profile": {},
            "checkins": [],
            "checkins_last_refresh": None,
            "conversation_history": [],
            "current_tools": [],
            "tool_calls": [],
            "needs_refresh": True,
            "error": None,
            "metrics": {},
            "structured_response": {
                "type": "text",
                "content": "",
                "actions": [],
            },
            "intermediate_steps": [],
        }

        # 3. 准备配置
        if thread_id is None:
            thread_id = f"user_{user_id}_{int(time.time())}"

        graph_config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        if config:
            graph_config["configurable"].update(config)

        # 4. 调用图
        logger.info("开始图执行: user_id=%s, thread_id=%s", user_id, thread_id)

        # 注意：这里需要确保节点函数能够从config中获取db参数
        final_state = await graph.ainvoke(
            initial_state,
            config=graph_config,
        )

        # 5. 提取结果
        result = {
            "success": True,
            "user_id": user_id,
            "thread_id": thread_id,
            "assistant_response": final_state.get("assistant_response", ""),
            "structured_response": final_state.get("structured_response", {}),
            "intermediate_steps": final_state.get("intermediate_steps", []),
            "tool_calls": final_state.get("tool_calls", []),
            "error": final_state.get("error"),
            "profile_loaded": bool(final_state.get("profile")),
            "checkins_loaded": len(final_state.get("checkins", [])),
            "conversation_history_length": len(
                final_state.get("conversation_history", [])
            ),
        }

        # 6. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_graph_invocation(
            graph_id, duration_ms, user_id=user_id, thread_id=thread_id, success=True
        )

        logger.info(
            "图调用完成: user_id=%s, thread_id=%s, 耗时=%.2fms, 响应长度=%d",
            user_id,
            thread_id,
            duration_ms,
            len(result["assistant_response"]),
        )

        return result

    except Exception as e:
        logger.exception(
            "图调用失败: user_id=%s, thread_id=%s, 错误=%s", user_id, thread_id, e
        )

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_graph_invocation(
            graph_id,
            duration_ms,
            user_id=user_id,
            thread_id=thread_id,
            success=False,
            error=str(e),
        )

        return {
            "success": False,
            "user_id": user_id,
            "thread_id": thread_id,
            "assistant_response": "抱歉，我在处理您的请求时遇到了一些困难。请稍后再试或联系技术支持。",
            "structured_response": {
                "type": "text",
                "content": "抱歉，我在处理您的请求时遇到了一些困难。请稍后再试或联系技术支持。",
                "actions": [],
            },
            "error": str(e),
            "timestamp": time.time(),
        }


async def get_graph_performance_summary(
    graph_id: str = "coach_graph",
) -> Dict[str, Any]:
    """获取图性能摘要"""
    try:
        summary = await get_performance_summary(graph_id)
        return {
            "success": True,
            "graph_id": graph_id,
            "summary": summary,
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.exception("获取图性能摘要失败: graph_id=%s, 错误=%s", graph_id, e)
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time(),
        }


async def reset_graph_cache(graph_id: Optional[str] = None):
    """重置图缓存"""
    async with _graph_cache_lock:
        if graph_id:
            # 重置特定图ID的所有变体
            keys_to_remove = [
                key for key in _graph_cache.keys() if key.startswith(graph_id)
            ]
            for key in keys_to_remove:
                del _graph_cache[key]
            logger.info(
                "重置图缓存: graph_id=%s, 移除键数=%d", graph_id, len(keys_to_remove)
            )
        else:
            # 重置所有缓存
            cache_size = len(_graph_cache)
            _graph_cache.clear()
            logger.info("重置所有图缓存: 缓存大小=%d", cache_size)


# 导出便捷函数
__all__ = [
    "create_coach_graph",
    "get_graph",
    "invoke_graph",
    "get_graph_performance_summary",
    "reset_graph_cache",
]
