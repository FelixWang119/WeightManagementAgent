"""
LangGraph Nodes实现
5个核心节点：load_profile, refresh_checkins, coach, tools, finalize
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .state import CoachState, CoachGraphState
from .monitor import monitor_node, performance_monitor
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)

# 导入数据库模型
try:
    from models.database import (
        UserProfile,
        WeightRecord,
        MealRecord,
        ExerciseRecord,
        WaterRecord,
        SleepRecord,
        User,
        ChatHistory,
        AsyncSessionLocal,
    )

    HAS_DB_MODELS = True
except ImportError as e:
    logger.warning("无法导入数据库模型: %s", e)
    HAS_DB_MODELS = False


# ============ Node 1: 加载用户画像 ============


@monitor_node(graph_id="coach_graph")
async def load_profile_node(
    state: CoachGraphState, config: Optional[Dict[str, Any]] = None
) -> CoachGraphState:
    """
    加载用户画像节点
    从数据库加载用户基础信息和健康档案
    """
    start_time = time.time()
    user_id = state.get("user_id")

    if not user_id:
        logger.error("load_profile_node: 缺少 user_id")
        state["error"] = "缺少用户ID"
        return state

    logger.info("加载用户画像: user_id=%s", user_id)

    # 创建新的数据库会话（避免序列化问题）
    try:
        async with AsyncSessionLocal() as db:
            # 1. 加载用户基本信息
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning("用户不存在: user_id=%s", user_id)
                state["error"] = f"用户 {user_id} 不存在"
                return state

            # 2. 加载用户画像
            profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            profile_result = await db.execute(profile_stmt)
            profile_record = profile_result.scalar_one_or_none()

            # 3. 构建profile字典
            profile = {}
            if profile_record:
                # 将SQLAlchemy对象转换为字典
                profile = {
                    "nickname": user.nickname or "用户",
                    "gender": profile_record.gender,
                    "age": profile_record.age,
                    "height": profile_record.height,
                    "bmr": profile_record.bmr,
                    "diet_preferences": profile_record.diet_preferences,
                    "exercise_habits": profile_record.exercise_habits,
                    "weight_history": profile_record.weight_history,
                    "body_signals": profile_record.body_signals,
                    "motivation_type": profile_record.motivation_type.value
                    if profile_record.motivation_type
                    else None,
                    "weak_points": profile_record.weak_points,
                    "memory_summary": profile_record.memory_summary,
                    "decision_mode": profile_record.decision_mode,
                    "points": profile_record.points,
                    "communication_style": profile_record.communication_style,
                    "updated_at": profile_record.updated_at.isoformat()
                    if profile_record.updated_at
                    else None,
                }
            else:
                profile = {
                    "nickname": user.nickname or "用户",
                    "gender": None,
                    "age": None,
                    "height": None,
                    "bmr": None,
                    "diet_preferences": None,
                    "exercise_habits": None,
                    "weight_history": None,
                    "body_signals": None,
                    "motivation_type": None,
                    "weak_points": None,
                    "memory_summary": None,
                    "decision_mode": "balanced",
                    "points": 0,
                    "communication_style": None,
                }

            # 4. 更新state
            state["profile"] = profile

            # 5. 记录性能指标
            duration_ms = (time.time() - start_time) * 1000
            performance_monitor.record_node_execution(
                "coach_graph", "load_profile_node", duration_ms, True, user_id=user_id
            )

            logger.info(
                "用户画像加载完成: user_id=%s, 耗时=%.2fms", user_id, duration_ms
            )

            return state

    except Exception as e:
        logger.exception("加载用户画像失败: user_id=%s, 错误=%s", user_id, e)
        state["error"] = f"加载用户画像失败: {str(e)}"

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "load_profile_node",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return state


# ============ Node 2: 刷新打卡数据（5分钟缓存） ============


@monitor_node(graph_id="coach_graph")
async def refresh_checkins_node(
    state: CoachGraphState, config: Optional[Dict[str, Any]] = None
) -> CoachGraphState:
    """
    刷新打卡数据节点
    实现5分钟缓存机制，避免频繁查询数据库
    """
    start_time = time.time()
    user_id = state.get("user_id")

    if not user_id:
        logger.error("refresh_checkins_node: 缺少 user_id")
        state["error"] = "缺少用户ID"
        return state

    logger.info("刷新打卡数据: user_id=%s", user_id)

    try:
        async with AsyncSessionLocal() as db:
            # 检查是否需要刷新
            checkins = state.get("checkins", [])
            last_refresh = state.get("checkins_last_refresh")
            needs_refresh = state.get("needs_refresh", True)

            # 5分钟缓存逻辑
            cache_duration = 5 * 60  # 5分钟，单位秒
            should_refresh = needs_refresh

            if last_refresh:
                if isinstance(last_refresh, str):
                    last_refresh = datetime.fromisoformat(last_refresh)

                time_since_refresh = datetime.now() - last_refresh
                should_refresh = should_refresh or (
                    time_since_refresh.total_seconds() > cache_duration
                )

            if not should_refresh and checkins:
                # 使用缓存数据
                logger.debug(
                    "使用缓存打卡数据: user_id=%s, 上次刷新=%s, 缓存条目=%d",
                    user_id,
                    last_refresh,
                    len(checkins),
                )

                state["needs_refresh"] = False

                duration_ms = (time.time() - start_time) * 1000
                performance_monitor.record_node_execution(
                    "coach_graph",
                    "refresh_checkins_node",
                    duration_ms,
                    True,
                    user_id=user_id,
                    cache_hit=True,
                )

                return state

            # 需要刷新，从数据库加载数据
            logger.info("从数据库加载打卡数据: user_id=%s", user_id)

            # 计算时间范围：最近7天
            cutoff_time = datetime.now() - timedelta(days=7)

            # 1. 加载体重记录
            weight_stmt = (
                select(WeightRecord)
                .where(
                    and_(
                        WeightRecord.user_id == user_id,
                        WeightRecord.record_time >= cutoff_time,
                    )
                )
                .order_by(desc(WeightRecord.record_time))
                .limit(20)
            )
            weight_result = await db.execute(weight_stmt)
            weight_records = weight_result.scalars().all()

            # 2. 加载餐食记录
            meal_stmt = (
                select(MealRecord)
                .where(
                    and_(
                        MealRecord.user_id == user_id,
                        MealRecord.record_time >= cutoff_time,
                    )
                )
                .order_by(desc(MealRecord.record_time))
                .limit(30)
            )
            meal_result = await db.execute(meal_stmt)
            meal_records = meal_result.scalars().all()

            # 3. 加载运动记录
            exercise_stmt = (
                select(ExerciseRecord)
                .where(
                    and_(
                        ExerciseRecord.user_id == user_id,
                        ExerciseRecord.record_time >= cutoff_time,
                    )
                )
                .order_by(desc(ExerciseRecord.record_time))
                .limit(20)
            )
            exercise_result = await db.execute(exercise_stmt)
            exercise_records = exercise_result.scalars().all()

            # 4. 加载饮水记录
            water_stmt = (
                select(WaterRecord)
                .where(
                    and_(
                        WaterRecord.user_id == user_id,
                        WaterRecord.record_time >= cutoff_time,
                    )
                )
                .order_by(desc(WaterRecord.record_time))
                .limit(20)
            )
            water_result = await db.execute(water_stmt)
            water_records = water_result.scalars().all()

            # 5. 加载睡眠记录（SleepRecord没有record_time字段，使用created_at）
            sleep_stmt = (
                select(SleepRecord)
                .where(
                    and_(
                        SleepRecord.user_id == user_id,
                        SleepRecord.created_at >= cutoff_time,
                    )
                )
                .order_by(desc(SleepRecord.created_at))
                .limit(20)
            )
            sleep_result = await db.execute(sleep_stmt)
            sleep_records = sleep_result.scalars().all()

            # 6. 构建统一的打卡数据格式
            checkins_data = []

            # 处理体重记录
            for record in weight_records:
                checkins_data.append(
                    {
                        "type": "weight",
                        "timestamp": record.record_time.isoformat()
                        if record.record_time
                        else None,
                        "data": {
                            "weight": record.weight,
                            "body_fat": record.body_fat,
                            "note": record.note,
                        },
                        "source": "database",
                    }
                )

            # 处理餐食记录
            for record in meal_records:
                checkins_data.append(
                    {
                        "type": "meal",
                        "timestamp": record.record_time.isoformat()
                        if record.record_time
                        else None,
                        "data": {
                            "meal_type": record.meal_type.value
                            if record.meal_type
                            else None,
                            "food_items": record.food_items or [],
                            "total_calories": record.total_calories,
                        },
                        "source": "database",
                    }
                )

            # 处理运动记录
            for record in exercise_records:
                checkins_data.append(
                    {
                        "type": "exercise",
                        "timestamp": record.record_time.isoformat()
                        if record.record_time
                        else None,
                        "data": {
                            "exercise_type": record.exercise_type,
                            "duration_minutes": record.duration_minutes,
                            "calories_burned": record.calories_burned,
                            "intensity": record.intensity.value
                            if record.intensity
                            else None,
                        },
                        "source": "database",
                    }
                )

            # 处理饮水记录
            for record in water_records:
                checkins_data.append(
                    {
                        "type": "water",
                        "timestamp": record.record_time.isoformat()
                        if record.record_time
                        else None,
                        "data": {
                            "amount_ml": record.amount_ml,
                        },
                        "source": "database",
                    }
                )

            # 处理睡眠记录
            for record in sleep_records:
                # 计算睡眠时长（小时）
                sleep_duration_hours = None
                if record.bed_time and record.wake_time:
                    sleep_duration_hours = (
                        record.wake_time - record.bed_time
                    ).total_seconds() / 3600

                checkins_data.append(
                    {
                        "type": "sleep",
                        "timestamp": record.created_at.isoformat()
                        if record.created_at
                        else None,
                        "data": {
                            "sleep_duration_hours": sleep_duration_hours,
                            "total_minutes": record.total_minutes,
                            "quality": record.quality,
                            "bed_time": record.bed_time.isoformat()
                            if record.bed_time
                            else None,
                            "wake_time": record.wake_time.isoformat()
                            if record.wake_time
                            else None,
                        },
                        "source": "database",
                    }
                )

            # 7. 按时间排序（最新的在前）
            checkins_data.sort(key=lambda x: x["timestamp"] or "", reverse=True)

            # 8. 更新state
            state["checkins"] = checkins_data
            state["checkins_last_refresh"] = datetime.now().isoformat()
            state["needs_refresh"] = False

            # 9. 记录性能指标
            duration_ms = (time.time() - start_time) * 1000
            performance_monitor.record_node_execution(
                "coach_graph",
                "refresh_checkins_node",
                duration_ms,
                True,
                user_id=user_id,
                cache_hit=False,
                record_counts={
                    "weight": len(weight_records),
                    "meal": len(meal_records),
                    "exercise": len(exercise_records),
                    "water": len(water_records),
                    "sleep": len(sleep_records),
                },
            )

            logger.info(
                "打卡数据刷新完成: user_id=%s, 耗时=%.2fms, 记录数=%d",
                user_id,
                duration_ms,
                len(checkins_data),
            )

            return state

    except Exception as e:
        logger.exception("刷新打卡数据失败: user_id=%s, 错误=%s", user_id, e)
        state["error"] = f"刷新打卡数据失败: {str(e)}"

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "refresh_checkins_node",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return state


# ============ Node 3: 教练核心逻辑 ============


@monitor_node(graph_id="coach_graph")
async def coach_node(
    state: CoachGraphState, config: Optional[Dict[str, Any]] = None
) -> CoachGraphState:
    """
    教练核心节点
    分析用户数据，生成个性化回复和工具调用建议
    """
    start_time = time.time()
    user_id = state.get("user_id")
    user_message = state.get("user_message", "")

    logger.info("教练节点执行: user_id=%s, 消息长度=%d", user_id, len(user_message))

    try:
        # 1. 准备数据
        profile = state.get("profile", {})
        checkins = state.get("checkins", [])

        # 2. 分析用户意图（简化实现）
        # 在实际应用中，这里可以使用NLP模型分析意图
        intent = _analyze_user_intent(user_message, checkins)

        # 3. 构建系统提示
        system_prompt = _build_system_prompt(profile, checkins, intent)

        # 4. 构建对话历史
        conversation_history = state.get("conversation_history", [])

        # 5. 构建完整消息
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history[-5:],  # 最近5条对话
            {"role": "user", "content": user_message},
        ]

        # 6. 调用AI服务
        # 注意：这里需要导入ai_service，暂时使用模拟响应
        ai_response = await _call_ai_service(messages)

        # 7. 分析是否需要工具调用
        tool_calls_needed = _analyze_tool_needs(intent, ai_response)

        # 8. 更新state
        state["assistant_response"] = ai_response
        state["current_tools"] = tool_calls_needed
        state["structured_response"] = {
            "type": "text",
            "content": ai_response,
            "actions": _extract_actions(ai_response),
        }

        # 9. 记录中间步骤
        intermediate_steps = state.get("intermediate_steps", [])
        intermediate_steps.append(
            {
                "step": "coach_analysis",
                "data": {
                    "intent": intent,
                    "tool_calls_needed": tool_calls_needed,
                    "prompt_length": len(system_prompt),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["intermediate_steps"] = intermediate_steps

        # 10. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "coach_node",
            duration_ms,
            True,
            user_id=user_id,
            intent=intent,
            has_tools=bool(tool_calls_needed),
        )

        logger.info(
            "教练节点完成: user_id=%s, 耗时=%.2fms, 意图=%s, 工具=%s",
            user_id,
            duration_ms,
            intent,
            tool_calls_needed,
        )

        return state

    except Exception as e:
        logger.exception("教练节点失败: user_id=%s, 错误=%s", user_id, e)
        state["error"] = f"教练处理失败: {str(e)}"
        state["assistant_response"] = (
            "抱歉，我在处理您的请求时遇到了一些困难。请稍后再试或联系技术支持。"
        )

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "coach_node",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return state


# ============ Node 4: 工具调用节点 ============


@monitor_node(graph_id="coach_graph")
async def tools_node(
    state: CoachGraphState, config: Optional[Dict[str, Any]] = None
) -> CoachGraphState:
    """
    工具调用节点
    根据coach_node的建议，调用相应的工具
    """
    start_time = time.time()
    user_id = state.get("user_id")
    tool_calls = state.get("current_tools", [])

    logger.info("工具节点执行: user_id=%s, 工具数=%d", user_id, len(tool_calls))

    try:
        if not tool_calls:
            # 没有需要调用的工具，直接返回
            logger.debug("没有需要调用的工具: user_id=%s", user_id)
            return state

        # 记录工具调用历史
        tool_calls_history = state.get("tool_calls", [])

        # 导入工具函数
        from .tools import (
            analyze_weight_trends_tool,
            search_long_term_memory_tool,
            calculate_bmi_tool,
            get_checkin_history_tool,
        )

        # 工具映射
        tool_map = {
            "analyze_weight_trends": analyze_weight_trends_tool,
            "search_long_term_memory": search_long_term_memory_tool,
            "calculate_bmi": calculate_bmi_tool,
            "get_checkin_history": get_checkin_history_tool,
        }

        # 执行工具调用
        tool_results = []
        for tool_name in tool_calls:
            if tool_name in tool_map:
                logger.info("调用工具: user_id=%s, tool=%s", user_id, tool_name)

                tool_start_time = time.time()

                try:
                    # 准备工具参数
                    tool_params = _prepare_tool_params(tool_name, state)

                    # 调用工具
                    tool_result = await tool_map[tool_name](**tool_params)

                    tool_duration_ms = (time.time() - tool_start_time) * 1000

                    # 记录工具调用
                    tool_call_record = {
                        "tool": tool_name,
                        "params": tool_params,
                        "result": tool_result,
                        "duration_ms": tool_duration_ms,
                        "timestamp": datetime.now().isoformat(),
                    }
                    tool_calls_history.append(tool_call_record)
                    tool_results.append(tool_result)

                    # 记录工具指标
                    performance_monitor.record_tool_call(
                        "coach_graph",
                        tool_name,
                        tool_duration_ms,
                        True,
                        user_id=user_id,
                    )

                    logger.info(
                        "工具调用成功: user_id=%s, tool=%s, 耗时=%.2fms",
                        user_id,
                        tool_name,
                        tool_duration_ms,
                    )

                except Exception as tool_error:
                    tool_duration_ms = (time.time() - tool_start_time) * 1000
                    logger.error(
                        "工具调用失败: user_id=%s, tool=%s, 错误=%s",
                        user_id,
                        tool_name,
                        tool_error,
                    )

                    tool_call_record = {
                        "tool": tool_name,
                        "params": tool_params,
                        "error": str(tool_error),
                        "duration_ms": tool_duration_ms,
                        "timestamp": datetime.now().isoformat(),
                    }
                    tool_calls_history.append(tool_call_record)

                    # 记录失败指标
                    performance_monitor.record_tool_call(
                        "coach_graph",
                        tool_name,
                        tool_duration_ms,
                        False,
                        user_id=user_id,
                        error=str(tool_error),
                    )
            else:
                logger.warning("未知工具: user_id=%s, tool=%s", user_id, tool_name)

        # 更新state
        state["tool_calls"] = tool_calls_history

        # 如果有工具结果，整合到回复中
        if tool_results:
            # 记录到中间步骤
            intermediate_steps = state.get("intermediate_steps", [])
            intermediate_steps.append(
                {
                    "step": "tool_execution",
                    "data": {
                        "tools_called": tool_calls,
                        "results_count": len(tool_results),
                        "results": tool_results,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
            state["intermediate_steps"] = intermediate_steps

            # 构建工具结果摘要，让AI能看到具体内容
            tool_summary = "\n\n【系统数据】\n"
            for result in tool_results:
                if result.get("success"):
                    if "checkins" in result:
                        tool_summary += f"用户近期打卡记录：\n"
                        for checkin in result["checkins"][:5]:  # 最多显示5条
                            checkin_type = checkin.get("type", "unknown")
                            timestamp = checkin.get("timestamp", "")
                            data = checkin.get("data", {})
                            if checkin_type == "meal":
                                food_items = data.get("food_items", [])
                                total_calories = data.get("total_calories", 0)
                                food_names = [
                                    item.get("name", "未知食物") for item in food_items
                                ]
                                tool_summary += f"- 餐食 ({timestamp}): {', '.join(food_names)} - {total_calories}卡\n"
                            elif checkin_type == "weight":
                                weight = data.get("weight", 0)
                                tool_summary += f"- 体重 ({timestamp}): {weight}kg\n"
                            elif checkin_type == "exercise":
                                exercise_type = data.get("exercise_type", "运动")
                                duration = data.get("duration_minutes", 0)
                                calories = data.get("calories_burned", 0)
                                tool_summary += f"- 运动 ({timestamp}): {exercise_type} {duration}分钟，消耗{calories}卡\n"
                            elif checkin_type == "water":
                                amount = data.get("amount_ml", 0)
                                tool_summary += f"- 饮水 ({timestamp}): {amount}ml\n"
                            elif checkin_type == "sleep":
                                total_minutes = data.get("total_minutes", 0)
                                quality = data.get("quality", 0)
                                tool_summary += f"- 睡眠 ({timestamp}): {total_minutes // 60}小时{total_minutes % 60}分钟，质量{quality}星\n"

            # 将工具结果追加到assistant_response
            current_response = state.get("assistant_response", "")
            if current_response:
                state["assistant_response"] = current_response + tool_summary

        # 记录节点性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "tools_node",
            duration_ms,
            True,
            user_id=user_id,
            tools_called=tool_calls,
        )

        logger.info(
            "工具节点完成: user_id=%s, 耗时=%.2fms, 成功工具数=%d",
            user_id,
            duration_ms,
            len(tool_results),
        )

        return state

    except Exception as e:
        logger.exception("工具节点失败: user_id=%s, 错误=%s", user_id, e)
        state["error"] = f"工具调用失败: {str(e)}"

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "tools_node",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return state


# ============ Node 5: 最终化节点 ============


@monitor_node(graph_id="coach_graph")
async def finalize_node(
    state: CoachGraphState, config: Optional[Dict[str, Any]] = None
) -> CoachGraphState:
    """
    最终化节点
    保存对话记录，清理状态，返回最终结果
    """
    start_time = time.time()
    user_id = state.get("user_id")

    logger.info("最终化节点执行: user_id=%s", user_id)

    try:
        async with AsyncSessionLocal() as db:
            # 1. 保存对话记录到数据库
            user_message = state.get("user_message")
        assistant_response = state.get("assistant_response")

        if user_message and assistant_response and HAS_DB_MODELS:
            # 保存用户消息
            user_msg = ChatHistory(
                user_id=user_id,
                role="user",
                content=user_message,
                created_at=datetime.now(),
            )
            db.add(user_msg)

            # 保存助手回复
            assistant_msg = ChatHistory(
                user_id=user_id,
                role="assistant",
                content=assistant_response,
                created_at=datetime.now(),
            )
            db.add(assistant_msg)

            await db.commit()
            logger.info("对话记录已保存: user_id=%s", user_id)

        # 2. 更新对话历史
        conversation_history = state.get("conversation_history", [])
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append(
            {"role": "assistant", "content": assistant_response}
        )

        # 限制历史长度
        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]

        state["conversation_history"] = conversation_history

        # 3. 清理临时状态
        state["needs_refresh"] = False  # 下次对话时再决定是否刷新

        # 4. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph", "finalize_node", duration_ms, True, user_id=user_id
        )

        logger.info("最终化节点完成: user_id=%s, 耗时=%.2fms", user_id, duration_ms)

        return state

    except Exception as e:
        logger.exception("最终化节点失败: user_id=%s, 错误=%s", user_id, e)
        state["error"] = f"最终化处理失败: {str(e)}"

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_node_execution(
            "coach_graph",
            "finalize_node",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return state


# ============ 辅助函数 ============


def _analyze_user_intent(user_message: str, checkins: List[Dict]) -> str:
    """分析用户意图（简化实现）"""
    user_message_lower = user_message.lower()

    # 关键词匹配
    weight_keywords = ["体重", "减肥", "增重", "胖", "瘦", "公斤", "斤", "bmi", "体脂"]
    meal_keywords = ["吃", "饭", "餐", "食物", "热量", "卡路里", "早餐", "午餐", "晚餐"]
    exercise_keywords = ["运动", "锻炼", "跑步", "健身", "瑜伽", "游泳", "卡路里消耗"]
    water_keywords = ["水", "喝水", "饮水", "毫升", "ml"]
    sleep_keywords = ["睡", "失眠", "熬夜", "睡眠", "起床", "就寝"]
    memory_keywords = ["记得", "以前", "上次", "历史", "记录"]
    general_keywords = ["你好", "谢谢", "帮助", "建议", "怎么办", "如何"]

    if any(keyword in user_message_lower for keyword in weight_keywords):
        return "weight_analysis"
    elif any(keyword in user_message_lower for keyword in meal_keywords):
        return "meal_analysis"
    elif any(keyword in user_message_lower for keyword in exercise_keywords):
        return "exercise_analysis"
    elif any(keyword in user_message_lower for keyword in water_keywords):
        return "water_analysis"
    elif any(keyword in user_message_lower for keyword in sleep_keywords):
        return "sleep_analysis"
    elif any(keyword in user_message_lower for keyword in memory_keywords):
        return "memory_search"
    elif any(keyword in user_message_lower for keyword in general_keywords):
        return "general_advice"
    else:
        return "unknown"


def _build_system_prompt(profile: Dict, checkins: List[Dict], intent: str) -> str:
    """构建系统提示"""
    base_prompt = """你是一个专业的体重管理助手，专注于帮助用户管理体重和健康。

你的职责：
1. 分析用户的体重变化趋势
2. 提供科学的减肥/增重建议
3. 结合用户的饮食和运动记录给出综合建议
4. 鼓励用户保持健康习惯
5. 回答与体重管理相关的问题

请保持专业、友好、鼓励的态度。"""

    # 添加用户画像信息
    profile_info = "用户信息：\n"
    if profile:
        for key, value in profile.items():
            if value:
                profile_info += f"- {key}: {value}\n"
    else:
        profile_info += "- 用户信息不完整，请引导用户完善\n"

    # 添加近期数据摘要
    data_summary = "近期打卡记录详情（最近7天）：\n"
    if checkins:
        # 按类型统计
        type_counts = {}
        for checkin in checkins:
            checkin_type = checkin.get("type")
            type_counts[checkin_type] = type_counts.get(checkin_type, 0) + 1

        # 显示统计
        data_summary += "统计："
        for checkin_type, count in type_counts.items():
            data_summary += f"{checkin_type}({count}条) "
        data_summary += "\n\n具体记录：\n"

        # 显示具体记录（最多10条）
        for i, checkin in enumerate(checkins[:10]):
            checkin_type = checkin.get("type", "unknown")
            timestamp = checkin.get("timestamp", "")
            data = checkin.get("data", {})

            if checkin_type == "meal":
                food_items = data.get("food_items", [])
                total_calories = data.get("total_calories", 0)
                food_names = [
                    item.get("name", "未知食物") for item in food_items[:3]
                ]  # 最多显示3个食物
                meal_type = data.get("meal_type", "餐食")
                data_summary += f"{i + 1}. [{meal_type}] {', '.join(food_names)} - {total_calories}卡 ({timestamp})\n"
            elif checkin_type == "weight":
                weight = data.get("weight", 0)
                body_fat = data.get("body_fat")
                body_fat_str = f", 体脂{body_fat}%" if body_fat else ""
                data_summary += (
                    f"{i + 1}. [体重] {weight}kg{body_fat_str} ({timestamp})\n"
                )
            elif checkin_type == "exercise":
                exercise_type = data.get("exercise_type", "运动")
                duration = data.get("duration_minutes", 0)
                calories = data.get("calories_burned", 0)
                data_summary += f"{i + 1}. [运动] {exercise_type} {duration}分钟, 消耗{calories}卡 ({timestamp})\n"
            elif checkin_type == "water":
                amount = data.get("amount_ml", 0)
                data_summary += f"{i + 1}. [饮水] {amount}ml ({timestamp})\n"
            elif checkin_type == "sleep":
                total_minutes = data.get("total_minutes", 0)
                quality = data.get("quality", 0)
                hours = total_minutes // 60
                minutes = total_minutes % 60
                data_summary += f"{i + 1}. [睡眠] {hours}小时{minutes}分钟, 质量{quality}星 ({timestamp})\n"
    else:
        data_summary += "- 暂无近期记录\n"

    # 根据意图调整提示
    intent_prompts = {
        "weight_analysis": "用户正在咨询体重相关问题，请重点分析体重趋势并提供专业建议。",
        "meal_analysis": "用户正在咨询饮食相关问题，请结合饮食记录给出营养建议。",
        "exercise_analysis": "用户正在咨询运动相关问题，请提供运动建议和激励。",
        "general_advice": "用户需要一般性健康建议，请提供综合性的指导。",
    }

    intent_prompt = intent_prompts.get(intent, "请根据用户问题提供专业、个性化的回复。")

    # 组合完整提示
    full_prompt = f"""{base_prompt}

{profile_info}

{data_summary}

{intent_prompt}

请根据以上信息，以专业体重管理助手的身份回复用户。"""

    return full_prompt


async def _call_ai_service(messages: List[Dict]) -> str:
    """调用AI服务（简化实现，实际应使用现有ai_service）"""
    try:
        # 尝试导入现有ai_service
        from services.ai_service import ai_service

        response = await ai_service.chat(messages, max_tokens=500)
        if hasattr(response, "content"):
            return response.content
        elif isinstance(response, dict) and "content" in response:
            return response["content"]
        else:
            return str(response)
    except ImportError:
        # 如果ai_service不可用，返回模拟响应
        logger.warning("ai_service不可用，使用模拟响应")
        return "我收到您的消息了。基于您的健康数据，我建议您继续保持规律的生活习惯，均衡饮食，适量运动。如果您有具体问题，可以告诉我更多细节。"


def _analyze_tool_needs(intent: str, ai_response: str) -> List[str]:
    """分析是否需要工具调用"""
    tool_needs = []

    # 根据意图决定工具
    if intent == "weight_analysis":
        tool_needs.append("analyze_weight_trends")
        tool_needs.append("calculate_bmi")
    elif intent == "memory_search":
        tool_needs.append("search_long_term_memory")
    elif intent in [
        "meal_analysis",
        "exercise_analysis",
        "water_analysis",
        "sleep_analysis",
    ]:
        tool_needs.append("get_checkin_history")

    # 根据AI回复内容决定工具
    if "历史" in ai_response or "记录" in ai_response:
        tool_needs.append("get_checkin_history")

    if "趋势" in ai_response or "变化" in ai_response:
        tool_needs.append("analyze_weight_trends")

    if "bmi" in ai_response.lower():
        tool_needs.append("calculate_bmi")

    # 去重
    return list(set(tool_needs))


def _extract_actions(ai_response: str) -> List[Dict]:
    """从AI回复中提取行动建议"""
    actions = []

    # 简单的关键词匹配
    keywords = {
        "记录体重": {"type": "weight_record", "label": "记录体重"},
        "记录饮食": {"type": "meal_record", "label": "记录饮食"},
        "记录运动": {"type": "exercise_record", "label": "记录运动"},
        "查看历史": {"type": "view_history", "label": "查看历史"},
    }

    for keyword, action_info in keywords.items():
        if keyword in ai_response:
            actions.append(action_info)

    return actions


def _prepare_tool_params(tool_name: str, state: Dict) -> Dict:
    """准备工具参数"""
    base_params = {
        "user_id": state.get("user_id"),
        "checkins": state.get("checkins", []),
    }

    # 只有需要profile的工具才添加
    tools_needing_profile = ["analyze_weight_trends", "calculate_bmi"]
    if tool_name in tools_needing_profile:
        base_params["profile"] = state.get("profile", {})

    # 为搜索工具添加query
    if tool_name == "search_long_term_memory":
        base_params["query"] = state.get("user_message", "")

    return base_params
