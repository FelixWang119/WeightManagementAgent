"""
食谱管理 API 路由
提供食谱查询、收藏、推荐功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from models.database import (
    get_db,
    User,
    RecipeDifficulty,
    RecipeCategory,
    RecipeCuisine,
)
from api.routes.user import get_current_user
from services.recipe_service import RecipeService, UserRecipeService, RecipeFilter

router = APIRouter()


# ============ 请求/响应模型 ============


class RecipeIngredientRequest(BaseModel):
    """食谱食材请求"""

    food_item_id: Optional[int] = None
    ingredient_name: str = Field(..., min_length=1, max_length=200)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = Field(None, max_length=200)


class RecipeStepRequest(BaseModel):
    """食谱步骤请求"""

    description: str = Field(..., min_length=1)
    image_url: Optional[str] = Field(None, max_length=500)


class RecipeCreateRequest(BaseModel):
    """创建食谱请求"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    prep_time: int = Field(..., ge=0)
    cook_time: int = Field(..., ge=0)
    servings: int = Field(..., ge=1)
    difficulty: RecipeDifficulty
    category: RecipeCategory
    cuisine: RecipeCuisine
    calories_per_serving: int = Field(..., ge=0)
    protein_per_serving: Optional[float] = Field(None, ge=0)
    fat_per_serving: Optional[float] = Field(None, ge=0)
    carbs_per_serving: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=500)
    is_public: bool = True
    ingredients: List[RecipeIngredientRequest]
    steps: List[RecipeStepRequest]

    @validator("ingredients")
    def validate_ingredients(cls, v):
        if not v:
            raise ValueError("食谱必须包含至少一种食材")
        return v

    @validator("steps")
    def validate_steps(cls, v):
        if not v:
            raise ValueError("食谱必须包含至少一个步骤")
        return v


class RecipeUpdateRequest(BaseModel):
    """更新食谱请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    prep_time: Optional[int] = Field(None, ge=0)
    cook_time: Optional[int] = Field(None, ge=0)
    servings: Optional[int] = Field(None, ge=1)
    difficulty: Optional[RecipeDifficulty] = None
    category: Optional[RecipeCategory] = None
    cuisine: Optional[RecipeCuisine] = None
    calories_per_serving: Optional[int] = Field(None, ge=0)
    protein_per_serving: Optional[float] = Field(None, ge=0)
    fat_per_serving: Optional[float] = Field(None, ge=0)
    carbs_per_serving: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    ingredients: Optional[List[RecipeIngredientRequest]] = None
    steps: Optional[List[RecipeStepRequest]] = None


class RecipeResponse(BaseModel):
    """食谱响应"""

    id: int
    name: str
    description: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    total_time: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    cuisine: Optional[str] = None
    calories_per_serving: Optional[int] = None
    protein_per_serving: Optional[float] = None
    fat_per_serving: Optional[float] = None
    carbs_per_serving: Optional[float] = None
    image_url: Optional[str] = None
    is_public: Optional[bool] = True
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ingredients: Optional[List[Dict[str, Any]]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    meal_type: Optional[str] = None
    tips: Optional[str] = None


class RecipeListResponse(BaseModel):
    """食谱列表响应"""

    recipes: List[RecipeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class FavoriteRequest(BaseModel):
    """收藏请求"""

    recipe_id: int


class RateRequest(BaseModel):
    """评价请求"""

    rating: int = Field(..., ge=1, le=5)
    notes: Optional[str] = None


# ============ API 端点 ============


@router.get("/recipes", response_model=RecipeListResponse)
async def list_recipes(
    category: Optional[RecipeCategory] = None,
    cuisine: Optional[RecipeCuisine] = None,
    difficulty: Optional[RecipeDifficulty] = None,
    max_calories: Optional[int] = Query(None, ge=0),
    max_prep_time: Optional[int] = Query(None, ge=0),
    max_cook_time: Optional[int] = Query(None, ge=0),
    search_query: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "created_at", regex="^(name|created_at|calories_per_serving)$"
    ),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    # current_user: User = Depends(get_current_user),  # 暂时移除认证要求
    db: AsyncSession = Depends(get_db),
):
    """
    列出食谱

    - **category**: 食谱分类
    - **cuisine**: 菜系
    - **difficulty**: 难度
    - **max_calories**: 最大热量
    - **max_prep_time**: 最大准备时间
    - **max_cook_time**: 最大烹饪时间
    - **search_query**: 搜索关键词
    - **page**: 页码
    - **page_size**: 每页大小
    - **sort_by**: 排序字段
    - **sort_order**: 排序顺序
    """
    try:
        # 构建过滤器
        filter_obj = RecipeFilter(
            category=category,
            cuisine=cuisine,
            difficulty=difficulty,
            max_calories=max_calories,
            max_prep_time=max_prep_time,
            max_cook_time=max_cook_time,
            search_query=search_query,
            is_public=True,
            user_id=None,  # 不需要用户ID
        )

        # 获取食谱列表
        recipes, total = await RecipeService.list_recipes(
            db, filter_obj, page, page_size, sort_by, sort_order
        )

        # 处理食谱数据（可能是字典或SQLAlchemy对象）
        recipes_dicts = []
        for recipe in recipes:
            if hasattr(recipe, "id"):  # SQLAlchemy对象
                recipe_dict = {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "prep_time": recipe.prep_time,
                    "cook_time": recipe.cook_time,
                    "total_time": recipe.total_time,
                    "servings": recipe.servings,
                    "difficulty": recipe.difficulty,
                    "category": recipe.category,
                    "cuisine": recipe.cuisine,
                    "calories_per_serving": recipe.calories_per_serving,
                    "protein_per_serving": recipe.protein_per_serving,
                    "fat_per_serving": recipe.fat_per_serving,
                    "carbs_per_serving": recipe.carbs_per_serving,
                    "image_url": recipe.image_url,
                    "is_public": recipe.is_public,
                    "created_by": recipe.created_by,
                    "created_at": recipe.created_at.isoformat()
                    if recipe.created_at
                    else None,
                    "updated_at": recipe.updated_at.isoformat()
                    if recipe.updated_at
                    else None,
                    "meal_type": getattr(recipe, "meal_type", None),
                    "tips": getattr(recipe, "tips", None),
                }
            else:  # 已经是字典
                recipe_dict = dict(recipe)
                # 确保datetime字段转换为字符串
                if "created_at" in recipe_dict and hasattr(
                    recipe_dict["created_at"], "isoformat"
                ):
                    recipe_dict["created_at"] = recipe_dict["created_at"].isoformat()
                if "updated_at" in recipe_dict and hasattr(
                    recipe_dict["updated_at"], "isoformat"
                ):
                    recipe_dict["updated_at"] = recipe_dict["updated_at"].isoformat()

            recipes_dicts.append(recipe_dict)

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return RecipeListResponse(
            recipes=recipes_dicts,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取食谱列表失败: {str(e)}",
        )


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: int,
    include_details: bool = Query(True, description="是否包含食材和步骤详情"),
    # current_user: User = Depends(get_current_user),  # 暂时移除认证要求
    db: AsyncSession = Depends(get_db),
):
    """
    获取食谱详情

    - **recipe_id**: 食谱ID
    - **include_details**: 是否包含食材和步骤详情
    """
    try:
        recipe = await RecipeService.get_recipe(db, recipe_id, include_details)

        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        # 检查食谱是否公开（暂时允许访问所有食谱）
        # if not recipe["is_public"] and recipe["created_by"] != current_user.id:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="无权访问此食谱",
        #     )

        return recipe

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取食谱详情失败: {str(e)}",
        )


@router.post("/recipes", response_model=RecipeResponse)
async def create_recipe(
    recipe_data: RecipeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建食谱

    - 需要登录用户
    - 创建者默认为当前用户
    """
    try:
        # 转换请求数据
        recipe_dict = recipe_data.dict()
        ingredients = recipe_dict.pop("ingredients")
        steps = recipe_dict.pop("steps")

        # 创建食谱
        recipe = await RecipeService.create_recipe(
            db,
            recipe_dict,
            [ing.dict() for ing in ingredients],
            [step.dict() for step in steps],
            current_user.id,
        )

        # 获取完整的食谱详情
        recipe_detail = await RecipeService.get_recipe(db, recipe.id, True)

        return recipe_detail

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建食谱失败: {str(e)}",
        )


@router.put("/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新食谱

    - 只能更新自己创建的食谱
    - 如果提供ingredients或steps，则替换现有数据
    """
    try:
        # 检查食谱是否存在且属于当前用户
        recipe_detail = await RecipeService.get_recipe(db, recipe_id, False)

        if not recipe_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        if recipe_detail["created_by"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权更新此食谱",
            )

        # 转换请求数据
        recipe_dict = recipe_data.dict(exclude_unset=True)
        ingredients = recipe_dict.pop("ingredients", None)
        steps = recipe_dict.pop("steps", None)

        # 更新食谱
        recipe = await RecipeService.update_recipe(
            db,
            recipe_id,
            recipe_dict,
            [ing.dict() for ing in ingredients] if ingredients else None,
            [step.dict() for step in steps] if steps else None,
        )

        if not recipe:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        # 获取更新后的食谱详情
        recipe_detail = await RecipeService.get_recipe(db, recipe.id, True)

        return recipe_detail

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新食谱失败: {str(e)}",
        )


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除食谱

    - 只能删除自己创建的食谱
    """
    try:
        # 检查食谱是否存在且属于当前用户
        recipe_detail = await RecipeService.get_recipe(db, recipe_id, False)

        if not recipe_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        if recipe_detail["created_by"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此食谱",
            )

        # 删除食谱
        success = await RecipeService.delete_recipe(db, recipe_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        return {"message": "食谱删除成功"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除食谱失败: {str(e)}",
        )


@router.get("/recipes/recommended", response_model=List[RecipeResponse])
async def get_recommended_recipes(
    category: Optional[RecipeCategory] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取推荐食谱

    - **category**: 食谱分类（可选）
    - **limit**: 返回数量
    """
    try:
        recipes = await RecipeService.get_recommended_recipes(
            db, current_user.id, limit, category
        )

        return recipes

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取推荐食谱失败: {str(e)}",
        )


@router.get("/recipes/search", response_model=RecipeListResponse)
async def search_recipes(
    query: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索食谱

    - **query**: 搜索关键词
    - **page**: 页码
    - **page_size**: 每页大小
    """
    try:
        recipes, total = await RecipeService.search_recipes(db, query, page, page_size)

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return RecipeListResponse(
            recipes=recipes,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索食谱失败: {str(e)}",
        )


# ============ 用户食谱交互 ============


@router.post("/recipes/{recipe_id}/favorite")
async def add_to_favorites(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    添加食谱到收藏
    """
    try:
        success = await UserRecipeService.add_to_favorites(
            db, current_user.id, recipe_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        return {"message": "已添加到收藏"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加到收藏失败: {str(e)}",
        )


@router.delete("/recipes/{recipe_id}/favorite")
async def remove_from_favorites(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    从收藏中移除食谱
    """
    try:
        success = await UserRecipeService.remove_from_favorites(
            db, current_user.id, recipe_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未收藏此食谱",
            )

        return {"message": "已从收藏中移除"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从收藏中移除失败: {str(e)}",
        )


@router.post("/recipes/{recipe_id}/cook")
async def mark_as_cooked(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    标记食谱为已烹饪
    """
    try:
        success = await UserRecipeService.mark_as_cooked(db, current_user.id, recipe_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        return {"message": "已标记为已烹饪"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"标记为已烹饪失败: {str(e)}",
        )


@router.post("/recipes/{recipe_id}/rate")
async def rate_recipe(
    recipe_id: int,
    rate_data: RateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    评价食谱

    - **rating**: 评分（1-5）
    - **notes**: 评价内容（可选）
    """
    try:
        success = await UserRecipeService.rate_recipe(
            db, current_user.id, recipe_id, rate_data.rating, rate_data.notes
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="食谱不存在",
            )

        return {"message": "评价成功"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评价失败: {str(e)}",
        )


@router.get("/recipes/favorites", response_model=RecipeListResponse)
async def get_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户收藏的食谱

    - **page**: 页码
    - **page_size**: 每页大小
    """
    try:
        recipes, total = await UserRecipeService.get_user_favorites(
            db, current_user.id, page, page_size
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return RecipeListResponse(
            recipes=recipes,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取收藏列表失败: {str(e)}",
        )


@router.get("/recipes/cooked", response_model=RecipeListResponse)
async def get_cooked_recipes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户烹饪过的食谱

    - **page**: 页码
    - **page_size**: 每页大小
    """
    try:
        recipes, total = await UserRecipeService.get_user_cooked_recipes(
            db, current_user.id, page, page_size
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        return RecipeListResponse(
            recipes=recipes,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取烹饪记录失败: {str(e)}",
        )
