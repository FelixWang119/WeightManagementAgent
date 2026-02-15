#!/usr/bin/env python3
"""
食谱生成工具主程序
使用通义千问API生成减脂餐食谱并导入数据库
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.recipe_generator.generator import DietRecipeGenerator
from tools.recipe_generator.importer import RecipeImporter
from tools.recipe_generator.checker import RecipeChecker


async def generate_recipes(count: int = 10, output_file: str = None):
    """生成食谱"""
    print(f"生成 {count} 个减脂餐食谱...")

    generator = DietRecipeGenerator()
    recipes = await generator.generate_recipes(count)

    if not recipes:
        print("未能生成食谱")
        return False

    print(f"成功生成 {len(recipes)} 个食谱")

    # 保存到文件
    if output_file:
        await generator.save_to_json(recipes, output_file)

    return True


async def import_recipes(json_file: str = None):
    """导入食谱到数据库"""
    print("导入食谱到数据库...")

    importer = RecipeImporter()

    if json_file:
        # 从JSON文件导入
        success = await importer.import_from_json(json_file)
    else:
        # 使用默认示例数据
        success = await importer.import_sample_recipes()

    return success


async def check_database():
    """检查数据库中的食谱"""
    print("检查数据库中的食谱...")

    checker = RecipeChecker()
    await checker.check_recipes()

    return True


async def full_pipeline(count: int = 10):
    """完整流程：生成、导入、检查"""
    print("=" * 60)
    print("食谱生成完整流程")
    print("=" * 60)

    # 1. 生成食谱
    print("\n1. 生成食谱...")
    generator = DietRecipeGenerator()
    recipes = await generator.generate_recipes(count)

    if not recipes:
        print("生成失败")
        return False

    print(f"生成 {len(recipes)} 个食谱")

    # 2. 保存到文件
    print("\n2. 保存到文件...")
    output_file = "generated_recipes.json"
    await generator.save_to_json(recipes, output_file)

    # 3. 导入数据库
    print("\n3. 导入数据库...")
    importer = RecipeImporter()
    import_success = await importer.import_recipes(recipes)

    if not import_success:
        print("导入失败")
        return False

    # 4. 检查数据库
    print("\n4. 检查数据库...")
    checker = RecipeChecker()
    await checker.check_recipes()

    print("\n" + "=" * 60)
    print("完整流程完成！")
    print("=" * 60)

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="食谱生成工具")
    parser.add_argument(
        "action",
        choices=["generate", "import", "check", "pipeline"],
        help="执行的操作：generate=生成食谱, import=导入数据库, check=检查数据库, pipeline=完整流程",
    )
    parser.add_argument(
        "-c", "--count", type=int, default=10, help="生成食谱的数量（默认10）"
    )
    parser.add_argument("-f", "--file", type=str, help="JSON文件路径（用于导入）")
    parser.add_argument("-o", "--output", type=str, help="输出JSON文件路径（用于生成）")

    args = parser.parse_args()

    try:
        if args.action == "generate":
            asyncio.run(generate_recipes(args.count, args.output))

        elif args.action == "import":
            asyncio.run(import_recipes(args.file))

        elif args.action == "check":
            asyncio.run(check_database())

        elif args.action == "pipeline":
            asyncio.run(full_pipeline(args.count))

        print("\n操作完成！")

    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
