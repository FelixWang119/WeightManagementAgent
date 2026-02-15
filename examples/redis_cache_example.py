#!/usr/bin/env python3
"""Redis缓存使用示例

演示如何在体重管理助手应用中使用Redis缓存。
"""

import asyncio
import time
from config.redis_config import RedisCache, cache_result


async def example_basic_cache():
    """基本缓存使用示例"""
    print("=== 基本缓存使用示例 ===")

    # 创建缓存实例
    cache = RedisCache(namespace="weight_app")

    # 检查Redis连接
    is_connected = await cache.ping()
    if not is_connected:
        print("⚠️  Redis未连接，使用内存回退或跳过缓存")
        return

    print("✅ Redis连接正常")

    # 设置缓存
    user_data = {"user_id": 123, "name": "张三", "weight": 70.5, "target_weight": 65.0}

    await cache.set("user:123", user_data, expire=300)  # 5分钟过期
    print("✅ 用户数据已缓存")

    # 获取缓存
    cached_data = await cache.get("user:123")
    print(f"✅ 从缓存获取用户数据: {cached_data}")

    # 检查缓存是否存在
    exists = await cache.exists("user:123")
    print(f"✅ 缓存存在性检查: {exists}")

    # 获取TTL
    ttl = await cache.ttl("user:123")
    print(f"✅ 缓存剩余生存时间: {ttl}秒")

    # 删除缓存
    await cache.delete("user:123")
    print("✅ 缓存已删除")

    # 清理命名空间
    await cache.clear_namespace()
    print("✅ 命名空间已清理")


async def example_cache_decorator():
    """缓存装饰器使用示例"""
    print("\n=== 缓存装饰器使用示例 ===")

    # 模拟一个耗时的计算函数
    @cache_result(expire=60, namespace="calculations")
    async def calculate_bmi(weight_kg: float, height_m: float) -> float:
        """计算BMI（体重指数）"""
        print(f"📊 计算BMI: weight={weight_kg}kg, height={height_m}m")
        await asyncio.sleep(0.5)  # 模拟耗时计算
        bmi = weight_kg / (height_m**2)
        return round(bmi, 2)

    # 第一次调用 - 应该执行计算
    start_time = time.time()
    bmi1 = await calculate_bmi(70.5, 1.75)
    elapsed1 = time.time() - start_time
    print(f"第一次调用 - BMI: {bmi1}, 耗时: {elapsed1:.2f}秒")

    # 第二次调用相同参数 - 应该从缓存获取
    start_time = time.time()
    bmi2 = await calculate_bmi(70.5, 1.75)
    elapsed2 = time.time() - start_time
    print(f"第二次调用 - BMI: {bmi2}, 耗时: {elapsed2:.2f}秒")

    # 第三次调用不同参数 - 应该重新计算
    start_time = time.time()
    bmi3 = await calculate_bmi(65.0, 1.75)
    elapsed3 = time.time() - start_time
    print(f"第三次调用 - BMI: {bmi3}, 耗时: {elapsed3:.2f}秒")

    if elapsed2 < elapsed1:
        print("✅ 缓存装饰器工作正常 - 第二次调用更快")
    else:
        print("⚠️  缓存可能未生效")


async def example_performance_cache():
    """性能优化缓存示例"""
    print("\n=== 性能优化缓存示例 ===")

    cache = RedisCache(namespace="performance")

    # 模拟数据库查询
    async def query_user_weights(user_id: int) -> list:
        """模拟数据库查询用户体重记录"""
        print(f"🗃️  查询数据库: user_id={user_id}")
        await asyncio.sleep(1.0)  # 模拟慢查询
        return [
            {"date": "2024-01-01", "weight": 72.0},
            {"date": "2024-01-08", "weight": 71.5},
            {"date": "2024-01-15", "weight": 70.5},
        ]

    # 使用缓存包装数据库查询
    async def get_user_weights_cached(user_id: int) -> list:
        cache_key = f"user_weights:{user_id}"

        # 尝试从缓存获取
        cached = await cache.get(cache_key)
        if cached is not None:
            print(f"✅ 从缓存获取用户体重记录: user_id={user_id}")
            return cached

        # 缓存未命中，查询数据库
        print(f"🔄 缓存未命中，查询数据库: user_id={user_id}")
        weights = await query_user_weights(user_id)

        # 将结果缓存1小时
        await cache.set(cache_key, weights, expire=3600)
        print(f"✅ 用户体重记录已缓存: user_id={user_id}")

        return weights

    # 测试
    print("第一次获取用户体重记录...")
    weights1 = await get_user_weights_cached(123)
    print(f"结果: {len(weights1)} 条记录")

    print("\n第二次获取相同用户体重记录（应该从缓存获取）...")
    weights2 = await get_user_weights_cached(123)
    print(f"结果: {len(weights2)} 条记录")

    print("\n获取不同用户体重记录...")
    weights3 = await get_user_weights_cached(456)
    print(f"结果: {len(weights3)} 条记录")

    # 清理
    await cache.clear_namespace()


async def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")

    cache = RedisCache(namespace="error_test")

    # 测试Redis未连接的情况
    is_connected = await cache.ping()
    if not is_connected:
        print("⚠️  Redis未连接，演示优雅降级")

        # 即使Redis未连接，代码也不应该崩溃
        try:
            result = await cache.get("nonexistent_key", default="fallback_value")
            print(f"✅ 优雅降级: 获取缓存返回默认值: {result}")

            # 设置缓存应该失败但不崩溃
            success = await cache.set("test_key", "test_value")
            print(f"✅ 设置缓存返回: {success} (预期为False)")

        except Exception as e:
            print(f"❌ 错误处理失败: {e}")
    else:
        print("✅ Redis连接正常，错误处理测试跳过")


async def main():
    """主函数"""
    print("Redis缓存使用示例\n")

    examples = [
        ("基本缓存", example_basic_cache),
        ("缓存装饰器", example_cache_decorator),
        ("性能优化", example_performance_cache),
        ("错误处理", example_error_handling),
    ]

    for name, example_func in examples:
        print(f"\n{'=' * 50}")
        print(f"运行示例: {name}")
        print("=" * 50)
        try:
            await example_func()
        except Exception as e:
            print(f"❌ 示例运行失败: {e}")

    print("\n" + "=" * 50)
    print("所有示例完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
