"""
性能监控模块
跟踪LangGraph节点执行时间、工具调用、缓存命中率等关键指标
集成AGENTS.md中要求的详细日志记录
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class NodeMetrics:
    """节点执行指标"""

    node_name: str
    execution_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    error_count: int = 0
    last_execution_time: Optional[datetime] = None

    def record_execution(self, duration_ms: float, success: bool = True):
        """记录一次执行"""
        self.execution_count += 1
        self.total_time_ms += duration_ms
        self.avg_time_ms = self.total_time_ms / self.execution_count
        self.last_execution_time = datetime.now()
        if not success:
            self.error_count += 1


@dataclass
class ToolMetrics:
    """工具调用指标"""

    tool_name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    error_count: int = 0
    last_call_time: Optional[datetime] = None

    def record_call(self, duration_ms: float, success: bool = True):
        """记录一次调用"""
        self.call_count += 1
        self.total_time_ms += duration_ms
        self.avg_time_ms = self.total_time_ms / self.call_count
        self.last_call_time = datetime.now()
        if not success:
            self.error_count += 1


@dataclass
class CacheMetrics:
    """缓存性能指标"""

    cache_name: str
    hit_count: int = 0
    miss_count: int = 0
    total_size: int = 0
    last_refresh_time: Optional[datetime] = None

    def record_hit(self):
        """记录一次缓存命中"""
        self.hit_count += 1

    def record_miss(self):
        """记录一次缓存未命中"""
        self.miss_count += 1

    @property
    def hit_rate(self) -> float:
        """计算缓存命中率"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0


@dataclass
class GraphMetrics:
    """图级别聚合指标"""

    graph_id: str
    total_invocations: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    node_metrics: Dict[str, NodeMetrics] = field(default_factory=dict)
    tool_metrics: Dict[str, ToolMetrics] = field(default_factory=dict)
    cache_metrics: Dict[str, CacheMetrics] = field(default_factory=dict)

    def add_node_metric(self, node_name: str) -> NodeMetrics:
        """添加或获取节点指标"""
        if node_name not in self.node_metrics:
            self.node_metrics[node_name] = NodeMetrics(node_name)
        return self.node_metrics[node_name]

    def add_tool_metric(self, tool_name: str) -> ToolMetrics:
        """添加或获取工具指标"""
        if tool_name not in self.tool_metrics:
            self.tool_metrics[tool_name] = ToolMetrics(tool_name)
        return self.tool_metrics[tool_name]

    def add_cache_metric(self, cache_name: str) -> CacheMetrics:
        """添加或获取缓存指标"""
        if cache_name not in self.cache_metrics:
            self.cache_metrics[cache_name] = CacheMetrics(cache_name)
        return self.cache_metrics[cache_name]

    def record_invocation(self, duration_ms: float):
        """记录一次图调用"""
        self.total_invocations += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_invocations


class PerformanceMonitor:
    """性能监控主类"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.metrics: Dict[str, GraphMetrics] = {}
            self._initialized = True

    async def get_or_create_metrics(self, graph_id: str) -> GraphMetrics:
        """获取或创建图指标"""
        async with self._lock:
            if graph_id not in self.metrics:
                self.metrics[graph_id] = GraphMetrics(graph_id)
                logger.info("创建性能监控指标: %s", graph_id)
            return self.metrics[graph_id]

    def record_node_execution(
        self,
        graph_id: str,
        node_name: str,
        duration_ms: float,
        success: bool = True,
        **kwargs,
    ):
        """记录节点执行（同步版本）"""
        try:
            metrics = self.metrics.get(graph_id)
            if not metrics:
                metrics = GraphMetrics(graph_id)
                self.metrics[graph_id] = metrics

            node_metric = metrics.add_node_metric(node_name)
            node_metric.record_execution(duration_ms, success)

            # 记录详细日志（遵循AGENTS.md规范）
            log_level = logger.info if success else logger.error
            log_level(
                "节点执行: graph=%s, node=%s, 耗时=%.2fms, 状态=%s",
                graph_id,
                node_name,
                duration_ms,
                "成功" if success else "失败",
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录节点执行指标失败: %s", e)

    async def record_node_execution_async(
        self,
        graph_id: str,
        node_name: str,
        duration_ms: float,
        success: bool = True,
        **kwargs,
    ):
        """记录节点执行（异步版本）"""
        try:
            metrics = await self.get_or_create_metrics(graph_id)
            node_metric = metrics.add_node_metric(node_name)
            node_metric.record_execution(duration_ms, success)

            # 记录详细日志
            log_level = logger.info if success else logger.error
            log_level(
                "节点执行: graph=%s, node=%s, 耗时=%.2fms, 状态=%s",
                graph_id,
                node_name,
                duration_ms,
                "成功" if success else "失败",
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录节点执行指标失败: %s", e)

    def record_tool_call(
        self,
        graph_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
        **kwargs,
    ):
        """记录工具调用"""
        try:
            metrics = self.metrics.get(graph_id)
            if not metrics:
                metrics = GraphMetrics(graph_id)
                self.metrics[graph_id] = metrics

            tool_metric = metrics.add_tool_metric(tool_name)
            tool_metric.record_call(duration_ms, success)

            # 记录详细日志
            log_level = logger.info if success else logger.error
            log_level(
                "工具调用: graph=%s, tool=%s, 耗时=%.2fms, 状态=%s",
                graph_id,
                tool_name,
                duration_ms,
                "成功" if success else "失败",
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录工具调用指标失败: %s", e)

    def record_cache_hit(self, graph_id: str, cache_name: str, **kwargs):
        """记录缓存命中"""
        try:
            metrics = self.metrics.get(graph_id)
            if not metrics:
                metrics = GraphMetrics(graph_id)
                self.metrics[graph_id] = metrics

            cache_metric = metrics.add_cache_metric(cache_name)
            cache_metric.record_hit()

            logger.debug(
                "缓存命中: graph=%s, cache=%s, 命中率=%.2f%%",
                graph_id,
                cache_name,
                cache_metric.hit_rate * 100,
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录缓存命中指标失败: %s", e)

    def record_cache_miss(self, graph_id: str, cache_name: str, **kwargs):
        """记录缓存未命中"""
        try:
            metrics = self.metrics.get(graph_id)
            if not metrics:
                metrics = GraphMetrics(graph_id)
                self.metrics[graph_id] = metrics

            cache_metric = metrics.add_cache_metric(cache_name)
            cache_metric.record_miss()

            logger.debug(
                "缓存未命中: graph=%s, cache=%s, 命中率=%.2f%%",
                graph_id,
                cache_name,
                cache_metric.hit_rate * 100,
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录缓存未命中指标失败: %s", e)

    def record_graph_invocation(self, graph_id: str, duration_ms: float, **kwargs):
        """记录图调用"""
        try:
            metrics = self.metrics.get(graph_id)
            if not metrics:
                metrics = GraphMetrics(graph_id)
                self.metrics[graph_id] = metrics

            metrics.record_invocation(duration_ms)

            logger.info(
                "图调用: graph=%s, 耗时=%.2fms, 平均耗时=%.2fms, 调用次数=%d",
                graph_id,
                duration_ms,
                metrics.avg_duration_ms,
                metrics.total_invocations,
                extra=kwargs,
            )

        except Exception as e:
            logger.exception("记录图调用指标失败: %s", e)

    def get_summary(self, graph_id: str) -> Dict[str, Any]:
        """获取性能摘要"""
        metrics = self.metrics.get(graph_id)
        if not metrics:
            return {"error": f"未找到图 {graph_id} 的指标"}

        summary = {
            "graph_id": metrics.graph_id,
            "total_invocations": metrics.total_invocations,
            "avg_duration_ms": round(metrics.avg_duration_ms, 2),
            "nodes": {},
            "tools": {},
            "caches": {},
        }

        # 节点指标
        for node_name, node_metric in metrics.node_metrics.items():
            summary["nodes"][node_name] = {
                "execution_count": node_metric.execution_count,
                "avg_time_ms": round(node_metric.avg_time_ms, 2),
                "error_count": node_metric.error_count,
                "error_rate": round(
                    node_metric.error_count / node_metric.execution_count * 100, 2
                )
                if node_metric.execution_count > 0
                else 0,
                "last_execution_time": node_metric.last_execution_time.isoformat()
                if node_metric.last_execution_time
                else None,
            }

        # 工具指标
        for tool_name, tool_metric in metrics.tool_metrics.items():
            summary["tools"][tool_name] = {
                "call_count": tool_metric.call_count,
                "avg_time_ms": round(tool_metric.avg_time_ms, 2),
                "error_count": tool_metric.error_count,
                "error_rate": round(
                    tool_metric.error_count / tool_metric.call_count * 100, 2
                )
                if tool_metric.call_count > 0
                else 0,
                "last_call_time": tool_metric.last_call_time.isoformat()
                if tool_metric.last_call_time
                else None,
            }

        # 缓存指标
        for cache_name, cache_metric in metrics.cache_metrics.items():
            summary["caches"][cache_name] = {
                "hit_count": cache_metric.hit_count,
                "miss_count": cache_metric.miss_count,
                "hit_rate": round(cache_metric.hit_rate * 100, 2),
                "total_size": cache_metric.total_size,
                "last_refresh_time": cache_metric.last_refresh_time.isoformat()
                if cache_metric.last_refresh_time
                else None,
            }

        return summary


# 全局监控器实例
performance_monitor = PerformanceMonitor()


# 装饰器函数
def monitor_node(graph_id: str = "default"):
    """节点执行监控装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                await performance_monitor.record_node_execution_async(
                    graph_id, func.__name__, duration_ms, success, **kwargs
                )

        return wrapper

    return decorator


def monitor_tool(graph_id: str = "default"):
    """工具调用监控装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                performance_monitor.record_tool_call(
                    graph_id, func.__name__, duration_ms, success, **kwargs
                )

        return wrapper

    return decorator


def monitor_cache(graph_id: str = "default"):
    """缓存监控装饰器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_name = func.__name__

            # 这里可以实现缓存逻辑，暂时只记录调用
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                # 根据参数判断是命中还是未命中
                # 这里简化处理，实际应根据缓存实现
                if "force_refresh" in kwargs and kwargs["force_refresh"]:
                    performance_monitor.record_cache_miss(
                        graph_id, cache_name, **kwargs
                    )
                else:
                    performance_monitor.record_cache_hit(graph_id, cache_name, **kwargs)

        return wrapper

    return decorator


# 快捷函数
async def get_performance_summary(graph_id: str = "default") -> Dict[str, Any]:
    """获取性能摘要"""
    return performance_monitor.get_summary(graph_id)


async def reset_metrics(graph_id: Optional[str] = None):
    """重置指标"""
    async with performance_monitor._lock:
        if graph_id:
            if graph_id in performance_monitor.metrics:
                del performance_monitor.metrics[graph_id]
                logger.info("重置性能指标: %s", graph_id)
        else:
            performance_monitor.metrics.clear()
            logger.info("重置所有性能指标")
