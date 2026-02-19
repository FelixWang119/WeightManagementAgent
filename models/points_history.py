"""
积分历史记录模型
用于记录用户积分的获取和消费明细
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from models.database import Base
import enum


class PointsType(enum.Enum):
    """积分类型"""

    EARN = "earn"  # 获得积分
    SPEND = "spend"  # 消耗积分


class PointsHistory(Base):
    """积分历史记录表"""

    __tablename__ = "points_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    points_type = Column(Enum(PointsType), nullable=False, comment="积分类型")
    amount = Column(Integer, nullable=False, comment="积分数量")
    reason = Column(String(100), nullable=False, comment="原因/来源")
    description = Column(Text, nullable=True, comment="详细描述")
    related_record_id = Column(Integer, nullable=True, comment="关联记录ID")
    related_record_type = Column(String(50), nullable=True, comment="关联记录类型")
    balance_after = Column(Integer, nullable=False, comment="操作后余额")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
