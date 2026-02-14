"""告警工具模块

提供统一的告警发送接口，支持结构化告警数据记录。
遵循项目日志规范，使用占位符而非f-string，考虑低配置机器性能。

使用示例：
    from utils.alert_utils import send_alert, AlertLevel, AlertCategory

    # 发送数据库错误告警
    send_alert(
        level=AlertLevel.ERROR,
        category=AlertCategory.DATABASE,
        message="数据库连接失败",
        details={"host": "localhost", "port": 5432},
        module="database_service",
        user_id="user_001"
    )

    # 使用快捷函数
    from utils.alert_utils import alert_error, alert_warning

    alert_error(
        category="API",
        message="API调用失败",
        details={"endpoint": "/api/users", "status_code": 500}
    )
"""

import json
import logging
from enum import Enum
from typing import Optional, Dict, Any, Union
from datetime import datetime

from config.logging_config import get_module_logger


class AlertLevel(Enum):
    """告警级别枚举"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __gt__(self, other: "AlertLevel") -> bool:
        """比较告警级别严重程度"""
        level_order = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        return level_order[self.value] > level_order[other.value]

    def __lt__(self, other: "AlertLevel") -> bool:
        """比较告警级别严重程度"""
        level_order = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        return level_order[self.value] < level_order[other.value]


class AlertCategory(Enum):
    """告警分类枚举"""

    SYSTEM = "SYSTEM"  # 系统级告警
    DATABASE = "DATABASE"  # 数据库相关
    API = "API"  # API接口相关
    AI_SERVICE = "AI_SERVICE"  # AI服务相关
    BUSINESS = "BUSINESS"  # 业务逻辑相关
    SECURITY = "SECURITY"  # 安全相关
    PERFORMANCE = "PERFORMANCE"  # 性能相关


# 模块级logger - 使用根logger确保告警处理器生效
_alert_logger = logging.getLogger()


def get_alert_logger() -> logging.Logger:
    """获取告警专用的logger

    Returns:
        配置好的告警logger实例
    """
    return _alert_logger


def send_alert(
    level: Union[AlertLevel, str],
    category: Union[AlertCategory, str],
    message: str,
    details: Optional[Dict[str, Any]] = None,
    module: Optional[str] = None,
    user_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """发送告警

    Args:
        level: 告警级别，可以是AlertLevel枚举或字符串
        category: 告警分类，可以是AlertCategory枚举或字符串
        message: 告警消息
        details: 详细的告警数据（字典格式）
        module: 触发告警的模块名
        user_id: 相关用户ID（如果有）
        logger: 可选的logger实例，默认使用告警专用logger

    Raises:
        ValueError: 当参数无效时
    """
    # 使用提供的logger或默认告警logger
    alert_logger = logger or _alert_logger

    # 参数验证和转换
    if isinstance(level, str):
        try:
            level = AlertLevel(level.upper())
        except ValueError:
            raise ValueError(f"无效的告警级别: {level}")

    if isinstance(category, str):
        try:
            category = AlertCategory(category.upper())
        except ValueError:
            # 如果不是预定义的分类，使用原字符串
            pass

    # 构建结构化告警数据
    alert_data = {
        "timestamp": datetime.now().isoformat(),
        "level": level.value if isinstance(level, AlertLevel) else str(level),
        "category": category.value
        if isinstance(category, AlertCategory)
        else str(category),
        "message": message,
        "module": module or "unknown",
        "user_id": user_id or "unknown",
        "details": details or {},
    }

    # 将details转换为JSON字符串（用于日志占位符）
    details_json = json.dumps(alert_data["details"], ensure_ascii=False)

    # 根据级别选择日志方法
    log_method = {
        AlertLevel.INFO: alert_logger.info,
        AlertLevel.WARNING: alert_logger.warning,
        AlertLevel.ERROR: alert_logger.error,
        AlertLevel.CRITICAL: alert_logger.critical,
    }.get(
        level if isinstance(level, AlertLevel) else AlertLevel(level.value),
        alert_logger.info,
    )

    # 使用占位符记录日志（避免f-string，遵循性能优化规范）
    log_method(
        "ALERT - 级别: %s, 分类: %s, 模块: %s, 用户: %s, 消息: %s, 详情: %s",
        alert_data["level"],
        alert_data["category"],
        alert_data["module"],
        alert_data["user_id"],
        alert_data["message"],
        details_json,
    )


def alert_error(
    category: Union[AlertCategory, str],
    message: str,
    details: Optional[Dict[str, Any]] = None,
    module: Optional[str] = None,
    user_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """发送错误级别告警（快捷函数）

    Args:
        category: 告警分类
        message: 告警消息
        details: 详细的告警数据
        module: 触发告警的模块名
        user_id: 相关用户ID
        logger: 可选的logger实例
    """
    send_alert(
        level=AlertLevel.ERROR,
        category=category,
        message=message,
        details=details,
        module=module,
        user_id=user_id,
        logger=logger,
    )


def alert_warning(
    category: Union[AlertCategory, str],
    message: str,
    details: Optional[Dict[str, Any]] = None,
    module: Optional[str] = None,
    user_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """发送警告级别告警（快捷函数）

    Args:
        category: 告警分类
        message: 告警消息
        details: 详细的告警数据
        module: 触发告警的模块名
        user_id: 相关用户ID
        logger: 可选的logger实例
    """
    send_alert(
        level=AlertLevel.WARNING,
        category=category,
        message=message,
        details=details,
        module=module,
        user_id=user_id,
        logger=logger,
    )


def alert_critical(
    category: Union[AlertCategory, str],
    message: str,
    details: Optional[Dict[str, Any]] = None,
    module: Optional[str] = None,
    user_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """发送严重级别告警（快捷函数）

    Args:
        category: 告警分类
        message: 告警消息
        details: 详细的告警数据
        module: 触发告警的模块名
        user_id: 相关用户ID
        logger: 可选的logger实例
    """
    send_alert(
        level=AlertLevel.CRITICAL,
        category=category,
        message=message,
        details=details,
        module=module,
        user_id=user_id,
        logger=logger,
    )


def alert_info(
    category: Union[AlertCategory, str],
    message: str,
    details: Optional[Dict[str, Any]] = None,
    module: Optional[str] = None,
    user_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """发送信息级别告警（快捷函数）

    Args:
        category: 告警分类
        message: 告警消息
        details: 详细的告警数据
        module: 触发告警的模块名
        user_id: 相关用户ID
        logger: 可选的logger实例
    """
    send_alert(
        level=AlertLevel.INFO,
        category=category,
        message=message,
        details=details,
        module=module,
        user_id=user_id,
        logger=logger,
    )


# 导出常用函数和枚举
__all__ = [
    "AlertLevel",
    "AlertCategory",
    "get_alert_logger",
    "send_alert",
    "alert_error",
    "alert_warning",
    "alert_critical",
    "alert_info",
]


if __name__ == "__main__":
    """模块测试代码"""
    from config.logging_config import setup_logging

    # 初始化日志
    setup_logging()

    # 测试各种告警
    print("测试告警工具模块...")

    # 测试不同级别的告警
    send_alert(
        level=AlertLevel.INFO,
        category=AlertCategory.SYSTEM,
        message="系统启动测试",
        details={"version": "1.0.0", "environment": "test"},
    )

    send_alert(
        level=AlertLevel.WARNING,
        category=AlertCategory.API,
        message="API响应缓慢",
        details={"endpoint": "/api/test", "response_time": 3.5},
    )

    send_alert(
        level=AlertLevel.ERROR,
        category=AlertCategory.DATABASE,
        message="数据库连接失败",
        details={"host": "localhost", "port": 5432, "error": "connection refused"},
    )

    send_alert(
        level=AlertLevel.CRITICAL,
        category=AlertCategory.SECURITY,
        message="安全漏洞检测",
        details={"vulnerability": "CVE-2024-1234", "severity": "high"},
    )

    # 测试快捷函数
    alert_info(
        category="BUSINESS",
        message="业务处理完成",
        details={"processed_items": 100, "success_rate": 0.95},
    )

    alert_warning(
        category="PERFORMANCE",
        message="内存使用过高",
        details={"memory_usage": "85%", "threshold": "80%"},
    )

    alert_error(
        category="AI_SERVICE",
        message="AI模型加载失败",
        details={"model_name": "gpt-4", "error": "model not found"},
    )

    alert_critical(
        category="SYSTEM",
        message="系统即将崩溃",
        details={"reason": "out of memory", "action": "restart required"},
    )

    print("告警测试完成，请查看 logs/alert.log 文件")
