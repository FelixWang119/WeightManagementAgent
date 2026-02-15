#!/usr/bin/env python3
"""
Day 2: 用户管理API测试运行脚本
运行用户管理相关的API测试
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load test environment
from dotenv import load_dotenv

env_test_path = project_root / ".env.test"
load_dotenv(env_test_path, override=True)


async def run_user_tests():
    """运行用户管理API测试"""
    print("🚀 开始Day 2: 用户管理API测试执行")
    print("=" * 60)

    # 检查测试环境
    print("🔍 检查测试环境...")
    assert "QWEN_API_KEY" in os.environ, "QWEN_API_KEY not set in environment"
    assert "DATABASE_URL" in os.environ, "DATABASE_URL not set in environment"

    test_db_path = project_root / "test_weight_management.db"
    assert test_db_path.exists(), f"Test database not found at {test_db_path}"

    print("✅ 测试环境检查通过")

    # 运行pytest测试
    print("\n🔧 运行用户管理API测试...")
    print("=" * 60)

    # 使用pytest运行测试
    import subprocess

    # 运行用户管理测试
    result = subprocess.run(
        ["pytest", "tests/test_user_management.py", "-v", "--tb=short"],
        cwd=project_root,
    )

    print("\n" + "=" * 60)

    if result.returncode == 0:
        print("🎉 Day 2测试完成: 所有用户管理API测试通过!")
        return True
    else:
        print("⚠️  Day 2测试完成: 部分测试失败，需要调试")
        print("\n📋 下一步:")
        print("1. 检查失败的测试用例")
        print("2. 调试应用代码")
        print("3. 修复问题后重新运行测试")
        return False


async def check_user_api_endpoints():
    """检查用户API端点是否可用"""
    print("\n🔍 检查用户API端点...")

    # 导入必要的模块
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # 测试端点列表
    endpoints = [
        ("POST", "/api/user/login", "用户登录"),
        ("POST", "/api/user/register", "用户注册"),
        ("GET", "/api/user/profile", "获取用户信息"),
        ("PUT", "/api/user/profile", "更新用户信息"),
        ("PUT", "/api/user/profile/bmr", "更新BMR"),
        ("GET", "/api/user/agent/config", "获取Agent配置"),
        ("GET", "/api/user/agent/styles", "获取Agent风格"),
        ("PUT", "/api/user/agent/config", "更新Agent配置"),
    ]

    available_endpoints = []
    unavailable_endpoints = []

    for method, path, description in endpoints:
        try:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json={})
            elif method == "PUT":
                response = client.put(path, json={})
            else:
                continue

            # 检查端点是否存在（404表示端点不存在，其他状态码可能表示参数错误等）
            if response.status_code != 404:
                available_endpoints.append((method, path, description))
            else:
                unavailable_endpoints.append((method, path, description))

        except Exception as e:
            unavailable_endpoints.append(
                (method, path, f"{description} - 错误: {str(e)}")
            )

    print(f"✅ 可用端点: {len(available_endpoints)}个")
    for method, path, desc in available_endpoints:
        print(f"   {method} {path} - {desc}")

    if unavailable_endpoints:
        print(f"⚠️  不可用端点: {len(unavailable_endpoints)}个")
        for method, path, desc in unavailable_endpoints:
            print(f"   {method} {path} - {desc}")

    return len(available_endpoints) > 0


async def main():
    """主函数"""
    print("=" * 60)
    print("Day 2: 用户管理API测试")
    print("=" * 60)

    # 检查API端点
    endpoints_ok = await check_user_api_endpoints()
    if not endpoints_ok:
        print("❌ API端点检查失败，无法继续测试")
        return False

    # 运行测试
    print("\n" + "=" * 60)
    print("开始执行用户管理API测试...")
    print("=" * 60)

    # 在实际环境中，应该使用pytest运行测试
    # 这里我们提供一个指导
    print("\n📋 执行测试的两种方式:")
    print("1. 使用pytest运行完整测试:")
    print("   cd /Users/felix/open_workdspace")
    print("   pytest tests/test_user_management.py -v")
    print("\n2. 使用本脚本检查环境:")
    print("   python tests/run_day2_user_tests.py")

    # 尝试运行测试
    try:
        success = await run_user_tests()
        return success
    except Exception as e:
        print(f"❌ 测试执行出错: {e}")
        print("\n💡 建议:")
        print("1. 确保测试数据库存在: test_weight_management.db")
        print("2. 检查环境变量配置: .env.test")
        print("3. 检查FastAPI应用是否能正常启动")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
