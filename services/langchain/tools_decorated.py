"""
使用 @tool 装饰器定义的工具（LangChain 推荐方式）

优点：
1. 自动从函数签名生成参数描述
2. 类型安全
3. 支持异步函数
4. 更好的 IDE 支持

使用示例：
    from services.langchain.tools_decorated import get_weight_management_tools
    
    tools = get_weight_management_tools(user_id, db)
    agent = create_react_agent(llm, tools, prompt)
"""

from typing import Optional
from datetime import datetime, date
import json
import logging

from langchain_core.tools import tool, Tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class ToolContext:
    """
    工具上下文管理器 - 用于在工具函数中访问用户ID和数据库
    
    这是解决 LangChain 工具无法直接访问外部状态的一种模式
    """
    
    def __init__(self):
        self._user_id: Optional[int] = None
        self._db: Optional[AsyncSession] = None
    
    def set_context(self, user_id: int, db: AsyncSession):
        """设置上下文"""
        self._user_id = user_id
        self._db = db
    
    def clear(self):
        """清除上下文"""
        self._user_id = None
        self._db = None
    
    @property
    def user_id(self) -> int:
        if self._user_id is None:
            raise RuntimeError("ToolContext.user_id 未设置")
        return self._user_id
    
    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            raise RuntimeError("ToolContext.db 未设置")
        return self._db


# 全局上下文实例（线程不安全，但在单线程 async 环境中可用）
tool_context = ToolContext()


# ============== 使用 @tool 装饰器定义的工具 ==============

@tool
def record_weight_tool(weight: float, note: str = "") -> str:
    """
    记录用户体重数据。
    
    当用户提到体重数值时调用，如：
    - "今天体重65kg"
    - "称重66.5公斤"
    - "现在70kg了"
    
    Args:
        weight: 体重数值，单位kg，例如：65.5
        note: 可选备注，例如："晨起空腹"
    
    Returns:
        记录结果的描述字符串
    """
    # 这是一个同步包装，实际逻辑在 ToolExecutor 中
    # 由于 LangChain 工具调用是同步的，我们需要使用 asyncio.run 或回调模式
    return f"准备记录体重: {weight}kg"


@tool
def record_meal_tool(
    meal_type: str, 
    food_description: str, 
    estimated_calories: Optional[int] = None
) -> str:
    """
    记录用户餐食。
    
    当用户提到吃了什么食物时调用，如：
    - "早餐吃了豆浆油条"
    - "中午吃了牛肉面"
    - "刚吃了个苹果"
    
    Args:
        meal_type: 餐食类型，可选值：
            - "breakfast": 早餐（6:00-10:00）
            - "lunch": 午餐（11:00-14:00）
            - "dinner": 晚餐（17:00-21:00）
            - "snack": 加餐/零食（其他时间）
        food_description: 食物描述，例如："牛肉面"、"豆浆、油条"
        estimated_calories: 估算热量（千卡），如果不确定可不填
    
    Returns:
        记录结果的描述字符串
    """
    return f"准备记录{meal_type}: {food_description}"


@tool
def record_exercise_tool(
    exercise_type: str, 
    duration_minutes: int, 
    calories_burned: Optional[int] = None
) -> str:
    """
    记录用户运动。
    
    当用户提到运动时调用，如：
    - "跑步30分钟"
    - "游泳一小时"
    - "走了5000步"
    
    Args:
        exercise_type: 运动类型，例如："跑步"、"游泳"、"快走"、"健身"
        duration_minutes: 运动时长（分钟），例如：30
        calories_burned: 消耗热量（千卡），如果不确定可不填
    
    Returns:
        记录结果的描述字符串
    """
    return f"准备记录运动: {exercise_type} {duration_minutes}分钟"


@tool
def record_water_tool(amount_ml: int, drink_type: str = "水") -> str:
    """
    记录用户饮水。
    
    当用户提到喝水时调用，如：
    - "喝了500ml水"
    - "喝了两杯咖啡"
    - "喝了瓶可乐"
    
    Args:
        amount_ml: 饮水量（毫升），例如：500
        drink_type: 饮品类型，例如："水"、"咖啡"、"茶"、"果汁"
    
    Returns:
        记录结果的描述字符串
    """
    return f"准备记录饮水: {amount_ml}ml {drink_type}"


@tool
def get_today_data_tool() -> str:
    """
    获取用户今日所有健康数据。
    
    包括：
    - 最新体重
    - 今日餐食记录
    - 今日运动记录
    - 今日饮水记录
    
    使用场景：
    - 用户问"今天记录了多少"
    - 用户问"今天吃了什么"
    - 用户问"今天运动了吗"
    
    Returns:
        今日数据的描述字符串
    """
    return "准备查询今日数据"


@tool
def query_history_tool(data_type: str, days: int = 7) -> str:
    """
    查询用户历史数据。
    
    使用场景：
    - 用户问"最近体重变化"
    - 用户问"这周运动了几次"
    
    Args:
        data_type: 数据类型，可选值："weight"、"meal"、"exercise"、"water"
        days: 查询天数，默认7天
    
    Returns:
        历史数据的描述字符串
    """
    return f"准备查询{days}天的{data_type}历史"


# ============== 工具集合 ==============

DECORATED_TOOLS = [
    record_weight_tool,
    record_meal_tool,
    record_exercise_tool,
    record_water_tool,
    get_today_data_tool,
    query_history_tool,
]


def get_decorated_tools() -> list:
    """
    获取使用 @tool 装饰器定义的工具列表
    
    Returns:
        LangChain Tool 对象列表
    """
    return DECORATED_TOOLS


# ============== 工具执行器（实际执行数据库操作）=============

class AsyncToolExecutor:
    """
    异步工具执行器
    
    由于 LangChain 的 @tool 装饰器创建的工具是同步的，
    我们使用这个执行器来实际执行异步的数据库操作
    """
    
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """执行工具调用"""
        try:
            if tool_name in ["record_weight_tool", "record_weight"]:
                return await self._record_weight(**arguments)
            elif tool_name in ["record_meal_tool", "record_meal"]:
                return await self._record_meal(**arguments)
            elif tool_name in ["record_exercise_tool", "record_exercise"]:
                return await self._record_exercise(**arguments)
            elif tool_name in ["record_water_tool", "record_water"]:
                return await self._record_water(**arguments)
            elif tool_name in ["get_today_data_tool", "get_today_data"]:
                return await self._get_today_data()
            elif tool_name in ["query_history_tool", "query_history"]:
                return await self._query_history(**arguments)
            else:
                return {"success": False, "message": f"未知工具: {tool_name}"}
        except Exception as e:
            self.logger.error(f"工具执行失败 {tool_name}: {e}", exc_info=True)
            return {"success": False, "message": f"执行失败: {str(e)}"}
    
    async def _record_weight(self, weight: float, note: str = "") -> dict:
        """记录体重"""
        from models.database import WeightRecord
        
        record = WeightRecord(
            user_id=self.user_id,
            weight=weight,
            note=note,
            record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()
        
        return {
            "success": True,
            "message": f"✅ 已记录体重：{weight}kg",
            "action_type": "weight_recorded",
            "data": {"weight": weight, "note": note}
        }
    
    async def _record_meal(
        self, 
        meal_type: str, 
        food_description: str, 
        estimated_calories: Optional[int] = None
    ) -> dict:
        """记录餐食"""
        from models.database import MealRecord, MealType
        
        meal_type_map = {
            "breakfast": MealType.BREAKFAST,
            "lunch": MealType.LUNCH,
            "dinner": MealType.DINNER,
            "snack": MealType.SNACK
        }
        meal_type_enum = meal_type_map.get(meal_type.lower(), MealType.SNACK)
        
        if not estimated_calories:
            estimated_calories = self._estimate_calories(food_description)
        
        record = MealRecord(
            user_id=self.user_id,
            meal_type=meal_type_enum,
            food_items=[{"name": food_description, "calories": estimated_calories}],
            total_calories=estimated_calories,
            record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()
        
        meal_names = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}
        return {
            "success": True,
            "message": f"✅ 已记录{meal_names.get(meal_type.lower(), '餐食')}：{food_description}（约{estimated_calories}千卡）",
            "action_type": "meal_recorded",
            "data": {
                "meal_type": meal_type,
                "food": food_description,
                "calories": estimated_calories
            }
        }
    
    def _estimate_calories(self, food_description: str) -> int:
        """估算食物热量"""
        food_lower = food_description.lower()
        
        high_calorie = ["炸鸡", "汉堡", "披萨", "火锅", "烧烤", "红烧肉", "蛋糕", "奶茶"]
        medium_calorie = ["米饭", "面条", "面包", "牛肉", "猪肉", "饺子", "包子"]
        low_calorie = ["蔬菜", "水果", "沙拉", "鸡蛋", "豆腐", "豆浆", "酸奶"]
        
        for food in high_calorie:
            if food in food_lower:
                return 600
        for food in medium_calorie:
            if food in food_lower:
                return 400
        for food in low_calorie:
            if food in food_lower:
                return 200
        return 350
    
    async def _record_exercise(
        self, 
        exercise_type: str, 
        duration_minutes: int,
        calories_burned: Optional[int] = None
    ) -> dict:
        """记录运动"""
        from models.database import ExerciseRecord
        
        if not calories_burned:
            calories_burned = self._estimate_exercise_calories(exercise_type, duration_minutes)
        
        record = ExerciseRecord(
            user_id=self.user_id,
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            calories_burned=calories_burned,
            record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()
        
        return {
            "success": True,
            "message": f"✅ 已记录运动：{exercise_type} {duration_minutes}分钟（消耗约{calories_burned}千卡）",
            "action_type": "exercise_recorded",
            "data": {
                "type": exercise_type,
                "duration": duration_minutes,
                "calories": calories_burned
            }
        }
    
    def _estimate_exercise_calories(self, exercise_type: str, duration_minutes: int) -> int:
        """估算运动热量"""
        calories_per_hour = {
            "跑步": 600, "慢跑": 500, "快跑": 700,
            "游泳": 500, "骑车": 400, "骑行": 400,
            "快走": 300, "散步": 200, "走路": 250,
            "健身": 450, "瑜伽": 250, "跳绳": 700
        }
        for key, calories in calories_per_hour.items():
            if key in exercise_type:
                return int(calories * duration_minutes / 60)
        return int(350 * duration_minutes / 60)
    
    async def _record_water(self, amount_ml: int, drink_type: str = "水") -> dict:
        """记录饮水"""
        from models.database import WaterRecord
        
        record = WaterRecord(
            user_id=self.user_id,
            amount_ml=amount_ml,
            record_time=datetime.utcnow()
        )
        self.db.add(record)
        await self.db.commit()
        
        return {
            "success": True,
            "message": f"✅ 已记录饮水：{amount_ml}ml {drink_type}",
            "action_type": "water_recorded",
            "data": {"amount_ml": amount_ml, "drink_type": drink_type}
        }
    
    async def _get_today_data(self) -> dict:
        """获取今日数据"""
        from models.database import WeightRecord, MealRecord, ExerciseRecord, WaterRecord
        from sqlalchemy import func
        
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        
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
            select(MealRecord).where(and_(
                MealRecord.user_id == self.user_id,
                MealRecord.record_time >= today_start,
                MealRecord.record_time <= today_end
            ))
        )
        meals = meal_result.scalars().all()
        
        # 今日运动
        exercise_result = await self.db.execute(
            select(ExerciseRecord).where(and_(
                ExerciseRecord.user_id == self.user_id,
                ExerciseRecord.record_time >= today_start,
                ExerciseRecord.record_time <= today_end
            ))
        )
        exercises = exercise_result.scalars().all()
        
        # 今日饮水
        water_result = await self.db.execute(
            select(WaterRecord).where(and_(
                WaterRecord.user_id == self.user_id,
                WaterRecord.record_time >= today_start,
                WaterRecord.record_time <= today_end
            ))
        )
        waters = water_result.scalars().all()
        
        data = {
            "latest_weight": latest_weight.weight if latest_weight else None,
            "meal_count": len(meals),
            "total_calories": sum(m.total_calories or 0 for m in meals),
            "exercise_minutes": sum(e.duration_minutes or 0 for e in exercises),
            "exercise_calories": sum(e.calories_burned or 0 for e in exercises),
            "total_water": sum(w.amount_ml or 0 for w in waters)
        }
        
        return {
            "success": True,
            "message": f"今日数据：体重{data['latest_weight'] or '暂无'}kg，餐食{data['meal_count']}次，运动{data['exercise_minutes']}分钟，饮水{data['total_water']}ml",
            "data": data
        }
    
    async def _query_history(self, data_type: str, days: int = 7) -> dict:
        """查询历史数据"""
        # 简化实现，实际应该根据 data_type 查询不同表
        return {
            "success": True,
            "message": f"查询了最近{days}天的{data_type}数据",
            "data": {"data_type": data_type, "days": days}
        }


# ============== 便捷函数 ==============

def get_weight_management_tools() -> list:
    """
    获取完整的体重管理工具列表
    
    Returns:
        适合传递给 create_react_agent 的工具列表
    """
    return get_decorated_tools()
