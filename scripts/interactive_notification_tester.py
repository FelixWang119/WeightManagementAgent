#!/usr/bin/env python3
"""
智能通知决策系统 - 交互式测试控制台
通过交互式界面测试各种场景下的主动提醒功能
"""

import asyncio
import sys
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入智能通知服务
sys.path.append('..')
from services.intelligent_notification_service import (
    intelligent_notification_service,
    check_and_send_notification,
    analyze_user_notification_preferences
)
from services.context_aware_event_detector import ContextAwareEventDetector
from services.intelligent_decision_engine import DecisionMode


class InteractiveNotificationTester:
    """交互式测试控制台"""
    
    def __init__(self):
        self.service = intelligent_notification_service
        self.event_detector = ContextAwareEventDetector()
        
        # 测试用户配置
        self.test_users = [
            {"id": 1, "name": "灵活型用户", "stress": 0.3, "flexibility": 0.8},
            {"id": 2, "name": "压力型用户", "stress": 0.7, "flexibility": 0.4},
            {"id": 3, "name": "严谨型用户", "stress": 0.5, "flexibility": 0.6}
        ]
        
        self.test_scenarios = [
            {"id": 1, "name": "标准运动提醒", "conversation": "", "plan": {"scheduled_time": "19:00"}},
            {"id": 2, "name": "应酬冲突", "conversation": "今晚有应酬，可能没时间运动了", "plan": {"scheduled_time": "19:00"}},
            {"id": 3, "name": "生病事件", "conversation": "感冒了不舒服，想休息", "plan": {"scheduled_time": "19:00"}},
            {"id": 4, "name": "旅行事件", "conversation": "明天出差三天，运动计划怎么安排", "plan": {"scheduled_time": "19:00"}},
            {"id": 5, "name": "压力事件", "conversation": "最近工作压力大，运动有点坚持不下去", "plan": {"scheduled_time": "19:00"}}
        ]
    
    def print_header(self):
        """打印标题"""
        print("=" * 70)
        print("🧠 智能通知决策系统 - 交互式测试控制台")
        print("=" * 70)
        print()
    
    def print_menu(self):
        """打印主菜单"""
        print("📋 测试选项:")
        print("1. 🔍 测试事件检测功能")
        print("2. 🧠 测试决策引擎")
        print("3. 💬 测试话术生成")
        print("4. 🚀 测试完整通知流程")
        print("5. 📊 测试用户偏好分析")
        print("6. 🎭 运行预设测试场景")
        print("7. ⚙️ 配置测试参数")
        print("0. ❌ 退出测试")
        print()
    
    async def test_event_detection(self):
        """测试事件检测功能"""
        print("\n🔍 事件检测测试")
        print("-" * 40)
        
        while True:
            print("\n请输入对话文本（输入 'quit' 返回主菜单）:")
            text = input("> ").strip()
            
            if text.lower() == 'quit':
                break
                
            if not text:
                print("请输入有效的对话文本")
                continue
            
            print(f"\n📝 分析文本: '{text}'")
            
            try:
                events = await self.event_detector.detect_events_from_conversation(text)
                
                if events:
                    print(f"✅ 检测到 {len(events)} 个事件:")
                    for i, event in enumerate(events, 1):
                        print(f"   {i}. 事件类型: {event.type}")
                        print(f"      置信度: {event.confidence:.2f}")
                        print(f"      影响等级: {event.impact_level}")
                        if event.time_info:
                            print(f"      时间信息: {event.time_info}")
                        print()
                else:
                    print("❌ 未检测到任何事件")
                    
            except Exception as e:
                print(f"❌ 事件检测出错: {e}")
    
    async def test_decision_engine(self, user_id=1, notification_type="exercise"):
        """测试决策引擎"""
        print(f"\n🧠 决策引擎测试 - 用户 {user_id}, 类型 {notification_type}")
        print("-" * 50)
        
        # 测试不同决策模式
        modes = [
            (DecisionMode.CONSERVATIVE, "保守模式"),
            (DecisionMode.BALANCED, "平衡模式"),
            (DecisionMode.INTELLIGENT, "智能模式")
        ]
        
        for mode, mode_name in modes:
            print(f"\n📊 测试 {mode_name}:")
            
            # 创建对应模式的引擎
            from services.intelligent_decision_engine import IntelligentDecisionEngine
            engine = IntelligentDecisionEngine(mode)
            
            # 测试决策
            result = await engine.make_decision(
                user_id=user_id,
                notification_type=notification_type,
                original_plan={"scheduled_time": "19:00"}
            )
            
            print(f"   ✅ 发送通知: {result.send_notification}")
            print(f"   🔄 是否调整: {result.adjusted}")
            print(f"   💭 推理原因: {result.reasoning}")
            
            if result.new_schedule:
                print(f"   📅 新计划: {result.new_schedule}")
    
    async def test_message_generation(self):
        """测试话术生成"""
        print("\n💬 话术生成测试")
        print("-" * 40)
        
        from services.intelligent_message_generator import (
            IntelligentMessageGenerator, MessageType, ToneStyle
        )
        
        generator = IntelligentMessageGenerator()
        
        # 测试不同消息类型
        message_types = [
            (MessageType.STANDARD_REMINDER, "标准提醒"),
            (MessageType.ADJUSTED_REMINDER, "调整提醒"),
            (MessageType.ENCOURAGEMENT, "鼓励消息"),
            (MessageType.CELEBRATION, "庆祝消息")
        ]
        
        tone_styles = [
            (ToneStyle.GENTLE, "温和"),
            (ToneStyle.PROFESSIONAL, "专业"),
            (ToneStyle.ENCOURAGING, "鼓励"),
            (ToneStyle.DIRECT, "直接"),
            (ToneStyle.PLAYFUL, "活泼")
        ]
        
        for msg_type, msg_name in message_types:
            print(f"\n📨 {msg_name}:")
            
            for tone_style, tone_name in tone_styles:
                message = await generator.generate_message(
                    message_type=msg_type,
                    tone_style=tone_style,
                    plan_type="exercise"
                )
                
                print(f"   🎭 {tone_name}语气: {message}")
    
    async def test_full_notification_flow(self, user_id=1, scenario_id=1):
        """测试完整通知流程"""
        print(f"\n🚀 完整通知流程测试 - 用户 {user_id}")
        print("-" * 50)
        
        # 获取测试场景
        scenario = next((s for s in self.test_scenarios if s["id"] == scenario_id), None)
        if not scenario:
            print("❌ 无效的场景ID")
            return
        
        print(f"📋 测试场景: {scenario['name']}")
        if scenario['conversation']:
            print(f"💬 对话内容: {scenario['conversation']}")
        
        # 执行完整通知流程
        result = await self.service.send_active_notification(
            user_id=user_id,
            notification_type="exercise",
            plan_data=scenario['plan']
        )
        
        print(f"\n📊 测试结果:")
        print(f"   ✅ 成功: {result.get('success', False)}")
        print(f"   📤 已发送: {result.get('sent', False)}")
        
        if 'notification_data' in result:
            nd = result['notification_data']
            print(f"   💬 消息内容: {nd.get('message', 'N/A')}")
            print(f"   🔄 是否调整: {nd.get('adjusted', False)}")
            print(f"   💭 推理原因: {nd.get('reasoning', 'N/A')}")
        
        if 'error' in result:
            print(f"   ❌ 错误信息: {result['error']}")
    
    async def test_user_preference_analysis(self, user_id=1):
        """测试用户偏好分析"""
        print(f"\n📊 用户偏好分析测试 - 用户 {user_id}")
        print("-" * 50)
        
        analysis = await self.service.analyze_user_notification_patterns(user_id)
        
        print("👤 用户画像:")
        profile = analysis.get('user_profile', {})
        print(f"   沟通风格: {profile.get('communication_style', 'N/A')}")
        print(f"   压力水平: {profile.get('stress_level', 0):.1f}")
        print(f"   灵活性偏好: {profile.get('flexibility_preference', 0):.1f}")
        
        print("\n📈 通知模式分析:")
        patterns = analysis.get('notification_patterns', {})
        print(f"   总体接受率: {patterns.get('overall_acceptance_rate', 0):.1%}")
        print(f"   偏好通知时间: {patterns.get('preferred_notification_times', [])}")
        
        print("\n💡 推荐建议:")
        recommendations = analysis.get('recommendations', [])
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    async def run_preset_scenarios(self):
        """运行预设测试场景"""
        print("\n🎭 预设测试场景")
        print("-" * 40)
        
        for scenario in self.test_scenarios:
            print(f"\n📋 场景 {scenario['id']}: {scenario['name']}")
            
            # 为每个场景测试不同的用户
            for user in self.test_users[:2]:  # 只测试前两个用户避免太多输出
                print(f"\n👤 测试用户: {user['name']} (ID: {user['id']})")
                
                await self.test_full_notification_flow(user['id'], scenario['id'])
                
                # 添加一点延迟避免输出太快
                await asyncio.sleep(0.5)
    
    def configure_test_parameters(self):
        """配置测试参数"""
        print("\n⚙️ 配置测试参数")
        print("-" * 40)
        
        print("当前配置:")
        print(f"   测试用户数量: {len(self.test_users)}")
        print(f"   测试场景数量: {len(self.test_scenarios)}")
        print(f"   决策模式: {self.service.decision_mode.value}")
        
        print("\n配置选项:")
        print("1. 添加测试用户")
        print("2. 添加测试场景")
        print("3. 修改决策模式")
        print("4. 返回主菜单")
        
        choice = input("请选择 (1-4): ").strip()
        
        if choice == '1':
            self._add_test_user()
        elif choice == '2':
            self._add_test_scenario()
        elif choice == '3':
            self._change_decision_mode()
    
    def _add_test_user(self):
        """添加测试用户"""
        print("\n👤 添加测试用户")
        name = input("用户名称: ").strip()
        stress = float(input("压力水平 (0-1): ").strip())
        flexibility = float(input("灵活性偏好 (0-1): ").strip())
        
        new_user = {
            "id": len(self.test_users) + 1,
            "name": name,
            "stress": stress,
            "flexibility": flexibility
        }
        
        self.test_users.append(new_user)
        print(f"✅ 已添加用户: {name}")
    
    def _add_test_scenario(self):
        """添加测试场景"""
        print("\n📋 添加测试场景")
        name = input("场景名称: ").strip()
        conversation = input("对话内容: ").strip()
        
        new_scenario = {
            "id": len(self.test_scenarios) + 1,
            "name": name,
            "conversation": conversation,
            "plan": {"scheduled_time": "19:00"}
        }
        
        self.test_scenarios.append(new_scenario)
        print(f"✅ 已添加场景: {name}")
    
    def _change_decision_mode(self):
        """修改决策模式"""
        print("\n🧠 修改决策模式")
        print("1. 保守模式 (80%规则+20%AI)")
        print("2. 平衡模式 (50%规则+50%AI)")
        print("3. 智能模式 (20%规则+80%AI)")
        
        choice = input("请选择模式 (1-3): ").strip()
        
        if choice == '1':
            self.service.decision_mode = DecisionMode.CONSERVATIVE
            print("✅ 已切换到保守模式")
        elif choice == '2':
            self.service.decision_mode = DecisionMode.BALANCED
            print("✅ 已切换到平衡模式")
        elif choice == '3':
            self.service.decision_mode = DecisionMode.INTELLIGENT
            print("✅ 已切换到智能模式")
        else:
            print("❌ 无效选择")
    
    async def run(self):
        """运行交互式测试控制台"""
        self.print_header()
        
        while True:
            self.print_menu()
            
            choice = input("请选择测试项目 (0-7): ").strip()
            
            if choice == '0':
                print("\n👋 感谢使用智能通知测试控制台！")
                break
            elif choice == '1':
                await self.test_event_detection()
            elif choice == '2':
                await self.test_decision_engine()
            elif choice == '3':
                await self.test_message_generation()
            elif choice == '4':
                await self.test_full_notification_flow()
            elif choice == '5':
                await self.test_user_preference_analysis()
            elif choice == '6':
                await self.run_preset_scenarios()
            elif choice == '7':
                self.configure_test_parameters()
            else:
                print("❌ 无效选择，请重新输入")


async def main():
    """主函数"""
    tester = InteractiveNotificationTester()
    await tester.run()


if __name__ == "__main__":
    print("🚀 启动智能通知交互式测试控制台...")
    asyncio.run(main())