#!/usr/bin/env python3
"""
项目主入口文件

使用示例：
    python main.py
    python main.py --config config.yaml
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 统一日志配置
from config.logging_config import setup_logging, get_module_logger
from config.settings import get_config, create_default_config_file
from utils.exceptions import protect_main, error_handler, retry_on_error

# 模块级 logger（必须：每个模块顶部初始化一次）
logger = get_module_logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="项目主程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py                    # 使用默认配置运行
    python main.py --debug            # 调试模式运行
    python main.py --config prod.yaml # 使用指定配置文件
        """
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="创建默认配置文件并退出"
    )
    
    return parser.parse_args()


@error_handler(default_return=None, log_level="error")
def initialize_app(args: argparse.Namespace) -> bool:
    """
    初始化应用程序
    
    Args:
        args: 命令行参数
    
    Returns:
        初始化是否成功
    """
    logger.info("=" * 60)
    logger.info("开始初始化应用程序")
    logger.info("=" * 60)
    
    # 创建默认配置文件（如果需要）
    if args.init_config:
        create_default_config_file()
        return True
    
    # 加载配置
    config = get_config()
    
    # 设置日志系统
    log_config = config.get_logging_config()
    if args.debug:
        log_config["level"] = "DEBUG"
    
    setup_logging(**log_config)
    logger.info("日志系统初始化完成")
    
    # 显示配置信息
    logger.info("应用名称: %s", config.get("app.name"))
    logger.info("调试模式: %s", "开启" if args.debug else "关闭")
    logger.info("环境: %s", config.get("app.env"))
    
    logger.info("应用程序初始化完成")
    return True


@retry_on_error(max_attempts=3, delay=1.0)
def fetch_data_example(url: str) -> dict:
    """
    示例：获取远程数据（带重试机制）
    
    Args:
        url: 数据 URL
    
    Returns:
        数据字典
    """
    logger.info("正在获取数据: %s", url)
    
    # 模拟网络请求（实际使用时替换为真实请求）
    import random
    if random.random() < 0.5:
        raise ConnectionError("网络连接失败")
    
    return {"status": "success", "data": "示例数据"}


@error_handler(default_return={"error": "处理失败"}, log_level="warning")
def process_data(data: dict) -> dict:
    """
    示例：处理数据（带错误处理）
    
    Args:
        data: 输入数据
    
    Returns:
        处理后的数据
    """
    logger.info("开始处理数据")
    
    # 模拟数据处理
    result = {
        "input": data,
        "processed": True,
        "timestamp": "2024-01-01T00:00:00"
    }
    
    logger.info("数据处理完成")
    return result


def main() -> int:
    """
    主函数
    
    Returns:
        退出码 (0=成功, 1=失败)
    """
    # 解析命令行参数
    args = parse_arguments()
    
    # 初始化应用
    if not initialize_app(args):
        logger.error("应用程序初始化失败")
        return 1
    
    # 如果只是创建配置，直接退出
    if args.init_config:
        return 0
    
    try:
        logger.info("=" * 60)
        logger.info("开始主程序逻辑")
        logger.info("=" * 60)
        
        # 示例 1：使用重试机制获取数据
        logger.info("\n【示例 1】带重试的数据获取")
        try:
            data = fetch_data_example("https://api.example.com/data")
            logger.info("获取数据成功: %s", data)
        except Exception as e:
            logger.error("获取数据失败: %s", str(e))
        
        # 示例 2：使用错误处理装饰器处理数据
        logger.info("\n【示例 2】带错误处理的数据处理")
        result = process_data({"key": "value"})
        logger.info("处理结果: %s", result)
        
        # 示例 3：不同类型的日志
        logger.info("\n【示例 3】日志级别示例")
        logger.debug("这是一条 DEBUG 日志（仅在调试模式显示）")
        logger.info("这是一条 INFO 日志")
        logger.warning("这是一条 WARNING 日志")
        logger.error("这是一条 ERROR 日志（测试用）")
        
        # 示例 4：使用占位符（性能优化，推荐）
        stock_code = "000001"
        score = 85.5
        count = 100
        logger.info("处理股票 %s，评分 %.2f，数量 %d", stock_code, score, count)
        
        logger.info("\n" + "=" * 60)
        logger.info("主程序执行完成")
        logger.info("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        return 130
    except Exception as e:
        logger.exception("主程序发生未预期错误: %s", str(e))
        return 1


if __name__ == "__main__":
    # 使用 protect_main 保护入口
    # 自动处理异常、记录日志、设置退出码
    from utils.exceptions import protect_main
    sys.exit(protect_main(main, exit_on_error=False))
