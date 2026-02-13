#!/usr/bin/env python3
"""
智能通知决策系统 - 实时监控工具
实时监控系统运行状态和通知效果
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading

# 配置日志
logging.basicConfig(level=logging.INFO)

# 导入智能通知服务
import sys
sys.path.append('..')
from services.intelligent_notification_service import IntelligentNotificationService


class RealTimeMonitor:
    """实时监控类"""
    
    def __init__(self):
        self.service = IntelligentNotificationService()
        self.monitoring_data = {
            "notifications_sent": 0,
            "notifications_adjusted": 0,
            "events_detected": 0,
            "errors_occurred": 0,
            "performance_metrics": [],
            "user_feedback": []
        }
        
        self.running = False
        self.monitor_thread = None
        
        # 模拟用户反馈数据
        self.user_feedback_db = [
            {"user_id": 1, "timestamp": datetime.now() - timedelta(hours=2), "rating": 4, "comment": "提醒很及时"},
            {"user_id": 2, "timestamp": datetime.now() - timedelta(hours=1), "rating": 5, "comment": "个性化建议很有帮助"},
            {"user_id": 3, "timestamp": datetime.now() - timedelta(minutes=30), "rating": 3, "comment": "有点频繁"}
        ]
    
    def start_monitoring(self):
        """开始监控"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print("🔍 实时监控已启动...")
        print("   按 Ctrl+C 停止监控")
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        
        print("\n🛑 实时监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        import time
        
        while self.running:
            # 更新性能指标
            self._update_performance_metrics()
            
            # 更新用户反馈数据
            self._update_user_feedback()
            
            # 显示监控面板
            self._display_dashboard()
            
            # 每5秒更新一次
            time.sleep(5)
    
    def _update_performance_metrics(self):
        """更新性能指标"""
        # 模拟性能数据
        current_metrics = {
            "timestamp": datetime.now(),
            "decision_time": 0.15 + (0.05 * (time.time() % 1)),  # 模拟波动
            "message_generation_time": 0.08 + (0.03 * (time.time() % 1)),
            "active_users": 5 + int(time.time() % 3),
            "notifications_per_minute": 2 + int(time.time() % 2)
        }
        
        self.monitoring_data["performance_metrics"].append(current_metrics)
        
        # 只保留最近10个数据点
        if len(self.monitoring_data["performance_metrics"]) > 10:
            self.monitoring_data["performance_metrics"] = self.monitoring_data["performance_metrics"][-10:]
    
    def _update_user_feedback(self):
        """更新用户反馈数据"""
        # 模拟新反馈数据
        if len(self.user_feedback_db) < 10:  # 限制数据量
            new_feedback = {
                "user_id": len(self.user_feedback_db) + 1,
                "timestamp": datetime.now(),
                "rating": 3 + int(time.time() % 3),  # 3-5分
                "comment": "测试反馈"
            }
            self.user_feedback_db.append(new_feedback)
        
        self.monitoring_data["user_feedback"] = self.user_feedback_db[-5:]  # 显示最近5条
    
    def _display_dashboard(self):
        """显示监控面板"""
        import os
        
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 80)
        print("🧠 智能通知决策系统 - 实时监控面板")
        print("=" * 80)
        print(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 显示核心指标
        self._display_key_metrics()
        
        # 显示性能图表
        self._display_performance_chart()
        
        # 显示用户反馈
        self._display_user_feedback()
        
        # 显示系统状态
        self._display_system_status()
        
        print("\n" + "-" * 80)
        print("💡 操作提示: 按 Ctrl+C 停止监控")
    
    def _display_key_metrics(self):
        """显示关键指标"""
        print("📊 关键指标:")
        print("-" * 40)
        
        metrics = self.monitoring_data["performance_metrics"]
        if metrics:
            latest = metrics[-1]
            
            print(f"   决策引擎平均耗时: {latest['decision_time'] * 1000:.1f} ms")
            print(f"   消息生成平均耗时: {latest['message_generation_time'] * 1000:.1f} ms")
            print(f"   活跃用户数: {latest['active_users']}")
            print(f"   每分钟通知数: {latest['notifications_per_minute']}")
        
        print(f"   累计发送通知: {self.monitoring_data['notifications_sent']}")
        print(f"   累计调整通知: {self.monitoring_data['notifications_adjusted']}")
        print(f"   累计检测事件: {self.monitoring_data['events_detected']}")
        print(f"   累计错误数: {self.monitoring_data['errors_occurred']}")
        print()
    
    def _display_performance_chart(self):
        """显示性能图表"""
        print("📈 性能趋势 (最近10个数据点):")
        print("-" * 40)
        
        metrics = self.monitoring_data["performance_metrics"]
        if not metrics:
            print("   暂无数据")
            print()
            return
        
        # 决策时间趋势
        decision_times = [m["decision_time"] * 1000 for m in metrics]
        self._print_simple_chart("决策时间(ms)", decision_times, 50, 200)
        
        # 消息生成时间趋势
        message_times = [m["message_generation_time"] * 1000 for m in metrics]
        self._print_simple_chart("消息生成(ms)", message_times, 30, 120)
        
        print()
    
    def _print_simple_chart(self, title: str, data: List[float], min_val: float, max_val: float):
        """打印简单图表"""
        print(f"   {title}:", end=" ")
        
        for value in data:
            # 归一化到0-1范围
            normalized = max(0, min(1, (value - min_val) / (max_val - min_val)))
            bar_length = int(normalized * 20)  # 20个字符宽度
            
            bar = "█" * bar_length + " " * (20 - bar_length)
            print(bar, end=" ")
        
        # 显示数值
        if data:
            print(f"({data[-1]:.1f})")
        else:
            print()
    
    def _display_user_feedback(self):
        """显示用户反馈"""
        print("💬 用户反馈 (最近5条):")
        print("-" * 40)
        
        feedbacks = self.monitoring_data["user_feedback"]
        
        if not feedbacks:
            print("   暂无用户反馈")
            print()
            return
        
        for i, feedback in enumerate(feedbacks, 1):
            time_str = feedback["timestamp"].strftime("%H:%M")
            stars = "★" * feedback["rating"] + "☆" * (5 - feedback["rating"])
            
            print(f"   {i}. 用户{feedback['user_id']} - {time_str} - {stars}")
            print(f"      评论: {feedback['comment']}")
        
        # 计算平均评分
        if feedbacks:
            avg_rating = sum(f["rating"] for f in feedbacks) / len(feedbacks)
            print(f"   平均评分: {avg_rating:.1f}/5.0")
        
        print()
    
    def _display_system_status(self):
        """显示系统状态"""
        print("🔧 系统状态:")
        print("-" * 40)
        
        # 模拟系统状态
        status_indicators = {
            "决策引擎": "✅ 正常",
            "事件检测": "✅ 正常",
            "话术生成": "✅ 正常",
            "通知发送": "✅ 正常",
            "用户画像": "⚠️ 模拟数据",
            "性能监控": "✅ 正常"
        }
        
        for component, status in status_indicators.items():
            print(f"   {component}: {status}")
        
        print()
    
    async def simulate_notification_workload(self, duration_minutes: int = 5):
        """模拟通知工作负载"""
        print(f"\n🎭 开始模拟通知工作负载 ({duration_minutes} 分钟)...")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        notification_count = 0
        
        while time.time() < end_time and self.running:
            # 模拟发送通知
            user_id = int(time.time() % 10) + 1
            
            try:
                result = await self.service.send_active_notification(
                    user_id=user_id,
                    notification_type="exercise",
                    plan_data={"scheduled_time": "19:00"}
                )
                
                self.monitoring_data["notifications_sent"] += 1
                
                if result.get("sent", False):
                    notification_count += 1
                    
                    # 随机模拟调整
                    if notification_count % 3 == 0:
                        self.monitoring_data["notifications_adjusted"] += 1
                    
                    # 随机模拟事件检测
                    if notification_count % 4 == 0:
                        self.monitoring_data["events_detected"] += 1
                
                # 每10秒显示一次进度
                if int(time.time()) % 10 == 0:
                    elapsed = time.time() - start_time
                    remaining = max(0, end_time - time.time())
                    
                    print(f"   已发送 {notification_count} 条通知 - "
                          f"已运行 {elapsed/60:.1f} 分钟 - "
                          f"剩余 {remaining/60:.1f} 分钟")
                
                # 随机延迟模拟真实负载
                await asyncio.sleep(2 + (time.time() % 3))
                
            except Exception as e:
                self.monitoring_data["errors_occurred"] += 1
                print(f"❌ 通知发送错误: {e}")
                await asyncio.sleep(1)
        
        print(f"\n✅ 模拟工作负载完成，共发送 {notification_count} 条通知")
    
    def export_monitoring_data(self, filename: str = "monitoring_report.json"):
        """导出监控数据"""
        report = {
            "export_time": datetime.now().isoformat(),
            "monitoring_duration": "实时监控数据",
            "summary": {
                "notifications_sent": self.monitoring_data["notifications_sent"],
                "notifications_adjusted": self.monitoring_data["notifications_adjusted"],
                "events_detected": self.monitoring_data["events_detected"],
                "errors_occurred": self.monitoring_data["errors_occurred"]
            },
            "performance_metrics": self.monitoring_data["performance_metrics"],
            "user_feedback": self.monitoring_data["user_feedback"]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"📄 监控数据已导出到: {filename}")


async def main():
    """主函数"""
    monitor = RealTimeMonitor()
    
    try:
        # 启动监控
        monitor.start_monitoring()
        
        # 模拟工作负载
        await monitor.simulate_notification_workload(3)  # 模拟3分钟
        
        # 让监控继续运行一段时间
        print("\n🔍 监控继续运行中...")
        await asyncio.sleep(30)  # 继续监控30秒
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断监控")
    
    finally:
        # 停止监控
        monitor.stop_monitoring()
        
        # 导出数据
        monitor.export_monitoring_data()
        
        print("\n👋 监控工具已退出")


if __name__ == "__main__":
    print("🔍 启动智能通知系统实时监控工具...")
    asyncio.run(main())