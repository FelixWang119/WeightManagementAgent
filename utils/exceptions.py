"""统一异常处理和装饰器模块

遵循 AGENTS.md 中的错误处理规范：
- 自定义异常类
- 统一错误处理装饰器
- 重试机制
- 事务上下文管理
"""

import functools
import logging
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union


# 获取 logger
logger = logging.getLogger(__name__)


# ============================================================================
# 自定义异常类
# ============================================================================

class AppError(Exception):
    """应用基础异常类"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            return f"[{self.error_code}] {self.message} - Context: {self.context}"
        return f"[{self.error_code}] {self.message}"


class ValidationError(AppError):
    """参数验证错误"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", context)


class DataError(AppError):
    """数据相关错误（数据库、文件、网络数据等）"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATA_ERROR", context)


class NetworkError(AppError):
    """网络相关错误"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, "NETWORK_ERROR", context)


class ConfigError(AppError):
    """配置相关错误"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", context)


class BusinessError(AppError):
    """业务逻辑错误"""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message, "BUSINESS_ERROR", context)


# ============================================================================
# 装饰器
# ============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    on_failure: Optional[Callable[[Exception], None]] = None
) -> Callable[[F], F]:
    """错误重试装饰器
    
    使用示例：
        @retry_on_error(max_attempts=3, delay=1.0)
        def fetch_data():
            return requests.get(url).json()
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟时间增长倍数
        exceptions: 捕获的异常类型
        on_retry: 重试时的回调函数
        on_failure: 最终失败时的回调函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        # 最后一次尝试失败
                        logger.error(
                            "%s 在 %d 次尝试后仍然失败: %s",
                            func.__name__, max_attempts, str(e)
                        )
                        if on_failure:
                            on_failure(e)
                        raise
                    
                    # 记录警告并等待
                    logger.warning(
                        "%s 第 %d/%d 次尝试失败: %s，%.1f秒后重试",
                        func.__name__, attempt, max_attempts, str(e), current_delay
                    )
                    
                    if on_retry:
                        on_retry(e, attempt)
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # 不应该执行到这里
            if last_exception:
                raise last_exception
            return None
        
        return wrapper
    return decorator


def error_handler(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    exceptions: Union[Type[Exception], tuple] = Exception
) -> Callable[[F], F]:
    """统一错误处理装饰器
    
    使用示例：
        @error_handler(default_return=None, log_level="warning")
        def process_data(data):
            return transform(data)
    
    Args:
        default_return: 出错时的默认返回值
        log_level: 日志级别 (debug/info/warning/error/critical)
        reraise: 是否重新抛出异常
        exceptions: 捕获的异常类型
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                # 记录日志
                log_func = getattr(logger, log_level.lower(), logger.error)
                log_func(
                    "%s 执行失败: %s\n%s",
                    func.__name__, str(e), traceback.format_exc()
                )
                
                if reraise:
                    raise
                
                return default_return
        
        return wrapper
    return decorator


def validate_input(
    validator: Callable[..., bool],
    error_message: str = "输入验证失败",
    exception_class: Type[Exception] = ValidationError
) -> Callable[[F], F]:
    """输入验证装饰器
    
    使用示例：
        @validate_input(lambda x: x > 0, "值必须大于0")
        def process(value):
            return value * 2
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not validator(*args, **kwargs):
                raise exception_class(error_message)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# 上下文管理器
# ============================================================================

@contextmanager
def error_context(
    operation_name: str,
    raise_on_error: bool = True,
    default_return: Any = None
):
    """错误处理上下文管理器
    
    使用示例：
        with error_context("数据库操作"):
            db.execute(query)
    
    Args:
        operation_name: 操作名称（用于日志）
        raise_on_error: 出错时是否抛出异常
        default_return: 不出错时的返回值
    """
    try:
        yield
    except Exception as e:
        logger.exception("%s 失败: %s", operation_name, str(e))
        if raise_on_error:
            raise AppError(f"{operation_name}失败: {str(e)}") from e


@contextmanager
def transaction_context(db_connection):
    """数据库事务上下文管理器
    
    使用示例：
        with transaction_context(db) as conn:
            conn.execute("INSERT ...")
            conn.commit()
    """
    try:
        yield db_connection
        db_connection.commit()
        logger.debug("事务提交成功")
    except Exception as e:
        db_connection.rollback()
        logger.error("事务回滚: %s", str(e))
        raise DataError(f"事务失败: {str(e)}") from e


@contextmanager
def timer_context(operation_name: str):
    """计时上下文管理器
    
    使用示例：
        with timer_context("数据处理"):
            process_large_data()
    """
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        logger.info("%s 耗时: %.3f秒", operation_name, elapsed)


# ============================================================================
# 保护函数
# ============================================================================

def protect_main(
    main_func: Callable[..., Any],
    exit_on_error: bool = True,
    error_code: int = 1
) -> Any:
    """保护主函数入口
    
    使用示例：
        if __name__ == "__main__":
            from utils.exceptions import protect_main
            protect_main(main)
    
    Args:
        main_func: 主函数
        exit_on_error: 出错时是否退出程序
        error_code: 错误退出码
    """
    try:
        return main_func()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        if exit_on_error:
            import sys
            sys.exit(130)
    except AppError as e:
        logger.error("程序错误: %s", str(e))
        if exit_on_error:
            import sys
            sys.exit(error_code)
    except Exception as e:
        logger.exception("程序发生未预期错误: %s", str(e))
        if exit_on_error:
            import sys
            sys.exit(error_code)


# ============================================================================
# 工具函数
# ============================================================================

def safe_get(
    obj: Dict[str, Any],
    key: str,
    default: Any = None,
    required: bool = False
) -> Any:
    """安全获取字典值
    
    Args:
        obj: 字典对象
        key: 键名
        default: 默认值
        required: 是否必需
    
    Returns:
        键值或默认值
    
    Raises:
        ValidationError: 如果 required=True 且键不存在
    """
    if key not in obj:
        if required:
            raise ValidationError(f"必需的参数缺失: {key}")
        return default
    return obj[key]


def validate_required(
    obj: Dict[str, Any],
    required_keys: list,
    context: str = "数据验证"
) -> None:
    """验证必需字段
    
    Args:
        obj: 字典对象
        required_keys: 必需的键列表
        context: 上下文信息
    
    Raises:
        ValidationError: 如果有必需字段缺失
    """
    missing = [key for key in required_keys if key not in obj or obj[key] is None]
    if missing:
        raise ValidationError(
            f"{context}: 缺少必需字段 {missing}",
            context={"missing_fields": missing}
        )


# ============================================================================
# 向后兼容
# ============================================================================

# 保留旧名称以便兼容
StockAnalysisError = BusinessError
DataFetchError = DataError
ConfigurationError = ConfigError


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试重试装饰器
    @retry_on_error(max_attempts=3, delay=0.5)
    def test_retry():
        import random
        if random.random() < 0.7:
            raise NetworkError("网络错误")
        return "成功"
    
    try:
        result = test_retry()
        print(f"重试测试结果: {result}")
    except Exception as e:
        print(f"重试测试失败: {e}")
    
    # 测试错误处理装饰器
    @error_handler(default_return="默认值", log_level="warning")
    def test_handler():
        raise ValueError("测试错误")
    
    result = test_handler()
    print(f"错误处理结果: {result}")
    
    # 测试上下文管理器
    with error_context("测试操作"):
        print("操作成功")
    
    print("\n所有测试完成")
