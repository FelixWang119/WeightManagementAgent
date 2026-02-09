"""
系统管理路由
提供系统监控、配置管理和备份功能
"""

import enum
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import json
import os
import psutil
import shutil

from models.database import get_db, SystemConfig, SystemBackup, User
from api.dependencies.auth_v2 import get_current_admin
from config.settings import get_fastapi_settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
settings = get_fastapi_settings()


# ============ 请求/响应模型 ============

class SystemHealthResponse(BaseModel):
    """系统健康状态响应"""
    status: str
    timestamp: str
    version: str
    uptime_seconds: int
    database_connected: bool


class DatabaseStats(BaseModel):
    """数据库统计信息"""
    total_tables: int
    total_records: Dict[str, int]
    database_size_mb: float
    table_sizes: Dict[str, float]


class SystemResourceInfo(BaseModel):
    """系统资源信息"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float


class SystemConfigResponse(BaseModel):
    """系统配置响应"""
    key: str
    value: Any
    description: str
    updated_at: Optional[datetime]
    updated_by: Optional[str]


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    value: Any
    description: Optional[str] = None


class BackupInfoResponse(BaseModel):
    """备份信息响应"""
    id: int
    filename: str
    size_mb: float
    created_at: datetime
    created_by: str
    backup_type: str
    status: str


class BackupSettingsRequest(BaseModel):
    """备份设置请求"""
    enabled: bool = True
    frequency: str = "daily"  # daily, weekly
    backup_time: str = "02:00"  # HH:MM
    retention_days: int = 30
    auto_backup: bool = True


class BackupSettingsResponse(BaseModel):
    """备份设置响应"""
    enabled: bool
    frequency: str
    backup_time: str
    retention_days: int
    auto_backup: bool
    last_backup: Optional[datetime]
    next_backup: Optional[datetime]


# ============ 辅助函数 ============

async def get_database_stats(db: AsyncSession) -> Dict:
    """获取数据库统计信息"""
    try:
        # 获取所有表名
        result = await db.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """))
        tables = [row[0] for row in result.fetchall()]
        
        # 获取每个表的记录数
        table_counts = {}
        for table in tables:
            try:
                count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                table_counts[table] = count_result.scalar()
            except Exception as e:
                logger.warning(f"获取表 {table} 记录数失败: {e}")
                table_counts[table] = 0
        
        # 获取数据库文件大小
        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        db_size_mb = 0
        if os.path.exists(db_path):
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
        
        return {
            "total_tables": len(tables),
            "total_records": table_counts,
            "database_size_mb": round(db_size_mb, 2),
            "tables": tables
        }
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        return {
            "total_tables": 0,
            "total_records": {},
            "database_size_mb": 0,
            "tables": []
        }


def get_system_resources() -> Dict:
    """获取系统资源信息"""
    try:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存信息
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        # 磁盘信息
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        
        return {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": memory.percent,
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_total_mb": round(memory_total_mb, 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk_used_gb, 2),
            "disk_total_gb": round(disk_total_gb, 2)
        }
    except Exception as e:
        logger.error(f"获取系统资源信息失败: {e}")
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_mb": 0,
            "memory_total_mb": 0,
            "disk_percent": 0,
            "disk_used_gb": 0,
            "disk_total_gb": 0
        }


def get_uptime() -> int:
    """获取系统运行时间（秒）"""
    try:
        boot_time = psutil.boot_time()
        uptime = datetime.now().timestamp() - boot_time
        return int(uptime)
    except Exception:
        return 0


# ============ API 路由 ============

@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取系统健康状态
    
    需要管理员权限
    """
    try:
        # 测试数据库连接
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False
    
    return SystemHealthResponse(
        status="healthy" if db_connected else "unhealthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.APP_VERSION,
        uptime_seconds=get_uptime(),
        database_connected=db_connected
    )


@router.get("/stats/database")
async def get_database_statistics(
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取数据库统计信息
    
    需要管理员权限
    """
    stats = await get_database_stats(db)
    return stats


@router.get("/stats/resources")
async def get_resource_statistics(
    user: User = Depends(get_current_admin)
):
    """
    获取系统资源使用情况
    
    需要管理员权限
    """
    resources = get_system_resources()
    return resources


@router.get("/configs")
async def list_system_configs(
    search: Optional[str] = Query(None, description="搜索配置键"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取系统配置列表
    
    需要管理员权限
    """
    query = select(SystemConfig)
    
    if search:
        query = query.where(SystemConfig.key.ilike(f"%{search}%"))
    
    result = await db.execute(query.order_by(SystemConfig.key))
    configs = result.scalars().all()
    
    return [
        SystemConfigResponse(
            key=config.key,
            value=config.value,
            description=config.description or "",
            updated_at=config.updated_at,
            updated_by=config.updated_by
        )
        for config in configs
    ]


@router.get("/configs/{config_key}")
async def get_system_config(
    config_key: str,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个配置项
    
    需要管理员权限
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == config_key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置项不存在"
        )
    
    return SystemConfigResponse(
        key=config.key,
        value=config.value,
        description=config.description or "",
        updated_at=config.updated_at,
        updated_by=config.updated_by
    )


@router.put("/configs/{config_key}")
async def update_system_config(
    config_key: str,
    request: ConfigUpdateRequest,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    更新系统配置
    
    需要管理员权限
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == config_key)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置项不存在"
        )
    
    # 更新配置
    config.value = request.value
    if request.description:
        config.description = request.description
    config.updated_at = datetime.utcnow()
    config.updated_by = user.nickname or user.phone or str(user.id)
    
    await db.commit()
    
    logger.info(f"配置项 {config_key} 已被 {config.updated_by} 更新")
    
    return SystemConfigResponse(
        key=config.key,
        value=config.value,
        description=config.description or "",
        updated_at=config.updated_at,
        updated_by=config.updated_by
    )


@router.get("/backups")
async def list_backups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取备份列表
    
    需要管理员权限
    """
    # 计算总数
    count_result = await db.execute(select(func.count(SystemBackup.id)))
    total = count_result.scalar_one()
    
    # 获取备份列表
    result = await db.execute(
        select(SystemBackup)
        .order_by(SystemBackup.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    backups = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            BackupInfoResponse(
                id=backup.id,
                filename=backup.filename,
                size_mb=backup.size_mb,
                created_at=backup.created_at,
                created_by=backup.created_by,
                backup_type=backup.backup_type,
                status=backup.status
            )
            for backup in backups
        ]
    }


@router.post("/backups")
async def create_backup(
    background_tasks: BackgroundTasks,
    backup_type: str = Query("manual", description="备份类型: manual, auto"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发备份
    
    需要管理员权限
    """
    from services.backup_service import create_database_backup
    
    try:
        # 在后台任务中执行备份
        backup_info = await create_database_backup(
            db=db,
            created_by=user.nickname or user.phone or str(user.id),
            backup_type=backup_type
        )
        
        return {
            "success": True,
            "message": "备份任务已启动",
            "backup_id": backup_info["id"],
            "filename": backup_info["filename"]
        }
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"备份失败: {str(e)}"
        )


@router.get("/backups/settings")
async def get_backup_settings(
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    获取备份设置
    
    需要管理员权限
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "backup_settings")
    )
    config = result.scalar_one_or_none()
    
    if config and config.value:
        settings_dict = config.value if isinstance(config.value, dict) else json.loads(config.value)
    else:
        # 默认设置
        settings_dict = {
            "enabled": True,
            "frequency": "daily",
            "backup_time": "02:00",
            "retention_days": 30,
            "auto_backup": True,
            "last_backup": None,
            "next_backup": None
        }
    
    return BackupSettingsResponse(**settings_dict)


@router.put("/backups/settings")
async def update_backup_settings(
    request: BackupSettingsRequest,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    更新备份设置
    
    需要管理员权限
    """
    # 计算下次备份时间
    now = datetime.utcnow()
    next_backup = None
    if request.enabled and request.auto_backup:
        hour, minute = map(int, request.backup_time.split(':'))
        next_backup = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_backup <= now:
            if request.frequency == "daily":
                next_backup += timedelta(days=1)
            else:  # weekly
                next_backup += timedelta(weeks=1)
    
    settings_dict = {
        "enabled": request.enabled,
        "frequency": request.frequency,
        "backup_time": request.backup_time,
        "retention_days": request.retention_days,
        "auto_backup": request.auto_backup,
        "last_backup": None,
        "next_backup": next_backup.isoformat() if next_backup else None
    }
    
    # 更新或创建设置
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "backup_settings")
    )
    config = result.scalar_one_or_none()
    
    if config:
        config.value = settings_dict
        config.updated_at = datetime.utcnow()
        config.updated_by = user.nickname or user.phone or str(user.id)
    else:
        config = SystemConfig(
            key="backup_settings",
            value=settings_dict,
            description="自动备份设置",
            updated_at=datetime.utcnow(),
            updated_by=user.nickname or user.phone or str(user.id)
        )
        db.add(config)
    
    await db.commit()
    
    logger.info(f"备份设置已被 {config.updated_by} 更新")
    
    return BackupSettingsResponse(**settings_dict)


@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: int,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    删除备份文件
    
    需要管理员权限
    """
    result = await db.execute(
        select(SystemBackup).where(SystemBackup.id == backup_id)
    )
    backup = result.scalar_one_or_none()
    
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="备份不存在"
        )
    
    # 删除文件
    backup_dir = os.path.join(os.getcwd(), "backups")
    backup_path = os.path.join(backup_dir, backup.filename)
    
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
            logger.info(f"备份文件已删除: {backup_path}")
    except Exception as e:
        logger.error(f"删除备份文件失败: {e}")
    
    # 删除数据库记录
    await db.delete(backup)
    await db.commit()
    
    return {"success": True, "message": "备份已删除"}


@router.post("/cleanup")
async def cleanup_old_data(
    days: int = Query(30, ge=7, le=365, description="清理多少天前的数据"),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    清理过期数据（如临时文件、过期缓存等）
    
    需要管理员权限
    """
    try:
        from services.cleanup_service import cleanup_old_records
        
        result = await cleanup_old_records(db, days)
        
        return {
            "success": True,
            "message": f"清理完成",
            "details": result
        }
    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理失败: {str(e)}"
        )