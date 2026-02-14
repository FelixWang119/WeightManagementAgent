"""
管理端提醒配置API
提供全局提醒设置的配置和管理功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, Literal
from pathlib import Path
import yaml
import os

from api.dependencies.auth_v2 import get_current_admin
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter()

# 配置文件路径
CONFIG_DIR = Path("config")
DEFAULT_CONFIG_PATH = CONFIG_DIR / "reminder_defaults.yaml"
CURRENT_CONFIG_PATH = CONFIG_DIR / "reminder_config.yaml"

# 提醒类型
ReminderType = Literal[
    "weight", "breakfast", "lunch", "dinner", "exercise", "water", "sleep"
]

# 有效的提醒类型列表
VALID_REMINDER_TYPES = [
    "weight",
    "breakfast",
    "lunch",
    "dinner",
    "exercise",
    "water",
    "sleep",
]


class TimeRange(BaseModel):
    """时间范围模型"""

    start: str = Field(..., description="开始时间 HH:MM")
    end: str = Field(..., description="结束时间 HH:MM")

    @validator("start", "end")
    def validate_time_format(cls, v: str) -> str:
        """验证时间格式 HH:MM"""
        try:
            hour, minute = v.split(":")
            h, m = int(hour), int(minute)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            return v
        except ValueError:
            raise ValueError(f"时间格式无效: {v}，应为 HH:MM (00:00-23:59)")


class ReminderTypeConfig(BaseModel):
    """单个提醒类型配置"""

    enabled: bool = Field(default=True, description="是否启用")
    time: str = Field(default="08:00", description="提醒时间 HH:MM")
    interval: Optional[int] = Field(
        default=None, description="间隔分钟数（仅water使用）"
    )
    message_template: str = Field(default="", description="消息模板字符串")

    @validator("time")
    def validate_time_format(cls, v: str) -> str:
        """验证时间格式 HH:MM"""
        try:
            hour, minute = v.split(":")
            h, m = int(hour), int(minute)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            return v
        except ValueError:
            raise ValueError(f"时间格式无效: {v}，应为 HH:MM (00:00-23:59)")

    @validator("interval")
    def validate_interval(cls, v: Optional[int]) -> Optional[int]:
        """验证间隔分钟数"""
        if v is not None:
            if not (1 <= v <= 1440):
                raise ValueError("间隔分钟数应在 1-1440 之间")
        return v


class GlobalSettings(BaseModel):
    """全局提醒设置"""

    do_not_disturb_default: TimeRange = Field(
        default_factory=lambda: TimeRange(start="22:00", end="07:00"),
        description="免打扰默认时间",
    )
    max_daily_notifications: int = Field(
        default=50, ge=1, le=500, description="每日最大提醒次数"
    )
    smart_adjustment_enabled: bool = Field(default=True, description="是否启用智能调整")


class ReminderConfigSchema(BaseModel):
    """提醒配置主模型"""

    weight: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True, time="07:00", message_template="记得记录今日体重哦！"
        )
    )
    breakfast: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True,
            time="07:30",
            message_template="早餐时间到啦，记得吃营养早餐！",
        )
    )
    lunch: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True, time="11:30", message_template="午餐时间，记得合理搭配饮食！"
        )
    )
    dinner: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True, time="17:30", message_template="晚餐时间，建议清淡饮食！"
        )
    )
    exercise: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True, time="18:00", message_template="运动时间到了，动起来吧！"
        )
    )
    water: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True,
            time="09:00",
            interval=120,
            message_template="该喝水啦，保持水分充足！",
        )
    )
    sleep: ReminderTypeConfig = Field(
        default_factory=lambda: ReminderTypeConfig(
            enabled=True,
            time="21:30",
            message_template="准备休息了吗？良好的睡眠有助于健康！",
        )
    )
    global_settings: GlobalSettings = Field(
        default_factory=GlobalSettings, description="全局设置"
    )


class ConfigResponse(BaseModel):
    """配置响应模型"""

    success: bool
    data: ReminderConfigSchema
    message: str


class DefaultConfigResponse(BaseModel):
    """默认配置响应模型"""

    success: bool
    data: ReminderConfigSchema
    message: str


class ResetResponse(BaseModel):
    """重置响应模型"""

    success: bool
    message: str


def get_default_config() -> ReminderConfigSchema:
    """获取默认配置"""
    return ReminderConfigSchema()


def load_yaml_config(path: Path) -> Optional[dict]:
    """从YAML文件加载配置

    Args:
        path: YAML文件路径

    Returns:
        配置字典，文件不存在或解析失败返回None
    """
    try:
        if not path.exists():
            logger.debug("配置文件不存在: %s", path)
            return None

        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            logger.debug("成功加载配置文件: %s", path)
            return content
    except yaml.YAMLError as e:
        logger.error("YAML解析失败 %s: %s", path, e)
        return None
    except Exception as e:
        logger.exception("加载配置文件失败 %s", path)
        return None


def save_yaml_config(path: Path, config: dict) -> bool:
    """保存配置到YAML文件

    Args:
        path: YAML文件路径
        config: 配置字典

    Returns:
        是否保存成功
    """
    try:
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                config, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        logger.info("配置已保存: %s", path)
        return True
    except Exception as e:
        logger.exception("保存配置文件失败 %s", path)
        return False


def get_current_config() -> ReminderConfigSchema:
    """获取当前配置（优先从当前配置文件加载，否则使用默认）

    Returns:
        ReminderConfigSchema 实例
    """
    # 尝试加载当前配置
    current_data = load_yaml_config(CURRENT_CONFIG_PATH)
    if current_data:
        try:
            return ReminderConfigSchema(**current_data)
        except Exception as e:
            logger.warning("当前配置加载失败，使用默认配置: %s", e)

    # 尝试加载默认配置文件
    default_data = load_yaml_config(DEFAULT_CONFIG_PATH)
    if default_data:
        try:
            return ReminderConfigSchema(**default_data)
        except Exception as e:
            logger.warning("默认配置文件加载失败，使用内置默认: %s", e)

    # 使用内置默认配置
    return get_default_config()


def save_current_config(config: ReminderConfigSchema) -> bool:
    """保存当前配置到文件

    Args:
        config: 配置对象

    Returns:
        是否保存成功
    """
    config_dict = config.model_dump()
    return save_yaml_config(CURRENT_CONFIG_PATH, config_dict)


def initialize_default_config():
    """初始化默认配置文件（如果不存在）"""
    if not DEFAULT_CONFIG_PATH.exists():
        default_config = get_default_config()
        config_dict = default_config.model_dump()
        if save_yaml_config(DEFAULT_CONFIG_PATH, config_dict):
            logger.info("已创建默认配置文件: %s", DEFAULT_CONFIG_PATH)
        else:
            logger.error("创建默认配置文件失败")


# 模块加载时初始化
initialize_default_config()


# ============ API 端点 ============


@router.get("/config", response_model=ConfigResponse)
async def get_reminder_config(admin=Depends(get_current_admin)):
    """
    获取当前提醒配置

    需要管理员权限

    Returns:
        当前提醒配置，包括所有提醒类型和全局设置
    """
    try:
        logger.info("管理员 %s 获取提醒配置", admin.id)
        config = get_current_config()

        return ConfigResponse(success=True, data=config, message="获取配置成功")
    except Exception as e:
        logger.exception("获取提醒配置失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}",
        )


@router.put("/config", response_model=ConfigResponse)
async def update_reminder_config(
    config: ReminderConfigSchema, admin=Depends(get_current_admin)
):
    """
    更新提醒配置（全量更新）

    需要管理员权限。将完全替换当前配置。

    Args:
        config: 完整的提醒配置对象

    Returns:
        更新后的配置
    """
    try:
        logger.info("管理员 %s 更新提醒配置", admin.id)

        # 保存配置
        if not save_current_config(config):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存配置失败"
            )

        logger.info("管理员 %s 成功更新提醒配置", admin.id)

        return ConfigResponse(success=True, data=config, message="配置更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新提醒配置失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新配置失败: {str(e)}",
        )


@router.get("/defaults", response_model=DefaultConfigResponse)
async def get_default_reminder_config(admin=Depends(get_current_admin)):
    """
    获取默认提醒配置

    需要管理员权限。返回系统内置的默认配置值。

    Returns:
        默认提醒配置
    """
    try:
        logger.info("管理员 %s 获取默认提醒配置", admin.id)

        # 优先从默认配置文件加载
        default_data = load_yaml_config(DEFAULT_CONFIG_PATH)
        if default_data:
            config = ReminderConfigSchema(**default_data)
        else:
            config = get_default_config()

        return DefaultConfigResponse(
            success=True, data=config, message="获取默认配置成功"
        )
    except Exception as e:
        logger.exception("获取默认提醒配置失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取默认配置失败: {str(e)}",
        )


@router.post("/reset", response_model=ResetResponse)
async def reset_reminder_config(admin=Depends(get_current_admin)):
    """
    重置提醒配置为默认值

    需要管理员权限。将当前配置恢复为系统默认。

    Returns:
        重置结果
    """
    try:
        logger.info("管理员 %s 重置提醒配置", admin.id)

        # 加载默认配置
        default_data = load_yaml_config(DEFAULT_CONFIG_PATH)
        if default_data:
            config = ReminderConfigSchema(**default_data)
        else:
            config = get_default_config()

        # 保存为当前配置
        if not save_current_config(config):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="重置配置失败"
            )

        logger.info("管理员 %s 成功重置提醒配置", admin.id)

        return ResetResponse(success=True, message="配置已重置为默认值")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("重置提醒配置失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置配置失败: {str(e)}",
        )
