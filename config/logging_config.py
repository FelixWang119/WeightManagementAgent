"""统一日志配置模块

遵循 AGENTS.md 中的日志规范：
- 统一使用 get_module_logger 获取 logger
- 支持文件和控制台双输出
- 低配置机器优化（异步日志）
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# 默认配置
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5

# 日志级别映射
LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（仅控制台）"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",  # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始级别名称
        original_levelname = record.levelname

        # 添加颜色
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            reset_color = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset_color}"

        # 格式化
        result = super().format(record)

        # 恢复原始级别名称
        record.levelname = original_levelname

        return result


class AlertFilter(logging.Filter):
    """告警过滤器 - 只允许WARNING及以上级别通过"""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING


def setup_logging(
    log_dir: str = DEFAULT_LOG_DIR,
    log_level: int = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    console_output: bool = True,
    file_output: bool = True,
    enable_alert_log: bool = True,
) -> None:
    """设置统一日志配置

    Args:
        log_dir: 日志文件目录
        log_level: 日志级别
        log_format: 日志格式
        date_format: 日期格式
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        enable_alert_log: 是否启用告警日志
    """
    # 创建日志目录
    if file_output:
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # 文件处理器
    if file_output:
        # 当前日期作为文件名
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"app_{current_date}.log")

        # 使用 RotatingFileHandler 防止日志文件过大
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # 错误日志单独文件
        error_log_file = os.path.join(log_dir, f"error_{current_date}.log")
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

        # 告警日志单独文件（WARNING及以上级别）
        if enable_alert_log:
            alert_log_file = os.path.join(log_dir, "alert.log")
            alert_handler = logging.handlers.RotatingFileHandler(
                alert_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            alert_handler.setLevel(logging.WARNING)
            alert_handler.setFormatter(file_formatter)
            alert_handler.name = "alert_handler"

            # 添加告警过滤器
            alert_filter = AlertFilter()
            alert_handler.addFilter(alert_filter)

            root_logger.addHandler(alert_handler)

    # 设置第三方库日志级别（减少噪音）
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    # 设置SQLAlchemy日志级别（大幅减少数据库操作日志）
    # 只显示WARNING及以上级别的日志
    sqlalchemy_loggers = [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
        "sqlalchemy.dialects.sqlite",
    ]
    for logger_name in sqlalchemy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # 记录日志系统初始化完成
    root_logger.info(
        "日志系统初始化完成 - 级别: %s, 目录: %s",
        logging.getLevelName(log_level),
        log_dir,
    )


def get_module_logger(module_name: Optional[str] = None) -> logging.Logger:
    """获取模块级 logger

    使用示例：
        logger = get_module_logger(__name__)
        logger.info("处理开始")

    Args:
        module_name: 模块名，通常传 __name__

    Returns:
        配置好的 logger 实例
    """
    if module_name is None:
        # 如果没有提供模块名，尝试从调用栈获取
        import inspect

        frame = inspect.currentframe()
        if frame and frame.f_back:
            module_name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            module_name = "unknown"

    logger = logging.getLogger(module_name)

    # 如果 logger 还没有处理器，且根 logger 也没有，设置默认配置
    if not logger.handlers and not logging.getLogger().handlers:
        setup_logging()

    return logger


def set_log_level(level: str) -> None:
    """动态设置日志级别

    Args:
        level: 日志级别字符串 (debug/info/warning/error/critical)
    """
    log_level = LOG_LEVEL_MAP.get(level.lower(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    # 更新所有处理器的级别
    for handler in logging.getLogger().handlers:
        handler.setLevel(log_level)

    logging.info("日志级别已设置为: %s", level.upper())


# 便捷函数
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """get_module_logger 的别名"""
    return get_module_logger(name)


# 模块级 logger（供 config 模块内部使用）
logger = get_module_logger(__name__)


if __name__ == "__main__":
    # 测试代码
    setup_logging()

    test_logger = get_module_logger(__name__)
    test_logger.debug("这是一条 DEBUG 日志")
    test_logger.info("这是一条 INFO 日志")
    test_logger.warning("这是一条 WARNING 日志")
    test_logger.error("这是一条 ERROR 日志")
    test_logger.exception("这是一条 EXCEPTION 日志（带堆栈）")

    print("\n日志测试完成，请查看 logs/ 目录")
