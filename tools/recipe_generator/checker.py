"""
食谱检查器模块
检查数据库中的食谱统计信息
"""

import asyncio
from typing import List
from pathlib import Path

# 添加项目根目录到Python路径
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import fastapi_settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from models.database import Recipe, RecipeCategory, RecipeCuisine, RecipeDifficulty


class RecipeChecker:
    """食谱检查器"""

    def __init__(self):
        # 创建数据库连接
        self.engine = create_async_engine(fastapi_settings.DATABASE_URL)
        self.AsyncSessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def check_recipes(self) -> bool:
        """检查数据库中的食谱"""

        print("检查数据库中的食谱...")

        async with self.AsyncSessionLocal() as session:
            # 1. 统计食谱总数
            total_result = await session.execute(select(func.count(Recipe.id)))
            total_recipes = total_result.scalar()
            print(f"1. 食谱总数: {total_recipes}")

            if total_recipes == 0:
                print("数据库中没有食谱")
                return False

            total_recipes_int = total_recipes if total_recipes else 0

            # 2. 按分类统计
            print("\n2. 按分类统计:")
            categories_result = await session.execute(
                select(Recipe.category, func.count(Recipe.id)).group_by(Recipe.category)
            )
            for category, count in categories_result:
                print(f"   {category.value}: {count}个")

            # 3. 按菜系统计
            print("\n3. 按菜系统计:")
            cuisines_result = await session.execute(
                select(Recipe.cuisine, func.count(Recipe.id)).group_by(Recipe.cuisine)
            )
            for cuisine, count in cuisines_result:
                print(f"   {cuisine.value}: {count}个")

            # 4. 按难度统计
            print("\n4. 按难度统计:")
            difficulties_result = await session.execute(
                select(Recipe.difficulty, func.count(Recipe.id)).group_by(
                    Recipe.difficulty
                )
            )
            for difficulty, count in difficulties_result:
                print(f"   {difficulty.value}: {count}个")

            # 5. 显示最新的10个食谱
            print("\n5. 最新10个食谱:")
            latest_recipes_result = await session.execute(
                select(Recipe).order_by(Recipe.created_at.desc()).limit(10)
            )
            latest_recipes = latest_recipes_result.scalars().all()

            for i, recipe in enumerate(latest_recipes, 1):
                print(f"   {i}. {recipe.name}")
                print(f"      描述: {recipe.description[:50]}...")
                print(
                    f"      分类: {recipe.category.value}, 菜系: {recipe.cuisine.value}"
                )
                print(f"      热量: {recipe.calories_per_serving}大卡/份")
                print(
                    f"      时间: {recipe.total_time}分钟, 难度: {recipe.difficulty.value}"
                )
                print(f"      创建时间: {recipe.created_at}")
                print()

            # 6. 检查减脂餐特征
            print("\n6. 减脂餐特征分析:")

            # 低热量食谱（<300大卡）
            low_calorie_result = await session.execute(
                select(func.count(Recipe.id)).where(Recipe.calories_per_serving < 300)
            )
            low_calorie_count = low_calorie_result.scalar() or 0
            if total_recipes_int > 0:
                print(
                    f"   低热量食谱（<300大卡）: {low_calorie_count}个 ({low_calorie_count / total_recipes_int * 100:.1f}%)"
                )
            else:
                print(f"   低热量食谱（<300大卡）: {low_calorie_count}个")

            # 高蛋白食谱（>15g蛋白质）
            high_protein_result = await session.execute(
                select(func.count(Recipe.id)).where(Recipe.protein_per_serving > 15)
            )
            high_protein_count = high_protein_result.scalar() or 0
            if total_recipes_int > 0:
                print(
                    f"   高蛋白食谱（>15g蛋白质）: {high_protein_count}个 ({high_protein_count / total_recipes_int * 100:.1f}%)"
                )
            else:
                print(f"   高蛋白食谱（>15g蛋白质）: {high_protein_count}个")

            # 快手食谱（<30分钟）
            quick_recipes_result = await session.execute(
                select(func.count(Recipe.id)).where(Recipe.total_time < 30)
            )
            quick_recipes_count = quick_recipes_result.scalar() or 0
            if total_recipes_int > 0:
                print(
                    f"   快手食谱（<30分钟）: {quick_recipes_count}个 ({quick_recipes_count / total_recipes_int * 100:.1f}%)"
                )
            else:
                print(f"   快手食谱（<30分钟）: {quick_recipes_count}个")

            # 简单食谱（easy难度）
            easy_recipes_result = await session.execute(
                select(func.count(Recipe.id)).where(
                    Recipe.difficulty == RecipeDifficulty.EASY
                )
            )
            easy_recipes_count = easy_recipes_result.scalar() or 0
            if total_recipes_int > 0:
                print(
                    f"   简单食谱（easy难度）: {easy_recipes_count}个 ({easy_recipes_count / total_recipes_int * 100:.1f}%)"
                )
            else:
                print(f"   简单食谱（easy难度）: {easy_recipes_count}个")

            # 7. 热量分布
            print("\n7. 热量分布:")
            calorie_stats = await session.execute(
                select(
                    func.min(Recipe.calories_per_serving).label("min"),
                    func.max(Recipe.calories_per_serving).label("max"),
                    func.avg(Recipe.calories_per_serving).label("avg"),
                )
            )
            stats = calorie_stats.first()
            if stats:
                print(f"   最低热量: {stats.min}大卡")
                print(f"   最高热量: {stats.max}大卡")
                print(f"   平均热量: {stats.avg:.1f}大卡")

            # 8. 时间分布
            print("\n8. 时间分布:")
            time_stats = await session.execute(
                select(
                    func.min(Recipe.total_time).label("min"),
                    func.max(Recipe.total_time).label("max"),
                    func.avg(Recipe.total_time).label("avg"),
                )
            )
            time_stats_result = time_stats.first()
            if time_stats_result:
                print(f"   最短时间: {time_stats_result.min}分钟")
                print(f"   最长时间: {time_stats_result.max}分钟")
                print(f"   平均时间: {time_stats_result.avg:.1f}分钟")

        print("\n检查完成！")
        return True

    async def list_recipes_by_category(self, category: str):
        """按分类列出食谱"""

        category_map = {
            "breakfast": RecipeCategory.BREAKFAST,
            "lunch": RecipeCategory.LUNCH,
            "dinner": RecipeCategory.DINNER,
            "snack": RecipeCategory.SNACK,
            "dessert": RecipeCategory.DESSERT,
            "soup": RecipeCategory.SOUP,
        }

        target_category = category_map.get(category.lower())
        if not target_category:
            print(f"无效的分类: {category}")
            return []

        async with self.AsyncSessionLocal() as session:
            result = await session.execute(
                select(Recipe)
                .where(Recipe.category == target_category)
                .order_by(Recipe.name)
            )
            recipes = result.scalars().all()

            print(f"{category}分类的食谱 ({len(recipes)}个):")
            for i, recipe in enumerate(recipes, 1):
                print(f"  {i}. {recipe.name} - {recipe.calories_per_serving}大卡")

            return recipes

    async def find_low_calorie_recipes(self, max_calories: int = 300):
        """查找低热量食谱"""

        async with self.AsyncSessionLocal() as session:
            result = await session.execute(
                select(Recipe)
                .where(Recipe.calories_per_serving <= max_calories)
                .order_by(Recipe.calories_per_serving)
            )
            recipes = result.scalars().all()

            print(f"低热量食谱（≤{max_calories}大卡） ({len(recipes)}个):")
            for i, recipe in enumerate(recipes, 1):
                print(
                    f"  {i}. {recipe.name} - {recipe.calories_per_serving}大卡 ({recipe.category.value})"
                )

            return recipes

    async def find_quick_recipes(self, max_time: int = 20):
        """查找快手食谱"""

        async with self.AsyncSessionLocal() as session:
            result = await session.execute(
                select(Recipe)
                .where(Recipe.total_time <= max_time)
                .order_by(Recipe.total_time)
            )
            recipes = result.scalars().all()

            print(f"快手食谱（≤{max_time}分钟） ({len(recipes)}个):")
            for i, recipe in enumerate(recipes, 1):
                print(
                    f"  {i}. {recipe.name} - {recipe.total_time}分钟 ({recipe.difficulty.value})"
                )

            return recipes
