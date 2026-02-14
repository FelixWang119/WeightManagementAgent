"""
记忆增强与监控服务
提供向量检索优化、长期记忆压缩、记忆权重管理、性能监控
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import time
import json
import statistics
from functools import wraps

from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class MemoryCache:
    """记忆缓存层"""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < 300:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any):
        """设置缓存"""
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, datetime.now())

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self._cache),
        }


memory_cache = MemoryCache()


def cached_search(func):
    """搜索结果缓存装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
        cached_result = memory_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"缓存命中: {cache_key}")
            return cached_result

        result = func(*args, **kwargs)
        memory_cache.set(cache_key, result)
        return result

    return wrapper


class MemoryCompressionService:
    """长期记忆压缩服务"""

    @staticmethod
    def compress_memory(memories: List[Dict], max_memories: int = 50) -> List[Dict]:
        """
        压缩记忆，保留最重要的记忆

        Args:
            memories: 记忆列表
            max_memories: 最大保留数量

        Returns:
            压缩后的记忆列表
        """
        if len(memories) <= max_memories:
            return memories

        scored_memories = []
        for mem in memories:
            score = MemoryCompressionService._calculate_importance(mem)
            scored_memories.append((score, mem))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored_memories[:max_memories]]

    @staticmethod
    def _calculate_importance(memory: Dict) -> float:
        """计算记忆重要性评分"""
        score = 0.0

        recency = memory.get("metadata", {}).get("recency_factor", 0.5)
        score += recency * 0.4

        importance = memory.get("metadata", {}).get("importance", 5)
        score += (importance / 10) * 0.3

        frequency = memory.get("metadata", {}).get("frequency", 1)
        score += min(frequency / 10, 1) * 0.2

        if memory.get("metadata", {}).get("has_feedback"):
            score += 0.1

        return score

    @staticmethod
    def summarize_memories(memories: List[Dict]) -> str:
        """将多条记忆压缩为摘要"""
        if not memories:
            return ""

        categories = defaultdict(list)
        for mem in memories:
            cat = mem.get("metadata", {}).get("category", "other")
            categories[cat].append(mem)

        summary_parts = []
        for cat, mems in categories.items():
            count = len(mems)
            if count > 0:
                summary_parts.append(f"{cat}: {count}条记录")

        return "; ".join(summary_parts)


class MemoryWeightManager:
    """记忆权重管理服务"""

    @staticmethod
    def update_weight(
        memory_id: str, feedback_type: str, current_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        根据反馈更新记忆权重

        Args:
            memory_id: 记忆ID
            feedback_type: 反馈类型 (positive/negative/neutral)
            current_weights: 当前权重

        Returns:
            更新后的权重
        """
        weights = current_weights.copy()

        if feedback_type == "positive":
            weights["importance"] = min(weights.get("importance", 5) + 0.5, 10)
            weights["relevance"] = min(weights.get("relevance", 0.5) + 0.1, 1.0)
        elif feedback_type == "negative":
            weights["importance"] = max(weights.get("importance", 5) - 0.5, 1)
            weights["relevance"] = max(weights.get("relevance", 0.5) - 0.1, 0.1)
        else:
            pass

        return weights

    @staticmethod
    def calculate_relevance(memory: Dict, query: str) -> float:
        """计算记忆与查询的相关性"""
        memory_text = memory.get("document", "")
        query_lower = query.lower()

        query_words = set(query_lower.split())
        memory_words = set(memory_text.lower().split())

        if not query_words:
            return 0.5

        overlap = len(query_words & memory_words)
        relevance = overlap / len(query_words)

        return min(relevance * 2, 1.0)


class PerformanceMonitor:
    """性能监控服务"""

    _response_times: List[float] = []
    _operation_counts: Dict[str, int] = defaultdict(int)
    _error_counts: Dict[str, int] = defaultdict(int)
    _start_time = datetime.now()

    @classmethod
    def record_response_time(cls, operation: str, duration: float):
        """记录响应时间"""
        cls._response_times.append(duration)
        cls._operation_counts[operation] += 1

        if len(cls._response_times) > 1000:
            cls._response_times = cls._response_times[-500:]

    @classmethod
    def record_error(cls, operation: str):
        """记录错误"""
        cls._error_counts[operation] += 1

    @classmethod
    def get_stats(cls, operation: Optional[str] = None) -> Dict[str, Any]:
        """获取性能统计"""
        if operation:
            return {
                "operation": operation,
                "count": cls._operation_counts.get(operation, 0),
                "errors": cls._error_counts.get(operation, 0),
                "error_rate": cls._error_counts.get(operation, 0)
                / max(cls._operation_counts.get(operation, 1), 1),
            }

        recent_times = cls._response_times[-100:] if cls._response_times else []
        return {
            "uptime_seconds": (datetime.now() - cls._start_time).total_seconds(),
            "total_operations": sum(cls._operation_counts.values()),
            "total_errors": sum(cls._error_counts.values()),
            "response_time": {
                "avg": round(statistics.mean(recent_times), 3) if recent_times else 0,
                "min": round(min(recent_times), 3) if recent_times else 0,
                "max": round(max(recent_times), 3) if recent_times else 0,
                "p95": round(
                    sorted(recent_times)[int(len(recent_times) * 0.95)]
                    if recent_times
                    else 0,
                    3,
                ),
            },
            "operations": dict(cls._operation_counts),
            "errors": dict(cls._error_counts),
        }

    @classmethod
    def reset(cls):
        """重置统计"""
        cls._response_times.clear()
        cls._operation_counts.clear()
        cls._error_counts.clear()
        cls._start_time = datetime.now()


class AccuracyTracker:
    """识别准确率追踪服务"""

    _predictions: List[Dict] = []
    _feedback_types = ["correct", "incorrect", "partial"]

    @classmethod
    def record_prediction(
        cls,
        prediction_type: str,
        predicted_value: Any,
        actual_value: Optional[Any] = None,
        metadata: Optional[Dict] = None,
    ):
        """记录预测结果"""
        cls._predictions.append(
            {
                "type": prediction_type,
                "predicted": predicted_value,
                "actual": actual_value,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat(),
                "feedback": None,
            }
        )

    @classmethod
    def record_feedback(
        cls, prediction_index: int, feedback: str, correct_value: Any = None
    ):
        """记录反馈"""
        if 0 <= prediction_index < len(cls._predictions):
            cls._predictions[prediction_index]["feedback"] = feedback
            if correct_value is not None:
                cls._predictions[prediction_index]["actual"] = correct_value

    @classmethod
    def get_accuracy(cls, prediction_type: Optional[str] = None) -> Dict[str, Any]:
        """获取准确率统计"""
        predictions = cls._predictions
        if prediction_type:
            predictions = [p for p in predictions if p["type"] == prediction_type]

        if not predictions:
            return {"accuracy": 0, "count": 0, "feedback_count": 0}

        with_feedback = [p for p in predictions if p["feedback"] is not None]
        if not with_feedback:
            return {"accuracy": 0, "count": len(predictions), "feedback_count": 0}

        correct = sum(1 for p in with_feedback if p["feedback"] == "correct")
        partial = sum(1 for p in with_feedback if p["feedback"] == "partial")

        accuracy = (correct + partial * 0.5) / len(with_feedback)

        by_type = defaultdict(lambda: {"correct": 0, "total": 0})
        for p in with_feedback:
            by_type[p["type"]]["total"] += 1
            if p["feedback"] == "correct":
                by_type[p["type"]]["correct"] += 1

        return {
            "accuracy": round(accuracy, 3),
            "count": len(predictions),
            "feedback_count": len(with_feedback),
            "by_type": {
                t: round(d["correct"] / max(d["total"], 1), 3)
                for t, d in by_type.items()
            },
        }

    @classmethod
    def reset(cls):
        """重置追踪数据"""
        cls._predictions.clear()


class QualityAssessment:
    """质量评估服务"""

    @staticmethod
    def assess_response_quality(response: Dict) -> Dict[str, Any]:
        """评估响应质量"""
        scores = {}

        if "content" in response:
            content = response["content"]
            scores["length"] = len(content) if content else 0

            has_numbers = any(c.isdigit() for c in content)
            scores["has_data"] = has_numbers

            sentences = content.count("。") + content.count("！") + content.count("？")
            scores["sentence_count"] = sentences

        helpfulness = response.get("metadata", {}).get("helpful", True)
        scores["helpfulness"] = 1.0 if helpfulness else 0.5

        overall = sum(scores.values()) / max(len(scores), 1)
        return {
            "scores": scores,
            "overall": round(overall, 2),
            "level": "high" if overall > 0.7 else "medium" if overall > 0.4 else "low",
        }

    @staticmethod
    def assess_data_quality(data: Dict) -> Dict[str, Any]:
        """评估数据质量"""
        issues = []
        score = 1.0

        if not data:
            issues.append("数据为空")
            score = 0
            return {"score": 0, "issues": issues, "valid": False}

        for key, value in data.items():
            if value is None:
                issues.append(f"{key}为空")
                score -= 0.1

        for key in ["weight", "calories", "exercise"]:
            if key in data and isinstance(data[key], (int, float)):
                if data[key] < 0:
                    issues.append(f"{key}为负数")
                    score -= 0.2

        return {
            "score": max(round(score, 2), 0),
            "issues": issues,
            "valid": score >= 0.7,
        }


def timed_operation(operation_name: str):
    """操作计时装饰器"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                PerformanceMonitor.record_response_time(operation_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start
                PerformanceMonitor.record_response_time(operation_name, duration)
                PerformanceMonitor.record_error(operation_name)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                PerformanceMonitor.record_response_time(operation_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start
                PerformanceMonitor.record_response_time(operation_name, duration)
                PerformanceMonitor.record_error(operation_name)
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
