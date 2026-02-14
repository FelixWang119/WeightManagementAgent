"""
可配置事件识别器 - 混合架构：规则引擎 + LLM兜底
基于YAML配置文件，支持热更新和丰富的规则配置
"""

import asyncio
import logging
import re
import time
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from config.logging_config import get_module_logger

logger = get_module_logger()


@dataclass
class DetectedEvent:
    """检测到的事件"""

    id: str
    type: str
    category: str
    name: str
    description: str
    confidence: float
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: str = "conversation"
    keywords: List[str] = None
    impact_level: int = 1
    priority: int = 5

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class RuleLoader:
    """规则加载器 - 支持热更新"""

    def __init__(self, config_file: str = "config/event_rules.yaml"):
        self.config_file = Path(config_file)
        self._rules: Dict[str, Any] = {}
        self._last_modified: float = 0
        self._last_loaded: float = 0

    def load_rules(self) -> Dict[str, Any]:
        """加载规则配置"""
        try:
            if not self.config_file.exists():
                logger.warning(f"配置文件不存在: {self.config_file}")
                return {}

            current_modified = self.config_file.stat().st_mtime
            if current_modified == self._last_modified:
                return self._rules

            with open(self.config_file, "r", encoding="utf-8") as f:
                self._rules = yaml.safe_load(f) or {}

            self._last_modified = current_modified
            self._last_loaded = time.time()

            logger.info(f"规则配置已加载: {self.config_file}")
            return self._rules

        except Exception as e:
            logger.error(f"加载规则配置失败: {e}")
            return {}

    def get_global_config(self, key: str, default: Any = None) -> Any:
        """获取全局配置"""
        rules = self.load_rules()
        return rules.get("global", {}).get(key, default)

    def get_event_types(self) -> Dict[str, Dict[str, Any]]:
        """获取事件类型定义"""
        rules = self.load_rules()
        return rules.get("event_types", {})

    def get_recognition_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取识别规则"""
        rules = self.load_rules()
        return rules.get("recognition_rules", {})

    def get_conflict_rules(self) -> Dict[str, Dict[str, Any]]:
        """获取冲突规则"""
        rules = self.load_rules()
        return rules.get("conflict_rules", {})

    def get_time_patterns(self) -> Dict[str, str]:
        """获取时间模式"""
        rules = self.load_rules()
        return rules.get("time_patterns", {})


class RuleEngine:
    """规则引擎 - 基于配置规则进行事件检测"""

    def __init__(self, rule_loader: RuleLoader):
        self.rule_loader = rule_loader
        self.logger = get_module_logger()

    def preprocess_text(self, text: str) -> str:
        """预处理文本"""
        text = text.lower()
        text = re.sub(r'[！？，。；：""\'\'（）【】《》]', " ", text)
        text = re.sub(r"\\s+", " ", text).strip()
        return text

    def detect_events(
        self, conversation_text: str, timestamp: datetime = None
    ) -> List[DetectedEvent]:
        """检测事件"""
        if timestamp is None:
            timestamp = datetime.now()

        self.logger.debug(f"开始分析对话文本: {conversation_text[:50]}...")

        processed_text = self.preprocess_text(conversation_text)
        detected_events = []

        event_types = self.rule_loader.get_event_types()
        recognition_rules = self.rule_loader.get_recognition_rules()

        for event_type, event_config in event_types.items():
            if event_type in recognition_rules:
                events = self._detect_specific_event(
                    processed_text,
                    event_type,
                    event_config,
                    recognition_rules[event_type],
                    timestamp,
                )
                detected_events.extend(events)

        detected_events = self._deduplicate_and_sort_events(detected_events)

        self.logger.info(f"规则引擎检测到 {len(detected_events)} 个事件")
        return detected_events

    def _detect_specific_event(
        self,
        text: str,
        event_type: str,
        event_config: Dict[str, Any],
        rules: Dict[str, Any],
        timestamp: datetime,
    ) -> List[DetectedEvent]:
        events = []

        exact_matches = self._match_exact_keywords(
            text, rules.get("exact_keywords", [])
        )
        variant_matches = self._match_variant_keywords(
            text, rules.get("variant_keywords", [])
        )
        pattern_matches = self._match_patterns(text, rules.get("patterns", []))
        semantic_matches = self._match_semantic_keywords(
            text, rules.get("semantic_keywords", [])
        )

        weights = rules.get("weights", {})
        confidence = self._calculate_confidence(
            exact_matches, variant_matches, pattern_matches, semantic_matches, weights
        )

        threshold = self.rule_loader.get_global_config("confidence_threshold", 0.6)
        if confidence >= threshold:
            time_info = self._extract_time_info(text, timestamp)

            event = DetectedEvent(
                id=f"{event_type}_{timestamp.strftime('%Y%m%d%H%M%S')}",
                type=event_type,
                category=event_config.get("category", "unknown"),
                name=event_config.get("name", event_type),
                description=event_config.get("description", ""),
                confidence=confidence,
                start_time=time_info.get("start_time"),
                end_time=time_info.get("end_time"),
                keywords=rules.get("exact_keywords", [])
                + rules.get("variant_keywords", []),
                impact_level=event_config.get("impact_level", 1),
                priority=event_config.get("priority", 5),
            )
            events.append(event)

        return events

    def _match_exact_keywords(self, text: str, keywords: List[str]) -> int:
        matches = 0
        for keyword in keywords:
            if keyword in text:
                matches += 1
        return matches

    def _match_variant_keywords(self, text: str, keywords: List[str]) -> int:
        matches = 0
        for keyword in keywords:
            if keyword in text or any(word in text for word in keyword.split()):
                matches += 1
        return matches

    def _match_patterns(self, text: str, patterns: List[str]) -> int:
        matches = 0
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    matches += 1
            except re.error as e:
                self.logger.warning(f"正则表达式错误 {pattern}: {e}")
        return matches

    def _match_semantic_keywords(self, text: str, keywords: List[str]) -> int:
        matches = 0
        for keyword in keywords:
            if self._check_semantic_similarity(text, keyword):
                matches += 1
        return matches

    def _check_semantic_similarity(self, text: str, keyword: str) -> bool:
        return keyword in text

    def _calculate_confidence(
        self,
        exact_matches: int,
        variant_matches: int,
        pattern_matches: int,
        semantic_matches: int,
        weights: Dict[str, float],
    ) -> float:
        exact_weight = weights.get("exact_keywords", 0.7)
        variant_weight = weights.get("variant_keywords", 0.5)
        pattern_weight = weights.get("patterns", 0.8)
        semantic_weight = weights.get("semantic_keywords", 0.6)

        score = (
            exact_matches * exact_weight
            + variant_matches * variant_weight
            + pattern_matches * pattern_weight
            + semantic_matches * semantic_weight
        )

        max_possible = len(weights) * 1.0

        confidence = min(score / max_possible if max_possible > 0 else 0, 1.0)

        match_types = sum(
            [
                exact_matches > 0,
                variant_matches > 0,
                pattern_matches > 0,
                semantic_matches > 0,
            ]
        )

        if match_types >= 2:
            confidence = min(confidence + 0.1, 1.0)

        return confidence

    def _extract_time_info(self, text: str, base_time: datetime) -> Dict[str, datetime]:
        time_info = {}
        time_patterns = self.rule_loader.get_time_patterns()

        if re.search(time_patterns.get("today", "今天"), text):
            time_info["start_time"] = base_time.replace(hour=9, minute=0, second=0)
            time_info["end_time"] = base_time.replace(hour=22, minute=0, second=0)
        elif re.search(time_patterns.get("tonight", "今晚"), text):
            time_info["start_time"] = base_time.replace(hour=18, minute=0, second=0)
            time_info["end_time"] = base_time.replace(hour=23, minute=0, second=0)
        elif re.search(time_patterns.get("tomorrow", "明天"), text):
            tomorrow = base_time + timedelta(days=1)
            time_info["start_time"] = tomorrow.replace(hour=9, minute=0, second=0)
            time_info["end_time"] = tomorrow.replace(hour=22, minute=0, second=0)

        specific_time_match = re.search(
            time_patterns.get("specific_time", r"(\\d{1,2}[:：]\\d{1,2})"), text
        )
        if specific_time_match:
            time_str = specific_time_match.group(1)
            try:
                hour, minute = map(int, re.split(r"[:：]", time_str))
                if time_info.get("start_time"):
                    time_info["start_time"] = time_info["start_time"].replace(
                        hour=hour, minute=minute
                    )
            except:
                pass

        return time_info

    def _deduplicate_and_sort_events(
        self, events: List[DetectedEvent]
    ) -> List[DetectedEvent]:
        if not events:
            return []

        events.sort(key=lambda x: (x.confidence, x.priority), reverse=True)

        unique_events = []
        seen_types = set()

        for event in events:
            if event.type not in seen_types:
                unique_events.append(event)
                seen_types.add(event.type)

        return unique_events


class LLMFallbackDetector:
    """LLM兜底检测器"""

    def __init__(self, rule_loader: RuleLoader):
        self.rule_loader = rule_loader
        self.logger = get_module_logger()

    async def detect_with_llm(
        self, conversation_text: str, timestamp: datetime = None
    ) -> List[DetectedEvent]:
        if timestamp is None:
            timestamp = datetime.now()

        if not self.rule_loader.get_global_config("llm_fallback.enabled", True):
            return []

        try:
            self.logger.info("LLM兜底检测被调用")
            return await self._simulate_llm_detection(conversation_text, timestamp)

        except Exception as e:
            self.logger.error(f"LLM检测失败: {e}")
            return []

    async def _simulate_llm_detection(
        self, text: str, timestamp: datetime
    ) -> List[DetectedEvent]:
        return []


class ConfigurableEventDetector:
    """可配置事件识别器"""

    def __init__(self, config_file: str = "config/event_rules.yaml"):
        self.rule_loader = RuleLoader(config_file)
        self.rule_engine = RuleEngine(self.rule_loader)
        self.llm_detector = LLMFallbackDetector(self.rule_loader)
        self.logger = get_module_logger()

    async def detect_events(
        self,
        conversation_text: str,
        use_llm_fallback: bool = True,
        timestamp: datetime = None,
    ) -> List[DetectedEvent]:
        if timestamp is None:
            timestamp = datetime.now()

        rule_based_events = self.rule_engine.detect_events(conversation_text, timestamp)

        threshold = self.rule_loader.get_global_config("confidence_threshold", 0.6)
        needs_llm = (
            use_llm_fallback
            and self.rule_loader.get_global_config("llm_fallback.enabled", True)
            and (
                not rule_based_events
                or max(e.confidence for e in rule_based_events) < threshold
            )
        )

        llm_events = []
        if needs_llm:
            self.logger.info("规则引擎置信度不足，触发LLM兜底检测")
            llm_events = await self.llm_detector.detect_with_llm(
                conversation_text, timestamp
            )

        final_events = self._fuse_results(rule_based_events, llm_events)

        self.logger.info(f"混合检测完成，共检测到 {len(final_events)} 个事件")
        return final_events

    def _fuse_results(
        self, rule_events: List[DetectedEvent], llm_events: List[DetectedEvent]
    ) -> List[DetectedEvent]:
        all_events = rule_events + llm_events

        all_events.sort(key=lambda x: x.confidence, reverse=True)

        unique_events = []
        seen_types = set()

        for event in all_events:
            if event.type not in seen_types:
                unique_events.append(event)
                seen_types.add(event.type)

        return unique_events

    async def get_conflicting_events(
        self, user_id: int, plan_type: str, planned_time: datetime = None
    ) -> List[DetectedEvent]:
        conflict_rules = self.rule_loader.get_conflict_rules()
        conflicting_types = conflict_rules.get(plan_type, {}).get(
            "conflicting_events", []
        )

        recent_events = await self._get_recent_events(user_id)

        conflicting_events = [
            event
            for event in recent_events
            if event.type in conflicting_types and event.confidence > 0.5
        ]

        if planned_time and conflicting_events:
            conflicting_events = [
                event
                for event in conflicting_events
                if self._check_time_conflict(event, planned_time)
            ]

        return conflicting_events

    async def detect_events_from_user_history(
        self, user_id: int, db
    ) -> List[DetectedEvent]:
        """从用户历史对话中检测事件"""
        from sqlalchemy import select
        from models.database import ChatHistory, MessageRole

        result = await db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(20)
        )
        records = result.scalars().all()

        if not records:
            return []

        user_messages = [r.content for r in records if r.role == MessageRole.USER]

        combined_text = " ".join(user_messages[-10:])

        events = await self.detect_events(combined_text, timestamp=datetime.now())

        self.logger.info(f"从用户 {user_id} 历史中检测到 {len(events)} 个事件")
        return events

    async def _get_recent_events(self, user_id: int) -> List[DetectedEvent]:
        return []

    def _check_time_conflict(
        self, event: DetectedEvent, planned_time: datetime
    ) -> bool:
        if not event.start_time or not event.end_time:
            return True

        event_duration = (event.end_time - event.start_time).total_seconds()

        if event_duration > 4 * 3600:
            return True

        if event.start_time <= planned_time <= event.end_time:
            return True

        plan_start = planned_time - timedelta(hours=2)
        plan_end = planned_time + timedelta(hours=2)

        return not (event.end_time < plan_start or event.start_time > plan_end)


async def demo():
    """演示使用方法"""
    detector = ConfigurableEventDetector()

    test_texts = [
        "今晚有个重要应酬，可能没时间运动了",
        "明天要出差去北京，大概三天",
        "今天感觉不太舒服，可能感冒了",
        "周末要和家人聚会，可能没时间记录饮食",
    ]

    for text in test_texts:
        print(f"\\n分析文本: {text}")
        events = await detector.detect_events(text)

        for event in events:
            print(
                f"  检测到事件: {event.name} (类型: {event.type}, 置信度: {event.confidence:.2f})"
            )


if __name__ == "__main__":
    asyncio.run(demo())
