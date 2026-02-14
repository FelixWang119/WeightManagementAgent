"""
餐食管理 API 路由（Phase 2 核心功能）
包含：餐食记录、AI识别、食物数据库
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, date, timedelta
import json
import os
import uuid

from models.database import get_db, User, MealRecord, FoodItem, UserFood, MealType
from api.routes.user import get_current_user
from config.settings import fastapi_settings
from services.ai_service import ai_service

router = APIRouter()


# ============ 食物数据库 ============

# 基础食物数据库（内置常见中餐）
DEFAULT_FOODS = [
    {
        "name": "米饭",
        "category": "staple",
        "calories_per_100g": 116,
        "common_portions": {"一碗": 150, "一拳": 100},
    },
    {
        "name": "馒头",
        "category": "staple",
        "calories_per_100g": 223,
        "common_portions": {"一个": 100},
    },
    {
        "name": "面条",
        "category": "staple",
        "calories_per_100g": 137,
        "common_portions": {"一碗": 200},
    },
    {
        "name": "小米粥",
        "category": "staple",
        "calories_per_100g": 46,
        "common_portions": {"一碗": 250},
    },
    {
        "name": "鸡蛋",
        "category": "meat",
        "calories_per_100g": 155,
        "common_portions": {"一个": 50},
    },
    {
        "name": "鸡胸肉",
        "category": "meat",
        "calories_per_100g": 165,
        "protein": 31,
        "fat": 3.6,
    },
    {
        "name": "猪肉",
        "category": "meat",
        "calories_per_100g": 250,
        "common_portions": {"一份": 100},
    },
    {"name": "牛肉", "category": "meat", "calories_per_100g": 250},
    {
        "name": "西红柿炒鸡蛋",
        "category": "vegetable",
        "calories_per_100g": 85,
        "common_portions": {"一份": 200},
    },
    {
        "name": "炒青菜",
        "category": "vegetable",
        "calories_per_100g": 45,
        "common_portions": {"一份": 150},
    },
    {
        "name": "苹果",
        "category": "fruit",
        "calories_per_100g": 52,
        "common_portions": {"一个": 200},
    },
    {
        "name": "香蕉",
        "category": "fruit",
        "calories_per_100g": 89,
        "common_portions": {"一根": 120},
    },
    {
        "name": "牛奶",
        "category": "drink",
        "calories_per_100g": 54,
        "common_portions": {"一杯": 250},
    },
    {
        "name": "豆浆",
        "category": "drink",
        "calories_per_100g": 31,
        "common_portions": {"一杯": 250},
    },
    {
        "name": "可乐",
        "category": "drink",
        "calories_per_100g": 42,
        "common_portions": {"一罐": 330},
    },
]


async def init_food_database(db: AsyncSession):
    """初始化食物数据库"""
    # 检查是否已有数据
    result = await db.execute(select(FoodItem).limit(1))
    if result.scalar_one_or_none():
        return

    # 添加默认食物
    for food_data in DEFAULT_FOODS:
        food = FoodItem(
            name=food_data["name"],
            category=food_data.get("category", "other"),
            calories_per_100g=food_data["calories_per_100g"],
            protein=food_data.get("protein"),
            fat=food_data.get("fat"),
            carbs=food_data.get("carbs"),
            common_portions=food_data.get("common_portions", {}),
            is_user_created=False,
        )
        db.add(food)

    await db.commit()
    print(f"✅ 已初始化食物数据库，共 {len(DEFAULT_FOODS)} 种食物")


# ============ API 路由 ============


@router.post("/record")
async def record_meal(
    meal_type: str,
    content: str,  # 食物描述或AI识别结果
    calories: Optional[int] = None,
    photo_url: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    记录餐食（同一天同一餐自动覆盖）

    - **meal_type**: 餐食类型 (breakfast/lunch/dinner/snack)
    - **content**: 食物内容描述
    - **calories**: 热量（千卡，可选）
    - **photo_url**: 照片URL（可选）
    """
    try:
        meal_enum = MealType(meal_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的餐食类型")

    # 如果没有提供热量，尝试从食物数据库计算
    if calories is None:
        calories = await estimate_calories(content, db)

    # 检查今天是否已有同类型的餐食记录
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(MealRecord)
        .where(
            and_(
                MealRecord.user_id == current_user.id,
                MealRecord.meal_type == meal_enum,
                MealRecord.record_time >= today_start,
                MealRecord.record_time <= today_end,
            )
        )
        .order_by(MealRecord.record_time.desc())  # 最新的排在前面
    )
    existing_records = result.scalars().all()
    existing_record = existing_records[0] if existing_records else None

    # 如果有多条旧记录，删除多余的（只保留最新的一条用于更新）
    if len(existing_records) > 1:
        for old_record in existing_records[1:]:
            await db.delete(old_record)

    if existing_record:
        # 更新已有记录
        existing_record.food_items = [{"name": content, "calories": calories}]
        existing_record.total_calories = calories or 0
        existing_record.photo_url = photo_url
        existing_record.record_time = datetime.utcnow()
        message = "餐食记录已更新"
        record_id = existing_record.id
    else:
        # 创建新记录
        record = MealRecord(
            user_id=current_user.id,
            meal_type=meal_enum,
            record_time=datetime.utcnow(),
            photo_url=photo_url,
            food_items=[{"name": content, "calories": calories}],
            total_calories=calories or 0,
            user_confirmed=True,
            ai_confidence=None,
        )
        db.add(record)
        await db.flush()  # 获取新记录的ID
        record_id = record.id
        message = "餐食记录成功"

    await db.commit()

    return {
        "success": True,
        "message": message,
        "data": {
            "id": record_id,
            "meal_type": meal_type,
            "content": content,
            "calories": calories,
            "is_update": existing_record is not None,
            "record_time": datetime.utcnow().isoformat(),
        },
    }


@router.post("/analyze")
async def analyze_meal_photo(
    meal_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI 分析餐食照片

    - **meal_type**: 餐食类型
    - **file**: 餐食照片文件

    返回 AI 识别的食物信息和热量估算
    """
    import base64

    # 保存上传的文件
    file_ext = os.path.splitext(file.filename)[1] or ".jpg"
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(fastapi_settings.UPLOAD_DIR, file_name)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 构建文件 URL（本地访问）
    file_url = f"/uploads/{file_name}"

    # 使用 AI 分析图片 - 通过base64编码直接传给AI
    ai_result = None
    try:
        # 压缩图片，限制大小以加快上传和API调用
        from PIL import Image
        import io

        # 打开图片
        img = Image.open(io.BytesIO(contents))

        # 转换为RGB（处理PNG等格式）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # 压缩图片：最大宽度1024px，质量85%
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # 保存为JPEG，压缩质量
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        compressed_contents = buffer.getvalue()

        print(
            f"图片压缩前: {len(contents) / 1024:.1f}KB, 压缩后: {len(compressed_contents) / 1024:.1f}KB"
        )

        # 将压缩后的图片转为base64
        image_base64 = base64.b64encode(compressed_contents).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{image_base64}"

        print(f"Base64长度: {len(data_url)} 字符")

        # 构建提示词
        prompt = """请分析这张餐食照片，识别出所有食物，并估算每种食物的热量和分量。

请按以下JSON格式返回结果：
{
    "foods": [
        {
            "name": "食物名称",
            "amount": "分量描述（如：一碗、一份、100克等）",
            "calories": 热量数值（整数）,
            "icon": "emoji图标（如：🍚、🥬、🍗等）"
        }
    ],
    "total_calories": 总热量,
    "suggestions": "营养建议（如：蛋白质充足、蔬菜偏少等）"
}

请确保：
1. 识别出所有可见的食物
2. 热量估算要合理（参考常见中餐热量）
3. 返回必须是有效的JSON格式"""

        # 调用AI进行视觉分析
        ai_response = await ai_service.analyze_image(data_url, prompt)

        print(f"AI Response: {ai_response}")
        print(f"AI Content type: {type(ai_response.content)}")
        print(
            f"AI Content: {ai_response.content[:200] if ai_response.content else 'None'}..."
        )

        if ai_response.error:
            raise Exception(ai_response.error)

        # 解析AI返回的JSON
        import json
        import re

        # 尝试从AI响应中提取JSON
        content = ai_response.content
        if isinstance(content, list):
            # 如果返回的是列表，取第一个元素
            content = content[0] if content else ""

        # 查找JSON块
        json_match = re.search(r"\{[\s\S]*\}", str(content))
        if json_match:
            ai_result = json.loads(json_match.group())
        else:
            # 尝试直接解析
            ai_result = json.loads(str(content))

    except Exception as e:
        print(f"AI分析失败: {e}")
        import traceback

        traceback.print_exc()
        # 返回错误信息，但仍然保存了图片
        return {
            "success": False,
            "message": f"AI分析失败: {str(e)}",
            "data": {
                "photo_url": file_url,
                "file_name": file_name,
                "meal_type": meal_type,
                "ai_analysis": None,
            },
        }

    return {
        "success": True,
        "message": "AI分析完成",
        "data": {
            "photo_url": file_url,
            "file_name": file_name,
            "meal_type": meal_type,
            "ai_analysis": ai_result,
            "foods": ai_result.get("foods", []),
            "total_calories": ai_result.get("total_calories", 0),
            "suggestions": ai_result.get("suggestions", ""),
        },
    }


@router.get("/today")
async def get_today_meals(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取今日餐食记录"""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(MealRecord)
        .where(
            and_(
                MealRecord.user_id == current_user.id,
                MealRecord.record_time >= today_start,
                MealRecord.record_time <= today_end,
            )
        )
        .order_by(MealRecord.record_time.desc())
    )

    records = result.scalars().all()

    # 按餐食类型统计
    meal_summary = {}
    total_calories = 0

    for record in records:
        meal_type = record.meal_type.value
        if meal_type not in meal_summary:
            meal_summary[meal_type] = {"count": 0, "calories": 0}
        meal_summary[meal_type]["count"] += 1
        meal_summary[meal_type]["calories"] += record.total_calories
        total_calories += record.total_calories

    return {
        "success": True,
        "date": today.isoformat(),
        "total_calories": total_calories,
        "meal_summary": meal_summary,
        "records": [
            {
                "id": r.id,
                "meal_type": r.meal_type.value,
                "food_items": r.food_items,
                "total_calories": r.total_calories,
                "photo_url": r.photo_url,
                "record_time": r.record_time.isoformat(),
            }
            for r in records
        ],
    }


@router.get("/search")
async def search_food(
    keyword: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索食物"""
    # 搜索系统食物库
    result = await db.execute(
        select(FoodItem).where(FoodItem.name.contains(keyword)).limit(limit)
    )
    system_foods = result.scalars().all()

    # 搜索用户自定义食物
    result = await db.execute(
        select(UserFood)
        .where(
            and_(
                UserFood.user_id == current_user.id,
                UserFood.food_name.contains(keyword),
            )
        )
        .limit(limit)
    )
    user_foods = result.scalars().all()

    return {
        "success": True,
        "keyword": keyword,
        "system_foods": [
            {
                "id": f.id,
                "name": f.name,
                "category": f.category.value if f.category else None,
                "calories_per_100g": f.calories_per_100g,
                "common_portions": f.common_portions,
            }
            for f in system_foods
        ],
        "user_foods": [
            {"id": f.id, "name": f.food_name, "calories": f.calories}
            for f in user_foods
        ],
    }


@router.post("/foods/custom")
async def add_custom_food(
    food_name: str,
    calories: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加自定义食物"""
    user_food = UserFood(
        user_id=current_user.id, food_name=food_name, calories=calories
    )
    db.add(user_food)
    await db.commit()

    return {
        "success": True,
        "message": "自定义食物添加成功",
        "data": {"id": user_food.id, "food_name": food_name, "calories": calories},
    }


# ============ 辅助函数 ============


async def estimate_calories(content: str, db: AsyncSession) -> Optional[int]:
    """估算食物热量"""
    # 简单匹配食物数据库
    total_calories = 0
    found_foods = []

    # 分词并匹配（简化版）
    for food_name in content.split():
        result = await db.execute(
            select(FoodItem).where(FoodItem.name.contains(food_name))
        )
        food = result.scalar_one_or_none()
        if food:
            # 使用常见分量估算
            portion = 100  # 默认100克
            if food.common_portions:
                # 使用第一个常见分量
                portion = list(food.common_portions.values())[0]

            calories = int(food.calories_per_100g * portion / 100)
            total_calories += calories
            found_foods.append(
                {"name": food.name, "portion": portion, "calories": calories}
            )

    # 如果没找到匹配的食物，返回 None
    if not found_foods:
        return None

    return total_calories


# 初始化食物数据库的便捷路由
@router.post("/init-database")
async def initialize_food_db(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """初始化食物数据库（仅管理员使用）"""
    await init_food_database(db)
    return {"success": True, "message": "食物数据库初始化完成"}


# ============ AI识别确认/修正系统 ============

# 临时存储AI识别结果（生产环境应使用Redis或数据库）
_temp_ai_results = {}


@router.post("/analyze-with-confirm")
async def analyze_meal_with_confirm(
    meal_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI分析餐食照片（带确认流程）

    返回AI识别结果，但不直接保存，等待用户确认
    """
    # 先调用原有的 analyze 逻辑
    result = await analyze_meal_photo(meal_type, file, current_user, db)

    if not result.get("success"):
        return result

    # 生成确认ID
    import uuid

    confirm_id = str(uuid.uuid4())

    # 保存到临时存储
    _temp_ai_results[confirm_id] = {
        "user_id": current_user.id,
        "meal_type": meal_type,
        "data": result["data"],
        "created_at": datetime.utcnow(),
    }

    # 添加确认ID到返回结果
    result["data"]["confirm_id"] = confirm_id
    result["data"]["needs_confirmation"] = True

    return result


@router.post("/confirm")
async def confirm_meal_record(
    confirm_id: str,
    adjustments: Optional[
        str
    ] = None,  # JSON字符串: {"foods": [{"name": "...", "calories": 300, "adjustment": 1.2}], "total_calories": 600}
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    确认AI识别结果并保存餐食记录

    - **confirm_id**: 确认ID（从 analyze-with-confirm 获得）
    - **adjustments**: 用户调整（可选），JSON格式包含修正后的食物列表和总热量
    """
    # 验证确认ID
    if confirm_id not in _temp_ai_results:
        raise HTTPException(status_code=404, detail="确认ID无效或已过期")

    temp_data = _temp_ai_results[confirm_id]

    # 验证用户权限
    if temp_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此确认ID")

    # 检查是否过期（30分钟）
    if datetime.utcnow() - temp_data["created_at"] > timedelta(minutes=30):
        del _temp_ai_results[confirm_id]
        raise HTTPException(status_code=400, detail="确认已过期，请重新上传")

    ai_data = temp_data["data"]
    meal_type = temp_data["meal_type"]

    # 解析用户调整
    foods = ai_data["foods"].copy()
    total_calories = ai_data["total_calories"]
    content_parts = []

    if adjustments:
        try:
            adj_data = json.loads(adjustments)

            # 应用用户调整
            if "foods" in adj_data:
                foods = adj_data["foods"]
                content_parts = [f["name"] for f in foods]

            if "total_calories" in adj_data:
                total_calories = adj_data["total_calories"]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="调整数据格式错误")
    else:
        # 使用原始AI识别结果
        content_parts = [f["name"] for f in foods]

    content = (
        "、".join(content_parts)
        if content_parts
        else ai_data.get("suggestions", "餐食")
    )

    # 保存餐食记录
    try:
        meal_enum = MealType(meal_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的餐食类型")

    today = date.today()

    # 检查今天是否已有该餐食类型的记录
    result = await db.execute(
        select(MealRecord).where(
            and_(
                MealRecord.user_id == current_user.id,
                MealRecord.meal_type == meal_enum,
                func.date(MealRecord.record_time) == today,
            )
        )
    )
    existing_record = result.scalar_one_or_none()

    if existing_record:
        # 覆盖已有记录
        existing_record.food_items = foods
        existing_record.total_calories = total_calories
        existing_record.photo_url = ai_data.get("photo_url")
        existing_record.record_time = datetime.utcnow()
        message = "餐食记录已更新"
    else:
        # 创建新记录
        record = MealRecord(
            user_id=current_user.id,
            meal_type=meal_enum,
            food_items=foods,
            total_calories=total_calories,
            photo_url=ai_data.get("photo_url"),
            record_time=datetime.utcnow(),
        )
        db.add(record)
        message = "餐食记录成功"

    await db.commit()

    # 清理临时数据
    del _temp_ai_results[confirm_id]

    return {
        "success": True,
        "message": message,
        "data": {
            "meal_type": meal_type,
            "content": content,
            "total_calories": total_calories,
            "food_count": len(foods),
            "adjusted": adjustments is not None,
            "record_time": datetime.utcnow().isoformat(),
        },
    }


@router.post("/reanalyze")
async def reanalyze_meal_description(
    confirm_id: str,
    description: str,  # 用户重新描述的食物内容
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    根据用户重新描述的内容重新分析餐食

    - **confirm_id**: 原确认ID
    - **description**: 用户重新描述的食物内容（如："一碗米饭、一份番茄炒蛋"）
    """
    # 验证确认ID
    if confirm_id not in _temp_ai_results:
        raise HTTPException(status_code=404, detail="确认ID无效或已过期")

    temp_data = _temp_ai_results[confirm_id]

    # 验证用户权限
    if temp_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此确认ID")

    # 使用AI服务分析文本描述
    prompt = f"""请分析以下餐食描述，识别出所有食物，并估算每种食物的热量和分量。

描述内容：{description}

请按以下JSON格式返回结果：
{{
    "foods": [
        {{
            "name": "食物名称",
            "amount": "分量描述（如：一碗、一份、100克等）",
            "calories": 热量数值（整数）,
            "icon": "emoji图标（如：🍚、🥬、🍗等）"
        }}
    ],
    "total_calories": 总热量,
    "suggestions": "营养建议"
}}

请确保：
1. 根据中文描述准确识别食物
2. 热量估算要合理（参考常见中餐热量）
3. 返回必须是有效的JSON格式"""

    try:
        ai_response = await ai_service.generate_text(prompt)

        if ai_response.error:
            raise Exception(ai_response.error)

        # 解析AI返回的JSON
        import re

        content = ai_response.content
        if isinstance(content, list):
            content = content[0] if content else ""

        json_match = re.search(r"\{[\s\S]*\}", str(content))
        if json_match:
            ai_result = json.loads(json_match.group())
        else:
            ai_result = json.loads(str(content))

        # 更新临时数据
        temp_data["data"]["foods"] = ai_result.get("foods", [])
        temp_data["data"]["total_calories"] = ai_result.get("total_calories", 0)
        temp_data["data"]["suggestions"] = ai_result.get("suggestions", "")
        temp_data["data"]["reanalyzed"] = True
        temp_data["data"]["user_description"] = description

        return {
            "success": True,
            "message": "重新分析完成",
            "data": {
                "confirm_id": confirm_id,
                "foods": ai_result.get("foods", []),
                "total_calories": ai_result.get("total_calories", 0),
                "suggestions": ai_result.get("suggestions", ""),
            },
        }

    except Exception as e:
        return {"success": False, "message": f"重新分析失败: {str(e)}", "data": None}


@router.post("/cancel")
async def cancel_meal_confirmation(
    confirm_id: str, current_user: User = Depends(get_current_user)
):
    """
    取消餐食确认（用户觉得识别结果完全不对）

    - **confirm_id**: 确认ID
    """
    if confirm_id not in _temp_ai_results:
        raise HTTPException(status_code=404, detail="确认ID无效或已过期")

    temp_data = _temp_ai_results[confirm_id]

    # 验证用户权限
    if temp_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此确认ID")

    # 清理临时数据
    del _temp_ai_results[confirm_id]

    return {
        "success": True,
        "message": "已取消，请重新上传照片或手动输入",
        "data": {"cancelled": True},
    }


# ============ 快速食物选择系统 ============


@router.get("/foods/recent")
async def get_recent_foods(
    limit: int = Query(10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取最近食用的食物记录

    - **limit**: 返回数量（1-30，默认10）

    返回用户最近记录过的食物，方便快速选择
    """
    # 查询最近的食物记录
    result = await db.execute(
        select(MealRecord)
        .where(MealRecord.user_id == current_user.id)
        .order_by(MealRecord.record_time.desc())
        .limit(limit * 2)  # 多获取一些用于提取食物
    )
    records = result.scalars().all()

    # 提取食物并去重
    recent_foods = {}
    for record in records:
        if record.food_items:
            for item in record.food_items:
                if isinstance(item, dict) and "name" in item:
                    food_name = item["name"]
                    if food_name not in recent_foods:
                        recent_foods[food_name] = {
                            "name": food_name,
                            "calories": item.get("calories", 0),
                            "icon": item.get("icon", "🍽️"),
                            "last_used": record.record_time.isoformat(),
                        }

        if len(recent_foods) >= limit:
            break

    foods_list = list(recent_foods.values())[:limit]

    return {"success": True, "count": len(foods_list), "foods": foods_list}


# 收藏食物存储（生产环境应使用数据库）
_user_favorites = {}


@router.get("/foods/favorites")
async def get_favorite_foods(current_user: User = Depends(get_current_user)):
    """
    获取收藏的食物列表
    """
    user_id = current_user.id
    favorites = _user_favorites.get(user_id, [])

    return {"success": True, "count": len(favorites), "foods": favorites}


@router.post("/foods/favorites")
async def add_favorite_food(
    food_name: str,
    calories: int,
    icon: str = "🍽️",
    current_user: User = Depends(get_current_user),
):
    """
    收藏食物

    - **food_name**: 食物名称
    - **calories**: 热量
    - **icon**: 图标emoji
    """
    user_id = current_user.id

    if user_id not in _user_favorites:
        _user_favorites[user_id] = []

    # 检查是否已收藏
    existing = [f for f in _user_favorites[user_id] if f["name"] == food_name]
    if existing:
        return {"success": False, "message": "该食物已收藏"}

    _user_favorites[user_id].append(
        {"name": food_name, "calories": calories, "icon": icon}
    )

    return {
        "success": True,
        "message": "收藏成功",
        "data": {"name": food_name, "calories": calories, "icon": icon},
    }


@router.delete("/foods/favorites")
async def remove_favorite_food(
    food_name: str, current_user: User = Depends(get_current_user)
):
    """
    取消收藏食物

    - **food_name**: 食物名称
    """
    user_id = current_user.id

    if user_id not in _user_favorites:
        return {"success": False, "message": "没有收藏该食物"}

    _user_favorites[user_id] = [
        f for f in _user_favorites[user_id] if f["name"] != food_name
    ]

    return {"success": True, "message": "已取消收藏"}


@router.get("/foods/quick")
async def get_quick_foods(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    获取快速选择的食物列表（系统常用 + 最近食用 + 收藏）
    """
    user_id = current_user.id

    # 1. 获取系统常用食物
    system_foods_result = await db.execute(select(FoodItem).limit(15))
    system_foods = [
        {
            "name": f.name,
            "calories": f.calories_per_100g,
            "icon": "🍽️",
            "source": "system",
        }
        for f in system_foods_result.scalars()
    ]

    # 2. 获取最近食用
    recent_result = await db.execute(
        select(MealRecord)
        .where(MealRecord.user_id == user_id)
        .order_by(MealRecord.record_time.desc())
        .limit(20)
    )
    recent_foods = {}
    for record in recent_result.scalars():
        if record.food_items:
            for item in record.food_items:
                if isinstance(item, dict) and "name" in item:
                    food_name = item["name"]
                    if food_name not in recent_foods:
                        recent_foods[food_name] = {
                            "name": food_name,
                            "calories": item.get("calories", 0),
                            "icon": item.get("icon", "🍽️"),
                            "source": "recent",
                        }
        if len(recent_foods) >= 10:
            break

    # 3. 获取收藏
    favorites = _user_favorites.get(user_id, [])
    favorite_foods = [{**f, "source": "favorite"} for f in favorites]

    return {
        "success": True,
        "data": {
            "system": system_foods,
            "recent": list(recent_foods.values())[:10],
            "favorites": favorite_foods,
        },
    }
