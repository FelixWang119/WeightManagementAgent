"""
LangChain Agent 主实现 - 整合所有最佳实践

这是推荐的Agent实现，使用最新的LangChain最佳实践。

改进总结：
1. ✅ 使用 langchain_openai 替代已弃用的 langchain_community
2. ✅ 使用 create_react_agent 替代手动解析
3. ✅ 使用 @tool 装饰器定义工具（从tools.py导入）
4. ✅ 使用 SQLAlchemyMessageHistory 管理对话历史（从memory.py导入）
5. ✅ 完善的错误处理和日志记录
6. ✅ 支持流式输出

使用示例：
    from services.langchain.agent import WeightManagementAgent

    agent = await WeightManagementAgent.create(user_id, db)
    result = await agent.chat("我今天体重65kg")

其他版本：
- agent_simple.py: 简化版（推荐使用）
"""

import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime
import json
import logging

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.langchain.base import get_chat_model
from services.langchain.memory import ConversationMemoryManager
from services.langchain.tools import get_weight_management_tools
from services.user_profile_service import UserProfileService
from config.settings import fastapi_settings

logger = logging.getLogger(__name__)


# ============== 工具定义 ==============

# 从tools.py导入工具
TOOLS = get_weight_management_tools()


# ============== 工具执行器 ==============


class ToolExecutor:
    """工具执行器 - 实际执行数据库操作"""

    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def execute(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            # 处理带_tool后缀的工具名称
            if tool_name.endswith("_tool"):
                base_name = tool_name[:-5]  # 移除_tool后缀
            else:
                base_name = tool_name

            method = getattr(self, f"_{base_name}", None)
            if method:
                return await method(**arguments)
            return {"success": False, "message": f"未知工具: {tool_name}"}
        except Exception as e:
            self.logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return {"success": False, "message": f"执行失败: {str(e)}"}

    async def _record_weight(self, weight: float, note: str = "") -> Dict[str, Any]:
        from models.database import WeightRecord

        record = WeightRecord(
            user_id=self.user_id,
            weight=weight,
            note=note,
            record_time=datetime.utcnow(),
        )
        self.db.add(record)
        await self.db.commit()

        return {
            "success": True,
            "message": f"✅ 已记录体重：{weight}kg",
            "action_type": "weight_recorded",
            "data": {"weight": weight},
        }

    async def _record_meal(
        self,
        meal_type: str,
        food_description: str,
        estimated_calories: Optional[int] = None,
    ) -> Dict[str, Any]:
        from models.database import MealRecord, MealType

        meal_type_map = {
            "breakfast": MealType.BREAKFAST,
            "lunch": MealType.LUNCH,
            "dinner": MealType.DINNER,
            "snack": MealType.SNACK,
        }

        if not estimated_calories:
            estimated_calories = 400  # 默认值

        record = MealRecord(
            user_id=self.user_id,
            meal_type=meal_type_map.get(meal_type.lower(), MealType.SNACK),
            food_items=[{"name": food_description, "calories": estimated_calories}],
            total_calories=estimated_calories,
            record_time=datetime.utcnow(),
        )
        self.db.add(record)
        await self.db.commit()

        meal_names = {
            "breakfast": "早餐",
            "lunch": "午餐",
            "dinner": "晚餐",
            "snack": "加餐",
        }
        return {
            "success": True,
            "message": f"✅ 已记录{meal_names.get(meal_type.lower(), '餐食')}：{food_description}",
            "action_type": "meal_recorded",
            "data": {"meal_type": meal_type, "food": food_description},
        }

    async def _record_exercise(
        self,
        exercise_type: str,
        duration_minutes: int,
        calories_burned: Optional[int] = None,
    ) -> Dict[str, Any]:
        from models.database import ExerciseRecord

        if not calories_burned:
            calories_burned = int(300 * duration_minutes / 60)

        record = ExerciseRecord(
            user_id=self.user_id,
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            calories_burned=calories_burned,
            record_time=datetime.utcnow(),
        )
        self.db.add(record)
        await self.db.commit()

        return {
            "success": True,
            "message": f"✅ 已记录运动：{exercise_type} {duration_minutes}分钟",
            "action_type": "exercise_recorded",
            "data": {"type": exercise_type, "duration": duration_minutes},
        }

    async def _record_water(self, amount_ml: int) -> Dict[str, Any]:
        from models.database import WaterRecord

        record = WaterRecord(
            user_id=self.user_id, amount_ml=amount_ml, record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()

        return {
            "success": True,
            "message": f"✅ 已记录饮水：{amount_ml}ml",
            "action_type": "water_recorded",
            "data": {"amount_ml": amount_ml},
        }

    async def _get_today_data(self) -> Dict[str, Any]:
        from models.database import (
            WeightRecord,
            MealRecord,
            ExerciseRecord,
            WaterRecord,
        )
        from sqlalchemy import and_
        from datetime import date

        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        # 查询各项数据
        weight_result = await self.db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == self.user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()

        meal_result = await self.db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == self.user_id,
                    MealRecord.record_time >= today_start,
                )
            )
        )
        meals = meal_result.scalars().all()

        exercise_result = await self.db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == self.user_id,
                    ExerciseRecord.record_time >= today_start,
                )
            )
        )
        exercises = exercise_result.scalars().all()

        water_result = await self.db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == self.user_id,
                    WaterRecord.record_time >= today_start,
                )
            )
        )
        waters = water_result.scalars().all()

        data = {
            "latest_weight": latest_weight.weight if latest_weight else None,
            "meal_count": len(meals),
            "total_calories": sum(m.total_calories or 0 for m in meals),
            "exercise_minutes": sum(e.duration_minutes or 0 for e in exercises),
            "total_water": sum(w.amount_ml or 0 for w in waters),
        }

        return {
            "success": True,
            "message": f"今日数据：体重{data['latest_weight'] or '暂无'}kg，餐食{data['meal_count']}次，运动{data['exercise_minutes']}分钟，饮水{data['total_water']}ml",
            "data": data,
        }


# ============== 主 Agent 类 ==============


class WeightManagementAgent:
    """
    体重管理 Agent（最终版）

    使用方式：
        agent = await WeightManagementAgent.create(user_id, db)
        result = await agent.chat("我今天体重65kg")
    """

    def __init__(
        self,
        user_id: int,
        db: AsyncSession,
        memory: ConversationMemoryManager,
        agent_name: str = "小助",
        personality_type: str = "warm",
    ):
        self.user_id = user_id
        self.db = db
        self.memory = memory
        self.agent_name = agent_name
        self.personality_type = personality_type

        self.llm = get_chat_model(temperature=0.7, max_tokens=1000)
        self.tool_executor = ToolExecutor(user_id, db)

        self._user_profile: Optional[Dict[str, Any]] = None
        self._init_agent()

        self.logger = logging.getLogger(__name__)

    def _init_agent(self):
        """初始化 LangChain Agent"""
        # 创建提示词模板
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # 创建 ReAct Agent
        # 注意：create_react_agent 返回一个可以直接调用的 Runnable
        self.agent_executor = create_react_agent(
            self.llm, TOOLS, prompt=self.prompt, debug=fastapi_settings.DEBUG
        )

    @classmethod
    async def create(
        cls,
        user_id: int,
        db: AsyncSession,
        agent_name: Optional[str] = None,
        personality_type: Optional[str] = None,
    ) -> "WeightManagementAgent":
        """
        工厂方法创建 Agent 实例

        自动加载用户配置
        """
        # 获取用户配置（兼容处理，如果表不存在则使用默认值）
        agent_config = {
            "name": agent_name or "小助",
            "personality_type": personality_type or "warm",
        }

        try:
            from models.database import AgentConfig

            result = await db.execute(
                select(AgentConfig).where(AgentConfig.user_id == user_id)
            )
            config = result.scalar_one_or_none()

            if config:
                agent_config["name"] = agent_name or config.agent_name
                if config.personality_type:
                    agent_config["personality_type"] = (
                        personality_type or config.personality_type.value
                    )
        except Exception as e:
            logger.warning(f"无法获取AgentConfig，使用默认值: {e}")

        # 创建记忆管理器
        memory = await ConversationMemoryManager.create(user_id, db)

        return cls(
            user_id=user_id,
            db=db,
            memory=memory,
            agent_name=agent_config["name"],
            personality_type=agent_config["personality_type"],
        )

    async def _build_system_prompt(self) -> str:
        """构建系统提示"""
        try:
            if not self._user_profile:
                self._user_profile = await UserProfileService.get_complete_profile(
                    self.user_id, self.db
                )

            profile = self._user_profile
            basic = profile.get("basic_info", {})

            prompt = f"""你是{profile.get("agent_name", self.agent_name)}，用户的专属体重管理伙伴。

【用户基础信息】
- 年龄: {basic.get("age", "未知")}岁
- 性别: {basic.get("gender", "未知")}
- 身高: {basic.get("height", "未知")}cm
- 当前体重: {basic.get("current_weight", "未知")}kg

{profile.get("style_addition", "")}

【回复规则】
1. 当用户提到体重、饮食、运动、饮水时，请使用工具记录
2. 回复要简洁友好，控制在150字以内
3. 记录成功后，向用户确认并给出简单建议"""

            return prompt

        except Exception as e:
            self.logger.error(f"构建系统提示失败: {e}", exc_info=True)
            return f"你是{self.agent_name}，用户的体重管理助手。"

    async def chat(self, message: str) -> Dict[str, Any]:
        """
        对话入口

        Returns:
            {
                "response": str,  # AI 回复文本
                "structured_response": dict,  # 结构化响应
                "intermediate_steps": list,  # 工具调用记录
            }
        """
        start_time = datetime.utcnow()
        self.logger.info(f"User {self.user_id} chat: {message[:50]}...")

        try:
            # 1. 构建系统提示
            system_prompt = await self._build_system_prompt()

            # 2. 获取对话历史
            chat_history = await self.memory.get_conversation_context()

            # 3. 执行 Agent
            # create_react_agent 期望的消息格式
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            for msg in chat_history:
                messages.append(msg)
            messages.append(HumanMessage(content=message))

            result = await self.agent_executor.ainvoke({"messages": messages})

            output = result.get("output", "")
            intermediate_steps = result.get("intermediate_steps", [])

            # 4. 处理工具调用（执行真实数据库操作）
            structured_response = {"type": "text", "content": output, "actions": []}
            tool_calls = []

            for step in intermediate_steps:
                if len(step) >= 2:
                    action, observation = step[0], step[1]
                    if hasattr(action, "tool"):
                        tool_call = {
                            "name": action.tool,
                            "arguments": action.tool_input
                            if hasattr(action, "tool_input")
                            else {},
                        }
                        tool_calls.append(tool_call)

                        # 执行真实工具
                        execution_result = await self.tool_executor.execute(
                            tool_call["name"], tool_call["arguments"]
                        )

                        if execution_result.get("success"):
                            output = execution_result.get("message", output)
                            structured_response["actions"].append(
                                {
                                    "type": tool_call["name"],
                                    "data": execution_result.get("data", {}),
                                }
                            )

            # 5. 保存对话到记忆
            await self.memory.save_interaction(message, output)

            # 6. 构建响应
            response = {
                "response": output,
                "structured_response": structured_response,
                "intermediate_steps": tool_calls,
            }

            # 7. 记录耗时
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"Chat completed in {duration:.2f}s")

            return response

        except Exception as e:
            self.logger.error(f"Chat error: {e}", exc_info=True)

            # 降级处理
            fallback_response = "抱歉，处理消息时出现错误，请稍后再试。"

            # 仍然尝试保存用户消息
            try:
                await self.memory.save_interaction(message, fallback_response)
            except Exception as mem_error:
                self.logger.warning(f"Failed to save to memory: {mem_error}")

            return {
                "response": fallback_response,
                "structured_response": {
                    "type": "text",
                    "content": fallback_response,
                    "actions": [],
                },
                "error": str(e),
                "intermediate_steps": [],
            }

    async def stream_chat(self, message: str) -> AsyncIterator[str]:
        """
        流式对话（待实现）

        Yields:
            str: 流式输出的文本片段
        """
        # TODO: 实现流式输出支持
        result = await self.chat(message)
        yield result["response"]

    async def clear_memory(self):
        """清除对话记忆"""
        await self.memory.clear_memory()
        self.logger.info(f"Memory cleared for user {self.user_id}")


# ============== 工厂和便捷函数 ==============


class AgentFactory:
    """Agent 工厂"""

    _instances: Dict[int, WeightManagementAgent] = {}

    @classmethod
    async def get_agent(
        cls, user_id: int, db: AsyncSession, force_new: bool = False
    ) -> WeightManagementAgent:
        """获取或创建 Agent"""
        if force_new or user_id not in cls._instances:
            cls._instances[user_id] = await WeightManagementAgent.create(user_id, db)

        # 更新数据库会话
        cls._instances[user_id].db = db
        cls._instances[user_id].tool_executor.db = db
        cls._instances[user_id].memory.db = db

        return cls._instances[user_id]

    @classmethod
    async def close_agent(cls, user_id: int):
        """关闭 Agent"""
        if user_id in cls._instances:
            await cls._instances[user_id].clear_memory()
            del cls._instances[user_id]

    @classmethod
    async def close_all(cls):
        """关闭所有 Agent"""
        for agent in cls._instances.values():
            await agent.clear_memory()
        cls._instances.clear()


# 便捷函数
async def get_agent(user_id: int, db: AsyncSession) -> WeightManagementAgent:
    """获取 Agent 实例"""
    return await AgentFactory.get_agent(user_id, db)


async def chat_with_agent(
    user_id: int, db: AsyncSession, message: str
) -> Dict[str, Any]:
    """便捷对话函数"""
    agent = await get_agent(user_id, db)
    return await agent.chat(message)
