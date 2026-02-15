"""Redis缓存配置模块

提供异步Redis客户端连接池管理和缓存操作。
遵循项目日志标准和使用占位符而非f-string。
"""

import asyncio
from typing import Any, Optional
from functools import wraps

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from contextlib import asynccontextmanager

from config.logging_config import get_module_logger

# 获取模块级logger
logger = get_module_logger(__name__)

# 全局Redis客户端实例
_redis_client: Optional[Redis] = None
_redis_client_initialized: bool = False
_redis_lock = asyncio.Lock()


class RedisConfig(BaseSettings):
    """Redis配置类，支持环境变量覆盖"""

    host: str = Field(default="localhost", description="Redis主机地址")
    port: int = Field(default=6379, description="Redis端口")
    db: int = Field(default=0, description="Redis数据库编号")
    password: Optional[str] = Field(default=None, description="Redis密码")
    max_connections: int = Field(default=10, description="连接池最大连接数")
    socket_timeout: float = Field(default=5.0, description="Socket超时时间（秒）")
    socket_connect_timeout: float = Field(
        default=5.0, description="Socket连接超时时间（秒）"
    )
    retry_on_timeout: bool = Field(default=True, description="超时是否重试")
    health_check_interval: int = Field(default=30, description="健康检查间隔（秒）")

    model_config = SettingsConfigDict(
        env_prefix="REDIS_", case_sensitive=False, extra="ignore"
    )

    @property
    def connection_url(self) -> str:
        """生成Redis连接URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    def create_connection_pool(self) -> ConnectionPool:
        """创建Redis连接池"""
        return ConnectionPool.from_url(
            self.connection_url,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            retry_on_timeout=self.retry_on_timeout,
            health_check_interval=self.health_check_interval,
        )


async def get_redis_client() -> Redis:
    """获取Redis客户端单例（异步）

    使用连接池管理，确保线程安全。

    Returns:
        Redis客户端实例
    """
    global _redis_client, _redis_client_initialized

    # 双重检查锁模式（异步版本）
    if not _redis_client_initialized:
        async with _redis_lock:
            if not _redis_client_initialized:
                try:
                    config = RedisConfig()
                    logger.info(
                        "初始化Redis连接池 - 主机: %s, 端口: %d, 数据库: %d",
                        config.host,
                        config.port,
                        config.db,
                    )

                    # 创建连接池
                    pool = config.create_connection_pool()

                    # 创建Redis客户端
                    _redis_client = redis.Redis(
                        connection_pool=pool,
                        decode_responses=True,  # 自动解码响应
                    )

                    # 测试连接
                    is_connected = await _redis_client.ping()
                    if is_connected:
                        logger.info("Redis连接成功")
                        _redis_client_initialized = True
                    else:
                        logger.error("Redis连接测试失败")
                        _redis_client = None

                except Exception:
                    logger.exception("初始化Redis客户端时发生错误")
                    _redis_client = None
                    _redis_client_initialized = False
                    raise

    if _redis_client is None:
        raise ConnectionError("Redis客户端未初始化或初始化失败")

    return _redis_client


async def close_redis_connections() -> None:
    """关闭Redis连接池

    在应用关闭时调用，确保资源正确释放。
    """
    global _redis_client, _redis_client_initialized

    if _redis_client_initialized and _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.exception("关闭Redis连接时发生错误: %s", str(e))
        finally:
            _redis_client = None
            _redis_client_initialized = False


@asynccontextmanager
async def redis_context():
    """Redis上下文管理器

    示例用法:
        async with redis_context() as client:
            await client.set("key", "value")
    """
    client = await get_redis_client()
    try:
        yield client
    finally:
        # 注意：这里不关闭连接，连接由连接池管理
        pass


class RedisCache:
    """Redis缓存操作封装类"""

    def __init__(self, namespace: str = ""):
        """初始化缓存实例

        Args:
            namespace: 缓存命名空间，用于键名前缀
        """
        self.namespace = namespace
        self.logger = get_module_logger(f"{__name__}.RedisCache")

    def _build_key(self, key: str) -> str:
        """构建完整的缓存键名"""
        if self.namespace:
            return f"{self.namespace}:{key}"
        return key

    async def ping(self) -> bool:
        """检查Redis连接状态

        Returns:
            连接成功返回True，否则返回False
        """
        try:
            client = await get_redis_client()
            result = await client.ping()
            return bool(result)
        except Exception as e:
            self.logger.warning("Redis ping失败: %s", str(e))
            return False

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒），None表示永不过期

        Returns:
            设置成功返回True，否则返回False
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)

            if expire:
                result = await client.setex(full_key, expire, value)
            else:
                result = await client.set(full_key, value)

            success = bool(result)
            if success:
                self.logger.debug("设置缓存成功 - 键: %s, 过期: %s秒", full_key, expire)
            else:
                self.logger.warning("设置缓存失败 - 键: %s", full_key)

            return success

        except Exception:
            self.logger.exception("设置缓存时发生错误 - 键: %s", key)
            return False

    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值

        Args:
            key: 缓存键
            default: 缓存不存在时的默认值

        Returns:
            缓存值或默认值
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)
            value = await client.get(full_key)

            if value is not None:
                self.logger.debug("获取缓存成功 - 键: %s", full_key)
                return value

            self.logger.debug("缓存未命中 - 键: %s", full_key)
            return default

        except Exception:
            self.logger.exception("获取缓存时发生错误 - 键: %s", key)
            return default

    async def delete(self, key: str) -> int:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            删除的键数量
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)
            result = await client.delete(full_key)

            self.logger.debug("删除缓存 - 键: %s, 结果: %d", full_key, result)
            return result

        except Exception:
            self.logger.exception("删除缓存时发生错误 - 键: %s", key)
            return 0

    async def exists(self, key: str) -> int:
        """检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            存在返回1，不存在返回0
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)
            result = await client.exists(full_key)

            return result

        except Exception:
            self.logger.exception("检查缓存存在性时发生错误 - 键: %s", key)
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """设置缓存过期时间

        Args:
            key: 缓存键
            seconds: 过期时间（秒）

        Returns:
            设置成功返回True，否则返回False
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)
            result = await client.expire(full_key, seconds)

            success = bool(result)
            if success:
                self.logger.debug(
                    "设置缓存过期时间 - 键: %s, 秒数: %d", full_key, seconds
                )

            return success

        except Exception:
            self.logger.exception("设置缓存过期时间时发生错误 - 键: %s", key)
            return False

    async def ttl(self, key: str) -> int:
        """获取缓存剩余生存时间

        Args:
            key: 缓存键

        Returns:
            剩余生存时间（秒），-1表示永不过期，-2表示键不存在
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)
            result = await client.ttl(full_key)

            return result

        except Exception:
            self.logger.exception("获取缓存TTL时发生错误 - 键: %s", key)
            return -2

    async def incr(self, key: str, amount: int = 1) -> int:
        """递增缓存值

        Args:
            key: 缓存键
            amount: 递增数量

        Returns:
            递增后的值
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)

            if amount == 1:
                result = await client.incr(full_key)
            else:
                result = await client.incrby(full_key, amount)

            self.logger.debug(
                "递增缓存值 - 键: %s, 数量: %d, 结果: %d", full_key, amount, result
            )
            return result

        except Exception:
            self.logger.exception("递增缓存值时发生错误 - 键: %s", key)
            return 0

    async def decr(self, key: str, amount: int = 1) -> int:
        """递减缓存值

        Args:
            key: 缓存键
            amount: 递减数量

        Returns:
            递减后的值
        """
        try:
            client = await get_redis_client()
            full_key = self._build_key(key)

            if amount == 1:
                result = await client.decr(full_key)
            else:
                result = await client.decrby(full_key, amount)

            self.logger.debug(
                "递减缓存值 - 键: %s, 数量: %d, 结果: %d", full_key, amount, result
            )
            return result

        except Exception:
            self.logger.exception("递减缓存值时发生错误 - 键: %s", key)
            return 0

    async def clear_namespace(self) -> int:
        """清除当前命名空间下的所有缓存

        Returns:
            删除的键数量
        """
        if not self.namespace:
            self.logger.warning("未指定命名空间，跳过清除操作")
            return 0

        try:
            client = await get_redis_client()
            pattern = f"{self.namespace}:*"

            # 获取所有匹配的键
            keys = await client.keys(pattern)

            if not keys:
                self.logger.debug("命名空间 %s 下没有缓存键", self.namespace)
                return 0

            # 批量删除
            result = await client.delete(*keys)
            self.logger.info(
                "清除命名空间缓存 - 命名空间: %s, 删除键数: %d", self.namespace, result
            )
            return result

        except Exception:
            self.logger.exception(
                "清除命名空间缓存时发生错误 - 命名空间: %s", self.namespace
            )
            return 0


def cache_result(expire: int = 300, namespace: str = "cache"):
    """缓存装饰器

    将函数结果缓存到Redis中。

    Args:
        expire: 缓存过期时间（秒），默认5分钟
        namespace: 缓存命名空间

    Returns:
        装饰器函数
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键（基于函数名和参数）
            import hashlib
            import pickle

            # 序列化参数
            key_parts = [
                func.__module__,
                func.__name__,
                str(args),
                str(sorted(kwargs.items())),
            ]
            key_str = ":".join(key_parts)

            # 生成MD5哈希作为缓存键
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            cache_key = f"{namespace}:{func.__name__}:{key_hash}"

            # 创建缓存实例
            cache = RedisCache(namespace=namespace)

            # 尝试从缓存获取
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug("缓存命中 - 函数: %s, 键: %s", func.__name__, cache_key)
                try:
                    # 反序列化缓存结果
                    return pickle.loads(cached_result)
                except Exception as e:
                    logger.warning("反序列化缓存结果失败: %s", str(e))
                    # 缓存损坏，继续执行函数

            # 缓存未命中，执行函数
            logger.debug("缓存未命中 - 函数: %s, 键: %s", func.__name__, cache_key)
            result = await func(*args, **kwargs)

            # 缓存结果
            try:
                serialized_result = pickle.dumps(result)
                await cache.set(cache_key, serialized_result, expire=expire)
                logger.debug(
                    "缓存设置成功 - 函数: %s, 键: %s, 过期: %d秒",
                    func.__name__,
                    cache_key,
                    expire,
                )
            except Exception as e:
                logger.warning("缓存结果失败: %s", str(e))

            return result

        return wrapper

    return decorator


# 便捷函数
async def ping() -> bool:
    """检查Redis连接状态（便捷函数）"""
    cache = RedisCache()
    return await cache.ping()


async def set_value(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """设置缓存值（便捷函数）"""
    cache = RedisCache()
    return await cache.set(key, value, expire)


async def get_value(key: str, default: Any = None) -> Any:
    """获取缓存值（便捷函数）"""
    cache = RedisCache()
    return await cache.get(key, default)


async def delete_key(key: str) -> int:
    """删除缓存键（便捷函数）"""
    cache = RedisCache()
    return await cache.delete(key)


async def key_exists(key: str) -> int:
    """检查键是否存在（便捷函数）"""
    cache = RedisCache()
    return await cache.exists(key)


# 导出主要类和函数
__all__ = [
    "RedisConfig",
    "get_redis_client",
    "close_redis_connections",
    "redis_context",
    "RedisCache",
    "cache_result",
    "ping",
    "set_value",
    "get_value",
    "delete_key",
    "key_exists",
]
