"""
通知队列模型
存储待发送的通知任务

注意: 此模型已移至 models/database.py 以避免循环导入
"""

# 重新导出以保持向后兼容
from models.database import NotificationQueue  # noqa: F401
