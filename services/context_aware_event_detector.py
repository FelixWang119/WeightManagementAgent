"""
上下文感知事件识别系统
集成现有的对话记忆系统，识别用户提及的特殊事件
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class EventCategory(Enum):
    """事件分类枚举"""
    WORK_RELATED = "work_related"      # 工作相关
    HEALTH_RELATED = "health_related"   # 健康相关
    PERSONAL = "personal"              # 个人事务
    SOCIAL = "social"                   # 社交活动
    SPECIAL = "special"                 # 特殊场合


@dataclass
class DetectedEvent:
    """检测到的事件"""
    id: str
    type: str
    category: EventCategory
    description: str
    confidence: float  # 置信度 0-1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: str = "conversation"  # 事件来源
    keywords: List[str] = None
    impact_level: int = 1  # 影响等级 1-5
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class ContextAwareEventDetector:
    """上下文感知事件识别器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.event_patterns = self._initialize_event_patterns()
        self.time_patterns = self._initialize_time_patterns()
    
    def _initialize_event_patterns(self) -> Dict[str, Dict[str, Any]]:
        """初始化事件识别模式"""
        return {
            # 工作相关事件
            "business_dinner": {
                "category": EventCategory.WORK_RELATED,
                "keywords": ["应酬", "饭局", "商务餐", "客户吃饭", "陪客户"],
                "patterns": [
                    r"(今晚|明天|今天).*?(有|要|需要).*?(应酬|饭局|商务餐)",
                    r"(陪|和).*?(客户|老板).*?(吃饭|聚餐)"
                ],
                "impact_level": 3
            },
            "overtime": {
                "category": EventCategory.WORK_RELATED,
                "keywords": ["加班", "晚点下班", "工作到很晚", "赶工"],
                "patterns": [
                    r"(今天|今晚).*?(要|需要).*?(加班|晚点下班)",
                    r"工作.*?(到很晚|到深夜)"
                ],
                "impact_level": 2
            },
            "meeting": {
                "category": EventCategory.WORK_RELATED,
                "keywords": ["开会", "会议", "讨论会", "培训"],
                "patterns": [
                    r"(下午|上午).*?(有|要).*?(会议|开会)",
                    r"参加.*?(培训|讨论)"
                ],
                "impact_level": 2
            },
            
            # 健康相关事件
            "illness": {
                "category": EventCategory.HEALTH_RELATED,
                "keywords": ["不舒服", "生病", "感冒", "发烧", "头疼"],
                "patterns": [
                    r"(身体|感觉).*?(不舒服|难受)",
                    r"(感冒|发烧|头疼).*?(了|中)"
                ],
                "impact_level": 4
            },
            "medical_appointment": {
                "category": EventCategory.HEALTH_RELATED,
                "keywords": ["看医生", "医院", "体检", "复诊"],
                "patterns": [
                    r"(明天|今天).*?(要|去).*?(医院|看医生)",
                    r"(体检|复诊).*?(安排|时间)"
                ],
                "impact_level": 3
            },
            
            # 个人事务
            "travel": {
                "category": EventCategory.PERSONAL,
                "keywords": ["旅行", "出差", "外出", "去外地"],
                "patterns": [
                    r"(明天|后天).*?(要|去).*?(旅行|出差)",
                    r"外出.*?(几天|一段时间)"
                ],
                "impact_level": 4
            },
            "family_event": {
                "category": EventCategory.PERSONAL,
                "keywords": ["家庭", "家人", "孩子", "父母"],
                "patterns": [
                    r"(家庭|家人).*?(有事|聚会)",
                    r"(陪|照顾).*?(孩子|父母)"
                ],
                "impact_level": 3
            },
            
            # 社交活动
            "social_gathering": {
                "category": EventCategory.SOCIAL,
                "keywords": ["聚会", "聚餐", "朋友", "同学"],
                "patterns": [
                    r"(晚上|周末).*?(有|要).*?(聚会|聚餐)",
                    r"(和|跟).*?(朋友|同学).*?(吃饭|见面)"
                ],
                "impact_level": 2
            },
            
            # 特殊场合
            "special_occasion": {
                "category": EventCategory.SPECIAL,
                "keywords": ["生日", "节日", "纪念日", "庆祝"],
                "patterns": [
                    r"(今天|明天).*?(是|过).*?(生日|节日)",
                    r"庆祝.*?(纪念日|节日)"
                ],
                "impact_level": 2
            }
        }
    
    def _initialize_time_patterns(self) -> Dict[str, str]:
        """初始化时间模式"""
        return {
            "today": r"(今天|今日)",
            "tonight": r"(今晚|今天晚上|今夜)",
            "tomorrow": r"(明天|明日)",
            "morning": r"(早上|早晨|上午)",
            "afternoon": r"(下午|午后)",
            "evening": r"(晚上|傍晚|晚间)",
            "specific_time": r"(\d{1,2}[:：]\d{1,2})"
        }
    
    async def detect_events_from_conversation(self, 
                                            conversation_text: str,
                                            timestamp: datetime = None) -> List[DetectedEvent]:
        """
        从对话文本中检测事件
        
        Args:
            conversation_text: 对话文本
            timestamp: 对话时间戳
            
        Returns:
            List[DetectedEvent]: 检测到的事件列表
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.logger.info(f"开始分析对话文本: {conversation_text[:50]}...")
        
        detected_events = []
        
        # 预处理文本
        processed_text = self._preprocess_text(conversation_text)
        
        # 识别事件类型
        for event_type, pattern_config in self.event_patterns.items():
            events = self._detect_specific_event(
                processed_text, event_type, pattern_config, timestamp
            )
            detected_events.extend(events)
        
        # 去重和置信度排序
        detected_events = self._deduplicate_and_sort_events(detected_events)
        
        self.logger.info(f"检测到 {len(detected_events)} 个事件")
        return detected_events
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 转换为小写
        text = text.lower()
        
        # 去除标点符号（保留中文标点用于模式匹配）
        text = re.sub(r'[！？，。；：""\'\'（）【】《》]', ' ', text)
        
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _detect_specific_event(self, 
                             text: str, 
                             event_type: str,
                             pattern_config: Dict[str, Any],
                             timestamp: datetime) -> List[DetectedEvent]:
        """检测特定类型的事件"""
        events = []
        
        # 关键词匹配（基础检测）
        keyword_matches = self._match_keywords(text, pattern_config["keywords"])
        
        # 正则模式匹配（精确检测）
        pattern_matches = self._match_patterns(text, pattern_config["patterns"])
        
        # 计算置信度
        confidence = self._calculate_confidence(keyword_matches, pattern_matches)
        
        if confidence > 0.3:  # 置信度阈值
            # 提取时间信息
            time_info = self._extract_time_info(text, timestamp)
            
            event = DetectedEvent(
                id=f"{event_type}_{timestamp.strftime('%Y%m%d%H%M%S')}",
                type=event_type,
                category=pattern_config["category"],
                description=f"检测到{event_type}事件",
                confidence=confidence,
                start_time=time_info.get("start_time"),
                end_time=time_info.get("end_time"),
                keywords=pattern_config["keywords"],
                impact_level=pattern_config.get("impact_level", 1)
            )
            events.append(event)
        
        return events
    
    def _match_keywords(self, text: str, keywords: List[str]) -> int:
        """关键词匹配"""
        matches = 0
        for keyword in keywords:
            if keyword in text:
                matches += 1
        return matches
    
    def _match_patterns(self, text: str, patterns: List[str]) -> int:
        """正则模式匹配"""
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text):
                matches += 1
        return matches
    
    def _calculate_confidence(self, keyword_matches: int, pattern_matches: int) -> float:
        """计算置信度"""
        # 基础置信度计算
        base_confidence = min(keyword_matches * 0.2 + pattern_matches * 0.3, 1.0)
        
        # 如果既有关键词匹配又有模式匹配，提高置信度
        if keyword_matches > 0 and pattern_matches > 0:
            base_confidence = min(base_confidence + 0.2, 1.0)
        
        return base_confidence
    
    def _extract_time_info(self, text: str, base_time: datetime) -> Dict[str, datetime]:
        """提取时间信息"""
        time_info = {}
        
        # 检测时间关键词
        if re.search(self.time_patterns["today"], text):
            time_info["start_time"] = base_time.replace(hour=9, minute=0, second=0)
            time_info["end_time"] = base_time.replace(hour=22, minute=0, second=0)
        elif re.search(self.time_patterns["tonight"], text):
            time_info["start_time"] = base_time.replace(hour=18, minute=0, second=0)
            time_info["end_time"] = base_time.replace(hour=23, minute=0, second=0)
        elif re.search(self.time_patterns["tomorrow"], text):
            tomorrow = base_time + timedelta(days=1)
            time_info["start_time"] = tomorrow.replace(hour=9, minute=0, second=0)
            time_info["end_time"] = tomorrow.replace(hour=22, minute=0, second=0)
        
        # 检测具体时间
        specific_time_match = re.search(self.time_patterns["specific_time"], text)
        if specific_time_match:
            time_str = specific_time_match.group(1)
            # 简单的时间解析（实际应该更复杂）
            try:
                hour, minute = map(int, re.split(r'[:：]', time_str))
                if time_info.get("start_time"):
                    time_info["start_time"] = time_info["start_time"].replace(
                        hour=hour, minute=minute
                    )
            except:
                pass
        
        return time_info
    
    def _deduplicate_and_sort_events(self, events: List[DetectedEvent]) -> List[DetectedEvent]:
        """去重和排序事件"""
        if not events:
            return []
        
        # 按置信度排序
        events.sort(key=lambda x: x.confidence, reverse=True)
        
        # 简单去重（相同类型保留置信度最高的）
        unique_events = []
        seen_types = set()
        
        for event in events:
            if event.type not in seen_types:
                unique_events.append(event)
                seen_types.add(event.type)
        
        return unique_events
    
    async def analyze_conversation_history(self, 
                                         user_id: int,
                                         hours: int = 24) -> List[DetectedEvent]:
        """
        分析用户最近一段时间的对话历史
        
        Args:
            user_id: 用户ID
            hours: 分析的时间范围（小时）
            
        Returns:
            List[DetectedEvent]: 检测到的事件列表
        """
        self.logger.info(f"开始分析用户 {user_id} 最近 {hours} 小时的对话历史")
        
        # TODO: 集成实际的对话记忆系统
        # 这里模拟获取对话历史
        conversation_history = await self._get_recent_conversations(user_id, hours)
        
        all_events = []
        
        for conv in conversation_history:
            events = await self.detect_events_from_conversation(
                conv["content"], conv["timestamp"]
            )
            all_events.extend(events)
        
        # 全局去重和排序
        all_events = self._deduplicate_and_sort_events(all_events)
        
        self.logger.info(f"从对话历史中检测到 {len(all_events)} 个事件")
        return all_events
    
    async def _get_recent_conversations(self, user_id: int, hours: int) -> List[Dict[str, Any]]:
        """获取最近对话记录（模拟实现）"""
        # TODO: 集成实际的对话记忆系统
        # 这里返回模拟数据
        
        # 模拟一些典型的对话场景
        sample_conversations = [
            {
                "content": "今晚有个重要应酬，可能没时间运动了",
                "timestamp": datetime.now() - timedelta(hours=2)
            },
            {
                "content": "明天要出差去上海，大概三天",
                "timestamp": datetime.now() - timedelta(hours=6)
            },
            {
                "content": "今天感觉不太舒服，可能感冒了",
                "timestamp": datetime.now() - timedelta(hours=12)
            },
            {
                "content": "周末要和家人聚会，可能没时间记录饮食",
                "timestamp": datetime.now() - timedelta(hours=18)
            }
        ]
        
        # 过滤时间范围
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [conv for conv in sample_conversations if conv["timestamp"] > cutoff_time]
    
    async def get_conflicting_events(self, 
                                   user_id: int,
                                   plan_type: str,
                                   planned_time: datetime = None) -> List[DetectedEvent]:
        """
        获取与计划冲突的事件
        
        Args:
            user_id: 用户ID
            plan_type: 计划类型（exercise, diet, weight, sleep）
            planned_time: 计划时间
            
        Returns:
            List[DetectedEvent]: 冲突事件列表
        """
        # 获取最近的事件
        recent_events = await self.analyze_conversation_history(user_id, hours=24)
        
        # 定义冲突规则
        conflict_rules = {
            "exercise": [
                "business_dinner", "overtime", "meeting", 
                "illness", "travel", "family_event", "social_gathering"
            ],
            "diet": ["business_dinner", "travel", "social_gathering", "special_occasion"],
            "weight": ["travel", "illness"],
            "sleep": ["overtime", "travel", "social_gathering"]
        }
        
        conflicting_types = conflict_rules.get(plan_type, [])
        conflicting_events = [
            event for event in recent_events 
            if event.type in conflicting_types and event.confidence > 0.5
        ]
        
        # 如果提供了计划时间，进行时间冲突检查
        if planned_time and conflicting_events:
            conflicting_events = [
                event for event in conflicting_events
                if self._check_time_conflict(event, planned_time)
            ]
        
        return conflicting_events
    
    def _check_time_conflict(self, event: DetectedEvent, planned_time: datetime) -> bool:
        """检查时间冲突"""
        if not event.start_time or not event.end_time:
            # 如果没有具体时间信息，假设有冲突
            return True
        
        # 简单的时间冲突检查
        event_duration = (event.end_time - event.start_time).total_seconds()
        
        # 如果事件持续时间超过4小时，认为会影响计划
        if event_duration > 4 * 3600:
            return True
        
        # 检查计划时间是否在事件时间范围内
        if event.start_time <= planned_time <= event.end_time:
            return True
        
        # 检查计划时间前后2小时是否与事件有重叠
        plan_start = planned_time - timedelta(hours=2)
        plan_end = planned_time + timedelta(hours=2)
        
        return not (event.end_time < plan_start or event.start_time > plan_end)


class EventAnalysisService:
    """事件分析服务"""
    
    def __init__(self):
        self.detector = ContextAwareEventDetector()
        self.logger = logging.getLogger(__name__)
    
    async def analyze_user_context(self, user_id: int) -> Dict[str, Any]:
        """分析用户上下文"""
        self.logger.info(f"开始分析用户 {user_id} 的上下文")
        
        # 检测事件
        events = await self.detector.analyze_conversation_history(user_id)
        
        # 分析事件影响
        analysis_result = {
            "user_id": user_id,
            "total_events": len(events),
            "events_by_category": {},
            "high_impact_events": [],
            "recommendations": []
        }
        
        # 按类别统计
        for event in events:
            category = event.category.value
            if category not in analysis_result["events_by_category"]:
                analysis_result["events_by_category"][category] = []
            analysis_result["events_by_category"][category].append(event)
            
            # 高影响事件
            if event.impact_level >= 3:
                analysis_result["high_impact_events"].append(event)
        
        # 生成建议
        analysis_result["recommendations"] = self._generate_recommendations(events)
        
        return analysis_result
    
    def _generate_recommendations(self, events: List[DetectedEvent]) -> List[str]:
        """基于事件生成建议"""
        recommendations = []
        
        event_types = [event.type for event in events]
        
        if "illness" in event_types:
            recommendations.append("检测到健康问题，建议优先关注休息和康复")
        
        if "travel" in event_types:
            recommendations.append("检测到旅行安排，建议调整计划以适应变化")
        
        if "business_dinner" in event_types or "social_gathering" in event_types:
            recommendations.append("检测到社交活动，饮食和运动计划可能需要调整")
        
        if "overtime" in event_types:
            recommendations.append("检测到工作压力，建议关注睡眠和休息质量")
        
        return recommendations


# 使用示例
async def demo():
    """演示使用方法"""
    detector = ContextAwareEventDetector()
    
    # 测试对话文本
    test_texts = [
        "今晚有个重要应酬，可能没时间运动了",
        "明天要出差去北京，大概三天",
        "今天感觉不太舒服，可能感冒了",
        "周末要和家人聚会，可能没时间记录饮食"
    ]
    
    for text in test_texts:
        print(f"\n分析文本: {text}")
        events = await detector.detect_events_from_conversation(text)
        
        for event in events:
            print(f"  检测到事件: {event.type} (置信度: {event.confidence:.2f})")
    
    # 测试事件分析服务
    service = EventAnalysisService()
    analysis = await service.analyze_user_context(1)
    print(f"\n用户上下文分析结果: {analysis}")


if __name__ == "__main__":
    asyncio.run(demo())