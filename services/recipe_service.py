"""
食谱服务
提供食谱管理、搜索、推荐功能
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import joinedload
from enum import Enum
import json

from models.database import (
    Recipe,
    RecipeIngredient,
    RecipeStep,
    UserRecipe,
    FoodItem,
    User,
    RecipeDifficulty,
    RecipeCategory,
    RecipeCuisine,
)
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class RecipeFilter:
    """食谱过滤器"""

    def __init__(
        self,
        category: Optional[RecipeCategory] = None,
        cuisine: Optional[RecipeCuisine] = None,
        difficulty: Optional[RecipeDifficulty] = None,
        max_calories: Optional[int] = None,
        max_prep_time: Optional[int] = None,
        max_cook_time: Optional[int] = None,
        search_query: Optional[str] = None,
        is_public: bool = True,
        user_id: Optional[int] = None,
    ):
        self.category = category
        self.cuisine = cuisine
        self.difficulty = difficulty
        self.max_calories = max_calories
        self.max_prep_time = max_prep_time
        self.max_cook_time = max_cook_time
        self.search_query = search_query
        self.is_public = is_public
        self.user_id = user_id


class RecipeService:
    """食谱服务"""

    @staticmethod
    async def create_recipe(
        db: AsyncSession,
        recipe_data: Dict[str, Any],
        ingredients: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
        created_by: Optional[int] = None,
    ) -> Recipe:
        """
        创建食谱

        Args:
            db: 数据库会话
            recipe_data: 食谱数据
            ingredients: 食材列表
            steps: 步骤列表
            created_by: 创建者ID

        Returns:
            创建的食谱对象
        """
        try:
            # 创建食谱
            recipe = Recipe(
                name=recipe_data["name"],
                description=recipe_data.get("description"),
                prep_time=recipe_data["prep_time"],
                cook_time=recipe_data["cook_time"],
                total_time=recipe_data["prep_time"] + recipe_data["cook_time"],
                servings=recipe_data["servings"],
                difficulty=recipe_data["difficulty"],
                category=recipe_data["category"],
                cuisine=recipe_data["cuisine"],
                calories_per_serving=recipe_data["calories_per_serving"],
                protein_per_serving=recipe_data.get("protein_per_serving"),
                fat_per_serving=recipe_data.get("fat_per_serving"),
                carbs_per_serving=recipe_data.get("carbs_per_serving"),
                image_url=recipe_data.get("image_url"),
                is_public=recipe_data.get("is_public", True),
                created_by=created_by,
            )

            db.add(recipe)
            await db.flush()

            # 添加食材
            for idx, ingredient_data in enumerate(ingredients):
                ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    food_item_id=ingredient_data.get("food_item_id"),
                    ingredient_name=ingredient_data["ingredient_name"],
                    quantity=ingredient_data["quantity"],
                    unit=ingredient_data["unit"],
                    notes=ingredient_data.get("notes"),
                    order_index=idx,
                )
                db.add(ingredient)

            # 添加步骤
            for idx, step_data in enumerate(steps):
                step = RecipeStep(
                    recipe_id=recipe.id,
                    step_number=idx + 1,
                    description=step_data["description"],
                    image_url=step_data.get("image_url"),
                    order_index=idx,
                )
                db.add(step)

            await db.commit()
            await db.refresh(recipe)

            logger.info("创建食谱成功: %s (ID: %s)", recipe.name, recipe.id)
            return recipe

        except Exception as e:
            await db.rollback()
            logger.exception("创建食谱失败: %s", str(e))
            raise

    @staticmethod
    async def get_recipe(
        db: AsyncSession, recipe_id: int, include_details: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        获取食谱详情

        Args:
            db: 数据库会话
            recipe_id: 食谱ID
            include_details: 是否包含食材和步骤详情

        Returns:
            食谱详情字典
        """
        try:
            # 先获取食谱基本信息
            query = select(Recipe).where(Recipe.id == recipe_id)
            result = await db.execute(query)
            recipe = result.scalar_one_or_none()

            if not recipe:
                return None

            recipe_dict = {
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "prep_time": recipe.prep_time,
                "cook_time": recipe.cook_time,
                "total_time": recipe.total_time,
                "servings": recipe.servings,
                "difficulty": recipe.difficulty.value,
                "category": recipe.category.value,
                "cuisine": recipe.cuisine.value,
                "calories_per_serving": recipe.calories_per_serving,
                "protein_per_serving": recipe.protein_per_serving,
                "fat_per_serving": recipe.fat_per_serving,
                "carbs_per_serving": recipe.carbs_per_serving,
                "image_url": recipe.image_url,
                "is_public": recipe.is_public,
                "created_by": recipe.created_by,
                "created_at": recipe.created_at.isoformat()
                if hasattr(recipe.created_at, "isoformat")
                else None,
                "updated_at": recipe.updated_at.isoformat()
                if recipe.updated_at and hasattr(recipe.updated_at, "isoformat")
                else None,
            }

            if include_details:
                # 单独获取食材
                ingredients_query = (
                    select(RecipeIngredient)
                    .where(RecipeIngredient.recipe_id == recipe_id)
                    .options(joinedload(RecipeIngredient.food_item))
                )
                ingredients_result = await db.execute(ingredients_query)
                ingredients = ingredients_result.scalars().all()

                recipe_dict["ingredients"] = [
                    {
                        "id": ing.id,
                        "ingredient_name": ing.ingredient_name,
                        "quantity": ing.quantity,
                        "unit": ing.unit,
                        "notes": ing.notes,
                        "food_item": (
                            {
                                "id": ing.food_item.id,
                                "name": ing.food_item.name,
                                "calories_per_100g": ing.food_item.calories_per_100g,
                                "protein": ing.food_item.protein,
                                "fat": ing.food_item.fat,
                                "carbs": ing.food_item.carbs,
                            }
                            if ing.food_item
                            else None
                        ),
                    }
                    for ing in ingredients
                ]

                # 单独获取步骤
                steps_query = (
                    select(RecipeStep)
                    .where(RecipeStep.recipe_id == recipe_id)
                    .order_by(RecipeStep.step_number)
                )
                steps_result = await db.execute(steps_query)
                steps = steps_result.scalars().all()

                recipe_dict["steps"] = [
                    {
                        "id": step.id,
                        "step_number": step.step_number,
                        "description": step.description,
                        "image_url": step.image_url,
                    }
                    for step in steps
                ]

            return recipe_dict

        except Exception as e:
            logger.exception("获取食谱详情失败: %s", str(e))
            raise

    @staticmethod
    async def list_recipes(
        db: AsyncSession,
        filter_obj: RecipeFilter,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        列出食谱

        Args:
            db: 数据库会话
            filter_obj: 过滤器
            page: 页码
            page_size: 每页大小
            sort_by: 排序字段
            sort_order: 排序顺序

        Returns:
            (食谱列表, 总数量)
        """
        try:
            # 构建查询
            query = select(Recipe)

            # 应用过滤器
            if filter_obj.is_public:
                query = query.where(Recipe.is_public == True)

            if filter_obj.category:
                query = query.where(Recipe.category == filter_obj.category)

            if filter_obj.cuisine:
                query = query.where(Recipe.cuisine == filter_obj.cuisine)

            if filter_obj.difficulty:
                query = query.where(Recipe.difficulty == filter_obj.difficulty)

            if filter_obj.max_calories:
                query = query.where(
                    Recipe.calories_per_serving <= filter_obj.max_calories
                )

            if filter_obj.max_prep_time:
                query = query.where(Recipe.prep_time <= filter_obj.max_prep_time)

            if filter_obj.max_cook_time:
                query = query.where(Recipe.cook_time <= filter_obj.max_cook_time)

            if filter_obj.search_query:
                search_term = f"%{filter_obj.search_query}%"
                query = query.where(
                    or_(
                        Recipe.name.ilike(search_term),
                        Recipe.description.ilike(search_term),
                    )
                )

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar()

            # 应用排序
            sort_column = getattr(Recipe, sort_by, Recipe.created_at)
            if sort_order == "asc":
                query = query.order_by(asc(sort_column))
            else:
                query = query.order_by(desc(sort_column))

            # 应用分页
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # 执行查询
            result = await db.execute(query)
            recipes = result.scalars().all()

            # 转换为字典
            recipe_list = []
            for recipe in recipes:
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty.value,
                    "category": recipe.category.value,
                    "cuisine": recipe.cuisine.value,
                    "calories_per_serving": recipe.calories_per_serving,
                    "image_url": recipe.image_url,
                    "created_at": recipe.created_at.isoformat()
                    if recipe.created_at
                    else None,
                }
                recipe_list.append(recipe_dict)

            return recipe_list, total

        except Exception as e:
            logger.exception("列出食谱失败: %s", str(e))
            raise

    @staticmethod
    async def update_recipe(
        db: AsyncSession,
        recipe_id: int,
        recipe_data: Dict[str, Any],
        ingredients: Optional[List[Dict[str, Any]]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Recipe]:
        """
        更新食谱

        Args:
            db: 数据库会话
            recipe_id: 食谱ID
            recipe_data: 食谱数据
            ingredients: 食材列表（如果提供则替换现有）
            steps: 步骤列表（如果提供则替换现有）

        Returns:
            更新后的食谱对象
        """
        try:
            # 获取食谱
            query = select(Recipe).where(Recipe.id == recipe_id)
            result = await db.execute(query)
            recipe = result.scalar_one_or_none()

            if not recipe:
                return None

            # 更新基本字段
            for key, value in recipe_data.items():
                if hasattr(recipe, key) and value is not None:
                    setattr(recipe, key, value)

            # 更新总时间
            if "prep_time" in recipe_data or "cook_time" in recipe_data:
                recipe.total_time = recipe.prep_time + recipe.cook_time

            # 更新食材（如果提供）
            if ingredients is not None:
                # 删除现有食材
                await db.execute(
                    select(RecipeIngredient).where(
                        RecipeIngredient.recipe_id == recipe_id
                    )
                )
                result = await db.execute(
                    select(RecipeIngredient).where(
                        RecipeIngredient.recipe_id == recipe_id
                    )
                )
                existing_ingredients = result.scalars().all()
                for ing in existing_ingredients:
                    await db.delete(ing)

                # 添加新食材
                for idx, ingredient_data in enumerate(ingredients):
                    ingredient = RecipeIngredient(
                        recipe_id=recipe.id,
                        food_item_id=ingredient_data.get("food_item_id"),
                        ingredient_name=ingredient_data["ingredient_name"],
                        quantity=ingredient_data["quantity"],
                        unit=ingredient_data["unit"],
                        notes=ingredient_data.get("notes"),
                        order_index=idx,
                    )
                    db.add(ingredient)

            # 更新步骤（如果提供）
            if steps is not None:
                # 删除现有步骤
                await db.execute(
                    select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)
                )
                result = await db.execute(
                    select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)
                )
                existing_steps = result.scalars().all()
                for step in existing_steps:
                    await db.delete(step)

                # 添加新步骤
                for idx, step_data in enumerate(steps):
                    step = RecipeStep(
                        recipe_id=recipe.id,
                        step_number=idx + 1,
                        description=step_data["description"],
                        image_url=step_data.get("image_url"),
                        order_index=idx,
                    )
                    db.add(step)

            recipe.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(recipe)

            logger.info("更新食谱成功: %s (ID: %s)", recipe.name, recipe.id)
            return recipe

        except Exception as e:
            await db.rollback()
            logger.exception("更新食谱失败: %s", str(e))
            raise

    @staticmethod
    async def delete_recipe(db: AsyncSession, recipe_id: int) -> bool:
        """
        删除食谱

        Args:
            db: 数据库会话
            recipe_id: 食谱ID

        Returns:
            是否删除成功
        """
        try:
            query = select(Recipe).where(Recipe.id == recipe_id)
            result = await db.execute(query)
            recipe = result.scalar_one_or_none()

            if not recipe:
                return False

            await db.delete(recipe)
            await db.commit()

            logger.info("删除食谱成功: %s (ID: %s)", recipe.name, recipe.id)
            return True

        except Exception as e:
            await db.rollback()
            logger.exception("删除食谱失败: %s", str(e))
            raise

    @staticmethod
    async def get_recommended_recipes(
        db: AsyncSession,
        user_id: int,
        limit: int = 10,
        category: Optional[RecipeCategory] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取推荐食谱

        Args:
            db: 数据库会话
            user_id: 用户ID
            limit: 返回数量
            category: 食谱分类

        Returns:
            推荐食谱列表
        """
        try:
            # 获取用户偏好（这里可以扩展为基于用户历史行为）
            # 目前实现简单推荐：基于分类和热度的食谱

            query = select(Recipe).where(Recipe.is_public == True)

            if category:
                query = query.where(Recipe.category == category)

            # 按创建时间倒序（模拟热度）
            query = query.order_by(desc(Recipe.created_at)).limit(limit)

            result = await db.execute(query)
            recipes = result.scalars().all()

            # 转换为字典
            recipe_list = []
            for recipe in recipes:
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty.value,
                    "category": recipe.category.value,
                    "cuisine": recipe.cuisine.value,
                    "calories_per_serving": recipe.calories_per_serving,
                    "image_url": recipe.image_url,
                }
                recipe_list.append(recipe_dict)

            return recipe_list

        except Exception as e:
            logger.exception("获取推荐食谱失败: %s", str(e))
            raise

    @staticmethod
    async def search_recipes(
        db: AsyncSession,
        search_query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        搜索食谱

        Args:
            db: 数据库会话
            search_query: 搜索关键词
            page: 页码
            page_size: 每页大小

        Returns:
            (食谱列表, 总数量)
        """
        try:
            if not search_query.strip():
                return [], 0

            search_term = f"%{search_query}%"

            # 构建查询
            query = (
                select(Recipe)
                .where(Recipe.is_public == True)
                .where(
                    or_(
                        Recipe.name.ilike(search_term),
                        Recipe.description.ilike(search_term),
                    )
                )
            )

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar()

            # 应用分页和排序
            offset = (page - 1) * page_size
            query = (
                query.order_by(desc(Recipe.created_at)).offset(offset).limit(page_size)
            )

            # 执行查询
            result = await db.execute(query)
            recipes = result.scalars().all()

            # 转换为字典
            recipe_list = []
            for recipe in recipes:
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty.value,
                    "category": recipe.category.value,
                    "cuisine": recipe.cuisine.value,
                    "calories_per_serving": recipe.calories_per_serving,
                    "image_url": recipe.image_url,
                }
                recipe_list.append(recipe_dict)

            return recipe_list, total

        except Exception as e:
            logger.exception("搜索食谱失败: %s", str(e))
            raise


class UserRecipeService:
    """用户食谱交互服务"""

    @staticmethod
    async def get_user_recipe_interaction(
        db: AsyncSession, user_id: int, recipe_id: int
    ) -> Optional[UserRecipe]:
        """
        获取用户食谱交互记录

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 食谱ID

        Returns:
            用户食谱交互记录
        """
        try:
            query = select(UserRecipe).where(
                and_(UserRecipe.user_id == user_id, UserRecipe.recipe_id == recipe_id)
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.exception("获取用户食谱交互失败: %s", str(e))
            raise

    @staticmethod
    async def add_to_favorites(db: AsyncSession, user_id: int, recipe_id: int) -> bool:
        """
        添加食谱到收藏

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 食谱ID

        Returns:
            是否成功
        """
        try:
            # 检查食谱是否存在
            recipe_query = select(Recipe).where(
                and_(Recipe.id == recipe_id, Recipe.is_public == True)
            )
            recipe_result = await db.execute(recipe_query)
            recipe = recipe_result.scalar_one_or_none()

            if not recipe:
                return False

            # 获取或创建交互记录
            interaction = await UserRecipeService.get_user_recipe_interaction(
                db, user_id, recipe_id
            )

            if interaction:
                interaction.is_favorite = True
                interaction.updated_at = datetime.utcnow()
            else:
                interaction = UserRecipe(
                    user_id=user_id,
                    recipe_id=recipe_id,
                    is_favorite=True,
                )
                db.add(interaction)

            await db.commit()
            logger.info("用户 %s 收藏食谱 %s", user_id, recipe_id)
            return True

        except Exception as e:
            await db.rollback()
            logger.exception("收藏食谱失败: %s", str(e))
            raise

    @staticmethod
    async def remove_from_favorites(
        db: AsyncSession, user_id: int, recipe_id: int
    ) -> bool:
        """
        从收藏中移除食谱

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 食谱ID

        Returns:
            是否成功
        """
        try:
            interaction = await UserRecipeService.get_user_recipe_interaction(
                db, user_id, recipe_id
            )

            if not interaction:
                return False

            interaction.is_favorite = False
            interaction.updated_at = datetime.utcnow()
            await db.commit()

            logger.info("用户 %s 取消收藏食谱 %s", user_id, recipe_id)
            return True

        except Exception as e:
            await db.rollback()
            logger.exception("取消收藏食谱失败: %s", str(e))
            raise

    @staticmethod
    async def mark_as_cooked(db: AsyncSession, user_id: int, recipe_id: int) -> bool:
        """
        标记食谱为已烹饪

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 食谱ID

        Returns:
            是否成功
        """
        try:
            # 检查食谱是否存在
            recipe_query = select(Recipe).where(
                and_(Recipe.id == recipe_id, Recipe.is_public == True)
            )
            recipe_result = await db.execute(recipe_query)
            recipe = recipe_result.scalar_one_or_none()

            if not recipe:
                return False

            # 获取或创建交互记录
            interaction = await UserRecipeService.get_user_recipe_interaction(
                db, user_id, recipe_id
            )

            now = datetime.utcnow()
            if interaction:
                interaction.last_cooked = now
                interaction.cooked_count += 1
                interaction.updated_at = now
            else:
                interaction = UserRecipe(
                    user_id=user_id,
                    recipe_id=recipe_id,
                    last_cooked=now,
                    cooked_count=1,
                )
                db.add(interaction)

            await db.commit()
            logger.info("用户 %s 标记食谱 %s 为已烹饪", user_id, recipe_id)
            return True

        except Exception as e:
            await db.rollback()
            logger.exception("标记食谱为已烹饪失败: %s", str(e))
            raise

    @staticmethod
    async def rate_recipe(
        db: AsyncSession,
        user_id: int,
        recipe_id: int,
        rating: int,
        notes: Optional[str] = None,
    ) -> bool:
        """
        评价食谱

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 食谱ID
            rating: 评分（1-5）
            notes: 评价内容

        Returns:
            是否成功
        """
        try:
            # 验证评分范围
            if rating < 1 or rating > 5:
                return False

            # 检查食谱是否存在
            recipe_query = select(Recipe).where(
                and_(Recipe.id == recipe_id, Recipe.is_public == True)
            )
            recipe_result = await db.execute(recipe_query)
            recipe = recipe_result.scalar_one_or_none()

            if not recipe:
                return False

            # 获取或创建交互记录
            interaction = await UserRecipeService.get_user_recipe_interaction(
                db, user_id, recipe_id
            )

            now = datetime.utcnow()
            if interaction:
                interaction.rating = rating
                interaction.notes = notes
                interaction.updated_at = now
            else:
                interaction = UserRecipe(
                    user_id=user_id,
                    recipe_id=recipe_id,
                    rating=rating,
                    notes=notes,
                )
                db.add(interaction)

            await db.commit()
            logger.info("用户 %s 评价食谱 %s: %s 星", user_id, recipe_id, rating)
            return True

        except Exception as e:
            await db.rollback()
            logger.exception("评价食谱失败: %s", str(e))
            raise

    @staticmethod
    async def get_user_favorites(
        db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取用户收藏的食谱

        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页大小

        Returns:
            (食谱列表, 总数量)
        """
        try:
            # 构建查询
            query = (
                select(Recipe)
                .join(UserRecipe, Recipe.id == UserRecipe.recipe_id)
                .where(
                    and_(
                        UserRecipe.user_id == user_id,
                        UserRecipe.is_favorite == True,
                        Recipe.is_public == True,
                    )
                )
            )

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar()

            # 应用分页和排序
            offset = (page - 1) * page_size
            query = (
                query.order_by(desc(UserRecipe.updated_at))
                .offset(offset)
                .limit(page_size)
            )

            # 执行查询
            result = await db.execute(query)
            recipes = result.scalars().all()

            # 转换为字典
            recipe_list = []
            for recipe in recipes:
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty.value,
                    "category": recipe.category.value,
                    "cuisine": recipe.cuisine.value,
                    "calories_per_serving": recipe.calories_per_serving,
                    "image_url": recipe.image_url,
                }
                recipe_list.append(recipe_dict)

            return recipe_list, total

        except Exception as e:
            logger.exception("获取用户收藏失败: %s", str(e))
            raise

    @staticmethod
    async def get_user_cooked_recipes(
        db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取用户烹饪过的食谱

        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页大小

        Returns:
            (食谱列表, 总数量)
        """
        try:
            # 构建查询
            query = (
                select(Recipe)
                .join(UserRecipe, Recipe.id == UserRecipe.recipe_id)
                .where(
                    and_(
                        UserRecipe.user_id == user_id,
                        UserRecipe.cooked_count > 0,
                        Recipe.is_public == True,
                    )
                )
            )

            # 获取总数
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar()

            # 应用分页和排序
            offset = (page - 1) * page_size
            query = (
                query.order_by(desc(UserRecipe.last_cooked))
                .offset(offset)
                .limit(page_size)
            )

            # 执行查询
            result = await db.execute(query)
            recipes = result.scalars().all()

            # 转换为字典
            recipe_list = []
            for recipe in recipes:
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty.value,
                    "category": recipe.category.value,
                    "cuisine": recipe.cuisine.value,
                    "calories_per_serving": recipe.calories_per_serving,
                    "image_url": recipe.image_url,
                }
                recipe_list.append(recipe_dict)

            return recipe_list, total

        except Exception as e:
            logger.exception("获取用户烹饪记录失败: %s", str(e))
            raise
