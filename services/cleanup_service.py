"""
清理服务
提供数据清理功能
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from models.database import ChatHistory, UserActivity

logger = logging.getLogger(__name__)


async def cleanup_old_records(db: AsyncSession, days: int = 30) -> dict:
    """
    清理过期数据
    
    Args:
        db: 数据库会话
        days: 清理多少天前的数据
    
    Returns:
        清理结果统计
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = {
        "deleted_chat_history": 0,
        "deleted_user_activities": 0,
        "errors": []
    }
    
    try:
        # 清理旧的用户活动记录
        stmt = delete(UserActivity).where(UserActivity.created_at < cutoff_date)
        activity_result = await db.execute(stmt)
        result["deleted_user_activities"] = activity_result.rowcount
        
        logger.info(f"已清理 {result['deleted_user_activities']} 条用户活动记录")
        
    except Exception as e:
        error_msg = f"清理用户活动记录失败: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    
    try:
        await db.commit()
        logger.info(f"数据清理完成: {result}")
    except Exception as e:
        await db.rollback()
        error_msg = f"提交清理事务失败: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
    
    return result


async def get_storage_stats(db: AsyncSession) -> dict:
    """
    获取存储统计信息
    
    Args:
        db: 数据库会话
    
    Returns:
        存储统计信息
    """
    stats = {
        "total_chat_messages": 0,
        "total_user_activities": 0,
        "old_chat_messages": 0,
        "old_user_activities": 0
    }
    
    try:
        # 统计总消息数
        result = await db.execute(select(func.count(ChatHistory.id)))
        stats["total_chat_messages"] = result.scalar_one()
        
        # 统计总活动记录数
        result = await db.execute(select(func.count(UserActivity.id)))
        stats["total_user_activities"] = result.scalar_one()
        
        # 统计30天前的数据
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        result = await db.execute(
            select(func.count(ChatHistory.id)).where(ChatHistory.created_at < cutoff_date)
        )
        stats["old_chat_messages"] = result.scalar_one()
        
        result = await db.execute(
            select(func.count(UserActivity.id)).where(UserActivity.created_at < cutoff_date)
        )
        stats["old_user_activities"] = result.scalar_one()
        
    except Exception as e:
        logger.error(f"获取存储统计失败: {e}")
    
    return stats