"""
智能通知决策引擎
采用混合智能模式，结合固定规则和AI决策
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from config.logging_config import get_module_logger
from services.configurable_event_detector import ConfigurableEventDetector, DetectedEvent

logger = get_module_logger()


class DecisionMode(Enum):
    """决策模式枚举"""
    CONSERVATIVE = "conservative"  # 保守模式：80%规则 + 20%AI
    BALANCED = "balanced"         # 平衡模式：50%规则 + 50%AI  
    INTELLIGENT = "intelligent"   # 智能模式：20%规则 + 80%AI

    @property
    def weights(self):
        """获取决策模式权重"""
        weight_map = {
            "conservative": {"rule_based": 0.8, "ai_decision": 0.2},
            "balanced": {"rule_based": 0.5, "ai_decision": 0.5},
            "intelligent": {"rule_based": 0.2, "ai_decision": 0.8}
        }
        return weight_map.get(self.value, weight_map["balanced"])


class EventType(Enum):
    """事件类型枚举"""
    BUSINESS_DINNER = "business_dinner"  # 商务应酬
    ILLNESS = "illness"                  # 身体不适
    TRAVEL = "travel"                    # 旅行出差
    OVERTIME = "overtime"                # 加班工作
    FAMILY_EVENT = "family_event"        # 家庭事务
    SPECIAL_OCCASION = "special_occasion"  # 特殊场合


class CommunicationStyle(Enum):
    """沟通风格枚举"""
    GENTLE = "gentle"        # 温和型
    PROFESSIONAL = "professional"  # 专业型
    ENCOURAGING = "encouraging"    # 鼓励型
    DIRECT = "direct"              # 直接型


@dataclass
class Event:
    """事件数据类"""
    type: EventType
    description: str
    start_time: datetime
    end_time: datetime
    confidence: float  # 识别置信度 0-1
    source: str  # 事件来源：conversation, profile, system


@dataclass
class DecisionResult:
    """决策结果数据类"""
    send_notification: bool
    adjusted: bool  # 是否调整了原计划
    message: str
    reasoning: str
    new_schedule: Optional[Dict[str, Any]] = None
    timing: Optional[datetime] = None


@dataclass
class UserProfile:
    """用户画像数据类"""
    user_id: int
    communication_style: CommunicationStyle
    notification_preferences: Dict[str, bool]  # 各类通知偏好
    habit_patterns: Dict[str, Any]  # 行为习惯模式
    stress_level: float  # 压力水平 0-1
    flexibility_preference: float  # 灵活性偏好 0-1


class IntelligentDecisionEngine:
    """智能决策引擎核心类"""
    
    def __init__(self, decision_mode: DecisionMode = DecisionMode.BALANCED):
        self.decision_mode = decision_mode
        self.mode_weights = self._get_mode_weights(decision_mode)
        self.logger = get_module_logger()
        self.event_detector = ConfigurableEventDetector()
        
    def _get_mode_weights(self, mode: DecisionMode) -> Dict[str, float]:
        """获取决策模式权重"""
        return mode.weights
    
    async def make_decision(self, 
                          user_id: int, 
                          notification_type: str,
                          original_plan: Optional[Dict[str, Any]] = None) -> DecisionResult:
        """
        执行智能决策
        
        Args:
            user_id: 用户ID
            notification_type: 通知类型
            original_plan: 原始计划数据
            
        Returns:
            DecisionResult: 决策结果
        """
        self.logger.info(f"开始为用户 {user_id} 进行 {notification_type} 通知决策")
        
        try:
            # 1. 获取用户画像
            user_profile = await self._get_user_profile(user_id)
            
            # 2. 执行固定规则检查
            rule_based_result = await self._rule_based_check(user_id, notification_type)
            
            if not rule_based_result.send_notification:
                return DecisionResult(
                    send_notification=False,
                    adjusted=False,
                    message="",
                    reasoning=rule_based_result.reasoning
                )
            
            # 3. 执行AI决策分析
            ai_decision_result = await self._ai_decision_analysis(
                user_id, notification_type, user_profile, original_plan
            )
            
            # 4. 综合决策
            final_decision = await self._combine_decisions(
                rule_based_result, ai_decision_result, user_profile
            )
            
            self.logger.info(f"用户 {user_id} 的 {notification_type} 通知决策完成: {final_decision}")
            return final_decision
            
        except Exception as e:
            self.logger.error(f"决策过程中发生错误: {e}", exc_info=True)
            # 错误时采用保守策略：发送基础提醒
            return DecisionResult(
                send_notification=True,
                adjusted=False,
                message=self._get_fallback_message(notification_type),
                reasoning=f"决策错误，采用保守策略: {str(e)}"
            )
    
    async def _get_user_profile(self, user_id: int) -> UserProfile:
        """获取用户画像（模拟实现）"""
        # TODO: 集成实际的用户画像系统
        return UserProfile(
            user_id=user_id,
            communication_style=CommunicationStyle.GENTLE,
            notification_preferences={
                "exercise": True,
                "diet": True,
                "weight": True,
                "sleep": True
            },
            habit_patterns={
                "preferred_exercise_times": ["morning", "evening"],
                "flexibility": 0.7
            },
            stress_level=0.3,
            flexibility_preference=0.8
        )
    
    async def _rule_based_check(self, user_id: int, notification_type: str) -> DecisionResult:
        """固定规则检查"""
        # 基础条件检查（模拟实现）
        basic_conditions = {
            "exercise": await self._check_exercise_conditions(user_id),
            "diet": await self._check_diet_conditions(user_id),
            "weight": await self._check_weight_conditions(user_id),
            "sleep": await self._check_sleep_conditions(user_id)
        }
        
        condition_met = basic_conditions.get(notification_type, False)
        
        return DecisionResult(
            send_notification=condition_met,
            adjusted=False,
            message="",
            reasoning="基础规则检查完成" if condition_met else "基础条件不满足"
        )
    
    async def _ai_decision_analysis(self, 
                                  user_id: int, 
                                  notification_type: str,
                                  user_profile: UserProfile,
                                  original_plan: Optional[Dict[str, Any]]) -> DecisionResult:
        """AI决策分析"""
        
        # 1. 上下文事件识别
        events = await self._detect_context_events(user_id)
        
        # 2. 分析事件影响
        conflicting_events = await self._analyze_event_conflicts(events, notification_type, original_plan)
        
        # 3. 智能决策
        if conflicting_events:
            # 有冲突事件，需要调整
            return await self._make_adjustment_decision(
                user_id, notification_type, user_profile, conflicting_events, original_plan
            )
        else:
            # 无冲突事件，标准提醒
            return await self._make_standard_decision(user_id, notification_type, user_profile)
    
    async def _detect_context_events(self, user_id: int) -> List[Event]:
        """检测上下文事件 - 使用可配置事件识别器"""
        events = []
        
        # 获取用户最近的对话内容
        recent_conversations = await self._get_recent_conversations(user_id)
        
        for conv in recent_conversations:
            # 使用可配置事件识别器检测事件
            detected_events = await self.event_detector.detect_events(
                conv["content"], 
                timestamp=conv["timestamp"]
            )
            
            # 将DetectedEvent转换为Event
            for detected_event in detected_events:
                events.append(Event(
                    type=EventType(detected_event.type),
                    description=detected_event.description,
                    start_time=detected_event.start_time or datetime.now(),
                    end_time=detected_event.end_time or datetime.now() + timedelta(hours=4),
                    confidence=detected_event.confidence,
                    source="conversation"
                ))
        
        return events
    
    async def _get_recent_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        """获取近期对话（模拟实现）"""
        # TODO: 集成实际的对话记忆系统
        return [
            {
                "content": "今晚有个重要应酬，可能没时间运动了",
                "timestamp": datetime.now() - timedelta(hours=2)
            },
            {
                "content": "明天要出差去北京，大概三天",
                "timestamp": datetime.now() - timedelta(hours=6)
            },
            {
                "content": "今天感觉不太舒服，可能感冒了",
                "timestamp": datetime.now() - timedelta(hours=12)
            }
        ]
    
    async def _analyze_event_conflicts(self, 
                                     events: List[Event], 
                                     notification_type: str,
                                     original_plan: Optional[Dict[str, Any]]) -> List[Event]:
        """分析事件冲突 - 使用可配置事件识别器的冲突检测"""
        conflicting_events = []
        
        # 获取计划时间
        planned_time = None
        if original_plan and "scheduled_time" in original_plan:
            try:
                # 简化时间解析，实际应该更复杂
                planned_time = datetime.now()
            except:
                pass
        
        # 使用可配置事件识别器的冲突检测
        for event in events:
            if await self._is_event_conflicting(event, notification_type, planned_time):
                conflicting_events.append(event)
        
        return conflicting_events
    
    async def _is_event_conflicting(self, 
                                  event: Event, 
                                  notification_type: str,
                                  planned_time: Optional[datetime]) -> bool:
        """判断事件是否冲突 - 使用可配置冲突规则"""
        # 使用可配置事件识别器的冲突检测
        try:
            # 模拟用户ID（实际应该使用真实的用户ID）
            user_id = 1
            
            # 调用可配置事件识别器的冲突检测
            conflicting_events = await self.event_detector.get_conflicting_events(
                user_id, notification_type, planned_time
            )
            
            # 检查当前事件是否在冲突列表中
            for conflicting_event in conflicting_events:
                if conflicting_event.type == event.type.value:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"冲突检测失败，使用默认规则: {e}")
            # 降级到默认规则
            conflict_rules = {
                EventType.BUSINESS_DINNER: ["exercise", "diet"],
                EventType.ILLNESS: ["exercise", "weight"],
                EventType.TRAVEL: ["exercise", "diet", "sleep"],
                EventType.OVERTIME: ["exercise", "sleep"],
                EventType.FAMILY_EVENT: ["exercise"],
                EventType.SPECIAL_OCCASION: ["diet"]
            }
            
            conflicting_types = conflict_rules.get(event.type, [])
            return notification_type in conflicting_types
    
    async def _make_adjustment_decision(self, 
                                       user_id: int,
                                       notification_type: str,
                                       user_profile: UserProfile,
                                       conflicting_events: List[Event],
                                       original_plan: Optional[Dict[str, Any]]) -> DecisionResult:
        """做出调整决策"""
        
        # 生成调整后的计划
        new_schedule = await self._suggest_reschedule(user_id, notification_type, conflicting_events)
        
        # 生成个性化消息
        message = await self._generate_adjusted_message(user_id, notification_type, conflicting_events, user_profile)
        
        return DecisionResult(
            send_notification=True,
            adjusted=True,
            message=message,
            reasoning=f"检测到{len(conflicting_events)}个冲突事件，已调整计划",
            new_schedule=new_schedule
        )
    
    async def _make_standard_decision(self, 
                                     user_id: int,
                                     notification_type: str,
                                     user_profile: UserProfile) -> DecisionResult:
        """做出标准决策"""
        
        message = await self._generate_standard_message(user_id, notification_type, user_profile)
        
        return DecisionResult(
            send_notification=True,
            adjusted=False,
            message=message,
            reasoning="无冲突事件，采用标准提醒"
        )
    
    async def _suggest_reschedule(self, 
                                 user_id: int,
                                 notification_type: str,
                                 conflicting_events: List[Event]) -> Dict[str, Any]:
        """建议重新安排计划"""
        
        # 分析事件影响时长
        max_duration = max([
            (event.end_time - event.start_time).total_seconds() 
            for event in conflicting_events
        ], default=0)
        
        # 基于用户习惯推荐时间窗口
        preferred_times = await self._get_user_preferred_times(user_id, notification_type)
        
        return {
            "original_plan": notification_type,
            "suggested_windows": preferred_times,
            "reason": f"因{conflicting_events[0].type.value}事件调整",
            "flexibility_required": True
        }
    
    async def _get_user_preferred_times(self, user_id: int, notification_type: str) -> List[str]:
        """获取用户偏好时间（模拟实现）"""
        time_preferences = {
            "exercise": ["早上 7:00-9:00", "晚上 18:00-20:00"],
            "diet": ["早餐时间", "午餐时间", "晚餐时间"],
            "weight": ["早上起床后", "晚上睡前"],
            "sleep": ["晚上 22:00-23:00"]
        }
        
        return time_preferences.get(notification_type, ["合适的时间"])
    
    async def _generate_adjusted_message(self, 
                                       user_id: int,
                                       notification_type: str,
                                       conflicting_events: List[Event],
                                       user_profile: UserProfile) -> str:
        """生成调整后的消息"""
        
        event = conflicting_events[0]
        
        # 基于用户沟通风格选择模板
        templates = {
            CommunicationStyle.GENTLE: {
                "business_dinner": "了解到您今晚有应酬，{plan}计划可以调整到{suggested_times}哦！重要的是保持连续性，偶尔调整没关系的~",
                "illness": "听说您身体不适，先好好休息，{plan}计划可以等康复后再安排~",
                "travel": "旅途辛苦了，{plan}计划可以等您安顿好再继续！"
            },
            CommunicationStyle.PROFESSIONAL: {
                "business_dinner": "检测到商务应酬安排，建议将{plan}计划调整至{suggested_times}。",
                "illness": "健康优先，建议暂停{plan}计划直至康复。",
                "travel": "旅行期间，{plan}计划可暂缓执行。"
            }
        }
        
        style_templates = templates.get(user_profile.communication_style, templates[CommunicationStyle.GENTLE])
        template = style_templates.get(event.type.value, "{plan}计划因{event}需要调整。")
        
        # 替换模板变量
        plan_names = {
            "exercise": "运动",
            "diet": "饮食记录", 
            "weight": "体重记录",
            "sleep": "睡眠记录"
        }
        
        event_names = {
            "business_dinner": "应酬",
            "illness": "身体不适",
            "travel": "旅行"
        }
        
        suggested_times = await self._get_user_preferred_times(user_id, notification_type)
        
        return template.format(
            plan=plan_names.get(notification_type, "计划"),
            event=event_names.get(event.type.value, "特殊事件"),
            suggested_times="、".join(suggested_times[:2])
        )
    
    async def _generate_standard_message(self, 
                                       user_id: int,
                                       notification_type: str,
                                       user_profile: UserProfile) -> str:
        """生成标准提醒消息"""
        
        standard_messages = {
            "exercise": "记得完成今天的运动计划哦！",
            "diet": "别忘了记录今天的饮食情况~",
            "weight": "该记录今天的体重了！",
            "sleep": "记得记录睡眠时间，好好休息~"
        }
        
        base_message = standard_messages.get(notification_type, "记得完成今天的计划哦！")
        
        # 基于用户风格添加个性化后缀
        style_suffixes = {
            CommunicationStyle.GENTLE: "加油！",
            CommunicationStyle.PROFESSIONAL: "请按时完成。",
            CommunicationStyle.ENCOURAGING: "你可以的！",
            CommunicationStyle.DIRECT: "请尽快完成。"
        }
        
        suffix = style_suffixes.get(user_profile.communication_style, "")
        
        return f"{base_message} {suffix}".strip()
    
    async def _combine_decisions(self, 
                               rule_result: DecisionResult,
                               ai_result: DecisionResult,
                               user_profile: UserProfile) -> DecisionResult:
        """综合决策结果"""
        
        # 基于权重进行综合决策
        rule_weight = self.mode_weights["rule_based"]
        ai_weight = self.mode_weights["ai_decision"]
        
        # 如果规则检查不通过，直接返回
        if not rule_result.send_notification:
            return rule_result
        
        # 综合AI决策结果
        if ai_result.adjusted:
            # AI建议调整，采用AI决策
            return ai_result
        else:
            # 无调整，采用标准提醒
            return ai_result
    
    def _get_fallback_message(self, notification_type: str) -> str:
        """获取降级消息"""
        fallback_messages = {
            "exercise": "记得完成运动计划！",
            "diet": "请记录饮食情况",
            "weight": "该记录体重了",
            "sleep": "记得记录睡眠"
        }
        return fallback_messages.get(notification_type, "提醒：请完成相关记录")
    
    # 基础条件检查方法（模拟实现）
    async def _check_exercise_conditions(self, user_id: int) -> bool:
        """检查运动条件"""
        # TODO: 集成实际的数据检查逻辑
        return True
    
    async def _check_diet_conditions(self, user_id: int) -> bool:
        """检查饮食条件"""
        return True
    
    async def _check_weight_conditions(self, user_id: int) -> bool:
        """检查体重条件"""
        return True
    
    async def _check_sleep_conditions(self, user_id: int) -> bool:
        """检查睡眠条件"""
        return True


# 使用示例
async def demo():
    """演示使用方法"""
    engine = IntelligentDecisionEngine(DecisionMode.BALANCED)
    
    # 模拟用户决策
    result = await engine.make_decision(
        user_id=1,
        notification_type="exercise",
        original_plan={"type": "exercise", "scheduled_time": "19:00"}
    )
    
    print(f"决策结果: {result}")


if __name__ == "__main__":
    asyncio.run(demo())