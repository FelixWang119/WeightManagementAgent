#!/usr/bin/env python3
"""
智能通知决策系统 - 主动提醒测试启动器
统一入口，提供多种测试方式选择
"""

import asyncio
import subprocess
import sys
import os
from pathlib import Path


class ActiveNotificationTestLauncher:
    """主动提醒测试启动器"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.test_options = [
            {
                "id": 1,
                "name": "快速单元测试",
                "description": "运行基础单元测试，验证核心功能",
                "command": ["pytest", "tests/test_intelligent_notification.py", "-v"],
                "file": "tests/test_intelligent_notification.py"
            },
            {
                "id": 2,
                "name": "交互式测试控制台",
                "description": "交互式界面，手动测试各种场景",
                "command": ["python", "scripts/interactive_notification_tester.py"],
                "file": "scripts/interactive_notification_tester.py"
            },
            {
                "id": 3,
                "name": "性能基准测试",
                "description": "测试系统性能，生成基准报告",
                "command": ["python", "scripts/performance_benchmark.py"],
                "file": "scripts/performance_benchmark.py"
            },
            {
                "id": 4,
                "name": "实时监控工具",
                "description": "实时监控系统运行状态",
                "command": ["python", "scripts/real_time_monitor.py"],
                "file": "scripts/real_time_monitor.py"
            },
            {
                "id": 5,
                "name": "完整测试套件",
                "description": "运行所有测试，生成完整报告",
                "command": ["pytest", "tests/", "-v", "--html=test_report.html", "--self-contained-html"],
                "file": "tests/"
            },
            {
                "id": 6,
                "name": "API直接测试",
                "description": "直接调用API进行测试",
                "command": ["python", "-c", self._get_api_test_code()],
                "file": "api_test"
            }
        ]
    
    def _get_api_test_code(self):
        """获取API测试代码"""
        return """
import asyncio
import sys
sys.path.append('.')

async def test_api():
    from services.intelligent_notification_service import intelligent_notification_service
    
    print("🧪 API直接测试")
    print("-" * 40)
    
    # 测试1: 标准通知
    print("\\n1. 测试标准运动通知:")
    result1 = await intelligent_notification_service.send_active_notification(
        user_id=1,
        notification_type="exercise",
        plan_data={"scheduled_time": "19:00"}
    )
    print(f"   结果: {result1}")
    
    # 测试2: 用户偏好分析
    print("\\n2. 测试用户偏好分析:")
    analysis = await intelligent_notification_service.analyze_user_notification_patterns(1)
    print(f"   分析完成，用户ID: {analysis.get('user_id', 'N/A')}")
    
    print("\\n✅ API测试完成")

asyncio.run(test_api())
"""
    
    def print_menu(self):
        """打印菜单"""
        print("=" * 70)
        print("🧠 智能通知决策系统 - 主动提醒测试启动器")
        print("=" * 70)
        print()
        
        print("📋 可用的测试选项:")
        for option in self.test_options:
            print(f"{option['id']}. {option['name']}")
            print(f"   {option['description']}")
            
            # 检查文件是否存在
            file_path = self.script_dir / option["file"]
            if file_path.exists():
                status = "✅ 可用"
            else:
                status = "❌ 文件不存在"
            
            print(f"   状态: {status}")
            print()
        
        print("0. 退出")
        print()
    
    def check_dependencies(self):
        """检查依赖"""
        print("🔍 检查依赖...")
        
        missing_deps = []
        
        # 检查pytest
        try:
            import pytest
            print("✅ pytest 已安装")
        except ImportError:
            missing_deps.append("pytest")
            print("❌ pytest 未安装")
        
        # 检查asyncio
        try:
            import asyncio
            print("✅ asyncio 可用")
        except ImportError:
            missing_deps.append("asyncio")
            print("❌ asyncio 不可用")
        
        # 检查智能通知服务
        try:
            sys.path.append('.')
            from services.intelligent_notification_service import intelligent_notification_service
            print("✅ 智能通知服务 可用")
        except ImportError as e:
            missing_deps.append("智能通知服务")
            print(f"❌ 智能通知服务导入失败: {e}")
        
        if missing_deps:
            print(f"\n⚠️ 缺少依赖: {', '.join(missing_deps)}")
            print("请先安装依赖: pip install pytest")
            return False
        
        print("✅ 所有依赖检查通过")
        return True
    
    def run_test(self, option_id: int):
        """运行测试"""
        option = next((opt for opt in self.test_options if opt["id"] == option_id), None)
        
        if not option:
            print("❌ 无效的选项ID")
            return False
        
        # 检查文件是否存在（除了API测试）
        if option["id"] != 6:  # API测试不需要文件检查
            file_path = self.script_dir / option["file"]
            if not file_path.exists():
                print(f"❌ 文件不存在: {file_path}")
                return False
        
        print(f"🚀 启动测试: {option['name']}")
        print("-" * 50)
        
        try:
            # 改变工作目录到项目根目录
            os.chdir(self.script_dir.parent)
            
            # 执行命令
            if option["id"] == 6:  # API测试特殊处理
                result = subprocess.run([sys.executable, "-c", option["command"][2]])
            else:
                result = subprocess.run(option["command"])
            
            if result.returncode == 0:
                print(f"\n✅ {option['name']} 测试完成")
                return True
            else:
                print(f"\n❌ {option['name']} 测试失败，返回码: {result.returncode}")
                return False
                
        except Exception as e:
            print(f"❌ 执行测试时出错: {e}")
            return False
    
    def run_interactive(self):
        """运行交互式选择"""
        while True:
            self.print_menu()
            
            try:
                choice = input("请选择测试选项 (0-6): ").strip()
                
                if choice == '0':
                    print("\n👋 再见！")
                    break
                
                option_id = int(choice)
                
                if 1 <= option_id <= 6:
                    success = self.run_test(option_id)
                    
                    if not success:
                        print("\n⚠️ 测试失败，请检查错误信息")
                    
                    input("\n按回车键继续...")
                else:
                    print("❌ 无效的选择，请输入 0-6 之间的数字")
                    
            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，再见！")
                break
    
    def run_quick_test(self):
        """运行快速测试（所有测试）"""
        print("🚀 启动快速完整测试套件...")
        print("=" * 60)
        
        test_results = {}
        
        # 按顺序运行关键测试
        key_tests = [1, 2, 3, 5]  # 单元测试、交互测试、性能测试、完整测试
        
        for test_id in key_tests:
            option = next((opt for opt in self.test_options if opt["id"] == test_id), None)
            if option:
                print(f"\n📋 运行: {option['name']}")
                print("-" * 40)
                
                success = self.run_test(test_id)
                test_results[option["name"]] = success
                
                if not success:
                    print(f"⚠️ {option['name']} 测试失败")
        
        # 生成测试报告
        print("\n" + "=" * 60)
        print("📊 快速测试报告")
        print("=" * 60)
        
        passed = sum(1 for success in test_results.values() if success)
        total = len(test_results)
        
        print(f"✅ 通过: {passed}/{total}")
        
        for test_name, success in test_results.items():
            status = "✅ 通过" if success else "❌ 失败"
            print(f"   {test_name}: {status}")
        
        if passed == total:
            print("\n🎉 所有测试通过！系统运行正常")
        else:
            print(f"\n⚠️ 有 {total - passed} 个测试失败，请检查问题")


def main():
    """主函数"""
    import sys
    
    launcher = ActiveNotificationTestLauncher()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        # 没有参数时使用默认模式
        mode = '2'  # 默认快速测试
    
    # 检查依赖
    if not launcher.check_dependencies():
        print("\n⚠️ 依赖检查失败，部分测试可能无法运行")
        print("继续运行快速测试...")
    
    print("\n" + "=" * 60)
    print("选择测试模式:")
    print("1. 交互式选择 (推荐新手)")
    print("2. 快速完整测试 (运行所有关键测试)")
    print("0. 退出")
    print(f"自动选择模式: {mode}")
    
    if mode == '0':
        print("👋 再见！")
    elif mode == '1':
        launcher.run_interactive()
    elif mode == '2':
        launcher.run_quick_test()
    else:
        print("❌ 无效的选择，使用默认模式2")
        launcher.run_quick_test()


if __name__ == "__main__":
    print("🚀 启动智能通知决策系统测试启动器...")
    main()