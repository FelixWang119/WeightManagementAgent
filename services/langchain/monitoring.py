"""
Agent 监控和性能收集模块

用于收集和分析 Agent 的性能指标，包括：
1. 响应时间
2. 成功率
3. 工具调用统计
4. 错误率
5. 用户满意度（通过关键词匹配）
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型"""

    RESPONSE_TIME = "response_time"
    SUCCESS_RATE = "success_rate"
    TOOL_CALL_COUNT = "tool_call_count"
    ERROR_RATE = "error_rate"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    user_id: int
    timestamp: datetime
    response_time: float  # 响应时间（秒）
    success: bool  # 是否成功
    tool_called: bool  # 是否调用了工具
    tool_name: Optional[str] = None  # 工具名称
    error_message: Optional[str] = None  # 错误信息
    response_length: int = 0  # 响应长度
    keywords_matched: List[str] = None  # 匹配的关键词

    def __post_init__(self):
        if self.keywords_matched is None:
            self.keywords_matched = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AgentMonitor:
    """
    Agent 监控器

    收集和分析 Agent 性能指标
    """

    def __init__(self, retention_days: int = 30):
        """
        初始化监控器

        Args:
            retention_days: 数据保留天数
        """
        self.retention_days = retention_days
        self.metrics: List[PerformanceMetrics] = []
        self._user_metrics: Dict[int, List[PerformanceMetrics]] = defaultdict(list)

        # 统计缓存
        self._stats_cache: Dict[str, Any] = {}
        self._cache_expiry = datetime.now()

        logger.info(f"AgentMonitor 初始化完成，数据保留天数: {retention_days}")

    def record_metric(self, metric: PerformanceMetrics):
        """
        记录性能指标

        Args:
            metric: 性能指标
        """
        self.metrics.append(metric)
        self._user_metrics[metric.user_id].append(metric)

        # 清理过期数据
        self._cleanup_old_metrics()

        # 清除缓存
        self._stats_cache.clear()

        logger.debug(
            f"记录指标: user_id={metric.user_id}, "
            f"response_time={metric.response_time:.2f}s, "
            f"success={metric.success}"
        )

    def record_chat(
        self,
        user_id: int,
        response_time: float,
        success: bool,
        tool_called: bool = False,
        tool_name: Optional[str] = None,
        error_message: Optional[str] = None,
        response: Optional[str] = None,
        expected_keywords: Optional[List[str]] = None,
    ) -> PerformanceMetrics:
        """
        记录聊天指标

        Args:
            user_id: 用户ID
            response_time: 响应时间
            success: 是否成功
            tool_called: 是否调用了工具
            tool_name: 工具名称
            error_message: 错误信息
            response: Agent响应
            expected_keywords: 预期关键词

        Returns:
            记录的指标
        """
        # 计算关键词匹配
        keywords_matched = []
        if response and expected_keywords:
            response_lower = response.lower()
            for keyword in expected_keywords:
                if keyword.lower() in response_lower:
                    keywords_matched.append(keyword)

        metric = PerformanceMetrics(
            user_id=user_id,
            timestamp=datetime.now(),
            response_time=response_time,
            success=success,
            tool_called=tool_called,
            tool_name=tool_name,
            error_message=error_message,
            response_length=len(response) if response else 0,
            keywords_matched=keywords_matched,
        )

        self.record_metric(metric)
        return metric

    def _cleanup_old_metrics(self):
        """清理过期指标"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)

        # 清理主列表
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff_time]

        # 清理用户指标
        for user_id in list(self._user_metrics.keys()):
            self._user_metrics[user_id] = [
                m for m in self._user_metrics[user_id] if m.timestamp > cutoff_time
            ]

            # 如果用户没有指标了，删除条目
            if not self._user_metrics[user_id]:
                del self._user_metrics[user_id]

    def get_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            user_id: 可选用户ID，如果提供则只返回该用户的统计

        Returns:
            统计信息字典
        """
        # 检查缓存
        cache_key = f"stats_{user_id}"
        if cache_key in self._stats_cache and datetime.now() < self._cache_expiry:
            return self._stats_cache[cache_key].copy()

        # 获取指标列表
        metrics = self.metrics
        if user_id is not None:
            metrics = self._user_metrics.get(user_id, [])

        if not metrics:
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "tool_call_rate": 0.0,
                "error_rate": 0.0,
                "avg_response_length": 0,
                "keyword_match_rate": 0.0,
            }

        # 计算统计
        total = len(metrics)
        successful = sum(1 for m in metrics if m.success)
        tool_calls = sum(1 for m in metrics if m.tool_called)
        errors = sum(1 for m in metrics if m.error_message)
        total_response_time = sum(m.response_time for m in metrics)
        total_response_length = sum(m.response_length for m in metrics)

        # 计算关键词匹配率
        total_keywords = 0
        matched_keywords = 0
        for m in metrics:
            if m.keywords_matched:
                total_keywords += len(m.keywords_matched)
                matched_keywords += len([k for k in m.keywords_matched if k])

        stats = {
            "total_requests": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_response_time": total_response_time / total if total > 0 else 0.0,
            "tool_call_rate": tool_calls / total if total > 0 else 0.0,
            "error_rate": errors / total if total > 0 else 0.0,
            "avg_response_length": total_response_length / total if total > 0 else 0,
            "keyword_match_rate": matched_keywords / total_keywords
            if total_keywords > 0
            else 0.0,
            "last_updated": datetime.now().isoformat(),
        }

        # 缓存结果（5分钟）
        self._stats_cache[cache_key] = stats.copy()
        self._cache_expiry = datetime.now() + timedelta(minutes=5)

        return stats

    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取工具使用统计

        Returns:
            工具统计字典
        """
        tool_stats = defaultdict(
            lambda: {
                "count": 0,
                "success_count": 0,
                "avg_response_time": 0.0,
                "total_response_time": 0.0,
            }
        )

        for metric in self.metrics:
            if metric.tool_called and metric.tool_name:
                stats = tool_stats[metric.tool_name]
                stats["count"] += 1
                stats["total_response_time"] += metric.response_time
                if metric.success:
                    stats["success_count"] += 1

        # 计算平均值
        for tool_name, stats in tool_stats.items():
            if stats["count"] > 0:
                stats["avg_response_time"] = (
                    stats["total_response_time"] / stats["count"]
                )
                stats["success_rate"] = stats["success_count"] / stats["count"]
            else:
                stats["avg_response_time"] = 0.0
                stats["success_rate"] = 0.0

        return dict(tool_stats)

    def get_user_stats(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户统计排名

        Args:
            top_n: 返回前N名用户

        Returns:
            用户统计列表
        """
        user_stats = []

        for user_id, metrics in self._user_metrics.items():
            if not metrics:
                continue

            stats = self.get_stats(user_id)
            user_stats.append(
                {
                    "user_id": user_id,
                    **stats,
                    "last_activity": max(m.timestamp for m in metrics).isoformat(),
                }
            )

        # 按请求数排序
        user_stats.sort(key=lambda x: x["total_requests"], reverse=True)

        return user_stats[:top_n]

    def export_metrics(self, filepath: str):
        """
        导出指标到文件

        Args:
            filepath: 文件路径
        """
        data = {
            "export_time": datetime.now().isoformat(),
            "total_metrics": len(self.metrics),
            "metrics": [m.to_dict() for m in self.metrics],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"指标已导出到: {filepath}")

    def clear_metrics(self):
        """清空所有指标"""
        self.metrics.clear()
        self._user_metrics.clear()
        self._stats_cache.clear()
        logger.info("所有指标已清空")


# 全局监控器实例
global_monitor = AgentMonitor()


def monitor_chat_decorator(func):
    """
    监控装饰器

    用于装饰 Agent 的 chat 方法，自动收集性能指标
    """

    async def wrapper(self, message: str, *args, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            # 调用原始方法
            result = await func(self, message, *args, **kwargs)

            # 计算响应时间
            response_time = time.time() - start_time

            # 提取信息
            success = "error" not in result or not result.get("error")
            response = result.get("response", "")

            # 检查是否有工具调用
            tool_called = False
            tool_name = None
            intermediate_steps = result.get("intermediate_steps", [])
            if intermediate_steps:
                tool_called = True
                # 尝试提取工具名称
                for step in intermediate_steps:
                    if isinstance(step, dict) and "tool" in step:
                        tool_name = step.get("tool")
                        break

            # 记录指标
            metric = global_monitor.record_chat(
                user_id=getattr(self, "user_id", 0),
                response_time=response_time,
                success=success,
                tool_called=tool_called,
                tool_name=tool_name,
                error_message=result.get("error"),
                response=response,
            )

            # 添加监控信息到结果
            if "monitoring" not in result:
                result["monitoring"] = {}
            result["monitoring"]["response_time"] = response_time
            result["monitoring"]["metric_id"] = id(metric)

            return result

        except Exception as e:
            # 记录错误
            response_time = time.time() - start_time
            global_monitor.record_chat(
                user_id=getattr(self, "user_id", 0),
                response_time=response_time,
                success=False,
                error_message=str(e),
            )
            raise

    return wrapper


def get_agent_monitor() -> AgentMonitor:
    """
    获取全局监控器实例

    Returns:
        AgentMonitor 实例
    """
    return global_monitor
