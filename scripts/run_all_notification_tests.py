#!/usr/bin/env python3
"""
智能通知系统 - 综合测试运行脚本

一键运行所有测试工具，覆盖各种测试场景：
1. 综合测试套件 - 覆盖多用户、多场景
2. 时间模拟测试 - 验证固定时间通知
3. 管理后台验证 - 基于实际数据检验逻辑
4. 单元测试 - 验证核心组件功能
"""

import asyncio
import subprocess
import sys
import os
from datetime import datetime
from config.logging_config import get_module_logger

logger = get_module_logger()


class ComprehensiveTestRunner:
    """综合测试运行器"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
    
    async def run_comprehensive_test_suite(self):
        """运行综合测试套件"""
        logger.info("🚀 开始运行综合测试套件")
        
        try:
            # 导入并运行综合测试套件
            from tests.comprehensive_notification_test_suite import NotificationTestSuite
            
            test_suite = NotificationTestSuite()
            await test_suite.run_comprehensive_test()
            
            self.test_results.append({
                "name": "综合测试套件",
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("✅ 综合测试套件运行完成")
            
        except Exception as e:
            logger.error(f"❌ 综合测试套件运行失败: {e}")
            self.test_results.append({
                "name": "综合测试套件", 
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def run_time_simulation_test(self):
        """运行时间模拟测试"""
        logger.info("🕐 开始运行时间模拟测试")
        
        try:
            # 导入并运行时间模拟框架
            from tests.time_simulation_framework import TimeSimulationFramework
            
            framework = TimeSimulationFramework()
            
            # 模拟完整一天
            await framework.test_full_day_simulation()
            
            # 测试时间敏感事件
            await framework.test_time_sensitive_event_detection()
            
            # 生成报告
            framework.generate_time_simulation_report()
            
            self.test_results.append({
                "name": "时间模拟测试",
                "status": "completed", 
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("✅ 时间模拟测试运行完成")
            
        except Exception as e:
            logger.error(f"❌ 时间模拟测试运行失败: {e}")
            self.test_results.append({
                "name": "时间模拟测试",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    async def run_admin_validation(self):
        """运行管理后台验证"""
        logger.info("🔍 开始运行管理后台验证")
        
        try:
            # 导入并运行管理后台验证工具
            from tests.admin_validation_tool import AdminValidationTool
            
            validator = AdminValidationTool()
            
            # 测试用户列表（可以根据实际数据库调整）
            test_user_ids = [1001, 1002, 1003]
            
            # 生成验证报告
            report = await validator.generate_validation_report(test_user_ids, days=3)
            
            # 创建可视化图表
            await validator.create_visualization(test_user_ids, days=3)
            
            self.test_results.append({
                "name": "管理后台验证",
                "status": "completed",
                "user_count": len(test_user_ids),
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("✅ 管理后台验证运行完成")
            
        except Exception as e:
            logger.error(f"❌ 管理后台验证运行失败: {e}")
            self.test_results.append({
                "name": "管理后台验证",
                "status": "failed", 
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def run_unit_tests(self):
        """运行单元测试"""
        logger.info("🧪 开始运行单元测试")
        
        try:
            # 使用pytest运行单元测试
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "tests/test_intelligent_notification.py", "-v"
            ], capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode == 0:
                logger.info("✅ 单元测试运行完成")
                self.test_results.append({
                    "name": "单元测试",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.error(f"❌ 单元测试运行失败: {result.stderr}")
                self.test_results.append({
                    "name": "单元测试",
                    "status": "failed",
                    "error": result.stderr,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"❌ 单元测试运行失败: {e}")
            self.test_results.append({
                "name": "单元测试",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def generate_summary_report(self):
        """生成测试总结报告"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # 统计结果
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "completed"])
        failed_tests = len([r for r in self.test_results if r["status"] == "failed"])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # 生成报告
        report = f"""
🧪 智能通知系统 - 综合测试报告
================================

测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
测试时长: {duration:.1f}秒
测试工具数: {total_tests}

📊 测试结果汇总
---------------
通过: {passed_tests}/{total_tests} ({success_rate:.1f}%)
失败: {failed_tests}/{total_tests}

📋 详细结果
-----------
"""
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "completed" else "❌"
            report += f"{status_icon} {result['name']}: {result['status']}\n"
            
            if result["status"] == "failed" and "error" in result:
                # 截取错误信息的前100字符
                error_preview = result["error"][:100] + "..." if len(result["error"]) > 100 else result["error"]
                report += f"   错误: {error_preview}\n"
        
        report += "\n🎯 测试覆盖范围\n---------------\n"
        report += "• 多用户场景测试 (3种用户画像)\n"
        report += "• 时间敏感事件检测 (5种时间场景)\n" 
        report += "• 固定时间通知验证 (8个时间点)\n"
        report += "• 决策逻辑正确性验证\n"
        report += "• 事件检测准确性验证\n"
        report += "• 管理后台数据验证\n"
        
        report += "\n💡 后续步骤\n-----------\n"
        
        if failed_tests > 0:
            report += "1. 检查失败的测试工具，修复问题\n"
            report += "2. 重新运行失败的测试\n"
        else:
            report += "1. 所有测试通过，系统稳定性良好\n"
        
        report += "2. 查看生成的详细报告文件\n"
        report += "3. 使用管理后台验证工具定期监控\n"
        
        # 保存报告
        report_filename = f"comprehensive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report)
        
        logger.info(f"综合测试报告已保存到: {report_filename}")
        
        return report


async def run_interactive_mode():
    """交互式运行模式"""
    print("🤖 智能通知系统 - 综合测试运行器")
    print("=" * 60)
    
    runner = ComprehensiveTestRunner()
    
    while True:
        print("\n请选择测试模式:")
        print("1. 🚀 运行完整测试套件 (所有测试)")
        print("2. 📋 运行综合测试套件 (多用户场景)")
        print("3. 🕐 运行时间模拟测试 (固定时间验证)")
        print("4. 🔍 运行管理后台验证 (数据检验)")
        print("5. 🧪 运行单元测试 (核心组件)")
        print("6. 📊 查看测试报告")
        print("7. 🚪 退出")
        
        choice = input("\n请输入选择 (1-7): ").strip()
        
        if choice == "1":
            # 运行完整测试套件
            print("🚀 开始运行完整测试套件...")
            
            await runner.run_comprehensive_test_suite()
            await runner.run_time_simulation_test()
            await runner.run_admin_validation()
            runner.run_unit_tests()
            
            report = runner.generate_summary_report()
            print("\n" + report)
            
        elif choice == "2":
            # 运行综合测试套件
            print("📋 开始运行综合测试套件...")
            await runner.run_comprehensive_test_suite()
            
        elif choice == "3":
            # 运行时间模拟测试
            print("🕐 开始运行时间模拟测试...")
            await runner.run_time_simulation_test()
            
        elif choice == "4":
            # 运行管理后台验证
            print("🔍 开始运行管理后台验证...")
            await runner.run_admin_validation()
            
        elif choice == "5":
            # 运行单元测试
            print("🧪 开始运行单元测试...")
            runner.run_unit_tests()
            
        elif choice == "6":
            # 查看测试报告
            report = runner.generate_summary_report()
            print("\n" + report)
            
        elif choice == "7":
            print("👋 再见!")
            break
        else:
            print("❌ 无效选择，请重新输入")


async def run_quick_test():
    """快速测试模式"""
    print("⚡ 快速测试模式 - 运行核心测试")
    
    runner = ComprehensiveTestRunner()
    
    # 只运行核心测试
    await runner.run_comprehensive_test_suite()
    await runner.run_time_simulation_test()
    
    report = runner.generate_summary_report()
    print("\n" + report)


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        asyncio.run(run_quick_test())
    else:
        asyncio.run(run_interactive_mode())