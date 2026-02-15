#!/usr/bin/env python3
"""
用户模拟器使用示例
展示如何在端到端测试中使用UserSimulator
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../")

from test_utils.user_simulator import UserSimulator, quick_test, PREDEFINED_USERS


def example_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("基础使用示例")
    print("=" * 60)

    # 1. 创建模拟器实例
    simulator = UserSimulator(base_url="http://localhost:8000")

    # 2. 登录用户（使用预定义的测试用户）
    user = simulator.login("exercise_test_user")

    if user:
        print(f"\n✅ 登录用户: {user.nickname} (ID: {user.id})")
        print(f"   Token: {user.token[:20]}...")
        print(f"   运动记录: {user.exercise_count} 条")
        print(f"   体重记录: {user.weight_count} 条")

        # 3. 获取认证headers（用于API调用）
        headers = simulator.get_headers()
        print(f"\n🔑 认证headers: {headers}")

        # 4. 测试API
        print("\n🧪 测试运动API:")
        exercise_results = simulator.test_exercise_api()

        print("\n🧪 测试体重API:")
        weight_results = simulator.test_weight_api()

        print("\n🧪 测试聊天API:")
        chat_results = simulator.test_chat_api("你好")

        if chat_results.get("success"):
            print(f"   AI回复: {chat_results.get('response', '')[:100]}...")


def example_create_test_data():
    """创建测试数据示例"""
    print("\n" + "=" * 60)
    print("创建测试数据示例")
    print("=" * 60)

    simulator = UserSimulator()

    # 登录新用户
    user = simulator.login("new_test_user")

    if user:
        print(f"用户: {user.nickname}")

        # 创建测试数据
        success = simulator.create_test_data(
            exercise_count=5,  # 5条运动记录
            weight_count=3,  # 3条体重记录
            include_ai_records=True,  # 包含AI记录
        )

        if success:
            print("✅ 测试数据创建成功")

            # 验证数据
            print("\n📊 验证数据:")
            simulator.test_exercise_api()
            simulator.test_weight_api()


def example_full_e2e_test():
    """完整端到端测试示例"""
    print("\n" + "=" * 60)
    print("完整端到端测试示例")
    print("=" * 60)

    simulator = UserSimulator()

    # 运行完整测试
    results = simulator.run_full_test(test_code="e2e_test_user", create_data=True)

    # 保存测试报告
    report_file = simulator.save_test_report(results, "e2e_test_report.json")
    print(f"\n📄 测试报告已保存: {report_file}")

    # 打印摘要
    print("\n📋 测试摘要:")
    if "exercise_api" in results and "checkins" in results["exercise_api"]:
        checkins = results["exercise_api"]["checkins"]
        if "record_count" in checkins:
            print(f"   运动记录: {checkins['record_count']} 条")

    if "weight_api" in results and "records" in results["weight_api"]:
        records = results["weight_api"]["records"]
        if "record_count" in records:
            print(f"   体重记录: {records['record_count']} 条")

    if "chat_api_basic" in results:
        chat = results["chat_api_basic"]
        if chat.get("success"):
            print(f"   聊天测试: ✅ 成功")
            if chat.get("has_tool_calls"):
                print(f"   工具调用: ✅ 检测到")


def example_quick_test_function():
    """快速测试函数示例"""
    print("\n" + "=" * 60)
    print("快速测试函数示例")
    print("=" * 60)

    # 使用预定义的quick_test函数
    results = quick_test("quick_demo_user")

    if results:
        print(f"\n📊 快速测试结果:")
        print(f"   用户: {results['user'].nickname}")
        print(f"   运动API: {'✅' if 'checkins' in results['exercise'] else '❌'}")
        print(f"   体重API: {'✅' if 'records' in results['weight'] else '❌'}")
        print(f"   聊天API: {'✅' if results['chat'].get('success') else '❌'}")


def example_predefined_users():
    """预定义用户示例"""
    print("\n" + "=" * 60)
    print("预定义用户示例")
    print("=" * 60)

    print("可用的预定义用户:")
    for code, info in PREDEFINED_USERS.items():
        print(f"  📝 {code}: {info['description']}")

    # 测试所有预定义用户
    simulator = UserSimulator()

    for code in PREDEFINED_USERS.keys():
        print(f"\n测试用户: {code}")
        user = simulator.login(code)

        if user:
            print(
                f"  ✅ {user.nickname} - 运动: {user.exercise_count}, 体重: {user.weight_count}"
            )
        else:
            print(f"  ❌ 登录失败")


def example_custom_test_scenario():
    """自定义测试场景示例"""
    print("\n" + "=" * 60)
    print("自定义测试场景示例")
    print("=" * 60)

    simulator = UserSimulator()

    # 场景1: 体重管理测试
    print("\n🏋️ 场景1: 体重管理测试")
    weight_user = simulator.login("weight_management_user")

    if weight_user:
        # 创建体重数据
        simulator.create_test_data(
            exercise_count=0, weight_count=5, include_ai_records=False
        )

        # 测试体重相关功能
        print("测试体重记录和统计...")
        weight_results = simulator.test_weight_api()

        # 测试AI体重记录
        print("\n测试AI体重记录...")
        chat_results = simulator.test_chat_api("我体重65.5kg")
        if chat_results.get("has_tool_calls"):
            print("✅ AI成功识别并记录了体重")

    # 场景2: 运动打卡测试
    print("\n🏃 场景2: 运动打卡测试")
    exercise_user = simulator.login("exercise_tracking_user")

    if exercise_user:
        # 创建运动数据
        simulator.create_test_data(
            exercise_count=6, weight_count=0, include_ai_records=True
        )

        # 测试运动相关功能
        print("测试运动记录和统计...")
        exercise_results = simulator.test_exercise_api()

        # 测试AI运动记录
        print("\n测试AI运动记录...")
        chat_results = simulator.test_chat_api("我今天慢跑了5公里，用时50分钟")
        if chat_results.get("has_tool_calls"):
            print("✅ AI成功识别并记录了运动")

    # 场景3: 完整健康管理测试
    print("\n🏥 场景3: 完整健康管理测试")
    health_user = simulator.login("health_management_user")

    if health_user:
        # 创建完整数据
        simulator.create_test_data(
            exercise_count=4, weight_count=3, include_ai_records=True
        )

        # 运行完整测试
        results = simulator.run_full_test(create_data=False)

        # 分析结果
        print("\n📈 健康管理测试结果:")

        exercise_success = (
            results.get("exercise_api", {}).get("checkins", {}).get("success", False)
        )
        weight_success = (
            results.get("weight_api", {}).get("records", {}).get("success", False)
        )
        chat_success = results.get("chat_api_basic", {}).get("success", False)

        print(f"   运动功能: {'✅' if exercise_success else '❌'}")
        print(f"   体重功能: {'✅' if weight_success else '❌'}")
        print(f"   聊天功能: {'✅' if chat_success else '❌'}")


def main():
    """主函数 - 运行所有示例"""
    print("用户模拟器使用示例")
    print("=" * 60)

    # 运行各个示例
    example_basic_usage()
    example_create_test_data()
    example_full_e2e_test()
    example_quick_test_function()
    example_predefined_users()
    example_custom_test_scenario()

    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)

    print("\n📚 使用说明:")
    print("1. 导入: from test_utils.user_simulator import UserSimulator")
    print("2. 创建实例: simulator = UserSimulator(base_url='http://localhost:8000')")
    print("3. 登录用户: user = simulator.login('your_test_code')")
    print("4. 创建数据: simulator.create_test_data(...)")
    print("5. 测试API: results = simulator.test_exercise_api()")
    print("6. 完整测试: results = simulator.run_full_test(...)")
    print("7. 保存报告: simulator.save_test_report(results, 'report.json')")


if __name__ == "__main__":
    main()
