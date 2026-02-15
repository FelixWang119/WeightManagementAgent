# Redis缓存集成

## 概述

为体重管理助手应用实现的Redis缓存集成，提供高性能的缓存解决方案，用于优化数据库查询和计算密集型操作。

## 功能特性

- ✅ **异步Redis客户端**：使用`redis.asyncio`库，完全异步支持
- ✅ **连接池管理**：自动管理Redis连接池，支持连接复用
- ✅ **配置管理**：支持环境变量和配置文件覆盖
- ✅ **命名空间支持**：多应用/模块隔离的缓存命名空间
- ✅ **缓存装饰器**：自动缓存函数结果的装饰器
- ✅ **优雅降级**：Redis未连接时优雅处理，不中断应用
- ✅ **完整测试**：TDD开发，包含单元测试和集成测试
- ✅ **代码规范**：遵循项目编码标准和日志规范

## 文件结构

```
config/
├── redis_config.py          # Redis配置和缓存操作
├── settings.py             # 更新了Redis配置
└── logging_config.py       # 日志配置

tests/
└── test_redis_config.py    # Redis配置测试

examples/
└── redis_cache_example.py  # 使用示例

docs/
└── redis_cache_integration.md  # 本文档
```

## 核心组件

### 1. RedisConfig
基于Pydantic的配置类，支持环境变量覆盖：
```python
from config.redis_config import RedisConfig

config = RedisConfig()
print(config.host)  # localhost
print(config.port)  # 6379
print(config.connection_url)  # redis://localhost:6379/0
```

### 2. RedisCache
主要的缓存操作类：
```python
from config.redis_config import RedisCache

# 创建缓存实例
cache = RedisCache(namespace="weight_app")

# 基本操作
await cache.set("user:123", user_data, expire=300)
data = await cache.get("user:123")
exists = await cache.exists("user:123")
await cache.delete("user:123")

# 高级操作
ttl = await cache.ttl("user:123")
await cache.expire("user:123", 600)
await cache.incr("counter")
await cache.clear_namespace()
```

### 3. 缓存装饰器
自动缓存函数结果：
```python
from config.redis_config import cache_result

@cache_result(expire=60, namespace="calculations")
async def calculate_bmi(weight_kg: float, height_m: float) -> float:
    # 耗时的计算
    return weight_kg / (height_m ** 2)

# 第一次调用执行计算并缓存
bmi1 = await calculate_bmi(70.5, 1.75)

# 第二次相同参数调用从缓存获取
bmi2 = await calculate_bmi(70.5, 1.75)  # 从缓存获取
```

### 4. 便捷函数
```python
from config.redis_config import ping, set_value, get_value

# 检查连接
is_connected = await ping()

# 快速设置获取
await set_value("key", "value", expire=60)
value = await get_value("key", default="default")
```

## 配置

### 环境变量
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=secret
REDIS_MAX_CONNECTIONS=10
REDIS_ENABLED=true
```

### 配置文件
在`config/settings.py`中已添加Redis配置：
```python
# Redis缓存配置
REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
REDIS_DB: int = 0
REDIS_PASSWORD: Optional[str] = None
REDIS_MAX_CONNECTIONS: int = 10
REDIS_SOCKET_TIMEOUT: float = 5.0
REDIS_SOCKET_CONNECT_TIMEOUT: float = 5.0
REDIS_RETRY_ON_TIMEOUT: bool = True
REDIS_HEALTH_CHECK_INTERVAL: int = 30
REDIS_ENABLED: bool = True
```

## 使用示例

### 基本使用
```python
import asyncio
from config.redis_config import RedisCache

async def main():
    cache = RedisCache(namespace="app")
    
    # 检查连接
    if await cache.ping():
        print("Redis连接正常")
    
    # 缓存用户数据
    user_data = {"id": 1, "name": "张三", "weight": 70.5}
    await cache.set(f"user:{user_data['id']}", user_data, expire=300)
    
    # 获取缓存数据
    cached = await cache.get("user:1")
    print(f"用户数据: {cached}")

asyncio.run(main())
```

### 性能优化示例
```python
async def get_user_profile_cached(user_id: int):
    """带缓存的用户资料获取"""
    cache = RedisCache(namespace="profiles")
    cache_key = f"user_profile:{user_id}"
    
    # 尝试从缓存获取
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached
    
    # 缓存未命中，查询数据库
    profile = await database.query_user_profile(user_id)
    
    # 缓存结果（1小时）
    await cache.set(cache_key, profile, expire=3600)
    
    return profile
```

### 错误处理
```python
async def safe_cache_operation():
    cache = RedisCache()
    
    try:
        # 即使Redis未连接，也不会崩溃
        result = await cache.get("key", default="fallback")
        print(f"结果: {result}")
        
        # 设置操作返回成功状态
        success = await cache.set("key", "value")
        if not success:
            print("缓存设置失败，但应用继续运行")
            
    except Exception as e:
        print(f"缓存操作异常: {e}")
        # 应用可以优雅降级
```

## 测试

### 运行测试
```bash
# 运行所有测试
pytest tests/test_redis_config.py -v

# 运行单元测试
pytest tests/test_redis_config.py::TestRedisConfig -v

# 运行集成测试（需要Redis服务器）
pytest tests/test_redis_config.py::TestRedisIntegration -v -k integration
```

### 测试覆盖率
- ✅ Redis配置初始化
- ✅ 连接池单例模式
- ✅ 基本缓存操作（set/get/delete/exists）
- ✅ 高级操作（ttl/expire/incr/decr）
- ✅ 命名空间管理
- ✅ 缓存装饰器
- ✅ 错误处理
- ✅ 集成测试（优雅跳过无Redis服务器）

## 性能考虑

### 低配置机器优化
1. **连接池管理**：限制最大连接数，避免资源耗尽
2. **懒加载**：首次使用时才建立连接
3. **超时设置**：合理的socket超时防止阻塞
4. **优雅降级**：Redis不可用时不影响核心功能

### 缓存策略建议
1. **热点数据**：用户资料、配置信息等
2. **计算结果**：BMI计算、热量计算等
3. **会话数据**：用户会话、临时数据
4. **API响应**：频繁查询的API结果

## 部署指南

### 1. 安装依赖
```bash
pip install redis
```

### 2. 启动Redis服务器
```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Linux
sudo apt-get install redis-server
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. 验证连接
```bash
python -c "from config.redis_config import ping; import asyncio; print(asyncio.run(ping()))"
```

### 4. 配置调整
根据部署环境调整`config/settings.py`中的Redis配置：
- 生产环境：使用密码认证、调整连接数
- 容器环境：使用服务名作为主机
- 云环境：使用云Redis服务

## 故障排除

### 常见问题

1. **连接失败**
   - 检查Redis服务器是否运行：`redis-cli ping`
   - 检查防火墙和端口
   - 验证主机名和端口配置

2. **性能问题**
   - 调整连接池大小
   - 检查网络延迟
   - 监控Redis内存使用

3. **缓存不一致**
   - 确保缓存键唯一性
   - 合理设置过期时间
   - 考虑缓存穿透保护

### 监控建议
1. **连接状态**：定期检查`ping()`结果
2. **内存使用**：监控Redis内存占用
3. **命中率**：统计缓存命中率优化策略
4. **错误日志**：关注Redis相关错误日志

## 下一步计划

1. **缓存策略扩展**：LRU、LFU等高级策略
2. **分布式缓存**：Redis集群支持
3. **监控集成**：Prometheus指标导出
4. **缓存预热**：启动时预加载热点数据
5. **多级缓存**：Redis + 内存多级缓存

## 贡献指南

1. 遵循TDD开发流程
2. 保持代码风格一致（flake8检查）
3. 添加适当的测试用例
4. 更新相关文档
5. 性能敏感代码需有基准测试

## 许可证

本项目遵循MIT许可证。