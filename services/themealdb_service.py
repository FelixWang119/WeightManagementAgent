"""
TheMealDB API 服务
用于从 TheMealDB 获取食谱数据并转换为本地格式
"""

import requests
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import re

from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class TheMealDBService:
    """TheMealDB API 服务"""

    BASE_URL = "https://www.themealdb.com/api/json/v1/1"
    TEST_API_KEY = "1"  # 开发测试用的API key

    # 分类映射表：将TheMealDB分类映射到我们的分类
    CATEGORY_MAPPING = {
        "Beef": "lunch",
        "Breakfast": "breakfast",
        "Chicken": "lunch",
        "Dessert": "dessert",
        "Goat": "lunch",
        "Lamb": "lunch",
        "Miscellaneous": "lunch",
        "Pasta": "lunch",
        "Pork": "lunch",
        "Seafood": "lunch",
        "Side": "snack",
        "Starter": "snack",
        "Vegan": "vegetarian",
        "Vegetarian": "vegetarian",
    }

    # 地区映射到菜系
    AREA_TO_CUISINE = {
        "American": "western",
        "British": "western",
        "Canadian": "western",
        "Chinese": "chinese",
        "Croatian": "western",
        "Dutch": "western",
        "Egyptian": "western",
        "Filipino": "western",
        "French": "western",
        "Greek": "western",
        "Indian": "western",
        "Irish": "western",
        "Italian": "western",
        "Jamaican": "western",
        "Japanese": "japanese",
        "Kenyan": "western",
        "Malaysian": "western",
        "Mexican": "western",
        "Moroccan": "western",
        "Polish": "western",
        "Portuguese": "western",
        "Russian": "western",
        "Spanish": "western",
        "Thai": "western",
        "Tunisian": "western",
        "Turkish": "western",
        "Unknown": "western",
        "Vietnamese": "western",
    }

    @classmethod
    def get_random_recipes(cls, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取随机食谱

        Args:
            count: 获取的食谱数量

        Returns:
            食谱列表
        """
        recipes = []
        for i in range(count):
            try:
                response = requests.get(f"{cls.BASE_URL}/random.php", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("meals"):
                        recipe = cls._convert_meal_to_recipe(data["meals"][0])
                        recipes.append(recipe)
                        logger.info(f"获取到随机食谱: {recipe['name']}")
                else:
                    logger.warning(f"获取随机食谱失败: {response.status_code}")
            except Exception as e:
                logger.error(f"获取随机食谱异常: {str(e)}")

        return recipes

    @classmethod
    def search_recipes(cls, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索食谱

        Args:
            query: 搜索关键词
            limit: 最大返回数量

        Returns:
            食谱列表
        """
        try:
            response = requests.get(f"{cls.BASE_URL}/search.php?s={query}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("meals"):
                    recipes = []
                    for meal in data["meals"][:limit]:
                        recipe = cls._convert_meal_to_recipe(meal)
                        recipes.append(recipe)
                    logger.info(f"搜索 '{query}' 找到 {len(recipes)} 个食谱")
                    return recipes
                else:
                    logger.info(f"搜索 '{query}' 未找到食谱")
                    return []
            else:
                logger.warning(f"搜索食谱失败: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"搜索食谱异常: {str(e)}")
            return []

    @classmethod
    def get_recipes_by_category(
        cls, category: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        按分类获取食谱

        Args:
            category: 分类名称
            limit: 最大返回数量

        Returns:
            食谱列表
        """
        try:
            response = requests.get(
                f"{cls.BASE_URL}/filter.php?c={category}", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("meals"):
                    recipes = []
                    # 获取每个食谱的详细信息
                    for meal_summary in data["meals"][:limit]:
                        recipe_detail = cls._get_recipe_by_id(meal_summary["idMeal"])
                        if recipe_detail:
                            recipes.append(recipe_detail)
                    logger.info(f"获取分类 '{category}' 的 {len(recipes)} 个食谱")
                    return recipes
                else:
                    logger.info(f"分类 '{category}' 没有食谱")
                    return []
            else:
                logger.warning(f"获取分类食谱失败: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"获取分类食谱异常: {str(e)}")
            return []

    @classmethod
    def _get_recipe_by_id(cls, meal_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取食谱详情"""
        try:
            response = requests.get(
                f"{cls.BASE_URL}/lookup.php?i={meal_id}", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("meals"):
                    return cls._convert_meal_to_recipe(data["meals"][0])
            return None
        except Exception as e:
            logger.error(f"获取食谱详情异常: {str(e)}")
            return None

    @classmethod
    def _convert_meal_to_recipe(cls, meal: Dict[str, Any]) -> Dict[str, Any]:
        """
        将TheMealDB的食谱格式转换为本地格式

        Args:
            meal: TheMealDB食谱数据

        Returns:
            本地格式的食谱数据
        """
        # 提取食材
        ingredients = []
        for i in range(1, 21):
            ingredient = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")

            if ingredient and ingredient.strip():
                # 清理食材名称和数量
                ingredient_name = ingredient.strip()
                measure_text = measure.strip() if measure else ""

                # 尝试解析数量
                quantity, unit = cls._parse_measure(measure_text)

                ingredients.append(
                    {
                        "ingredient_name": ingredient_name,
                        "quantity": quantity,
                        "unit": unit,
                        "notes": None,
                    }
                )

        # 解析步骤
        instructions = meal.get("strInstructions", "")
        steps = cls._parse_instructions(instructions)

        # 映射分类
        meal_category = meal.get("strCategory", "Miscellaneous")
        category = cls.CATEGORY_MAPPING.get(meal_category, "lunch")

        # 映射菜系
        meal_area = meal.get("strArea", "Unknown")
        cuisine = cls.AREA_TO_CUISINE.get(meal_area, "western")

        # 估算准备时间和烹饪时间
        prep_time, cook_time = cls._estimate_times(instructions, len(ingredients))

        # 估算份量
        servings = cls._estimate_servings(ingredients)

        # 估算热量（基于常见食材估算）
        calories = cls._estimate_calories(ingredients, servings)

        # 构建食谱数据
        recipe = {
            "name": meal.get("strMeal", "Unknown Recipe"),
            "description": cls._generate_description(meal),
            "prep_time": prep_time,
            "cook_time": cook_time,
            "total_time": prep_time + cook_time,
            "servings": servings,
            "difficulty": cls._estimate_difficulty(
                len(ingredients), len(steps), cook_time
            ),
            "category": category,
            "cuisine": cuisine,
            "calories_per_serving": calories,
            "protein_per_serving": None,  # 需要营养数据库才能准确计算
            "fat_per_serving": None,
            "carbs_per_serving": None,
            "image_url": meal.get("strMealThumb"),
            "is_public": True,
            "created_by": None,  # 外部导入，没有创建者
            "ingredients": ingredients,
            "steps": steps,
            "tips": cls._generate_tips(meal),
            "source": "TheMealDB",
            "source_id": meal.get("idMeal"),
            "source_url": meal.get("strSource"),
            "youtube_url": meal.get("strYoutube"),
        }

        return recipe

    @staticmethod
    def _parse_measure(measure_text: str) -> Tuple[Optional[float], str]:
        """解析数量单位"""
        if not measure_text:
            return None, ""

        # 清理文本
        measure_text = measure_text.strip()

        # 常见单位映射
        unit_mapping = {
            "g": "克",
            "gram": "克",
            "grams": "克",
            "kg": "千克",
            "kilogram": "千克",
            "kilograms": "千克",
            "ml": "毫升",
            "milliliter": "毫升",
            "milliliters": "毫升",
            "l": "升",
            "liter": "升",
            "liters": "升",
            "tsp": "茶匙",
            "teaspoon": "茶匙",
            "teaspoons": "茶匙",
            "tbsp": "汤匙",
            "tablespoon": "汤匙",
            "tablespoons": "汤匙",
            "cup": "杯",
            "cups": "杯",
            "oz": "盎司",
            "ounce": "盎司",
            "ounces": "盎司",
            "lb": "磅",
            "pound": "磅",
            "pounds": "磅",
            "piece": "个",
            "pieces": "个",
            "slice": "片",
            "slices": "片",
            "clove": "瓣",
            "cloves": "瓣",
            "leaf": "片",
            "leaves": "片",
        }

        # 尝试提取数字
        import re

        match = re.search(r"(\d+\.?\d*)", measure_text)
        if match:
            quantity = float(match.group(1))

            # 提取单位部分
            unit_part = measure_text[match.end() :].strip().lower()

            # 查找映射的单位
            for eng_unit, chi_unit in unit_mapping.items():
                if eng_unit in unit_part:
                    return quantity, chi_unit

            # 如果没有找到映射，返回原始单位
            return quantity, unit_part if unit_part else "适量"

        # 如果没有数字，可能是"适量"、"少许"等
        if any(
            word in measure_text.lower()
            for word in ["to taste", "as needed", "optional", "适量", "少许"]
        ):
            return None, "适量"

        return None, measure_text

    @staticmethod
    def _parse_instructions(instructions: str) -> List[Dict[str, Any]]:
        """解析步骤说明"""
        if not instructions:
            return []

        steps = []

        # 尝试按步骤编号分割
        step_patterns = [
            r"step\s*\d+[:\.]?\s*(.*?)(?=step\s*\d+[:\.]?|$)",
            r"\d+\.\s*(.*?)(?=\d+\.|$)",
            r"\d+\)\s*(.*?)(?=\d+\)|$)",
        ]

        for pattern in step_patterns:
            matches = re.findall(pattern, instructions, re.IGNORECASE | re.DOTALL)
            if matches:
                for i, step_text in enumerate(matches, 1):
                    step_text = step_text.strip()
                    if step_text:
                        steps.append(
                            {
                                "step_number": i,
                                "description": step_text,
                                "image_url": None,
                            }
                        )
                break

        # 如果没有找到编号步骤，按换行分割
        if not steps:
            lines = instructions.split("\n")
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line and len(line) > 10:  # 过滤太短的行
                    steps.append(
                        {
                            "step_number": i,
                            "description": line,
                            "image_url": None,
                        }
                    )

        # 如果还是没有步骤，将整个说明作为一个步骤
        if not steps and instructions.strip():
            steps.append(
                {
                    "step_number": 1,
                    "description": instructions.strip(),
                    "image_url": None,
                }
            )

        return steps

    @staticmethod
    def _estimate_times(instructions: str, ingredient_count: int) -> Tuple[int, int]:
        """估算准备时间和烹饪时间"""
        # 基于指令长度和食材数量估算
        instruction_length = len(instructions)

        # 准备时间估算（分钟）
        if ingredient_count <= 5:
            prep_time = 10
        elif ingredient_count <= 10:
            prep_time = 15
        else:
            prep_time = 20

        # 烹饪时间估算（分钟）
        if instruction_length < 500:
            cook_time = 15
        elif instruction_length < 1000:
            cook_time = 30
        else:
            cook_time = 45

        return prep_time, cook_time

    @staticmethod
    def _estimate_servings(ingredients: List[Dict[str, Any]]) -> int:
        """估算份量"""
        # 基于食材数量估算
        ingredient_count = len(ingredients)

        if ingredient_count <= 5:
            return 2
        elif ingredient_count <= 8:
            return 4
        else:
            return 6

    @staticmethod
    def _estimate_calories(ingredients: List[Dict[str, Any]], servings: int) -> int:
        """估算每份热量"""
        # 这是一个简化的估算，实际需要营养数据库
        # 基于常见食材类型估算

        total_estimated_calories = 0

        for ingredient in ingredients:
            name = ingredient["ingredient_name"].lower()
            quantity = ingredient["quantity"] or 1

            # 常见食材的热量估算（每100克/毫升）
            calorie_per_100g = {
                "chicken": 165,
                "beef": 250,
                "pork": 242,
                "fish": 206,
                "shrimp": 99,
                "egg": 155,
                "rice": 130,
                "pasta": 131,
                "bread": 265,
                "potato": 77,
                "tomato": 18,
                "onion": 40,
                "garlic": 149,
                "carrot": 41,
                "broccoli": 34,
                "spinach": 23,
                "cheese": 402,
                "milk": 42,
                "butter": 717,
                "oil": 884,
                "sugar": 387,
                "flour": 364,
            }

            # 查找匹配的食材
            for key, calories in calorie_per_100g.items():
                if key in name:
                    # 假设数量单位是克
                    estimated_calories = (calories * quantity) / 100
                    total_estimated_calories += estimated_calories
                    break

        # 如果没有匹配到，使用默认估算
        if total_estimated_calories == 0:
            total_estimated_calories = len(ingredients) * 100

        # 计算每份热量
        calories_per_serving = int(total_estimated_calories / servings)

        # 确保在合理范围内
        return max(100, min(800, calories_per_serving))

    @staticmethod
    def _estimate_difficulty(
        ingredient_count: int, step_count: int, cook_time: int
    ) -> str:
        """估算难度"""
        score = ingredient_count * 0.3 + step_count * 0.4 + (cook_time / 60) * 0.3

        if score < 3:
            return "easy"
        elif score < 6:
            return "medium"
        else:
            return "hard"

    @staticmethod
    def _generate_description(meal: Dict[str, Any]) -> str:
        """生成描述"""
        category = meal.get("strCategory", "")
        area = meal.get("strArea", "")

        if category and area:
            return f"{area}风味的{category}，美味可口"
        elif category:
            return f"美味的{category}，简单易做"
        else:
            return "一道美味的菜肴，适合家庭聚餐"

    @staticmethod
    def _generate_tips(meal: Dict[str, Any]) -> str:
        """生成小贴士"""
        tags = meal.get("strTags", "")
        if tags:
            tags_list = tags.split(",")
            if len(tags_list) > 0:
                return f"小贴士：这道菜的关键是{tags_list[0].lower()}。"

        return "小贴士：根据个人口味调整调料用量。"


def test_themealdb_service():
    """测试TheMealDB服务"""
    print("=== 测试TheMealDB服务 ===")

    # 测试获取随机食谱
    print("\n1. 获取3个随机食谱:")
    random_recipes = TheMealDBService.get_random_recipes(3)
    print(f"   获取到 {len(random_recipes)} 个食谱")
    for i, recipe in enumerate(random_recipes, 1):
        print(
            f"   {i}. {recipe['name']} ({recipe['category']}) - {len(recipe['ingredients'])}种食材"
        )

    # 测试搜索功能
    print("\n2. 搜索'chicken'食谱:")
    chicken_recipes = TheMealDBService.search_recipes("chicken", 2)
    print(f"   找到 {len(chicken_recipes)} 个鸡肉食谱")
    for i, recipe in enumerate(chicken_recipes, 1):
        print(f"   {i}. {recipe['name']} - {recipe['calories_per_serving']}大卡/份")

    # 测试按分类获取
    print("\n3. 获取'Vegetarian'分类食谱:")
    veg_recipes = TheMealDBService.get_recipes_by_category("Vegetarian", 2)
    print(f"   找到 {len(veg_recipes)} 个素食食谱")
    for i, recipe in enumerate(veg_recipes, 1):
        print(f"   {i}. {recipe['name']} - {recipe['difficulty']}难度")

    # 显示一个食谱的详细信息
    if random_recipes:
        print("\n4. 第一个食谱的详细信息:")
        recipe = random_recipes[0]
        print(f"   名称: {recipe['name']}")
        print(f"   描述: {recipe['description']}")
        print(f"   分类: {recipe['category']}")
        print(f"   菜系: {recipe['cuisine']}")
        print(f"   准备时间: {recipe['prep_time']}分钟")
        print(f"   烹饪时间: {recipe['cook_time']}分钟")
        print(f"   份量: {recipe['servings']}人份")
        print(f"   难度: {recipe['difficulty']}")
        print(f"   热量: {recipe['calories_per_serving']}大卡/份")
        print(f"   食材数量: {len(recipe['ingredients'])}")
        print(f"   步骤数量: {len(recipe['steps'])}")
        print(
            f"   图片URL: {recipe['image_url'][:50]}..."
            if recipe["image_url"]
            else "   无图片"
        )

        print("\n   前3个食材:")
        for ing in recipe["ingredients"][:3]:
            quantity = ing["quantity"] if ing["quantity"] is not None else "适量"
            print(f"     - {ing['ingredient_name']}: {quantity} {ing['unit']}")

        print("\n   前2个步骤:")
        for step in recipe["steps"][:2]:
            print(f"     {step['step_number']}. {step['description'][:50]}...")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_themealdb_service()
