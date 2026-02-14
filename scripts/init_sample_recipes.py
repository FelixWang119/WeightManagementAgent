"""
初始化示例食谱数据
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    Base,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    FoodItem,
    RecipeDifficulty,
    RecipeCategory,
    RecipeCuisine,
    FoodCategory,
)
from config.settings import fastapi_settings


# 示例食谱数据
SAMPLE_RECIPES = [
    {
        "name": "鸡胸肉沙拉",
        "description": "低卡高蛋白的健身餐，适合减脂期",
        "prep_time": 15,
        "cook_time": 10,
        "servings": 1,
        "difficulty": RecipeDifficulty.EASY,
        "category": RecipeCategory.LUNCH,
        "cuisine": RecipeCuisine.LOW_CALORIE,
        "calories_per_serving": 320,
        "protein_per_serving": 35.0,
        "fat_per_serving": 12.0,
        "carbs_per_serving": 15.0,
        "image_url": None,
        "is_public": True,
        "ingredients": [
            {"ingredient_name": "鸡胸肉", "quantity": 150, "unit": "克"},
            {"ingredient_name": "生菜", "quantity": 100, "unit": "克"},
            {"ingredient_name": "小番茄", "quantity": 50, "unit": "克"},
            {"ingredient_name": "黄瓜", "quantity": 50, "unit": "克"},
            {"ingredient_name": "橄榄油", "quantity": 5, "unit": "毫升"},
            {"ingredient_name": "柠檬汁", "quantity": 10, "unit": "毫升"},
        ],
        "steps": [
            {"description": "鸡胸肉洗净，用厨房纸吸干水分"},
            {"description": "平底锅加热，放入鸡胸肉，中火煎至两面金黄"},
            {"description": "生菜、小番茄、黄瓜洗净切好，放入碗中"},
            {"description": "将煎好的鸡胸肉切成条状，放在蔬菜上"},
            {"description": "淋上橄榄油和柠檬汁，拌匀即可食用"},
        ],
    },
    {
        "name": "燕麦早餐碗",
        "description": "营养丰富的早餐，提供持久能量",
        "prep_time": 5,
        "cook_time": 5,
        "servings": 1,
        "difficulty": RecipeDifficulty.EASY,
        "category": RecipeCategory.BREAKFAST,
        "cuisine": RecipeCuisine.HIGH_PROTEIN,
        "calories_per_serving": 280,
        "protein_per_serving": 15.0,
        "fat_per_serving": 8.0,
        "carbs_per_serving": 40.0,
        "image_url": None,
        "is_public": True,
        "ingredients": [
            {"ingredient_name": "燕麦片", "quantity": 40, "unit": "克"},
            {"ingredient_name": "牛奶", "quantity": 150, "unit": "毫升"},
            {"ingredient_name": "香蕉", "quantity": 1, "unit": "根"},
            {"ingredient_name": "蓝莓", "quantity": 30, "unit": "克"},
            {"ingredient_name": "杏仁", "quantity": 10, "unit": "克"},
        ],
        "steps": [
            {"description": "燕麦片和牛奶放入碗中，微波炉加热2分钟"},
            {"description": "香蕉切片，蓝莓洗净"},
            {"description": "将香蕉片和蓝莓放在燕麦上"},
            {"description": "撒上杏仁碎，即可食用"},
        ],
    },
    {
        "name": "番茄鸡蛋面",
        "description": "简单快手的中式面食，温暖饱腹",
        "prep_time": 10,
        "cook_time": 15,
        "servings": 1,
        "difficulty": RecipeDifficulty.EASY,
        "category": RecipeCategory.LUNCH,
        "cuisine": RecipeCuisine.CHINESE,
        "calories_per_serving": 380,
        "protein_per_serving": 18.0,
        "fat_per_serving": 10.0,
        "carbs_per_serving": 55.0,
        "image_url": None,
        "is_public": True,
        "ingredients": [
            {"ingredient_name": "面条", "quantity": 100, "unit": "克"},
            {"ingredient_name": "鸡蛋", "quantity": 2, "unit": "个"},
            {"ingredient_name": "番茄", "quantity": 1, "unit": "个"},
            {"ingredient_name": "葱花", "quantity": 5, "unit": "克"},
            {"ingredient_name": "盐", "quantity": 2, "unit": "克"},
            {"ingredient_name": "食用油", "quantity": 10, "unit": "毫升"},
        ],
        "steps": [
            {"description": "番茄洗净切块，鸡蛋打散"},
            {"description": "锅中烧水，水开后下面条，煮至8分熟捞出"},
            {"description": "热锅倒油，倒入鸡蛋液炒散，盛出备用"},
            {"description": "锅中再加少许油，放入番茄块炒至出汁"},
            {"description": "加入炒好的鸡蛋和煮好的面条，加盐调味"},
            {"description": "翻炒均匀，撒上葱花即可出锅"},
        ],
    },
    {
        "name": "蔬菜豆腐汤",
        "description": "清淡低卡的素食汤品，适合晚餐",
        "prep_time": 10,
        "cook_time": 20,
        "servings": 2,
        "difficulty": RecipeDifficulty.EASY,
        "category": RecipeCategory.DINNER,
        "cuisine": RecipeCuisine.VEGETARIAN,
        "calories_per_serving": 150,
        "protein_per_serving": 12.0,
        "fat_per_serving": 5.0,
        "carbs_per_serving": 10.0,
        "image_url": None,
        "is_public": True,
        "ingredients": [
            {"ingredient_name": "嫩豆腐", "quantity": 200, "unit": "克"},
            {"ingredient_name": "菠菜", "quantity": 100, "unit": "克"},
            {"ingredient_name": "香菇", "quantity": 50, "unit": "克"},
            {"ingredient_name": "胡萝卜", "quantity": 50, "unit": "克"},
            {"ingredient_name": "姜片", "quantity": 2, "unit": "片"},
            {"ingredient_name": "盐", "quantity": 3, "unit": "克"},
            {"ingredient_name": "香油", "quantity": 5, "unit": "毫升"},
        ],
        "steps": [
            {"description": "豆腐切块，菠菜洗净，香菇切片，胡萝卜切丝"},
            {"description": "锅中加水烧开，放入姜片和香菇煮5分钟"},
            {"description": "加入豆腐块和胡萝卜丝，煮10分钟"},
            {"description": "放入菠菜，煮1分钟"},
            {"description": "加盐调味，淋上香油即可"},
        ],
    },
    {
        "name": "希腊酸奶杯",
        "description": "高蛋白低糖的零食，适合加餐",
        "prep_time": 5,
        "cook_time": 0,
        "servings": 1,
        "difficulty": RecipeDifficulty.EASY,
        "category": RecipeCategory.SNACK,
        "cuisine": RecipeCuisine.HIGH_PROTEIN,
        "calories_per_serving": 180,
        "protein_per_serving": 20.0,
        "fat_per_serving": 5.0,
        "carbs_per_serving": 15.0,
        "image_url": None,
        "is_public": True,
        "ingredients": [
            {"ingredient_name": "希腊酸奶", "quantity": 150, "unit": "克"},
            {"ingredient_name": "草莓", "quantity": 50, "unit": "克"},
            {"ingredient_name": "奇亚籽", "quantity": 10, "unit": "克"},
            {"ingredient_name": "蜂蜜", "quantity": 5, "unit": "毫升"},
        ],
        "steps": [
            {"description": "草莓洗净切片"},
            {"description": "杯底铺一层希腊酸奶"},
            {"description": "放上草莓片，撒上奇亚籽"},
            {"description": "再铺一层希腊酸奶，淋上蜂蜜"},
            {"description": "冷藏10分钟后食用更佳"},
        ],
    },
]


async def init_sample_recipes():
    """初始化示例食谱"""
    # 创建数据库引擎
    engine = create_async_engine(
        fastapi_settings.DATABASE_URL,
        echo=False,
    )

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 检查是否已有食谱
            result = await session.execute(select(Recipe))
            existing_recipes = result.scalars().all()

            if existing_recipes:
                print(f"⚠️ 数据库中已有 {len(existing_recipes)} 个食谱，跳过初始化")
                return

            print("开始初始化示例食谱...")

            # 创建示例食谱
            for recipe_data in SAMPLE_RECIPES:
                # 创建食谱对象
                recipe = Recipe(
                    name=recipe_data["name"],
                    description=recipe_data["description"],
                    prep_time=recipe_data["prep_time"],
                    cook_time=recipe_data["cook_time"],
                    total_time=recipe_data["prep_time"] + recipe_data["cook_time"],
                    servings=recipe_data["servings"],
                    difficulty=recipe_data["difficulty"],
                    category=recipe_data["category"],
                    cuisine=recipe_data["cuisine"],
                    calories_per_serving=recipe_data["calories_per_serving"],
                    protein_per_serving=recipe_data["protein_per_serving"],
                    fat_per_serving=recipe_data["fat_per_serving"],
                    carbs_per_serving=recipe_data["carbs_per_serving"],
                    image_url=recipe_data["image_url"],
                    is_public=recipe_data["is_public"],
                    created_by=None,  # 系统创建
                )

                session.add(recipe)
                await session.flush()

                # 添加食材
                for idx, ingredient_data in enumerate(recipe_data["ingredients"]):
                    # 尝试查找对应的食物项
                    food_item = None
                    if ingredient_data["ingredient_name"] in [
                        "鸡胸肉",
                        "牛奶",
                        "鸡蛋",
                        "豆腐",
                        "希腊酸奶",
                    ]:
                        result = await session.execute(
                            select(FoodItem).where(
                                FoodItem.name == ingredient_data["ingredient_name"]
                            )
                        )
                        food_item = result.scalar_one_or_none()

                    ingredient = RecipeIngredient(
                        recipe_id=recipe.id,
                        food_item_id=food_item.id if food_item else None,
                        ingredient_name=ingredient_data["ingredient_name"],
                        quantity=ingredient_data["quantity"],
                        unit=ingredient_data["unit"],
                        order_index=idx,
                    )
                    session.add(ingredient)

                # 添加步骤
                for idx, step_data in enumerate(recipe_data["steps"]):
                    step = RecipeStep(
                        recipe_id=recipe.id,
                        step_number=idx + 1,
                        description=step_data["description"],
                        order_index=idx,
                    )
                    session.add(step)

                print(f"✅ 创建食谱: {recipe_data['name']}")

            await session.commit()
            print(f"✅ 成功初始化 {len(SAMPLE_RECIPES)} 个示例食谱")

        except Exception as e:
            await session.rollback()
            print(f"❌ 初始化失败: {str(e)}")
            raise


if __name__ == "__main__":
    asyncio.run(init_sample_recipes())
