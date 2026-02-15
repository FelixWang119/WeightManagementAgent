"""
食谱导入器模块
将生成的食谱导入到数据库
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

# 添加项目根目录到Python路径
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import fastapi_settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from models.database import (
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeDifficulty,
    RecipeCategory,
    RecipeCuisine,
)


class RecipeImporter:
    """食谱导入器"""

    def __init__(self):
        # 创建数据库连接
        self.engine = create_async_engine(fastapi_settings.DATABASE_URL)
        self.AsyncSessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def import_recipes(self, recipes: List[Dict[str, Any]]) -> bool:
        """导入食谱列表到数据库"""

        if not recipes:
            print("没有可导入的食谱")
            return False

        print(f"开始导入 {len(recipes)} 个食谱到数据库...")

        imported_count = 0
        skipped_count = 0

        async with self.AsyncSessionLocal() as session:
            for recipe_data in recipes:
                try:
                    # 检查是否已存在同名食谱
                    existing = await session.execute(
                        select(Recipe).where(Recipe.name == recipe_data["name"])
                    )
                    existing_recipe = existing.scalar_one_or_none()

                    if existing_recipe:
                        print(f"跳过已存在的食谱: {recipe_data['name']}")
                        skipped_count += 1
                        continue

                    # 创建食谱
                    recipe = Recipe(
                        name=recipe_data["name"],
                        description=recipe_data["description"],
                        prep_time=recipe_data["prep_time"],
                        cook_time=recipe_data["cook_time"],
                        total_time=recipe_data["total_time"],
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
                        created_by=None,
                    )

                    session.add(recipe)
                    await session.flush()

                    # 添加食材
                    for ingredient_data in recipe_data["ingredients"]:
                        ingredient = RecipeIngredient(
                            recipe_id=recipe.id,
                            ingredient_name=ingredient_data["ingredient_name"],
                            quantity=ingredient_data["quantity"],
                            unit=ingredient_data["unit"],
                            order_index=ingredient_data.get("order_index", 0),
                        )
                        session.add(ingredient)

                    # 添加步骤
                    for step_data in recipe_data["steps"]:
                        step = RecipeStep(
                            recipe_id=recipe.id,
                            step_number=step_data["step_number"],
                            description=step_data["description"],
                            order_index=step_data.get("order_index", 0),
                        )
                        session.add(step)

                    imported_count += 1
                    print(f"导入: {recipe_data['name']}")

                except Exception as e:
                    print(f"导入食谱 {recipe_data.get('name', '未知')} 失败: {e}")
                    continue

            await session.commit()

        print(f"\n导入完成!")
        print(f"成功导入: {imported_count} 个食谱")
        print(f"跳过重复: {skipped_count} 个食谱")

        return imported_count > 0

    async def import_from_json(self, json_file: str) -> bool:
        """从JSON文件导入食谱"""

        file_path = Path(json_file)
        if not file_path.exists():
            print(f"文件不存在: {json_file}")
            return False

        print(f"从文件导入: {json_file}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                recipes_data = json.load(f)

            if not isinstance(recipes_data, list):
                print("JSON文件格式错误：应该是一个数组")
                return False

            # 转换JSON数据为食谱对象
            recipes = []
            for recipe_data in recipes_data:
                recipe = self._convert_json_to_recipe(recipe_data)
                if recipe:
                    recipes.append(recipe)

            if not recipes:
                print("没有有效的食谱数据")
                return False

            return await self.import_recipes(recipes)

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return False
        except Exception as e:
            print(f"导入文件失败: {e}")
            return False

    def _convert_json_to_recipe(
        self, recipe_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """将JSON数据转换为食谱对象"""

        try:
            # 转换枚举值
            difficulty_map = {
                "easy": RecipeDifficulty.EASY,
                "medium": RecipeDifficulty.MEDIUM,
                "hard": RecipeDifficulty.HARD,
            }

            category_map = {
                "breakfast": RecipeCategory.BREAKFAST,
                "lunch": RecipeCategory.LUNCH,
                "dinner": RecipeCategory.DINNER,
                "snack": RecipeCategory.SNACK,
                "dessert": RecipeCategory.DESSERT,
                "soup": RecipeCategory.SOUP,
            }

            cuisine_map = {
                "chinese": RecipeCuisine.CHINESE,
                "western": RecipeCuisine.WESTERN,
                "japanese": RecipeCuisine.JAPANESE,
                "korean": RecipeCuisine.KOREAN,
                "vegetarian": RecipeCuisine.VEGETARIAN,
                "low_calorie": RecipeCuisine.LOW_CALORIE,
                "high_protein": RecipeCuisine.HIGH_PROTEIN,
            }

            recipe = {
                "name": recipe_data["name"],
                "description": recipe_data.get("description", ""),
                "prep_time": recipe_data.get("prep_time", 10),
                "cook_time": recipe_data.get("cook_time", 10),
                "total_time": recipe_data.get("prep_time", 10)
                + recipe_data.get("cook_time", 10),
                "servings": recipe_data.get("servings", 1),
                "difficulty": difficulty_map.get(
                    str(recipe_data.get("difficulty", "medium")).lower(),
                    RecipeDifficulty.MEDIUM,
                ),
                "category": category_map.get(
                    str(recipe_data.get("category", "lunch")).lower(),
                    RecipeCategory.LUNCH,
                ),
                "cuisine": cuisine_map.get(
                    str(recipe_data.get("cuisine", "chinese")).lower(),
                    RecipeCuisine.CHINESE,
                ),
                "calories_per_serving": recipe_data.get("calories_per_serving", 250),
                "protein_per_serving": recipe_data.get("protein_per_serving", 15.0),
                "fat_per_serving": recipe_data.get("fat_per_serving", 8.0),
                "carbs_per_serving": recipe_data.get("carbs_per_serving", 25.0),
                "image_url": recipe_data.get("image_url"),
                "is_public": recipe_data.get("is_public", True),
                "ingredients": recipe_data.get("ingredients", []),
                "steps": recipe_data.get("steps", []),
            }

            # 为食材和步骤添加索引
            for i, ingredient in enumerate(recipe["ingredients"]):
                ingredient["order_index"] = i

            for i, step in enumerate(recipe["steps"]):
                step["step_number"] = i + 1
                step["order_index"] = i

            return recipe

        except Exception as e:
            print(f"转换食谱数据失败: {e}")
            return None

    async def import_sample_recipes(self) -> bool:
        """导入示例食谱"""

        print("导入示例减脂餐食谱...")

        # 示例食谱数据
        sample_recipes = [
            {
                "name": "鸡胸肉沙拉",
                "description": "高蛋白低脂肪，适合减脂期",
                "prep_time": 10,
                "cook_time": 5,
                "servings": 1,
                "difficulty": RecipeDifficulty.EASY,
                "category": RecipeCategory.LUNCH,
                "cuisine": RecipeCuisine.LOW_CALORIE,
                "calories_per_serving": 220,
                "protein_per_serving": 30.0,
                "fat_per_serving": 5.0,
                "carbs_per_serving": 15.0,
                "image_url": None,
                "is_public": True,
                "ingredients": [
                    {"ingredient_name": "鸡胸肉", "quantity": 150, "unit": "克"},
                    {"ingredient_name": "生菜", "quantity": 100, "unit": "克"},
                    {"ingredient_name": "黄瓜", "quantity": 50, "unit": "克"},
                    {"ingredient_name": "橄榄油", "quantity": 5, "unit": "毫升"},
                    {"ingredient_name": "柠檬汁", "quantity": 10, "unit": "毫升"},
                ],
                "steps": [
                    {"description": "鸡胸肉洗净，用厨房纸吸干水分"},
                    {"description": "平底锅加热，放入鸡胸肉，中火煎至两面金黄"},
                    {"description": "生菜、黄瓜洗净切好，放入碗中"},
                    {"description": "将煎好的鸡胸肉切成条状，放在蔬菜上"},
                    {"description": "淋上橄榄油和柠檬汁，拌匀即可食用"},
                ],
            }
        ]

        return await self.import_recipes(sample_recipes)
