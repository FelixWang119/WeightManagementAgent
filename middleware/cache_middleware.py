"""
API响应缓存中间件

基于内存的简单缓存中间件，用于提高API响应性能。
遵循AGENTS.md中的编码标准和日志规范。
"""

import time
import hashlib
import json
from typing import Dict, Any, Optional, Tuple, Callable, AsyncIterator
from collections import OrderedDict
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class AsyncIteratorWrapper:
    """包装异步迭代器"""

    def __init__(self, data: list):
        self.data = data
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        result = self.data[self.index]
        self.index += 1
        return result


class LRUCache:
    """LRU缓存实现"""

    def __init__(self, maxsize: int = 1000):
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.maxsize = maxsize

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self.cache:
            return None

        value, expiry = self.cache[key]

        # 检查是否过期
        if expiry and time.time() > expiry:
            del self.cache[key]
            return None

        # 移动到最近使用的位置
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        expiry = time.time() + ttl if ttl else None

        if key in self.cache:
            self.cache.move_to_end(key)

        self.cache[key] = (value, expiry)

        # 如果超过最大大小，移除最旧的项
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """删除缓存项"""
        if key in self.cache:
            del self.cache[key]

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()

    def invalidate_pattern(self, pattern: str) -> None:
        """根据模式使缓存失效"""
        keys_to_delete = []
        for key in self.cache:
            if pattern in key:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache[key]


def generate_cache_key(request: Request) -> str:
    """
    生成缓存键

    基于请求方法、路径、查询参数和用户身份生成唯一缓存键。
    """
    # 基础部分：方法 + 路径
    key_parts = [request.method, request.url.path]

    # 添加查询参数（排序以确保一致性）
    if request.query_params:
        sorted_params = sorted(request.query_params.items())
        key_parts.append(str(sorted_params))

    # 添加用户身份（如果存在）
    # 注意：这里需要根据实际的身份验证系统调整
    user_id = (
        getattr(request.state, "user_id", None)
        if hasattr(request.state, "user_id")
        else None
    )
    if user_id:
        key_parts.append(f"user:{user_id}")

    # 生成哈希键
    key_string = ":".join(str(part) for part in key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


# 缓存配置：端点路径 -> TTL（秒）
CACHE_CONFIG = {
    "/api/user/profile": 300,  # 5分钟
    "/api/recipes": 1800,  # 30分钟
    "/api/achievements/achievements": 600,  # 10分钟
    "/api/habit/stats": 600,  # 10分钟
    "/api/sleep/analysis/dashboard": 600,  # 10分钟
}


class CacheMiddleware(BaseHTTPMiddleware):
    """缓存中间件"""

    def __init__(self, app: ASGIApp, max_cache_size: int = 1000):
        super().__init__(app)
        self.cache = LRUCache(maxsize=max_cache_size)
        logger.info("缓存中间件已初始化，最大缓存大小: %d", max_cache_size)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        处理请求，实现缓存逻辑
        """
        # 只缓存GET请求
        if request.method != "GET":
            return await call_next(request)

        # 检查是否是需要缓存的端点
        path = request.url.path
        ttl = None

        for cache_path, cache_ttl in CACHE_CONFIG.items():
            if path.startswith(cache_path):
                ttl = cache_ttl
                break

        if not ttl:
            # 不需要缓存的端点
            return await call_next(request)

        # 生成缓存键
        cache_key = generate_cache_key(request)

        # 尝试从缓存获取
        cached_response = self.cache.get(cache_key)

        if cached_response:
            # 缓存命中
            logger.debug("缓存命中: %s %s", request.method, path)
            response_data, headers = cached_response

            # 创建响应
            response = Response(
                content=json.dumps(response_data),
                media_type="application/json",
                headers=headers,
            )

            # 添加缓存头
            response.headers["X-Cache"] = "HIT"
            response.headers["Cache-Control"] = f"max-age={ttl}"

            return response

        # 缓存未命中，处理请求
        logger.debug("缓存未命中: %s %s", request.method, path)
        response = await call_next(request)

        # 只缓存成功的JSON响应
        if response.status_code == 200 and "application/json" in response.headers.get(
            "content-type", ""
        ):
            try:
                # 读取响应体
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk

                # 重新创建响应体迭代器
                response.body_iterator = AsyncIteratorWrapper([response_body])

                response_data = json.loads(response_body)

                # 准备缓存数据
                cache_headers = dict(response.headers)
                # 移除不适合缓存的头
                cache_headers.pop("content-length", None)
                cache_headers.pop("date", None)

                # 存储到缓存
                self.cache.set(cache_key, (response_data, cache_headers), ttl)
                logger.debug("已缓存响应: %s %s (TTL: %ds)", request.method, path, ttl)

                # 添加缓存头
                response.headers["X-Cache"] = "MISS"
                response.headers["Cache-Control"] = f"max-age={ttl}"

            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("无法缓存响应 %s %s: %s", request.method, path, e)
                # 添加缓存头表示未缓存
                response.headers["X-Cache"] = "SKIP"

        return response

    def invalidate_cache(self, pattern: str) -> None:
        """
        使匹配模式的缓存失效

        Args:
            pattern: 缓存键模式
        """
        self.cache.invalidate_pattern(pattern)
        logger.info("已使缓存失效: %s", pattern)

    def clear_cache(self) -> None:
        """清空所有缓存"""
        self.cache.clear()
        logger.info("已清空所有缓存")


# 缓存失效装饰器
def invalidate_cache(pattern: str):
    """
    装饰器：在函数执行后使匹配模式的缓存失效

    Args:
        pattern: 缓存键模式（如"/api/user/profile"）
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 执行函数
            result = (
                await func(*args, **kwargs) if callable(func) else func(*args, **kwargs)
            )

            # 使缓存失效
            # 注意：这里需要获取到缓存中间件实例
            # 在实际使用中，可能需要通过依赖注入或其他方式获取
            try:
                from main import app

                for middleware in app.user_middleware:
                    if (
                        hasattr(middleware.cls, "__name__")
                        and middleware.cls.__name__ == "CacheMiddleware"
                    ):
                        middleware.cls.invalidate_cache(pattern)
                        break
            except (ImportError, AttributeError) as e:
                logger.warning("无法使缓存失效 %s: %s", pattern, e)

            return result

        return wrapper

    return decorator


# 创建中间件实例的便捷函数
def create_cache_middleware(max_cache_size: int = 1000):
    """创建缓存中间件实例"""
    return CacheMiddleware


# 导出
__all__ = [
    "CacheMiddleware",
    "create_cache_middleware",
    "invalidate_cache",
    "generate_cache_key",
    "LRUCache",
]
