"""
统一时间服务 - 服务端时间控制中枢

功能：
1. 提供统一的时间获取接口（today(), now()）
2. 支持测试模式：冻结时间、相对偏移
3. 所有业务代码必须通过此服务获取时间，禁止直接使用date.today()

使用规范：
- 业务代码: from services.time_service import today, now
- 测试框架: 通过 /test/time/control API 控制服务端时间
"""

import os
import threading
from datetime import date, datetime, timedelta
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


class TimeService:
    """
    统一时间服务 - 线程安全的时间控制
    
    生产模式：返回真实时间
    测试模式：返回设定的时间（冻结或偏移）
    """
    
    # 线程锁保护状态变更
    _lock = threading.RLock()
    
    # 测试模式状态
    _test_mode = False
    _frozen_date: Optional[date] = None
    _frozen_datetime: Optional[datetime] = None
    _offset_days = 0
    _offset_seconds = 0
    
    @classmethod
    def _get_env_bool(cls, key: str, default: bool = False) -> bool:
        """获取环境变量布尔值"""
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        if value in ("false", "0", "no", "off"):
            return False
        return default
    
    @classmethod
    def is_test_mode(cls) -> bool:
        """检查是否处于测试模式"""
        with cls._lock:
            return cls._test_mode
    
    @classmethod
    def enable_test_mode(cls):
        """启用测试模式"""
        with cls._lock:
            cls._test_mode = True
            logger.info("[TimeService] 测试模式已启用")
    
    @classmethod
    def disable_test_mode(cls):
        """禁用测试模式，恢复真实时间"""
        with cls._lock:
            cls._test_mode = False
            cls._frozen_date = None
            cls._frozen_datetime = None
            cls._offset_days = 0
            cls._offset_seconds = 0
            logger.info("[TimeService] 测试模式已禁用，恢复真实时间")
    
    @classmethod
    def set_frozen_time(cls, target_time: Union[date, datetime, str]):
        """
        冻结到指定时间
        
        Args:
            target_time: date对象、datetime对象或ISO格式字符串(YYYY-MM-DD)
        """
        with cls._lock:
            if isinstance(target_time, str):
                target_time = date.fromisoformat(target_time)
            
            if isinstance(target_time, datetime):
                cls._frozen_datetime = target_time
                cls._frozen_date = target_time.date()
            else:
                cls._frozen_date = target_time
                cls._frozen_datetime = None
            
            cls._offset_days = 0
            cls._offset_seconds = 0
            cls._test_mode = True
            
            logger.info(f"[TimeService] 时间已冻结: {target_time}")
    
    @classmethod
    def set_offset(cls, days: int = 0, seconds: int = 0):
        """
        设置相对偏移
        
        Args:
            days: 天数偏移（正数=未来，负数=过去）
            seconds: 秒数偏移
        """
        with cls._lock:
            cls._offset_days = days
            cls._offset_seconds = seconds
            cls._frozen_date = None
            cls._frozen_datetime = None
            cls._test_mode = True
            
            logger.info(f"[TimeService] 时间偏移已设置: {days}天 {seconds}秒")
    
    @classmethod
    def reset(cls):
        """重置所有时间控制，恢复真实时间"""
        with cls._lock:
            cls._frozen_date = None
            cls._frozen_datetime = None
            cls._offset_days = 0
            cls._offset_seconds = 0
            logger.info("[TimeService] 时间已重置")
    
    @classmethod
    def today(cls) -> date:
        """
        获取当前日期
        
        生产模式: 返回真实日期 date.today()
        测试模式: 返回设定的时间
        """
        with cls._lock:
            if not cls._test_mode:
                return date.today()
            
            # 测试模式：返回设定的时间
            if cls._frozen_date:
                return cls._frozen_date
            
            if cls._frozen_datetime:
                return cls._frozen_datetime.date()
            
            # 计算偏移后的时间
            base_date = date.today()
            if cls._offset_days:
                base_date += timedelta(days=cls._offset_days)
            if cls._offset_seconds:
                # 秒数偏移可能影响日期
                base_datetime = datetime.combine(base_date, datetime.min.time())
                base_datetime += timedelta(seconds=cls._offset_seconds)
                return base_datetime.date()
            
            return base_date
    
    @classmethod
    def now(cls) -> datetime:
        """
        获取当前日期时间
        
        生产模式: 返回真实时间 datetime.now()
        测试模式: 返回设定的时间
        """
        with cls._lock:
            if not cls._test_mode:
                return datetime.now()
            
            # 测试模式：返回设定的时间
            if cls._frozen_datetime:
                return cls._frozen_datetime
            
            if cls._frozen_date:
                return datetime.combine(cls._frozen_date, datetime.min.time())
            
            # 计算偏移后的时间
            base_datetime = datetime.now()
            if cls._offset_days:
                base_datetime += timedelta(days=cls._offset_days)
            if cls._offset_seconds:
                base_datetime += timedelta(seconds=cls._offset_seconds)
            
            return base_datetime
    
    @classmethod
    def get_status(cls) -> dict:
        """获取当前时间服务状态"""
        with cls._lock:
            return {
                "test_mode": cls._test_mode,
                "frozen_date": cls._frozen_date.isoformat() if cls._frozen_date else None,
                "frozen_datetime": cls._frozen_datetime.isoformat() if cls._frozen_datetime else None,
                "offset_days": cls._offset_days,
                "offset_seconds": cls._offset_seconds,
                "effective_today": cls.today().isoformat(),
                "effective_now": cls.now().isoformat()
            }


# 便捷函数 - 业务代码直接使用这些函数

def today() -> date:
    """获取当前日期（通过TimeService）"""
    return TimeService.today()


def now() -> datetime:
    """获取当前日期时间（通过TimeService）"""
    return TimeService.now()


def is_test_mode() -> bool:
    """检查是否处于测试模式"""
    return TimeService.is_test_mode()


# 测试控制函数（仅供测试路由调用）

def enable_test_mode():
    """启用测试模式"""
    TimeService.enable_test_mode()


def disable_test_mode():
    """禁用测试模式"""
    TimeService.disable_test_mode()


def set_frozen_time(target_time: Union[date, datetime, str]):
    """冻结到指定时间"""
    TimeService.set_frozen_time(target_time)


def set_offset(days: int = 0, seconds: int = 0):
    """设置相对偏移"""
    TimeService.set_offset(days, seconds)


def reset():
    """重置时间控制"""
    TimeService.reset()


def get_status() -> dict:
    """获取状态"""
    return TimeService.get_status()
