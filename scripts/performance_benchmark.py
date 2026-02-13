#!/usr/bin/env python3
"""
智能通知决策系统 - 性能基准测试
测试系统在各种负载下的性能表现
"""

import asyncio
import time
import statistics
import logging
from datetime import datetime
from typing import List, Dict, Any

# 配置日志
logging.basicConfig(level=logging.WARNING)  # 测试时降低日志级别

# 导入智能通知服务
import sys
sys.path.append('..')
from services.intelligent_notification_service import IntelligentNotificationService
from services.intelligent_decision_engine import DecisionMode


class PerformanceBenchmark:
    """性能基准测试类"""
    
    def __init__(self):
        self.service = IntelligentNotificationService()
        self.results = {}
    
    async def benchmark_decision_engine(self, iterations: int = 100) -> Dict[str, Any]:
        """测试决策引擎性能"""
        print(f"🧠 测试决策引擎性能 ({iterations} 次迭代)...")
        
        times = []
        
        start_time = time.time()
        
        for i in range(iterations):
            user_id = i % 10 + 1  # 循环使用10个用户ID
            
            iteration_start = time.time()
            
            result = await self.service.decision_engine.make_decision(
                user_id=user_id,
                notification_type="exercise",
                original_plan={"scheduled_time": "19:00"}
            )
            
            iteration_time = time.time() - iteration_start
            times.append(iteration_time)
            
            # 每10次显示进度
            if (i + 1) % 10 == 0:
                print(f"   已完成 {i+1}/{iterations} 次决策")
        
        total_time = time.time() - start_time
        
        return {
            "total_iterations": iterations,
            "total_time": total_time,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "throughput": iterations / total_time,
            "times": times
        }
    
    async def benchmark_message_generation(self, iterations: int = 100) -> Dict[str, Any]:
        """测试消息生成性能"""
        print(f"💬 测试消息生成性能 ({iterations} 次迭代)...")
        
        times = []
        
        start_time = time.time()
        
        for i in range(iterations):
            user_id = i % 10 + 1
            
            iteration_start = time.time()
            
            message = await self.service.message_generator.generate_message(
                message_type="standard_reminder",
                tone_style="gentle",
                plan_type="exercise"
            )
            
            iteration_time = time.time() - iteration_start
            times.append(iteration_time)
            
            # 每10次显示进度
            if (i + 1) % 10 == 0:
                print(f"   已完成 {i+1}/{iterations} 次生成")
        
        total_time = time.time() - start_time
        
        return {
            "total_iterations": iterations,
            "total_time": total_time,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "throughput": iterations / total_time,
            "times": times
        }
    
    async def benchmark_full_notification(self, iterations: int = 50) -> Dict[str, Any]:
        """测试完整通知流程性能"""
        print(f"🚀 测试完整通知流程性能 ({iterations} 次迭代)...")
        
        times = []
        
        start_time = time.time()
        
        for i in range(iterations):
            user_id = i % 10 + 1
            
            iteration_start = time.time()
            
            result = await self.service.send_active_notification(
                user_id=user_id,
                notification_type="exercise",
                plan_data={"scheduled_time": "19:00"}
            )
            
            iteration_time = time.time() - iteration_start
            times.append(iteration_time)
            
            # 每5次显示进度（完整流程较慢）
            if (i + 1) % 5 == 0:
                print(f"   已完成 {i+1}/{iterations} 次完整通知")
        
        total_time = time.time() - start_time
        
        return {
            "total_iterations": iterations,
            "total_time": total_time,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "throughput": iterations / total_time,
            "times": times
        }
    
    async def benchmark_concurrent_users(self, num_users: int = 10, iterations_per_user: int = 10) -> Dict[str, Any]:
        """测试并发用户性能"""
        print(f"👥 测试并发用户性能 ({num_users} 用户 × {iterations_per_user} 次)...")
        
        async def user_workload(user_id: int):
            """单个用户的工作负载"""
            user_times = []
            
            for i in range(iterations_per_user):
                start_time = time.time()
                
                await self.service.decision_engine.make_decision(
                    user_id=user_id,
                    notification_type="exercise",
                    original_plan={"scheduled_time": "19:00"}
                )
                
                user_times.append(time.time() - start_time)
            
            return user_times
        
        start_time = time.time()
        
        # 并发执行所有用户的工作负载
        tasks = [user_workload(i + 1) for i in range(num_users)]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # 合并所有时间数据
        all_times = []
        for user_times in results:
            all_times.extend(user_times)
        
        total_iterations = num_users * iterations_per_user
        
        return {
            "num_users": num_users,
            "iterations_per_user": iterations_per_user,
            "total_iterations": total_iterations,
            "total_time": total_time,
            "avg_time": statistics.mean(all_times),
            "min_time": min(all_times),
            "max_time": max(all_times),
            "std_dev": statistics.stdev(all_times) if len(all_times) > 1 else 0,
            "throughput": total_iterations / total_time,
            "times": all_times
        }
    
    async def benchmark_different_modes(self) -> Dict[str, Any]:
        """测试不同决策模式的性能"""
        print("📊 测试不同决策模式的性能...")
        
        modes = [
            (DecisionMode.CONSERVATIVE, "保守模式"),
            (DecisionMode.BALANCED, "平衡模式"),
            (DecisionMode.INTELLIGENT, "智能模式")
        ]
        
        results = {}
        
        for mode, mode_name in modes:
            print(f"\n🧠 测试 {mode_name}...")
            
            # 创建对应模式的服务实例
            service = IntelligentNotificationService(mode)
            
            times = []
            
            start_time = time.time()
            
            for i in range(50):  # 每个模式测试50次
                user_id = i % 10 + 1
                
                iteration_start = time.time()
                
                result = await service.decision_engine.make_decision(
                    user_id=user_id,
                    notification_type="exercise",
                    original_plan={"scheduled_time": "19:00"}
                )
                
                times.append(time.time() - iteration_start)
            
            total_time = time.time() - start_time
            
            results[mode_name] = {
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times),
                "throughput": 50 / total_time
            }
        
        return results
    
    def print_results(self, results: Dict[str, Any], test_name: str):
        """打印测试结果"""
        print(f"\n📈 {test_name} 测试结果:")
        print("-" * 50)
        
        if "total_iterations" in results:
            print(f"总迭代次数: {results['total_iterations']}")
            print(f"总耗时: {results['total_time']:.3f} 秒")
            print(f"平均耗时: {results['avg_time'] * 1000:.2f} 毫秒")
            print(f"最小耗时: {results['min_time'] * 1000:.2f} 毫秒")
            print(f"最大耗时: {results['max_time'] * 1000:.2f} 毫秒")
            print(f"标准差: {results['std_dev'] * 1000:.2f} 毫秒")
            print(f"吞吐量: {results['throughput']:.2f} 次/秒")
        else:
            # 不同模式比较的结果
            for mode_name, mode_results in results.items():
                print(f"\n{mode_name}:")
                print(f"  平均耗时: {mode_results['avg_time'] * 1000:.2f} 毫秒")
                print(f"  吞吐量: {mode_results['throughput']:.2f} 次/秒")
    
    def generate_report(self):
        """生成性能测试报告"""
        print("\n" + "=" * 70)
        print("📊 智能通知决策系统性能测试报告")
        print("=" * 70)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        for test_name, results in self.results.items():
            self.print_results(results, test_name)
        
        print("\n🎯 性能指标评估:")
        print("-" * 40)
        
        # 评估决策引擎性能
        if "decision_engine" in self.results:
            de_results = self.results["decision_engine"]
            avg_time_ms = de_results["avg_time"] * 1000
            
            if avg_time_ms < 100:
                rating = "优秀"
            elif avg_time_ms < 300:
                rating = "良好"
            elif avg_time_ms < 500:
                rating = "一般"
            else:
                rating = "需要优化"
            
            print(f"决策引擎性能: {rating} ({avg_time_ms:.2f} ms)")
        
        # 评估消息生成性能
        if "message_generation" in self.results:
            mg_results = self.results["message_generation"]
            avg_time_ms = mg_results["avg_time"] * 1000
            
            if avg_time_ms < 50:
                rating = "优秀"
            elif avg_time_ms < 150:
                rating = "良好"
            elif avg_time_ms < 300:
                rating = "一般"
            else:
                rating = "需要优化"
            
            print(f"消息生成性能: {rating} ({avg_time_ms:.2f} ms)")
        
        print("\n💡 优化建议:")
        print("- 如果决策引擎平均耗时 > 300ms，考虑添加缓存机制")
        print("- 如果消息生成耗时 > 200ms，优化模板处理逻辑")
        print("- 如果并发性能不足，考虑异步处理优化")
    
    async def run_all_benchmarks(self):
        """运行所有性能测试"""
        print("🚀 开始智能通知系统性能基准测试...")
        print()
        
        # 1. 决策引擎性能测试
        self.results["decision_engine"] = await self.benchmark_decision_engine(100)
        
        # 2. 消息生成性能测试
        self.results["message_generation"] = await self.benchmark_message_generation(100)
        
        # 3. 完整通知流程性能测试
        self.results["full_notification"] = await self.benchmark_full_notification(30)
        
        # 4. 并发用户性能测试
        self.results["concurrent_users"] = await self.benchmark_concurrent_users(10, 5)
        
        # 5. 不同决策模式性能测试
        self.results["different_modes"] = await self.benchmark_different_modes()
        
        # 生成最终报告
        self.generate_report()


async def main():
    """主函数"""
    benchmark = PerformanceBenchmark()
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    print("🚀 启动智能通知系统性能基准测试...")
    asyncio.run(main())