"""
备份服务
提供数据库备份功能
"""

import os
import shutil
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import SystemBackup

logger = logging.getLogger(__name__)


async def create_database_backup(
    db: AsyncSession,
    created_by: str = "system",
    backup_type: str = "manual"
) -> dict:
    """
    创建数据库备份
    
    Args:
        db: 数据库会话
        created_by: 创建者
        backup_type: 备份类型 (manual, auto)
    
    Returns:
        备份信息字典
    """
    from config.settings import fastapi_settings
    
    # 创建备份目录
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, filename)
    
    # 获取数据库文件路径
    db_url = fastapi_settings.DATABASE_URL
    if "sqlite" in db_url:
        db_path = db_url.replace("sqlite+aiosqlite:///", "")
        db_path = db_path.replace("sqlite:///", "")
        
        # 复制数据库文件
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            logger.info(f"数据库已备份到: {backup_path}")
        else:
            logger.error(f"数据库文件不存在: {db_path}")
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    else:
        # 对于非SQLite数据库，可以使用pg_dump或其他工具
        logger.warning("非SQLite数据库备份需要使用专门的工具")
        raise NotImplementedError("仅支持SQLite数据库备份")
    
    # 计算文件大小
    size_mb = os.path.getsize(backup_path) / (1024 * 1024)
    
    # 创建备份记录
    backup = SystemBackup(
        filename=filename,
        size_mb=round(size_mb, 2),
        created_by=created_by,
        backup_type=backup_type,
        status="completed",
        file_path=backup_path
    )
    
    db.add(backup)
    await db.commit()
    
    logger.info(f"备份记录已创建: {filename}, 大小: {size_mb:.2f} MB")
    
    return {
        "id": backup.id,
        "filename": filename,
        "size_mb": round(size_mb, 2),
        "path": backup_path
    }


async def cleanup_old_backups(db: AsyncSession, retention_days: int = 30):
    """
    清理过期的备份文件
    
    Args:
        db: 数据库会话
        retention_days: 保留天数
    """
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    # 查找过期备份
    result = await db.execute(
        select(SystemBackup).where(
            SystemBackup.created_at < cutoff_date,
            SystemBackup.backup_type == "auto"
        )
    )
    old_backups = result.scalars().all()
    
    deleted_count = 0
    for backup in old_backups:
        try:
            # 删除文件
            if backup.file_path and os.path.exists(backup.file_path):
                os.remove(backup.file_path)
                logger.info(f"已删除过期备份文件: {backup.file_path}")
            
            # 删除记录
            await db.delete(backup)
            deleted_count += 1
        except Exception as e:
            logger.error(f"删除备份失败 {backup.filename}: {e}")
    
    if deleted_count > 0:
        await db.commit()
        logger.info(f"已清理 {deleted_count} 个过期备份")
    
    return deleted_count