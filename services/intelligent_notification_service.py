"""
智能通知决策服务
集成智能决策引擎到现有Agent系统，提供主动通知功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from services.intelligent_decision_engine import (
    IntelligentDecisionEngine, DecisionMode, DecisionResult
)
from services.context_aware_event_detector import (
    ContextAwareEventDetector, EventAnalysisService
)
from services.intelligent_message_generator import (
    IntelligentMessageGenerator, MessageType, ToneStyle
)

logger = logging.getLogger(__name__)


class IntelligentNotificationService:
    """智能通知决策服务"""
    
    def __init__(self, decision_mode: DecisionMode = DecisionMode.BALANCED):
        self.decision_mode = decision_mode
        
        # 初始化核心组件
        self.decision_engine = IntelligentDecisionEngine(decision_mode)
        self.event_detector = ContextAwareEventDetector()
        self.event_analyzer = EventAnalysisService()
        self.message_generator = IntelligentMessageGenerator()
        
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"智能通知服务已初始化，决策模式: {decision_mode.value}")
    
    async def should_send_notification(self, 
                                     user_id: int,
                                     notification_type: str,
                                     plan_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        判断是否应该发送通知
        
        Args:
            user_id: 用户ID
            notification_type: 通知类型
            plan_data: 计划数据
            
        Returns:
            bool: 是否发送通知
        """
        decision_result = await self.decision_engine.make_decision(
            user_id, notification_type, plan_data
        )
        
        return decision_result.send_notification
    
    async def generate_intelligent_notification(self,
                                              user_id: int,
                                              notification_type: str,
                                              plan_data: Optional[Dict[str, Any]] = None,
                                              user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        生成智能通知消息
        
        Args:
            user_id: 用户ID
            notification_type: 通知类型
            plan_data: 计划数据
            user_profile: 用户画像数据
            
        Returns:
            Dict[str, Any]: 通知消息和相关信息
        """
        self.logger.info(f"为用户 {user_id} 生成 {notification_type} 智能通知")
        
        try:
            # 1. 执行智能决策
            decision_result = await self.decision_engine.make_decision(
                user_id, notification_type, plan_data
            )
            
            if not decision_result.send_notification:
                return {
                    "send": False,
                    "reason": decision_result.reasoning,
                    "message": "",
                    "adjusted": False
                }
            
            # 2. 获取用户上下文分析
            context_analysis = await self.event_analyzer.analyze_user_context(user_id)
            
            # 3. 获取或生成用户画像
            if not user_profile:
                user_profile = await self._get_user_profile(user_id)
            
            # 4. 生成个性化消息
            message_type = (
                MessageType.ADJUSTED_REMINDER if decision_result.adjusted 
                else MessageType.STANDARD_REMINDER
            )
            
            event_info = None
            if decision_result.adjusted and decision_result.new_schedule:
                event_info = {
                    "type": decision_result.new_schedule.get("reason", "特殊事件"),
                    "suggested_times": decision_result.new_schedule.get("suggested_windows", [])
                }
            
            message = await self.message_generator.generate_complex_message(
                user_id=user_id,
                message_type=message_type,
                plan_type=notification_type,
                user_profile=user_profile,
                event_info=event_info
            )
            
            # 5. 构建通知结果
            notification_result = {
                "send": True,
                "message": message,
                "adjusted": decision_result.adjusted,
                "reasoning": decision_result.reasoning,
                "context_analysis": context_analysis,
                "user_profile": user_profile,
                "timing": decision_result.timing or datetime.now(),
                "new_schedule": decision_result.new_schedule
            }
            
            self.logger.info(f"智能通知生成完成: {notification_result}")
            return notification_result
            
        except Exception as e:
            self.logger.error(f"生成智能通知时发生错误: {e}", exc_info=True)
            
            # 错误时返回基础通知
            return {
                "send": True,
                "message": self._get_fallback_message(notification_type),
                "adjusted": False,
                "reasoning": f"决策错误，采用基础提醒: {str(e)}",
                "error": str(e)
            }
    
    async def analyze_user_notification_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        分析用户通知模式
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户通知模式分析结果
        """
        self.logger.info(f"分析用户 {user_id} 的通知模式")
        
        # 获取用户上下文
        context_analysis = await self.event_analyzer.analyze_user_context(user_id)
        
        # 获取用户画像
        user_profile = await self._get_user_profile(user_id)
        
        # 分析通知接受度模式
        notification_patterns = await self._analyze_notification_acceptance(user_id)
        
        return {
            "user_id": user_id,
            "context_analysis": context_analysis,
            "user_profile": user_profile,
            "notification_patterns": notification_patterns,
            "recommendations": await self._generate_notification_recommendations(
                user_id, context_analysis, user_profile, notification_patterns
            )
        }
    
    async def _get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """获取用户画像（模拟实现）"""
        # TODO: 集成实际的用户画像系统
        
        # 模拟用户画像数据
        profile_templates = [
            {
                "communication_style": "gentle",
                "stress_level": 0.3,
                "flexibility_preference": 0.8,
                "notification_preferences": {
                    "exercise": True,
                    "diet": True,
                    "weight": True,
                    "sleep": True
                }
            },
            {
                "communication_style": "professional", 
                "stress_level": 0.6,
                "flexibility_preference": 0.4,
                "notification_preferences": {
                    "exercise": True,
                    "diet": False,
                    "weight": True,
                    "sleep": True
                }
            },
            {
                "communication_style": "encouraging",
                "stress_level": 0.2,
                "flexibility_preference": 0.9,
                "notification_preferences": {
                    "exercise": True,
                    "diet": True,
                    "weight": True,
                    "sleep": False
                }
            }
        ]
        
        # 基于用户ID选择模板（模拟）
        template_index = user_id % len(profile_templates)
        profile = profile_templates[template_index].copy()
        profile["user_id"] = user_id
        
        return profile
    
    async def _analyze_notification_acceptance(self, user_id: int) -> Dict[str, Any]:
        """分析用户通知接受度模式（模拟实现）"""
        # TODO: 集成实际的通知历史数据分析
        
        return {
            "overall_acceptance_rate": 0.85,
            "preferred_notification_times": ["09:00", "19:00"],
            "most_accepted_types": ["exercise", "weight"],
            "least_accepted_types": ["diet"],
            "response_time_avg": 15.5,  # 分钟
            "adjustment_acceptance_rate": 0.92
        }
    
    async def _generate_notification_recommendations(self,
                                                    user_id: int,
                                                    context_analysis: Dict[str, Any],
                                                    user_profile: Dict[str, Any],
                                                    notification_patterns: Dict[str, Any]) -> List[str]:
        """生成通知建议"""
        recommendations = []
        
        # 基于上下文分析的建议
        high_impact_events = context_analysis.get("high_impact_events", [])
        if high_impact_events:
            recommendations.append("检测到高影响事件，建议调整通知频率和内容")
        
        # 基于用户画像的建议
        stress_level = user_profile.get("stress_level", 0)
        if stress_level > 0.7:
            recommendations.append("用户压力水平较高，建议使用更温和的通知方式")
        
        flexibility = user_profile.get("flexibility_preference", 0.5)
        if flexibility > 0.8:
            recommendations.append("用户偏好灵活性，建议提供更多调整选项")
        
        # 基于通知模式的分析
        acceptance_rate = notification_patterns.get("overall_acceptance_rate", 0)
        if acceptance_rate < 0.7:
            recommendations.append("通知接受度较低，建议优化通知时机和内容")
        
        return recommendations
    
    def _get_fallback_message(self, notification_type: str) -> str:
        """获取降级消息"""
        fallback_messages = {
            "exercise": "记得完成运动计划！",
            "diet": "请记录饮食情况",
            "weight": "该记录体重了",
            "sleep": "记得记录睡眠"
        }
        return fallback_messages.get(notification_type, "提醒：请完成相关记录")
    
    async def send_active_notification(self,
                                     user_id: int,
                                     notification_type: str,
                                     plan_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        发送主动通知（集成到现有系统）
        
        Args:
            user_id: 用户ID
            notification_type: 通知类型
            plan_data: 计划数据
            
        Returns:
            Dict[str, Any]: 发送结果
        """
        self.logger.info(f"为用户 {user_id} 发送主动 {notification_type} 通知")
        
        try:
            # 生成智能通知
            notification = await self.generate_intelligent_notification(
                user_id, notification_type, plan_data
            )
            
            if not notification["send"]:
                return {
                    "success": False,
                    "sent": False,
                    "reason": notification["reason"],
                    "notification_data": notification
                }
            
            # TODO: 集成到现有的通知发送系统
            # 这里模拟发送过程
            send_result = await self._send_notification_to_user(user_id, notification)
            
            return {
                "success": True,
                "sent": True,
                "notification_data": notification,
                "send_result": send_result
            }
            
        except Exception as e:
            self.logger.error(f"发送主动通知时发生错误: {e}", exc_info=True)
            return {
                "success": False,
                "sent": False,
                "error": str(e)
            }
    
    async def _send_notification_to_user(self, 
                                       user_id: int,
                                       notification: Dict[str, Any]) -> Dict[str, Any]:
        """发送通知到用户（模拟实现）"""
        # TODO: 集成实际的通知发送系统
        
        # 模拟发送过程
        await asyncio.sleep(0.1)  # 模拟网络延迟
        
        return {
            "sent": True,
            "timestamp": datetime.now(),
            "message": notification["message"],
            "channel": "chat",  # 模拟通过聊天渠道发送
            "user_id": user_id
        }


# 全局服务实例
intelligent_notification_service = IntelligentNotificationService()


# 工具函数，用于集成到现有Agent系统
async def check_and_send_notification(user_id: int, 
                                    notification_type: str,
                                    plan_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    检查并发送通知（外部调用接口）
    
    Args:
        user_id: 用户ID
        notification_type: 通知类型
        plan_data: 计划数据
        
    Returns:
        Dict[str, Any]: 发送结果
    """
    return await intelligent_notification_service.send_active_notification(
        user_id, notification_type, plan_data
    )


async def analyze_user_notification_preferences(user_id: int) -> Dict[str, Any]:
    """
    分析用户通知偏好（外部调用接口）
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict[str, Any]: 分析结果
    """
    return await intelligent_notification_service.analyze_user_notification_patterns(user_id)


# 演示和测试函数
async def demo_intelligent_notification():
    """演示智能通知功能"""
    print("🧠 演示智能通知决策系统")
    
    service = IntelligentNotificationService()
    
    # 测试1: 标准运动提醒
    print("\n📋 测试1: 标准运动提醒")
    result1 = await service.send_active_notification(
        user_id=1,
        notification_type="exercise",
        plan_data={"scheduled_time": "19:00"}
    )
    print(f"结果: {result1}")
    
    # 测试2: 有冲突事件的提醒
    print("\n📋 测试2: 有冲突事件的提醒")
    result2 = await service.send_active_notification(
        user_id=2,
        notification_type="exercise",
        plan_data={"scheduled_time": "19:00"}
    )
    print(f"结果: {result2}")
    
    # 测试3: 用户偏好分析
    print("\n📋 测试3: 用户偏好分析")
    analysis = await service.analyze_user_notification_patterns(user_id=1)
    print(f"分析结果: {analysis}")


if __name__ == "__main__":
    asyncio.run(demo_intelligent_notification())