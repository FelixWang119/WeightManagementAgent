"""
性能监控工具

用于收集和报告关键性能指标，帮助识别瓶颈。
适用于低配置机器，轻量级设计。
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import statistics
import threading
from collections import defaultdict, deque

# 全局性能存储
_perf_metrics = defaultdict(lambda: defaultdict(list))
_perf_lock = threading.RLock()


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, name: str, max_samples: int = 100):
        self.name = name
        self.max_samples = max_samples
        self.timings = deque(maxlen=max_samples)
        self.errors = deque(maxlen=50)
        self.call_count = 0
        self.error_count = 0

    def record_time(self, duration: float):
        """记录执行时间"""
        with _perf_lock:
            self.timings.append(duration)
            self.call_count += 1

    def record_error(self, error: str):
        """记录错误"""
        with _perf_lock:
            self.errors.append(error)
            self.error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with _perf_lock:
            if not self.timings:
                return {
                    "name": self.name,
                    "call_count": self.call_count,
                    "error_count": self.error_count,
                    "latest_errors": list(self.errors),
                }

            return {
                "name": self.name,
                "call_count": self.call_count,
                "error_count": self.error_count,
                "avg_time_ms": statistics.mean(self.timings) * 1000,
                "min_time_ms": min(self.timings) * 1000,
                "max_time_ms": max(self.timings) * 1000,
                "p50_ms": statistics.quantiles(self.timings, n=4)[1] * 1000,
                "p95_ms": statistics.quantiles(self.timings, n=20)[18] * 1000
                if len(self.timings) >= 20
                else None,
                "latest_errors": list(self.errors)[-5:],  # 最近5个错误
            }


# 全局监控器注册表
_monitors: Dict[str, PerformanceMonitor] = {}
_monitors_lock = threading.RLock()


def get_monitor(name: str) -> PerformanceMonitor:
    """获取或创建性能监控器"""
    with _monitors_lock:
        if name not in _monitors:
            _monitors[name] = PerformanceMonitor(name)
        return _monitors[name]


def measure_time(name: Optional[str] = None):
    """
    执行时间测量装饰器

    使用示例:
    ```python
    @measure_time("database_query")
    def query_data():
        ...

    @measure_time()
    async def async_operation():
        ...
    ```
    """

    def decorator(func):
        monitor_name = name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                monitor = get_monitor(monitor_name)
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    monitor.record_time(time.perf_counter() - start_time)
                    return result
                except Exception as e:
                    monitor.record_error(str(e))
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                monitor = get_monitor(monitor_name)
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    monitor.record_time(time.perf_counter() - start_time)
                    return result
                except Exception as e:
                    monitor.record_error(str(e))
                    raise

            return sync_wrapper

    return decorator


def measure_time_ctx(name: str):
    """
    上下文管理器版本的时间测量

    使用示例:
    ```python
    with measure_time_ctx("expensive_calculation"):
        # 执行耗时操作
        ...
    ```
    """

    class TimingContext:
        def __init__(self, monitor_name: str):
            self.monitor_name = monitor_name
            self.monitor = get_monitor(monitor_name)
            self.start_time = None

        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.perf_counter() - self.start_time
            self.monitor.record_time(duration)
            if exc_type is not None:
                self.monitor.record_error(str(exc_val))

    return TimingContext(name)


async def measure_time_async_ctx(name: str):
    """
    异步上下文管理器版本的时间测量

    使用示例:
    ```python
    async with measure_time_async_ctx("database_operation") as timer:
        # 执行异步耗时操作
        ...
    ```
    """
    monitor = get_monitor(name)
    start_time = time.perf_counter()

    class AsyncTimingContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            duration = time.perf_counter() - start_time
            monitor.record_time(duration)
            if exc_type is not None:
                monitor.record_error(str(exc_val))

    return AsyncTimingContext()


def get_all_metrics() -> Dict[str, Dict[str, Any]]:
    """获取所有监控器的指标"""
    with _monitors_lock:
        return {name: monitor.get_stats() for name, monitor in _monitors.items()}


def get_slow_operations(threshold_ms: float = 100.0) -> Dict[str, Dict[str, Any]]:
    """获取执行时间超过阈值的操作"""
    slow_ops = {}
    for name, monitor in _monitors.items():
        stats = monitor.get_stats()
        avg_time = stats.get("avg_time_ms")
        if avg_time and avg_time > threshold_ms:
            slow_ops[name] = stats
    return slow_ops


def clear_metrics(name: Optional[str] = None):
    """清除指标数据"""
    with _monitors_lock:
        if name:
            if name in _monitors:
                _monitors.pop(name)
        else:
            _monitors.clear()


# 关键路径监控点
CRITICAL_PATHS = {
    "memory_manager.load_checkins": "加载打卡记录到短期记忆",
    "memory_manager.add_message": "添加消息到记忆系统",
    "memory_manager.get_context": "获取上下文",
    "vector_store.add_documents": "向量存储添加文档",
    "vector_store.similarity_search": "向量存储相似性搜索",
    "embedding.compute": "嵌入向量计算",
    "ai_service.generate": "AI服务生成",
    "notification_scheduler.check": "通知调度检查",
    "checkin_sync.sync_user": "打卡记录同步",
}


def monitor_critical_path(name: str, description: Optional[str] = None):
    """
    监控关键路径的装饰器

    使用示例:
    ```python
    @monitor_critical_path("memory_manager.add_message")
    async def add_message(...):
        ...
    """
    path_desc = description or CRITICAL_PATHS.get(name, name)

    def decorator(func):
        monitor_name = f"critical.{name}"

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with measure_time_ctx(monitor_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with measure_time_ctx(monitor_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def report_performance():
    """生成性能报告"""
    all_metrics = get_all_metrics()
    if not all_metrics:
        return "暂无性能数据"

    report_lines = ["=== 性能报告 ==="]

    # 按平均执行时间排序
    sorted_metrics = sorted(
        [
            (name, stats)
            for name, stats in all_metrics.items()
            if stats.get("avg_time_ms")
        ],
        key=lambda x: x[1]["avg_time_ms"],
        reverse=True,
    )

    for name, stats in sorted_metrics[:10]:  # 前10个最慢的操作
        report_lines.append(
            f"{name}: {stats['avg_time_ms']:.1f}ms (调用{stats['call_count']}次)"
        )

    # 检查慢操作
    slow_ops = get_slow_operations(threshold_ms=500.0)
    if slow_ops:
        report_lines.append("\n=== 警告：慢操作（>500ms）===")
        for name, stats in slow_ops.items():
            report_lines.append(f"⚠️  {name}: {stats['avg_time_ms']:.1f}ms")

    # 错误统计
    error_ops = [
        (name, stats)
        for name, stats in all_metrics.items()
        if stats.get("error_count", 0) > 0
    ]
    if error_ops:
        report_lines.append("\n=== 错误统计 ===")
        for name, stats in error_ops:
            report_lines.append(f"❌ {name}: {stats['error_count']}次错误")

    return "\n".join(report_lines)
