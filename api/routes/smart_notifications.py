"""
智能通知 API 路由
提供智能通知分析和优化功能
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List
import json

from models.database import get_db, User
from api.routes.user import get_current_user
from services.smart_notification_service import SmartNotificationService
from services.ab_testing_service import ABTestingService
from config.logging_config import get_module_logger

router = APIRouter()
logger = get_module_logger(__name__)

# 初始化服务
smart_notification_service = SmartNotificationService()
ab_testing_service = ABTestingService()


@router.get("/engagement/{user_id}")
async def get_user_engagement(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户参与度分析"""
    try:
        # 权限检查：只能查看自己的数据或管理员
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        engagement_level = await smart_notification_service.analyze_user_engagement(
            user_id, db
        )

        return {
            "user_id": user_id,
            "engagement_level": engagement_level.value,
            "description": _get_engagement_description(engagement_level),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取用户参与度失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取用户参与度失败: {str(e)}")


@router.get("/effectiveness/{user_id}/{notification_type}")
async def get_notification_effectiveness(
    user_id: int,
    notification_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知效果分析"""
    try:
        # 权限检查
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        effectiveness = (
            await smart_notification_service.analyze_notification_effectiveness(
                user_id, notification_type, db
            )
        )

        return {
            "user_id": user_id,
            "notification_type": notification_type,
            "effectiveness": effectiveness.value,
            "description": _get_effectiveness_description(effectiveness),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取通知效果失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取通知效果失败: {str(e)}")


@router.get("/optimal-time/{user_id}")
async def get_optimal_notification_time(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户最佳通知时间"""
    try:
        # 权限检查
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        optimal_time = await smart_notification_service.get_optimal_notification_time(
            user_id, db
        )

        return {
            "user_id": user_id,
            "optimal_time": optimal_time,
            "recommendation": _get_time_recommendation(optimal_time),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取最佳通知时间失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取最佳通知时间失败: {str(e)}")


@router.post("/personalize")
async def personalize_notification(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """个性化通知内容"""
    try:
        user_id = request.get("user_id", current_user.id)
        notification_type = request.get("notification_type", "system")
        base_content = request.get("base_content", "")

        # 权限检查
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        if not base_content:
            raise HTTPException(status_code=400, detail="基础内容不能为空")

        personalized_content = (
            await smart_notification_service.personalize_notification_content(
                user_id, notification_type, base_content, db
            )
        )

        return {
            "user_id": user_id,
            "notification_type": notification_type,
            "original_content": base_content,
            "personalized_content": personalized_content,
            "changes_made": personalized_content != base_content,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("个性化通知失败: %s", e)
        raise HTTPException(status_code=500, detail=f"个性化通知失败: {str(e)}")


@router.post("/should-send")
async def should_send_notification(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """判断是否应该发送通知"""
    try:
        user_id = request.get("user_id", current_user.id)
        notification_type = request.get("notification_type", "system")

        # 权限检查
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        should_send, reason = await smart_notification_service.should_send_notification(
            user_id, notification_type, db
        )

        return {
            "user_id": user_id,
            "notification_type": notification_type,
            "should_send": should_send,
            "reason": reason,
            "recommendation": "发送通知" if should_send else "暂不发送",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("判断是否发送通知失败: %s", e)
        raise HTTPException(status_code=500, detail=f"判断是否发送通知失败: {str(e)}")


@router.post("/create-smart")
async def create_smart_notification(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建智能通知"""
    try:
        user_id = request.get("user_id", current_user.id)
        notification_type = request.get("notification_type", "system")
        base_title = request.get("title", "通知")
        base_message = request.get("message", "")
        priority = request.get("priority", "medium")
        trigger_type = request.get("trigger_type", "system")
        metadata = request.get("metadata", {})

        # 权限检查
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权访问该用户数据")

        if not base_message:
            raise HTTPException(status_code=400, detail="通知内容不能为空")

        # 创建智能通知
        notification = await smart_notification_service.create_smart_notification(
            user_id=user_id,
            notification_type=notification_type,
            base_title=base_title,
            base_message=base_message,
            priority=priority,
            trigger_type=trigger_type,
            metadata=metadata,
            db=db,
        )

        if notification:
            return {
                "success": True,
                "notification_id": notification.id,
                "message": "智能通知创建成功",
                "details": {
                    "user_id": user_id,
                    "type": notification_type,
                    "channel": notification.channel,
                    "status": notification.status,
                },
            }
        else:
            return {
                "success": False,
                "message": "智能通知创建被跳过",
                "details": "根据用户参与度和通知效果分析，当前不适合发送此通知",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建智能通知失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建智能通知失败: {str(e)}")


@router.get("/analysis/overview")
async def get_notification_analysis_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知分析概览（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        analysis_results = (
            await smart_notification_service.analyze_and_optimize_notifications(db)
        )

        return {
            "success": True,
            "analysis": analysis_results,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取通知分析概览失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取通知分析概览失败: {str(e)}")


@router.post("/ab-test/create")
async def create_ab_test(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建A/B测试（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        name = request.get("name")
        description = request.get("description", "")
        test_type = request.get("test_type", "notification_optimization")
        target_metric = request.get("target_metric", "click_through_rate")
        variants = request.get("variants", [])
        target_users = request.get("target_users")
        sample_size = request.get("sample_size")
        duration_days = request.get("duration_days", 7)

        if not name:
            raise HTTPException(status_code=400, detail="测试名称不能为空")

        if not variants or len(variants) < 2:
            raise HTTPException(status_code=400, detail="至少需要2个变体")

        # 创建测试
        test = await ab_testing_service.create_test(
            name=name,
            description=description,
            test_type=test_type,
            target_metric=target_metric,
            variants=variants,
            target_users=target_users,
            sample_size=sample_size,
            duration_days=duration_days,
            db=db,
        )

        if test:
            return {
                "success": True,
                "test_id": test.id,
                "message": "A/B测试创建成功",
                "details": {
                    "name": test.name,
                    "status": test.status,
                    "variants": len(test.variants),
                },
            }
        else:
            raise HTTPException(status_code=500, detail="A/B测试创建失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建A/B测试失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建A/B测试失败: {str(e)}")


@router.post("/ab-test/{test_id}/start")
async def start_ab_test(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动A/B测试（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        success = await ab_testing_service.start_test(test_id, db)

        if success:
            return {"success": True, "message": "A/B测试启动成功", "test_id": test_id}
        else:
            raise HTTPException(status_code=500, detail="A/B测试启动失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("启动A/B测试失败: %s", e)
        raise HTTPException(status_code=500, detail=f"启动A/B测试失败: {str(e)}")


@router.get("/ab-test/{test_id}/results")
async def get_ab_test_results(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取A/B测试结果（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        results = await ab_testing_service.analyze_test_results(test_id, db)

        return {"success": True, "test_id": test_id, "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取A/B测试结果失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取A/B测试结果失败: {str(e)}")


@router.post("/ab-test/{test_id}/complete")
async def complete_ab_test(
    test_id: int,
    request: Dict[str, Any] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """完成A/B测试（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        winning_variant_id = request.get("winning_variant_id") if request else None

        success = await ab_testing_service.complete_test(
            test_id, winning_variant_id, db
        )

        if success:
            return {"success": True, "message": "A/B测试完成成功", "test_id": test_id}
        else:
            raise HTTPException(status_code=500, detail="A/B测试完成失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("完成A/B测试失败: %s", e)
        raise HTTPException(status_code=500, detail=f"完成A/B测试失败: {str(e)}")


@router.get("/ab-test/active")
async def get_active_ab_tests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取活跃的A/B测试（管理员功能）"""
    try:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        tests = await ab_testing_service.get_active_tests(db)

        return {
            "success": True,
            "active_tests": [
                {
                    "id": test.id,
                    "name": test.name,
                    "test_type": test.test_type,
                    "status": test.status,
                    "start_date": test.start_date.isoformat()
                    if test.start_date
                    else None,
                    "end_date": test.end_date.isoformat() if test.end_date else None,
                    "variants": len(test.variants),
                }
                for test in tests
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取活跃A/B测试失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取活跃A/B测试失败: {str(e)}")


# ============ 辅助函数 ============


def _get_engagement_description(level) -> str:
    """获取参与度描述"""
    descriptions = {
        "high": "高参与度用户：频繁使用应用，积极互动",
        "medium": "中等参与度用户：规律使用应用",
        "low": "低参与度用户：偶尔使用应用",
        "inactive": "不活跃用户：长期未使用应用",
    }
    return descriptions.get(level.value, "未知参与度级别")


def _get_effectiveness_description(effectiveness) -> str:
    """获取通知效果描述"""
    descriptions = {
        "high": "高效果通知：用户积极回应",
        "medium": "中等效果通知：用户偶尔回应",
        "low": "低效果通知：用户很少回应",
        "negative": "负面效果通知：用户反感或关闭通知",
    }
    return descriptions.get(effectiveness.value, "未知效果级别")


def _get_time_recommendation(optimal_time: Dict[str, Any]) -> str:
    """获取时间推荐"""
    best_hours = optimal_time.get("best_hours", [])
    method = optimal_time.get("analysis_method", "default")
    confidence = optimal_time.get("confidence", 0.5)

    if not best_hours:
        return "无法确定最佳通知时间"

    hour_str = "、".join(str(h) for h in best_hours)

    if confidence > 0.7:
        confidence_desc = "高置信度"
    elif confidence > 0.4:
        confidence_desc = "中等置信度"
    else:
        confidence_desc = "低置信度"

    methods = {
        "historical_interaction": "基于历史互动模式",
        "sleep_pattern": "基于睡眠模式",
        "default": "基于默认设置",
        "error_fallback": "基于错误回退",
    }

    method_desc = methods.get(method, "未知分析方法")

    return f"建议在{hour_str}点发送通知（{method_desc}，{confidence_desc}）"


# 导入datetime用于时间戳
from datetime import datetime
