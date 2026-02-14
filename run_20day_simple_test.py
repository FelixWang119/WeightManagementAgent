#!/usr/bin/env python3
"""
运行20天simple版本测试
使用真实认证，测试simple版本的性能
"""

import sys
import os
import asyncio
import json
from datetime import datetime, timedelta
import logging

# 设置simple版本
os.environ["AGENT_VERSION"] = "simple"

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.main_test_runner import MainTestRunner

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_simple_version_test():
    """运行simple版本测试"""
    print("🚀 启动Simple版本20天真实场景测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Agent版本: simple")
    print(f"测试周期: 20天模拟")
    print(f"用户类型: 4种不同画像")
    print(f"使用真实认证: 是")
    print("=" * 60)

    # 创建测试运行器（使用真实认证）
    runner = MainTestRunner(base_url="http://127.0.0.1:8000", use_real_auth=True)

    try:
        # 1. 设置测试用户
        print("\n1. 📋 设置测试用户...")
        await runner.setup_test_users()
        print(f"   ✓ 已创建 {len(runner.framework.users)} 个测试用户:")
        for user_id, profile in runner.framework.users.items():
            print(f"     - {profile.name} ({profile.occupation}, {profile.age}岁)")

        # 2. 生成测试计划
        print("\n2. 📅 生成测试计划...")
        test_plan = runner.generate_test_plan()

        # 统计测试点
        total_tests = 0
        for user_id, tests in test_plan.items():
            user_name = runner.framework.users[user_id].name
            print(f"     {user_name}: {len(tests)} 个测试点")
            total_tests += len(tests)

        print(f"   ✓ 总计生成 {total_tests} 个测试点")

        # 3. 运行简化测试（为了速度，只运行部分测试）
        print("\n3. 🧪 运行简化测试（每个用户2个测试点）...")
        print("   注意: 为了快速获得结果，只运行部分测试")
        print("   " + "-" * 40)

        # 创建简化测试计划
        simplified_plan = {}
        for user_id, tests in test_plan.items():
            if tests:
                simplified_plan[user_id] = tests[:2]  # 每个用户只运行前2个测试

        # 运行测试
        results = []
        for user_id, tests in simplified_plan.items():
            user_name = runner.framework.users[user_id].name
            print(f"\n   👤 测试用户: {user_name}")

            for i, test in enumerate(tests, 1):
                print(f"     {i}. 第{test.day}天 {test.time}")
                print(f"        输入: {test.user_input}")
                print(f"        期望记忆: {test.expected_memory_recall}")

                try:
                    # 执行测试
                    result = await runner.framework.execute_test(user_id, test)

                    if result.passed:
                        print(f"        ✅ 通过")
                    else:
                        print(f"        ❌ 失败: {result.error_message}")

                    results.append(result)

                except Exception as e:
                    print(f"        ⚠️  错误: {str(e)[:100]}")
                    results.append(None)

        # 4. 分析结果
        print("\n4. 📊 分析测试结果...")

        total = len(results)
        passed = sum(1 for r in results if r and r.passed)
        failed = sum(1 for r in results if r and not r.passed)
        errors = sum(1 for r in results if r is None)

        success_rate = (passed / total * 100) if total > 0 else 0

        print(f"   📈 测试统计:")
        print(f"     总测试数: {total}")
        print(f"     通过数: {passed}")
        print(f"     失败数: {failed}")
        print(f"     错误数: {errors}")
        print(f"     成功率: {success_rate:.1f}%")

        # 5. 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"simple_version_test_report_{timestamp}.json"

        report = {
            "summary": {
                "total_tests": total,
                "passed_tests": passed,
                "failed_tests": failed,
                "error_tests": errors,
                "success_rate": success_rate,
                "agent_version": "simple",
                "test_duration": "简化20天测试",
                "user_count": len(runner.framework.users),
                "generated_at": datetime.now().isoformat(),
            },
            "test_details": [
                {
                    "user_id": result.user_id if result else None,
                    "test_description": result.test_description if result else "错误",
                    "passed": result.passed if result else False,
                    "error_message": result.error_message if result else "执行错误",
                    "response_time": result.response_time if result else None,
                }
                for result in results
            ],
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n   💾 报告已保存: {report_file}")

        # 6. 评估结果
        print("\n5. 🎯 评估Simple版本性能...")
        print("   " + "-" * 40)

        if success_rate >= 50:
            print(f"   ✅ Simple版本表现良好 (成功率: {success_rate:.1f}%)")
            print(f"   建议: 可以继续进行全面20天测试")
        elif success_rate > 0:
            print(f"   ⚠️  Simple版本表现一般 (成功率: {success_rate:.1f}%)")
            print(f"   建议: 需要优化后再测试")
        else:
            print(f"   ❌ Simple版本表现不佳 (成功率: {success_rate:.1f}%)")
            print(f"   建议: 需要修复问题")

        print("\n" + "=" * 60)
        print("✅ Simple版本测试完成")

        return report

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("🔧 检查环境...")
    print(f"当前Agent版本: {os.environ.get('AGENT_VERSION', '未设置')}")

    asyncio.run(run_simple_version_test())
