"""
食谱生成器模块
使用通义千问API生成减脂餐食谱
"""

import asyncio
import json
import os
import httpx
from typing import List, Dict, Any, Optional
from pathlib import Path

# 临时禁用代理（如果需要）
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["all_proxy"] = ""

# 添加项目根目录到Python路径
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import fastapi_settings
from models.database import (
    RecipeDifficulty,
    RecipeCategory,
    RecipeCuisine,
)


class DietRecipeGenerator:
    """减脂餐食谱生成器"""

    def __init__(self):
        self.api_key = fastapi_settings.QWEN_API_KEY
        if not self.api_key:
            raise ValueError("未配置通义千问API密钥，请在.env文件中设置QWEN_API_KEY")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 食谱主题
        self.recipe_themes = [
            "中式减脂餐",
            "西式轻食沙拉",
            "高蛋白健身餐",
            "快手减脂早餐",
            "低卡晚餐",
            "办公室健康便当",
            "素食减脂餐",
            "日韩低卡料理",
        ]

    async def generate_recipes(self, count: int = 10) -> List[Dict[str, Any]]:
        """生成减脂餐食谱"""

        print(f"使用通义千问API生成 {count} 个减脂餐食谱...")

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        prompt = self._build_generation_prompt(count)

        payload = {
            "model": "qwen-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的营养师和厨师，擅长制作健康减脂餐。请用中文回答，返回严格的JSON格式。",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 3000,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print("发送API请求...")
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]

                    print(f"API响应长度: {len(content)} 字符")

                    # 解析响应
                    recipes = self._parse_response(content)
                    print(f"成功解析 {len(recipes)} 个食谱")

                    # 验证和标准化
                    validated_recipes = []
                    for recipe in recipes:
                        validated = self._validate_recipe(recipe)
                        if validated:
                            validated_recipes.append(validated)

                    return validated_recipes
                else:
                    print(f"API错误: {response.status_code}")
                    print(f"响应: {response.text[:200]}")
                    return []

        except Exception as e:
            print(f"生成食谱失败: {e}")
            import traceback

            traceback.print_exc()
            return []

    def _build_generation_prompt(self, count: int) -> str:
        """构建生成提示词"""

        return f"""请生成{count}个减脂餐食谱，返回JSON格式。

要求：
1. 食谱特点：减脂、轻食、快手、健康、利于减肥
2. 语言：中文
3. 格式：严格的JSON数组

每个食谱包含以下字段：
- name: 食谱名称（中文）
- description: 简短描述（20字以内，说明减脂特点）
- prep_time: 准备时间（5-15分钟）
- cook_time: 烹饪时间（5-25分钟）
- servings: 份量（1-2人份）
- difficulty: 难度（easy/medium/hard）
- category: 分类（breakfast/lunch/dinner/snack/dessert/soup）
- cuisine: 菜系（chinese/western/japanese/korean/vegetarian/low_calorie/high_protein）
- calories_per_serving: 每份热量（150-350大卡）
- protein_per_serving: 每份蛋白质（10-25克）
- fat_per_serving: 每份脂肪（3-12克）
- carbs_per_serving: 每份碳水化合物（15-35克）
- image_url: null
- is_public: true
- ingredients: 食材数组（3-6种），每个食材包含：
    - ingredient_name: 食材名称（中文）
    - quantity: 数量
    - unit: 单位（克、毫升、个、适量等）
- steps: 步骤数组（3-5步），每个步骤包含：
    - description: 步骤描述（中文，15字以内）

减脂餐设计原则：
1. 低热量：每份150-350大卡
2. 高蛋白：每份10-25克蛋白质
3. 低脂肪：使用健康油脂
4. 高纤维：多蔬菜，全谷物
5. 少加工：天然食材，避免精加工食品
6. 快手：总时间不超过40分钟
7. 简单：步骤清晰，适合新手

请直接返回JSON数组，不要有其他文字。"""

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """解析API响应"""

        if not response_text:
            return []

        response_text = response_text.strip()

        try:
            # 尝试直接解析
            recipes = json.loads(response_text)
            if not isinstance(recipes, list):
                recipes = [recipes]
            return recipes

        except json.JSONDecodeError:
            # 尝试提取JSON
            import re

            json_pattern = r"\[\s*\{.*?\}\s*\]"
            matches = re.findall(json_pattern, response_text, re.DOTALL)

            if matches:
                try:
                    recipes = json.loads(matches[0])
                    return recipes if isinstance(recipes, list) else [recipes]
                except:
                    pass

            print(f"无法解析响应: {response_text[:200]}...")
            return []

    def _validate_recipe(self, recipe: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """验证和标准化食谱"""

        try:
            # 必需字段
            required = ["name", "description", "prep_time", "cook_time", "servings"]
            for field in required:
                if field not in recipe:
                    print(f"警告：食谱缺少字段 {field}")
                    return None

            # 设置默认值
            recipe.setdefault("difficulty", "medium")
            recipe.setdefault("category", "lunch")
            recipe.setdefault("cuisine", "chinese")
            recipe.setdefault("calories_per_serving", 250)
            recipe.setdefault("protein_per_serving", 15.0)
            recipe.setdefault("fat_per_serving", 8.0)
            recipe.setdefault("carbs_per_serving", 25.0)
            recipe.setdefault("image_url", None)
            recipe.setdefault("is_public", True)

            # 计算总时间
            recipe["total_time"] = recipe["prep_time"] + recipe["cook_time"]

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

            recipe["difficulty"] = difficulty_map.get(
                str(recipe["difficulty"]).lower(), RecipeDifficulty.MEDIUM
            )

            recipe["category"] = category_map.get(
                str(recipe["category"]).lower(), RecipeCategory.LUNCH
            )

            recipe["cuisine"] = cuisine_map.get(
                str(recipe["cuisine"]).lower(), RecipeCuisine.CHINESE
            )

            # 验证食材和步骤
            recipe.setdefault("ingredients", [])
            recipe.setdefault("steps", [])

            if not isinstance(recipe["ingredients"], list):
                recipe["ingredients"] = []

            if not isinstance(recipe["steps"], list):
                recipe["steps"] = []

            # 为食材和步骤添加索引
            for i, ingredient in enumerate(recipe["ingredients"]):
                ingredient["order_index"] = i

            for i, step in enumerate(recipe["steps"]):
                step["step_number"] = i + 1
                step["order_index"] = i

            return recipe

        except Exception as e:
            print(f"验证食谱失败: {e}")
            return None

    async def save_to_json(
        self, recipes: List[Dict[str, Any]], filename: str = "generated_recipes.json"
    ):
        """保存食谱到JSON文件"""

        output_path = Path(filename)

        # 转换为可序列化的格式
        serializable_recipes = []
        for recipe in recipes:
            serializable = recipe.copy()
            serializable["difficulty"] = serializable["difficulty"].value
            serializable["category"] = serializable["category"].value
            serializable["cuisine"] = serializable["cuisine"].value
            serializable_recipes.append(serializable)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_recipes, f, ensure_ascii=False, indent=2)

        print(f"食谱已保存到: {output_path}")
        return output_path
