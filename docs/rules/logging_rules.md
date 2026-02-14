# 日志规则

## 概述

本项目使用统一的日志配置和规则，确保日志记录的一致性、可读性和性能优化。

## 目录结构

```
logs/
├── 20250213.log          # 按日期命名的日志文件
├── test_20250213.log     # 测试日志
├── error_20250213.log    # 错误日志
└── .gitkeep              # 保持目录结构
```

## 日志配置

### 基本配置

```python
# 统一日志配置
from config.logging_config import setup_logging, get_module_logger

# 模块级初始化（每个模块一次）
logger = get_module_logger(__name__)
```

### 日志级别使用规范

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| `DEBUG` | 调试信息，仅开发使用 | `logger.debug("处理用户 %s 的数据", user_id)` |
| `INFO` | 关键流程节点 | `logger.info("开始选股分析")` |
| `WARNING` | 异常情况但不影响主流程 | `logger.warning("股票 %s 数据缺失", stock_code)` |
| `ERROR` | 功能失败，必须处理的问题 | `logger.error("API调用失败: %s", error)` |
| `CRITICAL` | 系统级严重错误 | `logger.critical("数据库连接失败")` |

## 最佳实践

### 1. 使用占位符而非字符串拼接

```python
# ✅ 推荐（性能优化）
logger.info("处理股票 %s，评分 %.2f", stock_code, score)

# ❌ 避免
logger.info(f"处理股票 {stock_code}，评分 {score}")
```

### 2. 异常记录

```python
try:
    result = process_data()
except DataError as e:
    logger.warning("获取 %s 数据失败: %s", symbol, e)
    return pd.DataFrame()
except Exception as e:
    logger.exception("处理数据时发生未知错误")  # 自动记录堆栈
    return {"error": str(e)}
```

### 3. 避免高频日志

```python
# ❌ 避免在循环中高频打印
for item in large_list:
    logger.debug("处理项目 %s", item)  # 可能产生大量日志
    
# ✅ 推荐使用采样或仅记录关键节点
if i % 100 == 0:
    logger.info("已处理 %d 个项目", i)
```

### 4. 上下文信息

```python
# 添加额外上下文信息
logger.info("用户登录成功", extra={
    "user_id": user.id,
    "ip_address": request.remote_addr,
    "user_agent": request.headers.get("User-Agent")
})
```

## 日志文件管理

### 文件命名规则

1. **按日期命名**: `YYYYMMDD.log` (如 `20250213.log`)
2. **按类型命名**: `type_YYYYMMDD.log` (如 `test_20250213.log`)
3. **按模块命名**: `module_YYYYMMDD.log` (如 `api_20250213.log`)

### 文件轮转

日志文件自动轮转策略：
- 按日期轮转：每天生成新文件
- 按大小轮转：单个文件超过 10MB 时轮转
- 保留最近 30 天的日志文件

### 清理策略

```bash
# 清理30天前的日志
find logs/ -name "*.log" -mtime +30 -delete

# 保留.gitkeep文件
find logs/ -name "*.log" -mtime +7 -exec rm {} \;
```

## 性能考虑

### 低配置机器优化

1. **减少DEBUG日志**: 生产环境使用 INFO 级别
2. **异步日志**: 使用异步日志处理器
3. **批量写入**: 配置适当的缓冲区大小
4. **选择性记录**: 仅记录关键业务逻辑

### 配置示例

```python
# config/logging_config.py
import logging
from logging.handlers import RotatingFileHandler
from config.paths import get_log_file

def setup_logging(level=logging.INFO, log_to_file=True):
    """设置日志配置"""
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    handlers = [console_handler]
    
    # 文件处理器（可选）
    if log_to_file:
        log_path = get_log_file()
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=level,
        handlers=handlers
    )
    
    # 减少第三方库的日志噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
```

## 测试日志

### 测试专用日志

```python
# 测试中使用专用日志文件
from config.paths import get_log_file

test_log_file = get_log_file("test", suffix=".log")
logging.basicConfig(
    filename=test_log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 日志断言

```python
import logging
import io

def test_log_output():
    """测试日志输出"""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    
    logger = logging.getLogger("test_logger")
    logger.addHandler(handler)
    
    # 执行测试
    logger.info("测试日志消息")
    
    # 验证日志
    assert "测试日志消息" in log_capture.getvalue()
```

## 安全注意事项

### 敏感信息保护

```python
# ❌ 避免记录敏感信息
logger.info("用户密码: %s", password)
logger.info("API密钥: %s", api_key)

# ✅ 使用掩码或哈希
logger.info("用户登录尝试: %s", user_id)
logger.info("API调用: %s", endpoint)
```

### 日志访问控制

1. **权限设置**: 日志文件设置为只读权限
2. **加密存储**: 敏感日志可加密存储
3. **访问审计**: 记录日志文件的访问记录

## 监控与告警

### 关键指标监控

1. **错误率**: ERROR 级别日志数量
2. **响应时间**: 关键操作耗时
3. **异常模式**: 特定错误模式出现频率

### 告警规则

```python
# 监控错误频率
error_count = count_errors_last_hour()
if error_count > 10:
    logger.critical("过去一小时错误数超过阈值: %d", error_count)
    # 触发告警
```

## 常见问题

### Q: 日志文件太大怎么办？
A: 启用日志轮转，定期清理旧日志文件。

### Q: 如何调试生产环境问题？
A: 临时提高日志级别，使用远程日志收集。

### Q: 日志影响性能怎么办？
A: 使用异步日志，减少不必要的DEBUG日志。

### Q: 如何统一日志格式？
A: 使用统一的日志配置模块，所有模块导入相同配置。

## 更新记录

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2025-02-13 | 1.0.0 | 初始版本，定义基本日志规则 |
| 2025-02-13 | 1.1.0 | 添加性能优化和安全注意事项 |