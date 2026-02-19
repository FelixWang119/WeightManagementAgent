"""
LangGraph State定义
使用TypedDict定义结构化对话状态，支持打卡数据缓存和工具调用
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator


# 定义State结构
class CoachState(TypedDict):
    """体重教练对话状态"""

    # 基础信息
    user_id: int
    user_message: str
    assistant_response: str

    # 用户数据
    profile: Dict[str, Any]  # 用户画像（来自数据库）
    checkins: List[Dict[str, Any]]  # 打卡记录（带5分钟缓存）
    checkins_last_refresh: Optional[datetime]  # 上次刷新时间

    # 对话管理
    conversation_history: List[Dict[str, str]]  # 对话历史（用于上下文）
    current_tools: List[str]  # 当前可用的工具列表
    tool_calls: List[Dict[str, Any]]  # 工具调用历史

    # 系统状态
    needs_refresh: bool  # 是否需要刷新打卡数据
    error: Optional[str]  # 错误信息
    metrics: Dict[str, Any]  # 性能指标

    # 输出结果
    structured_response: Dict[str, Any]  # 结构化响应
    intermediate_steps: List[Dict[str, Any]]  # 中间步骤记录


# 创建合成State类型，用于LangGraph
from langgraph.graph import add_messages
from langchain_core.messages import AnyMessage


# 定义消息State
class MessagesState(TypedDict):
    """消息State（用于LangGraph的消息流）"""

    messages: Annotated[List[AnyMessage], add_messages]


# 定义完整的CoachState合成类型
CoachGraphState = Annotated[Dict[str, Any], operator.add]
