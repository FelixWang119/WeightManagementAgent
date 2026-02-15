"""项目配置管理模块

集中管理所有可配置项，避免硬编码。
支持从配置文件、环境变量加载配置。

新增：Pydantic Settings 支持（用于 FastAPI）
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============ Pydantic Settings (FastAPI 使用) ============


class FastAPISettings(BaseSettings):
    """FastAPI 应用配置（支持环境变量）"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 基础配置
    APP_NAME: str = "体重管理助手"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENV: str = "development"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./weight_management.db"

    # AI/LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_MAX_TOKENS: int = 2000
    OPENAI_TEMPERATURE: float = 0.7

    # 通义千问(Qwen)配置
    QWEN_API_KEY: Optional[str] = None
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-turbo"
    QWEN_MAX_TOKENS: int = 2000
    QWEN_TEMPERATURE: float = 0.7

    # 默认使用的AI模型: openai / qwen
    DEFAULT_AI_PROVIDER: str = "qwen"

    # 微信
    WECHAT_APPID: Optional[str] = None
    WECHAT_SECRET: Optional[str] = None

    # 安全
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ADMIN_PASSWORD: str = "admin123"

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    # 上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

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
    REDIS_ENABLED: bool = True  # 是否启用Redis缓存


@lru_cache()
def get_fastapi_settings() -> FastAPISettings:
    """获取 FastAPI 配置单例"""
    return FastAPISettings()


# 便捷导出
fastapi_settings = get_fastapi_settings()


# 获取 logger
logger = logging.getLogger(__name__)


# 默认配置
DEFAULT_CONFIG = {
    # 应用基础配置
    "app": {
        "name": "my_app",
        "version": "1.0.0",
        "debug": False,
        "env": "development",  # development, testing, production
    },
    # 日志配置
    "logging": {
        "level": "INFO",
        "dir": "logs",
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "console_output": True,
        "file_output": True,
    },
    # 数据库配置
    "database": {
        "url": "sqlite:///data/app.db",
        "pool_size": 5,
        "max_overflow": 10,
        "echo": False,
    },
    # 性能配置（低配置机器优化）
    "performance": {
        "max_workers": 1,  # 低配置机器使用单线程
        "batch_size": 10,
        "use_cache": True,
        "cache_ttl": 1800,  # 30分钟
    },
    # 记忆配置
    "memory": {
        "short_term_limit": 20,  # 短期记忆保留的对话轮次（每轮包含用户+助手消息）
        "history_injection_rounds": 5,  # 注入到提示中的对话轮次
        "enable_vector_memory": True,  # 是否启用向量长期记忆
    },
    # API 配置
    "api": {
        "timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 1.0,
    },
    # 外部服务配置
    "external_services": {
        "enable_monitoring": False,
        "rate_limit": 100,  # 每分钟请求数
    },
    # Redis缓存配置
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "max_connections": 10,
        "socket_timeout": 5.0,
        "socket_connect_timeout": 5.0,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        "enabled": True,
    },
}


class Config:
    """配置管理类"""

    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}

    def __new__(cls) -> "Config":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """加载配置"""
        # 从默认配置开始
        self._config = DEFAULT_CONFIG.copy()

        # 尝试从文件加载
        config_file = self._find_config_file()
        if config_file:
            self._load_from_file(config_file)

        # 从环境变量加载（覆盖文件配置）
        self._load_from_env()

        logger.debug("配置加载完成: %s", self._config)

    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        possible_paths = [
            Path("config.yaml"),
            Path("config.yml"),
            Path("config.json"),
            Path("configs/config.yaml"),
            Path(os.getenv("APP_CONFIG", "")),
        ]

        for path in possible_paths:
            if path and path.exists():
                return path

        return None

    def _load_from_file(self, config_file: Path) -> None:
        """从文件加载配置"""
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                if config_file.suffix in [".yaml", ".yml"]:
                    file_config = yaml.safe_load(f)
                else:
                    file_config = json.load(f)

            # 递归合并配置
            self._deep_update(self._config, file_config)
            logger.info("从 %s 加载配置", config_file)

        except Exception as e:
            logger.warning("无法从 %s 加载配置: %s", config_file, str(e))

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 支持的环境变量前缀
        prefix = "APP_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # 将 APP_DATABASE_URL 转换为 database.url
                config_key = key[len(prefix) :].lower().replace("_", ".")
                self._set_nested_value(
                    self._config, config_key, self._parse_value(value)
                )

    def _parse_value(self, value: str) -> Union[str, int, float, bool, None]:
        """解析环境变量值"""
        # 布尔值
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        if value.lower() in ("null", "none", ""):
            return None

        # 整数
        try:
            return int(value)
        except ValueError:
            pass

        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 字符串
        return value

    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """递归更新字典"""
        for key, value in update_dict.items():
            if (
                key in base_dict
                and isinstance(base_dict[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def _set_nested_value(self, config_dict: Dict, key_path: str, value: Any) -> None:
        """设置嵌套值"""
        keys = key_path.split(".")
        current = config_dict

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key_path: 配置路径，如 "database.url" 或 "logging.level"
            default: 默认值

        Returns:
            配置值或默认值
        """
        keys = key_path.split(".")
        current = self._config

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> None:
        """设置配置值"""
        self._set_nested_value(self._config, key_path, value)
        logger.debug("设置配置: %s = %s", key_path, value)

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()

    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置（用于 logging_config.setup_logging）"""
        return self._config.get("logging", {})

    def get_database_url(self) -> str:
        """获取数据库 URL"""
        return self._config.get("database", {}).get("url", "sqlite:///data/app.db")

    def get_redis_config(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return self._config.get("redis", {})

    def is_redis_enabled(self) -> bool:
        """是否启用Redis缓存"""
        return self._config.get("redis", {}).get("enabled", True)

    def is_debug(self) -> bool:
        """是否调试模式"""
        return self._config.get("app", {}).get("debug", False)

    def is_production(self) -> bool:
        """是否生产环境"""
        return self._config.get("app", {}).get("env", "development") == "production"

    def reload(self) -> None:
        """重新加载配置"""
        self._load_config()
        logger.info("配置已重新加载")

    def save_to_file(self, filepath: str = "config.yaml") -> None:
        """保存配置到文件"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                if filepath.endswith(".json"):
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
                else:
                    yaml.dump(
                        self._config, f, default_flow_style=False, allow_unicode=True
                    )
            logger.info("配置已保存到 %s", filepath)
        except Exception as e:
            logger.error("保存配置失败: %s", str(e))
            raise


# 便捷函数
def get_config() -> Config:
    """获取配置实例（单例）"""
    return Config()


def get_config_value(key_path: str, default: Any = None) -> Any:
    """便捷获取配置值"""
    return get_config().get(key_path, default)


# 创建默认配置文件示例
def create_default_config_file(filepath: str = "config.yaml") -> None:
    """创建默认配置文件示例"""
    example_config = {
        "app": {
            "name": "my_application",
            "version": "1.0.0",
            "debug": False,
        },
        "logging": {
            "level": "INFO",
            "dir": "logs",
        },
        "database": {
            "url": "sqlite:///data/app.db",
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# 项目配置文件\n")
        f.write("# 可根据需要修改以下配置\n\n")
        yaml.dump(example_config, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ 默认配置文件已创建: {filepath}")


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    config = get_config()

    print("当前配置:")
    print(f"  应用名称: {config.get('app.name')}")
    print(f"  日志级别: {config.get('logging.level')}")
    print(f"  数据库URL: {config.get_database_url()}")
    print(f"  调试模式: {config.is_debug()}")

    # 测试设置
    config.set("test.value", 123)
    print(f"  测试值: {config.get('test.value')}")

    # 创建示例配置文件
    create_default_config_file("config_example.yaml")

    print("\n配置测试完成")
