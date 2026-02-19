"""
每日汇总任务
定时检查用户的连续打卡、完美一周等成就
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from models.database import User
from services.integration_service import DailyCheckinService
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class DailySummaryTask:
    """每日汇总任务"""

    @staticmethod
    async def process_all_users(db: AsyncSession) -> Dict[str, Any]:
        """处理所有用户的每日汇总"""
        logger.info("开始执行每日汇总任务")

        try:
            # 获取所有用户
            from sqlalchemy import select

            result = await db.execute(select(User.id, User.username))
            users = result.fetchall()

            processed_count = 0
            total_points_issued = 0
            achievements_unlocked = []

            for user in users:
                try:
                    logger.debug("处理用户每日汇总: %s (%s)", user.username, user.id)

                    # 执行每日打卡处理
                    result = await DailyCheckinService.process_daily_checkin(
                        user.id, db
                    )

                    processed_count += 1
                    total_points_issued += result.get("points_earned", 0)

                    if result.get("achievements_unlocked"):
                        achievements_unlocked.extend(result["achievements_unlocked"])

                except Exception as e:
                    logger.exception("处理用户 %s 每日汇总时出错: %s", user.id, e)
                    continue

            summary = {
                "processed_users": processed_count,
                "total_points_issued": total_points_issued,
                "achievements_unlocked_count": len(achievements_unlocked),
                "completed_at": datetime.utcnow().isoformat(),
            }

            logger.info("每日汇总任务完成: %s", summary)

            return {"success": True, "data": summary}

        except Exception as e:
            logger.exception("执行每日汇总任务失败: %s", e)
            return {"success": False, "error": str(e)}

    @staticmethod
    async def process_single_user(user_id: int, db: AsyncSession) -> Dict[str, Any]:
        """处理单个用户的每日汇总"""
        logger.info("处理用户 %s 的每日汇总", user_id)

        try:
            result = await DailyCheckinService.process_daily_checkin(user_id, db)

            return {"success": True, "data": result}

        except Exception as e:
            logger.exception("处理用户 %s 每日汇总失败: %s", user_id, e)
            return {"success": False, "error": str(e)}
