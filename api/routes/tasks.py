"""
任务管理路由
用于手动触发定时任务
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict

from models.database import get_db, User
from api.routes.user import get_current_user
from tasks.daily_summary import DailySummaryTask
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter()


@router.post("/daily-summary")
async def run_daily_summary(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动触发每日汇总任务（仅当前用户）"""
    logger.info("用户 %s 手动触发每日汇总", current_user.id)

    try:
        result = await DailySummaryTask.process_single_user(current_user.id, db)

        if result["success"]:
            return {
                "success": True,
                "message": "每日汇总处理完成",
                "data": result["data"],
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))

    except Exception as e:
        logger.exception("每日汇总任务失败: %s", e)
        raise HTTPException(status_code=500, detail="处理失败")


@router.post("/daily-summary/all")
async def run_daily_summary_all(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发所有用户的每日汇总任务
    注意：这应该是管理员功能，需要添加权限检查
    """
    # TODO: 添加管理员权限检查
    logger.info("管理员手动触发全量每日汇总")

    try:
        result = await DailySummaryTask.process_all_users(db)

        if result["success"]:
            return {
                "success": True,
                "message": "全量每日汇总处理完成",
                "data": result["data"],
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))

    except Exception as e:
        logger.exception("全量每日汇总任务失败: %s", e)
        raise HTTPException(status_code=500, detail="处理失败")
