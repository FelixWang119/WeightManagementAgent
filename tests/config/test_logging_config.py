"""测试日志配置模块"""

import os
import tempfile
import shutil
import logging


def test_alert_handler_configuration():
    """测试告警处理器配置"""
    from config.logging_config import setup_logging, get_module_logger

    # 创建临时目录用于测试
    temp_dir = tempfile.mkdtemp()
    try:
        # 设置日志
        setup_logging(log_dir=temp_dir, enable_alert_log=True)

        # 获取logger
        logger = get_module_logger("test_alert")

        # 检查根logger是否有告警处理器
        root_logger = logging.getLogger()
        alert_handlers = [
            h
            for h in root_logger.handlers
            if hasattr(h, "name") and h.name == "alert_handler"
        ]
        assert len(alert_handlers) == 1, "告警处理器未正确配置"

        # 检查告警日志文件是否存在
        alert_log_path = os.path.join(temp_dir, "alert.log")
        assert os.path.exists(alert_log_path), "告警日志文件未创建"

        # 测试告警日志记录
        logger.error("测试错误告警")
        logger.warning("测试警告告警")
        logger.info("测试信息日志 - 不应出现在告警日志中")

        # 验证告警日志内容
        with open(alert_log_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "测试错误告警" in content, "错误日志应记录到告警文件"
            assert "测试警告告警" in content, "警告日志应记录到告警文件"
            assert "测试信息日志" not in content, "信息日志不应记录到告警文件"

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_alert_handler_disabled():
    """测试禁用告警处理器"""
    from config.logging_config import setup_logging, get_module_logger

    # 创建临时目录用于测试
    temp_dir = tempfile.mkdtemp()
    try:
        # 设置日志，禁用告警日志
        setup_logging(log_dir=temp_dir, enable_alert_log=False)

        # 获取logger（用于验证日志系统正常工作）
        _ = get_module_logger("test_alert_disabled")

        # 检查根logger是否有告警处理器
        root_logger = logging.getLogger()
        alert_handlers = [
            h
            for h in root_logger.handlers
            if hasattr(h, "name") and h.name == "alert_handler"
        ]
        assert len(alert_handlers) == 0, "告警处理器应被禁用"

        # 检查告警日志文件不存在
        alert_log_path = os.path.join(temp_dir, "alert.log")
        assert not os.path.exists(alert_log_path), "告警日志文件不应被创建"

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_alert_handler_level_filter():
    """测试告警处理器级别过滤"""
    from config.logging_config import setup_logging, get_module_logger

    # 创建临时目录用于测试
    temp_dir = tempfile.mkdtemp()
    try:
        # 设置日志
        setup_logging(log_dir=temp_dir, enable_alert_log=True, log_level=logging.DEBUG)

        # 获取logger
        logger = get_module_logger("test_alert_level")

        # 记录各种级别的日志
        logger.debug("调试信息 - 不应出现在告警日志中")
        logger.info("普通信息 - 不应出现在告警日志中")
        logger.warning("警告信息 - 应出现在告警日志中")
        logger.error("错误信息 - 应出现在告警日志中")
        logger.critical("严重错误 - 应出现在告警日志中")

        # 验证告警日志内容
        alert_log_path = os.path.join(temp_dir, "alert.log")
        with open(alert_log_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "调试信息" not in content, "调试日志不应记录到告警文件"
            assert "普通信息" not in content, "信息日志不应记录到告警文件"
            assert "警告信息" in content, "警告日志应记录到告警文件"
            assert "错误信息" in content, "错误日志应记录到告警文件"
            assert "严重错误" in content, "严重错误日志应记录到告警文件"

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)
