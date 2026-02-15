"""
LangChain Agent 简化版 - 使用 LangGraph 的 create_react_agent

这个版本直接使用 LangGraph 的 create_react_agent，让 LangChain 自动处理：
1. 工具调用
2. 消息传递
3. 循环执行

我们的 ToolExecutor 包装工具，在工具执行时添加数据库操作
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_core.tools import tool, BaseTool
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.langchain.base import get_chat_model
from services.langchain.memory import ConversationMemoryManager
from services.langchain.monitoring import monitor_chat_decorator, get_agent_monitor
from services.user_profile_service import UserProfileService
from config.settings import fastapi_settings

logger = logging.getLogger(__name__)


# ============== 工具定义（需要绑定用户上下文）=============


class ContextualTool:
    """
    上下文工具包装器

    用于在工具执行时访问 user_id 和 db
    """

    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db

    def get_tools(self) -> list:
        """获取绑定了上下文的工具列表"""
        return [
            self._make_record_weight_tool(),
            self._make_record_meal_tool(),
            self._make_record_exercise_tool(),
            self._make_record_water_tool(),
            self._make_get_today_data_tool(),
            self._make_get_weight_history_tool(),
            self._make_get_food_history_tool(),
            self._make_get_exercise_history_tool(),
            self._make_calculate_bmi_tool(),
            self._make_calculate_calories_tool(),
            self._make_calculate_bmr_tool(),
        ]

    def _make_record_weight_tool(self):
        @tool
        def record_weight(weight: float, note: str = "") -> str:
            """记录用户体重数据。当用户提到体重数值时调用，如'体重65kg'、'今天称重66.5公斤'"""
            # 使用 asyncio.create_task 来执行异步操作
            # 注意：这是一个简化实现，实际应该在异步环境中执行
            return f"准备记录体重: {weight}kg (user_id={self.user_id})"

        return record_weight

    def _make_record_meal_tool(self):
        @tool
        def record_meal(
            meal_type: str,
            food_description: str,
            estimated_calories: Optional[int] = None,
        ) -> str:
            """记录用户餐食。当用户提到吃了什么食物时调用，如'吃了牛肉面'、'早餐吃了豆浆油条'"""
            return f"准备记录{meal_type}: {food_description}"

        return record_meal

    def _make_record_exercise_tool(self):
        @tool
        def record_exercise(
            exercise_type: str,
            duration_minutes: int,
            calories_burned: Optional[int] = None,
        ) -> str:
            """记录用户运动。当用户提到运动时调用，如'跑步30分钟'、'游泳一小时'、'慢跑5公里50分钟'"""
            return f"准备记录运动: {exercise_type} {duration_minutes}分钟"

        return record_exercise

    def _make_record_water_tool(self):
        @tool
        def record_water(amount_ml: int) -> str:
            """记录用户饮水。当用户提到喝水时调用，如'喝了500ml水'、'喝了两杯水'"""
            return f"准备记录饮水: {amount_ml}ml"

        return record_water

    def _make_get_today_data_tool(self):
        @tool
        def get_today_data() -> str:
            """获取用户今日所有健康数据（体重、餐食、运动、饮水）。用户问'今天记录了多少'时调用"""
            return "准备查询今日数据"

        return get_today_data

    def _make_get_weight_history_tool(self):
        @tool
        def get_weight_history(days: int = 7) -> str:
            """获取用户体重历史记录。当用户询问'体重变化'、'查看体重记录'时调用"""
            return f"准备查询最近{days}天的体重记录 (user_id={self.user_id})"

        return get_weight_history

    def _make_get_food_history_tool(self):
        @tool
        def get_food_history(days: int = 7) -> str:
            """获取用户饮食历史记录。当用户询问'饮食记录'、'吃了什么'时调用"""
            return f"准备查询最近{days}天的饮食记录 (user_id={self.user_id})"

        return get_food_history

    def _make_get_exercise_history_tool(self):
        @tool
        def get_exercise_history(days: int = 7) -> str:
            """获取用户运动历史记录。当用户询问'运动情况'、'锻炼记录'时调用"""
            return f"准备查询最近{days}天的运动记录 (user_id={self.user_id})"

        return get_exercise_history

    def _make_calculate_bmi_tool(self):
        @tool
        def calculate_bmi(height_cm: float, weight_kg: float) -> str:
            """计算身体质量指数(BMI)。当用户询问'BMI'、'计算BMI'时调用"""
            bmi = weight_kg / ((height_cm / 100) ** 2)
            return f"BMI计算结果: {bmi:.2f} (身高{height_cm}cm, 体重{weight_kg}kg)"

        return calculate_bmi

    def _make_calculate_calories_tool(self):
        @tool
        def calculate_calories(
            activity: str, duration_minutes: int, weight_kg: float = 65
        ) -> str:
            """计算运动消耗的卡路里。当用户询问'消耗多少卡路里'时调用"""
            # 简化的卡路里计算
            calories_per_minute = {
                "跑步": 0.12,
                "散步": 0.05,
                "瑜伽": 0.04,
                "游泳": 0.13,
                "健身房": 0.08,
                "自行车": 0.07,
            }
            base_rate = calories_per_minute.get(activity.lower(), 0.06)
            calories = base_rate * duration_minutes * weight_kg
            return f"运动消耗: {calories:.0f}千卡 ({activity} {duration_minutes}分钟)"

        return calculate_calories

    def _make_calculate_bmr_tool(self):
        @tool
        def calculate_bmr(
            weight_kg: float, height_cm: float, age: int, gender: str = "male"
        ) -> str:
            """计算基础代谢率(BMR)。当用户询问'基础代谢率'时调用"""
            if gender.lower() == "male":
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
            else:
                bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
            return f"基础代谢率(BMR): {bmr:.0f}千卡/天"

        return calculate_bmr


# ============== 异步工具执行器 ==============


class AsyncToolExecutor:
    """
    异步工具执行器

    实际执行数据库操作
    """

    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def record_weight(self, weight: float, note: str = "") -> str:
        """记录体重"""
        from models.database import WeightRecord
        from datetime import date

        now = datetime.utcnow()
        record = WeightRecord(
            user_id=self.user_id,
            weight=weight,
            note=note,
            record_time=now,
            record_date=now.date(),
        )
        self.db.add(record)
        await self.db.commit()

        return f"✅ 已记录体重：{weight}kg"

    async def record_meal(
        self,
        meal_type: str,
        food_description: str,
        estimated_calories: Optional[int] = None,
    ) -> str:
        """记录餐食"""
        from models.database import MealRecord, MealType

        meal_type_map = {
            "breakfast": MealType.BREAKFAST,
            "lunch": MealType.LUNCH,
            "dinner": MealType.DINNER,
            "snack": MealType.SNACK,
        }

        if not estimated_calories:
            estimated_calories = 400

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
        return f"✅ 已记录{meal_names.get(meal_type.lower(), '餐食')}：{food_description}（约{estimated_calories}千卡）"

    async def record_exercise(
        self,
        exercise_type: str,
        duration_minutes: int,
        calories_burned: Optional[int] = None,
    ) -> str:
        """记录运动"""
        from models.database import ExerciseRecord

        if not calories_burned:
            calories_burned = int(300 * duration_minutes / 60)

        record = ExerciseRecord(
            user_id=self.user_id,
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            calories_burned=calories_burned,
            record_time=datetime.utcnow(),
            is_checkin=False,  # AI记录的不是手动打卡
        )
        self.db.add(record)
        await self.db.commit()

        return f"✅ 已记录运动：{exercise_type} {duration_minutes}分钟（消耗约{calories_burned}千卡）"

    async def record_water(self, amount_ml: int) -> str:
        """记录饮水"""
        from models.database import WaterRecord

        record = WaterRecord(
            user_id=self.user_id, amount_ml=amount_ml, record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()

        return f"✅ 已记录饮水：{amount_ml}ml"

    async def get_today_data(self) -> str:
        """获取今日数据"""
        from models.database import (
            WeightRecord,
            MealRecord,
            ExerciseRecord,
            WaterRecord,
        )
        from sqlalchemy import and_
        from datetime import date

        today_start = datetime.combine(date.today(), datetime.min.time())

        # 最新体重
        weight_result = await self.db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == self.user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()

        # 今日餐食
        meal_result = await self.db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == self.user_id,
                    MealRecord.record_time >= today_start,
                )
            )
        )
        scalars_result = meal_result.scalars()
        meals = (
            scalars_result.all()
            if hasattr(scalars_result, "all")
            else list(scalars_result)
        )

        # 今日运动
        exercise_result = await self.db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == self.user_id,
                    ExerciseRecord.record_time >= today_start,
                )
            )
        )
        scalars_result = exercise_result.scalars()
        exercises = (
            scalars_result.all()
            if hasattr(scalars_result, "all")
            else list(scalars_result)
        )

        # 今日饮水
        water_result = await self.db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == self.user_id,
                    WaterRecord.record_time >= today_start,
                )
            )
        )
        scalars_result = water_result.scalars()
        waters = (
            scalars_result.all()
            if hasattr(scalars_result, "all")
            else list(scalars_result)
        )

        data = {
            "latest_weight": latest_weight.weight if latest_weight else None,
            "meal_count": len(meals),
            "total_calories": sum(m.total_calories or 0 for m in meals),
            "exercise_minutes": sum(e.duration_minutes or 0 for e in exercises),
            "total_water": sum(w.amount_ml or 0 for w in waters),
        }

        return f"今日数据：体重{data['latest_weight'] or '暂无'}kg，餐食{data['meal_count']}次，运动{data['exercise_minutes']}分钟，饮水{data['total_water']}ml"

    async def get_weight_history(self, days: int = 7) -> str:
        """获取体重历史记录"""
        from models.database import WeightRecord
        from sqlalchemy import and_
        from datetime import datetime, timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == self.user_id,
                    WeightRecord.record_time >= start_date,
                )
            )
            .order_by(WeightRecord.record_time.desc())
        )
        # 兼容处理：scalars() 可能返回列表或 ScalarResult
        scalars_result = result.scalars()
        if hasattr(scalars_result, "all"):
            records = scalars_result.all()
        else:
            records = list(scalars_result) if scalars_result else []

        if not records:
            return f"最近{days}天没有体重记录"

        weights = [f"{r.weight}kg ({r.record_time.strftime('%m-%d')})" for r in records]
        return f"最近{days}天体重的记录：{' → '.join(weights)}"

    async def get_food_history(self, days: int = 7) -> str:
        """获取饮食历史记录"""
        from models.database import MealRecord
        from sqlalchemy import and_
        from datetime import datetime, timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(MealRecord)
            .where(
                and_(
                    MealRecord.user_id == self.user_id,
                    MealRecord.record_time >= start_date,
                )
            )
            .order_by(MealRecord.record_time.desc())
        )
        # 兼容处理：scalars() 可能返回列表或 ScalarResult
        scalars_result = result.scalars()
        if hasattr(scalars_result, "all"):
            records = scalars_result.all()
        else:
            records = list(scalars_result) if scalars_result else []

        if not records:
            return f"最近{days}天没有饮食记录"

        meals = [f"{r.meal_type}: {r.food_description}" for r in records]
        return (
            f"最近{days}天饮食记录：{len(meals)}餐\n"
            + "\n".join(meals[:5])
            + ("\n..." if len(meals) > 5 else "")
        )

    async def get_exercise_history(self, days: int = 7) -> str:
        """获取运动历史记录"""
        from models.database import ExerciseRecord
        from sqlalchemy import and_
        from datetime import datetime, timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(ExerciseRecord)
            .where(
                and_(
                    ExerciseRecord.user_id == self.user_id,
                    ExerciseRecord.record_time >= start_date,
                )
            )
            .order_by(ExerciseRecord.record_time.desc())
        )
        # 兼容处理：scalars() 可能返回列表或 ScalarResult
        scalars_result = result.scalars()
        if hasattr(scalars_result, "all"):
            records = scalars_result.all()
        else:
            records = list(scalars_result) if scalars_result else []

        if not records:
            return f"最近{days}天没有运动记录"

        exercises = [f"{r.exercise_type} {r.duration_minutes}分钟" for r in records]
        total_minutes = sum(r.duration_minutes or 0 for r in records)
        return (
            f"最近{days}天运动记录：{len(exercises)}次，共{total_minutes}分钟\n"
            + "\n".join(exercises[:5])
            + ("\n..." if len(exercises) > 5 else "")
        )

    async def calculate_bmi(self, height_cm: float, weight_kg: float) -> str:
        """计算BMI"""
        bmi = weight_kg / ((height_cm / 100) ** 2)

        if bmi < 18.5:
            status = "偏瘦"
        elif bmi < 24:
            status = "正常"
        elif bmi < 28:
            status = "超重"
        else:
            status = "肥胖"

        return f"BMI: {bmi:.1f} ({status}) - 身高{height_cm}cm, 体重{weight_kg}kg"

    async def calculate_calories(
        self, activity: str, duration_minutes: int, weight_kg: float = 65
    ) -> str:
        """计算运动消耗的卡路里"""
        calories_per_minute = {
            "跑步": 0.12,
            "散步": 0.05,
            "瑜伽": 0.04,
            "游泳": 0.13,
            "健身房": 0.08,
            "自行车": 0.07,
        }

        base_rate = calories_per_minute.get(activity.lower(), 0.06)
        calories = base_rate * duration_minutes * weight_kg

        return f"{activity} {duration_minutes}分钟消耗约{calories:.0f}千卡"

    async def calculate_bmr(
        self, weight_kg: float, height_cm: float, age: int, gender: str = "male"
    ) -> str:
        """计算基础代谢率"""
        if gender.lower() == "male":
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        else:
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }

        daily_calories = {
            level: bmr * mult for level, mult in activity_multipliers.items()
        }

        return f"基础代谢率(BMR): {bmr:.0f}千卡/天\n每日热量需求：\n" + "\n".join(
            [f"  {level}: {cal:.0f}千卡" for level, cal in daily_calories.items()]
        )


# ============== 主 Agent 类 ==============


class SimpleWeightAgent:
    """
    简化的体重管理 Agent

    使用方式：
        agent = await SimpleWeightAgent.create(user_id, db)
        result = await agent.chat("我今天体重65kg")
    """

    def __init__(
        self,
        user_id: int,
        db: AsyncSession,
        agent_name: str = "小助",
        personality_type: str = "warm",
    ):
        self.user_id = user_id
        self.db = db
        self.agent_name = agent_name
        self.personality_type = personality_type

        self.llm = get_chat_model(temperature=0.7, max_tokens=1000)
        self.tool_executor = AsyncToolExecutor(user_id, db)
        self._user_profile: Optional[Dict[str, Any]] = None

        self.logger = logging.getLogger(__name__)

        # 多轮对话状态管理
        self._conversation_history: List[BaseMessage] = []  # 对话历史
        self._pending_tool_calls: List[Dict[str, Any]] = []  # 待确认的工具调用
        self._confirmation_state: bool = False  # 是否处于确认状态

    @classmethod
    async def create(
        cls,
        user_id: int,
        db: AsyncSession,
        agent_name: Optional[str] = None,
        personality_type: Optional[str] = None,
    ) -> "SimpleWeightAgent":
        """工厂方法创建 Agent"""
        # 兼容处理，如果表不存在则使用默认值
        final_agent_name = agent_name or "小助"
        final_personality_type = personality_type or "warm"

        try:
            from models.database import AgentConfig

            result = await db.execute(
                select(AgentConfig).where(AgentConfig.user_id == user_id)
            )
            config = result.scalar_one_or_none()

            if config:
                final_agent_name = agent_name or config.agent_name
                if config.personality_type:
                    final_personality_type = (
                        personality_type or config.personality_type.value
                    )
        except Exception as e:
            logger.warning(f"无法获取AgentConfig，使用默认值: {e}")

        return cls(
            user_id=user_id,
            db=db,
            agent_name=final_agent_name,
            personality_type=final_personality_type,
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

            return f"""你是{profile.get("agent_name", self.agent_name)}，用户的专属体重管理伙伴。

【用户基础信息】
- 年龄: {basic.get("age", "未知")}岁
- 性别: {basic.get("gender", "未知")}
- 身高: {basic.get("height", "未知")}cm
- 当前体重: {basic.get("current_weight", "未知")}kg

{profile.get("style_addition", "")}

【工具调用规则 - 必须遵守】
当用户提到以下内容时，必须使用工具记录：

1. 体重记录（必须调用 record_weight）：
   - 用户提到具体体重数值（如65kg、65公斤）
   - 包含"体重"和数字的组合
   - 示例："今天体重65kg"、"体重反弹到78.5kg"

2. 餐食记录（必须调用 record_meal）：
   - 用户提到吃了什么食物
   - 包含餐食类型（早餐/午餐/晚餐/加餐）
   - 示例："早餐吃了燕麦牛奶"、"午餐吃了鸡胸肉沙拉"

3. 运动记录（必须调用 record_exercise）：
   - 用户提到运动类型和持续时间
   - 包含运动名称和时间单位
   - 示例："跑步30分钟"、"游泳1小时"

4. 饮水记录（必须调用 record_water）：
   - 用户提到喝了多少水
   - 包含水量和单位（ml/毫升）
   - 示例："喝了500ml水"、"饮水1000毫升"

5. 数据查询（必须调用相应查询工具）：
   - 用户询问历史记录时调用 get_*_history
   - 包含"记录"、"历史"、"查看"等关键词
   - 示例："查看上周体重"、"最近7天饮食记录"

6. 计算类（必须调用相应计算工具）：
   - 用户询问BMI时调用 calculate_bmi
   - 用户询问卡路里消耗时调用 calculate_calories
   - 用户询问基础代谢率时调用 calculate_bmr
   - 示例："计算我的BMI"、"跑步消耗多少卡路里"

【确认机制 - 重要】
当用户意图不够明确或缺少必要参数时，必须先确认再调用工具：

1. 需要确认的情况：
   - 用户只说了"记录体重"但没有提供具体数值
   - 用户说"吃了早餐"但没有说吃了什么
   - 用户说"运动了"但没有说运动类型和时长
   - 任何缺少必要参数的情况

2. 确认流程：
   - 第一步：询问用户具体信息（不要调用工具）
   - 第二步：用户回复后，根据完整信息调用工具
   - 示例：
     用户："记录体重"
     你："请问您今天的体重是多少呢？"
     用户："65.2公斤"
     你：TOOL_CALL: {"tool": "record_weight", "args": {"weight": 65.2}}

3. 用户确认后的调用：
   - 当用户回复了缺失的信息后，立即调用相应工具
   - 不要再次询问，直接执行

【回复要求】
1. 信息完整时：先调用工具记录数据，再回复用户
2. 信息不完整时：先询问确认，等待用户补充
3. 回复要简洁友好，控制在150字以内
4. 记录成功后，明确告诉用户已记录
5. 给出简单建议或鼓励"""

        except Exception as e:
            self.logger.error(f"构建系统提示失败: {e}")
            return f"你是{self.agent_name}，用户的体重管理助手。"

    @monitor_chat_decorator
    async def chat(self, message: str) -> Dict[str, Any]:
        """对话入口 - 支持多轮确认机制"""
        import re
        import json

        start_time = datetime.utcnow()
        self.logger.info(f"User {self.user_id}: {message[:50]}...")

        try:
            # 检查是否有待确认的工具调用
            if self._confirmation_state and self._pending_tool_calls:
                self.logger.info(f"检测到待确认的工具调用: {self._pending_tool_calls}")

                # 用户回复了确认信息，执行待确认的工具调用
                tool_results = []
                executed_tools = []

                for pending_tool in self._pending_tool_calls:
                    try:
                        tool_name = pending_tool["tool"]
                        tool_args = pending_tool["args"]

                        # 尝试从用户消息中提取缺失的参数
                        extracted_params = self._extract_params_from_message(
                            message, tool_name
                        )
                        if extracted_params:
                            tool_args.update(extracted_params)
                            self.logger.info(
                                f"从用户消息中提取参数: {extracted_params}"
                            )

                        self.logger.info(
                            f"执行待确认工具: {tool_name}, 参数: {tool_args}"
                        )

                        # 执行工具
                        method = getattr(self.tool_executor, tool_name, None)
                        if method:
                            result = await method(**tool_args)
                            tool_results.append(f"{tool_name}: {result}")
                            executed_tools.append(tool_name)
                        else:
                            tool_results.append(f"{tool_name}: 工具不存在")

                    except Exception as tool_error:
                        self.logger.error(f"工具执行失败: {tool_error}")
                        tool_results.append(f"错误: {tool_error}")

                # 清除待确认状态
                self._confirmation_state = False
                self._pending_tool_calls = []

                # 生成回复
                if tool_results:
                    all_results = "\n".join(tool_results)
                    confirm_prompt = f"用户确认了信息，工具执行结果:\n{all_results}\n\n请基于以上结果，用友好自然的语气回复用户，并告知已成功记录。"

                    messages = [
                        SystemMessage(content=await self._build_system_prompt()),
                        HumanMessage(content=message),
                        AIMessage(content=confirm_prompt),
                    ]

                    final_response = await self.llm.ainvoke(messages)
                    ai_content = final_response.content

                    # 保存对话历史
                    self._conversation_history.extend(
                        [HumanMessage(content=message), AIMessage(content=ai_content)]
                    )

                    return {
                        "response": ai_content,
                        "structured_response": {
                            "type": "text",
                            "content": ai_content,
                            "actions": [],
                        },
                        "intermediate_steps": [],
                        "tool_calls_executed": executed_tools,
                    }

            # 构建系统提示和工具描述
            system_prompt = await self._build_system_prompt()
            tools_description = self._get_tools_description()

            # 构建消息列表（包含历史对话）
            messages = [SystemMessage(content=system_prompt + tools_description)]

            # 添加历史对话（最多保留最近5轮）
            if self._conversation_history:
                messages.extend(
                    self._conversation_history[-10:]
                )  # 保留最近10条消息（5轮对话）

            # 添加当前消息
            messages.append(HumanMessage(content=message))

            # 调用 LLM
            response = await self.llm.ainvoke(messages)
            ai_content = response.content

            # 检查是否有工具调用（支持多个）
            tool_call_matches = re.findall(
                r"TOOL_CALL:\s*(\{.*?\})(?=\n|TOOL_CALL:|$)", ai_content, re.DOTALL
            )

            if tool_call_matches:
                # 收集所有工具调用
                pending_calls = []

                for tool_call_text in tool_call_matches:
                    try:
                        self.logger.info(f"原始工具调用文本: {tool_call_text}")

                        # 修复 JSON 格式问题
                        if tool_call_text.count("{") > tool_call_text.count("}"):
                            tool_call_text += "}" * (
                                tool_call_text.count("{") - tool_call_text.count("}")
                            )
                        tool_call_text = re.sub(r",\s*}", "}", tool_call_text)
                        tool_call_text = re.sub(r",\s*]", "]", tool_call_text)

                        self.logger.info(f"修复后工具调用文本: {tool_call_text}")

                        tool_call = json.loads(tool_call_text)
                        tool_name = tool_call.get("tool")
                        tool_args = tool_call.get("args", {})

                        # 检查参数是否完整
                        if self._is_params_complete(tool_name, tool_args):
                            pending_calls.append({"tool": tool_name, "args": tool_args})
                        else:
                            # 参数不完整，标记为需要确认
                            self._pending_tool_calls.append(
                                {"tool": tool_name, "args": tool_args}
                            )

                    except Exception as e:
                        self.logger.error(f"解析工具调用失败: {e}")

                if pending_calls:
                    # 执行参数完整的工具调用
                    tool_results = []
                    for call in pending_calls:
                        try:
                            tool_name = call["tool"]
                            tool_args = call["args"]

                            self.logger.info(
                                f"执行工具: {tool_name}, 参数: {tool_args}"
                            )
                            method = getattr(self.tool_executor, tool_name, None)
                            if method:
                                result = await method(**tool_args)
                                tool_results.append(f"{tool_name}: {result}")
                            else:
                                tool_results.append(f"{tool_name}: 工具不存在")
                        except Exception as tool_error:
                            self.logger.error(f"工具执行失败: {tool_error}")
                            tool_results.append(f"错误: {tool_error}")

                    # 基于工具结果生成回复
                    if tool_results:
                        all_results = "\n".join(tool_results)
                        messages.extend(
                            [
                                AIMessage(content=ai_content),
                                HumanMessage(
                                    content=f"工具执行结果:\n{all_results}\n\n请基于以上结果，用友好自然的语气回复用户。"
                                ),
                            ]
                        )
                        final_response = await self.llm.ainvoke(messages)
                        ai_content = final_response.content

                if self._pending_tool_calls:
                    # 有需要确认的工具调用
                    self._confirmation_state = True
                    self.logger.info(
                        f"设置确认状态，待确认工具: {self._pending_tool_calls}"
                    )

                    # 保存当前对话状态
                    self._conversation_history.extend(
                        [HumanMessage(content=message), AIMessage(content=ai_content)]
                    )

                    return {
                        "response": ai_content,
                        "structured_response": {
                            "type": "text",
                            "content": ai_content,
                            "actions": [],
                        },
                        "intermediate_steps": [],
                        "needs_confirmation": True,
                        "pending_tools": [p["tool"] for p in self._pending_tool_calls],
                    }

            # 保存对话历史
            self._conversation_history.extend(
                [HumanMessage(content=message), AIMessage(content=ai_content)]
            )

            # 限制历史记录长度
            if len(self._conversation_history) > 20:
                self._conversation_history = self._conversation_history[-20:]

            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"Chat completed in {duration:.2f}s")

            return {
                "response": ai_content,
                "structured_response": {
                    "type": "text",
                    "content": ai_content,
                    "actions": [],
                },
                "intermediate_steps": [],
                "needs_confirmation": False,
            }

        except Exception as e:
            self.logger.error(f"Chat error: {e}", exc_info=True)
            return {
                "response": "抱歉，处理消息时出现错误，请稍后再试。",
                "structured_response": {
                    "type": "text",
                    "content": "抱歉，处理消息时出现错误。",
                    "actions": [],
                },
                "error": str(e),
            }

    def _get_tools_description(self) -> str:
        """获取工具描述"""
        return """
可用工具：
【数据记录工具】
1. record_weight(weight: float, note: str) - 记录体重（必须参数：weight）
2. record_meal(meal_type: str, food_description: str, estimated_calories: int) - 记录餐食（必须参数：meal_type, food_description）
3. record_exercise(exercise_type: str, duration_minutes: int, calories_burned: int) - 记录运动（必须参数：exercise_type, duration_minutes）
4. record_water(amount_ml: int) - 记录饮水（必须参数：amount_ml）

【数据查询工具】
5. get_today_data() - 获取今日数据
6. get_weight_history(days: int) - 获取体重历史记录
7. get_food_history(days: int) - 获取饮食历史记录
8. get_exercise_history(days: int) - 获取运动历史记录

【计算工具】
9. calculate_bmi(height_cm: float, weight_kg: float) - 计算BMI（必须参数：height_cm, weight_kg）
10. calculate_calories(activity: str, duration_minutes: int, weight_kg: float) - 计算运动消耗（必须参数：activity, duration_minutes）
11. calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) - 计算基础代谢率（必须参数：weight_kg, height_cm, age）

如需使用工具，请按以下格式回复（可调用多个工具）：
TOOL_CALL: {"tool": "record_weight", "args": {"weight": 65.5}}
TOOL_CALL: {"tool": "record_meal", "args": {"meal_type": "早餐", "food_description": "面包"}}
TOOL_CALL: {"tool": "record_exercise", "args": {"exercise_type": "跑步", "duration_minutes": 30}}

如需正常回复，直接回复即可。

【重要】当用户一次提供多个数据时（如同时提到体重、饮食、运动），必须分别调用对应的工具记录所有数据。
"""

    def _is_params_complete(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """检查工具参数是否完整（包括非零值检查）"""
        required_params = {
            "record_weight": ["weight"],
            "record_meal": ["meal_type", "food_description"],
            "record_exercise": ["exercise_type", "duration_minutes"],
            "record_water": ["amount_ml"],
            "calculate_bmi": ["height_cm", "weight_kg"],
            "calculate_calories": ["activity", "duration_minutes"],
            "calculate_bmr": ["weight_kg", "height_cm", "age"],
        }

        if tool_name not in required_params:
            return True  # 查询类工具不需要检查

        required = required_params[tool_name]
        for param in required:
            if param not in params or params[param] is None:
                return False
            # 数值参数必须大于0
            if param in ["weight", "duration_minutes", "amount_ml", "height_cm", "age"]:
                if params[param] <= 0:
                    return False
        return True

    def _extract_params_from_message(
        self, message: str, tool_name: str
    ) -> Dict[str, Any]:
        """从用户消息中提取参数"""
        import re

        extracted = {}
        message_lower = message.lower()

        if tool_name == "record_weight":
            # 提取体重数值
            weight_patterns = [
                r"(\d+\.?\d*)\s*公斤",
                r"(\d+\.?\d*)\s*kg",
                r"(\d+\.?\d*)\s*千克",
                r"体重\s*(\d+\.?\d*)",  # 新增：匹配"体重65.5"
                r"(\d+\.?\d*)\s*斤",  # 新增：匹配"130斤"（转换为公斤）
            ]
            for pattern in weight_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    weight = float(match.group(1))
                    # 如果是斤，转换为公斤
                    if "斤" in message_lower:
                        weight = weight / 2
                    extracted["weight"] = weight
                    self.logger.info(
                        f"Extracted weight: {weight}kg from message: {message}"
                    )
                    break

        elif tool_name == "record_meal":
            # 提取餐食类型
            if "早餐" in message or "早上" in message:
                extracted["meal_type"] = "早餐"
            elif "午餐" in message or "中午" in message:
                extracted["meal_type"] = "午餐"
            elif "晚餐" in message or "晚上" in message:
                extracted["meal_type"] = "晚餐"
            elif "加餐" in message or "零食" in message:
                extracted["meal_type"] = "加餐"

        elif tool_name == "record_exercise":
            # 提取运动类型和时长
            exercise_types = [
                "跑步",
                "慢跑",
                "散步",
                "瑜伽",
                "游泳",
                "健身",
                "骑行",
                "跳绳",
                "快走",
            ]
            for ex_type in exercise_types:
                if ex_type in message:
                    extracted["exercise_type"] = ex_type
                    break

            # 提取距离（如"5公里"）
            distance_patterns = [
                r"(\d+\.?\d*)\s*公里",
                r"(\d+\.?\d*)\s*km",
                r"(\d+\.?\d*)\s*千米",
            ]
            for pattern in distance_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    distance = float(match.group(1))
                    # 如果提到距离但没提到运动类型，默认为跑步
                    if "exercise_type" not in extracted:
                        extracted["exercise_type"] = "跑步"
                    break

            # 提取时长
            duration_patterns = [
                r"(\d+)\s*分钟",
                r"(\d+)\s*分",
                r"(\d+)\s*小时",
                r"(\d+)\s*个?小时",
                r"(\d+)\s*半小时",
                r"半个\s*小时",
            ]
            for pattern in duration_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    duration = int(match.group(1)) if match.group(1) else 30
                    if "小时" in message_lower or "半小时" in message_lower:
                        duration *= 60
                    extracted["duration_minutes"] = duration
                    break

        elif tool_name == "record_water":
            # 提取水量
            water_patterns = [
                r"(\d+)\s*ml",
                r"(\d+)\s*毫升",
                r"(\d+)\s*升",
                r"(\d+)\s*L",
            ]
            for pattern in water_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    amount = int(match.group(1))
                    if "升" in message_lower or "L" in message:
                        amount *= 1000
                    extracted["amount_ml"] = amount
                    break

        return extracted

    def reset_conversation(self):
        """重置对话状态"""
        self._conversation_history = []
        self._pending_tool_calls = []
        self._confirmation_state = False
        self.logger.info("对话状态已重置")


# ============== 便捷函数 ==============


async def chat_with_simple_agent(
    user_id: int, db: AsyncSession, message: str
) -> Dict[str, Any]:
    """便捷对话函数"""
    agent = await SimpleWeightAgent.create(user_id, db)
    return await agent.chat(message)


# ============== AgentFactory ==============


class AgentFactory:
    """Agent 工厂（简化版）"""

    _instances: Dict[int, SimpleWeightAgent] = {}

    @classmethod
    async def get_agent(
        cls, user_id: int, db: AsyncSession, force_new: bool = False
    ) -> SimpleWeightAgent:
        """获取或创建 Agent"""
        if force_new or user_id not in cls._instances:
            cls._instances[user_id] = await SimpleWeightAgent.create(user_id, db)

        # 更新数据库会话
        cls._instances[user_id].db = db
        if hasattr(cls._instances[user_id], "tool_executor"):
            cls._instances[user_id].tool_executor.db = db

        return cls._instances[user_id]

    @classmethod
    async def close_agent(cls, user_id: int):
        """关闭 Agent"""
        if user_id in cls._instances:
            del cls._instances[user_id]

    @classmethod
    async def close_all(cls):
        """关闭所有 Agent"""
        cls._instances.clear()


# 便捷函数
async def get_agent(user_id: int, db: AsyncSession) -> SimpleWeightAgent:
    """获取 Agent 实例"""
    return await AgentFactory.get_agent(user_id, db)
