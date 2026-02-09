"""
工具函数

定义 Agent 可用的工具
"""

from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


def create_tools_for_user(db: AsyncSession, user_id: int):
    """创建用户可用的工具列表"""
    return [
        {
            "name": "record_weight",
            "description": "记录用户体重数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "weight": {"type": "number", "description": "体重（kg）"},
                    "note": {"type": "string", "description": "备注（可选）"}
                },
                "required": ["weight"]
            }
        },
        {
            "name": "query_history",
            "description": "查询用户历史数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {"type": "string", "description": "数据类型：weight/meal/exercise"},
                    "days": {"type": "integer", "description": "查询天数，默认7天"}
                }
            }
        },
        {
            "name": "get_today_data",
            "description": "获取用户今日数据",
            "parameters": {"type": "object", "properties": {}}
        }
    ]


async def execute_tool(tool_name: str, arguments: Dict[str, Any], user_id: int, db: AsyncSession) -> str:
    """执行工具调用"""
    if tool_name == "record_weight":
        return await _record_weight(arguments.get("weight"), arguments.get("note"), user_id, db)
    elif tool_name == "query_history":
        return await _query_history(arguments.get("data_type"), arguments.get("days", 7), user_id, db)
    elif tool_name == "get_today_data":
        return await _get_today_data(user_id, db)
    return f"未知工具: {tool_name}"


async def _record_weight(weight: float, note: Optional[str], user_id: int, db: AsyncSession) -> str:
    """记录体重"""
    try:
        from models.database import WeightRecord
        record = WeightRecord(
            user_id=user_id,
            weight=weight,
            note=note,
            record_time=datetime.utcnow()
        )
        db.add(record)
        await db.commit()
        return f"已记录体重：{weight}kg"
    except Exception as e:
        return f"记录体重失败: {e}"


async def _query_history(data_type: str, days: int, user_id: int, db: AsyncSession) -> str:
    """查询历史数据"""
    try:
        from models.database import WeightRecord, MealRecord
        from datetime import timedelta

        if data_type == "weight":
            result = await db.execute(
                select(WeightRecord)
                .where(WeightRecord.user_id == user_id)
                .order_by(WeightRecord.record_time.desc())
                .limit(days)
            )
            records = result.scalars().all()
            if records:
                return "近期体重记录：\n" + "\n".join([f"- {r.record_time.strftime('%Y-%m-%d')}: {r.weight}kg" for r in records])
            return "暂无体重记录"
        return f"查询 {data_type} 历史记录"
    except Exception as e:
        return f"查询失败: {e}"


async def _get_today_data(user_id: int, db: AsyncSession) -> str:
    """获取今日数据"""
    try:
        from models.database import WeightRecord, MealRecord
        from datetime import date

        weight_result = await db.execute(
            select(WeightRecord)
            .where(WeightRecord.user_id == user_id)
            .order_by(WeightRecord.record_time.desc())
            .limit(1)
        )
        latest_weight = weight_result.scalar_one_or_none()

        meal_result = await db.execute(
            select(MealRecord)
            .where(MealRecord.user_id == user_id)
            .where(MealRecord.record_time >= datetime.combine(date.today(), datetime.min.time()))
        )
        meals = meal_result.scalars().all()

        return f"今日数据：\n最新体重：{latest_weight.weight if latest_weight else '暂无'}kg\n记录餐次：{len(meals)}次"
    except Exception as e:
        return f"获取数据失败: {e}"
