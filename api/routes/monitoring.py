"""
监控与记忆增强 API
提供性能监控、准确率追踪、记忆管理
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Any, List

from models.database import User
from api.routes.user import get_current_user
from services.memory_enhancement_service import (
    PerformanceMonitor,
    AccuracyTracker,
    QualityAssessment,
    MemoryCache,
    memory_cache,
)

router = APIRouter()


class FeedbackRequest(BaseModel):
    prediction_index: int
    feedback: str
    correct_value: Optional[Any] = None


class PredictionRequest(BaseModel):
    prediction_type: str
    predicted_value: Any
    actual_value: Optional[Any] = None
    metadata: Optional[dict] = None


@router.get("/performance")
async def get_performance_stats():
    """
    获取性能监控统计

    - 响应时间统计（平均、最小、最大、P95）
    - 操作次数统计
    - 错误统计
    """
    stats = PerformanceMonitor.get_stats()
    return {"success": True, "data": stats}


@router.get("/performance/{operation}")
async def get_operation_stats(operation: str):
    """获取特定操作的性能统计"""
    stats = PerformanceMonitor.get_stats(operation)
    return {"success": True, "data": stats}


@router.post("/performance/reset")
async def reset_performance_stats():
    """重置性能统计"""
    PerformanceMonitor.reset()
    return {"success": True, "message": "性能统计已重置"}


@router.get("/accuracy")
async def get_accuracy_stats(prediction_type: Optional[str] = None):
    """
    获取识别准确率统计

    - prediction_type: 可选，按类型过滤
    - 返回准确率和各类别统计
    """
    stats = AccuracyTracker.get_accuracy(prediction_type)
    return {"success": True, "data": stats}


@router.post("/accuracy/prediction")
async def record_prediction(request: PredictionRequest):
    """记录预测结果"""
    AccuracyTracker.record_prediction(
        prediction_type=request.prediction_type,
        predicted_value=request.predicted_value,
        actual_value=request.actual_value,
        metadata=request.metadata,
    )
    return {"success": True, "message": "预测已记录"}


@router.post("/accuracy/feedback")
async def record_feedback(request: FeedbackRequest):
    """记录用户反馈"""
    AccuracyTracker.record_feedback(
        prediction_index=request.prediction_index,
        feedback=request.feedback,
        correct_value=request.correct_value,
    )
    return {"success": True, "message": "反馈已记录"}


@router.get("/accuracy/reset")
async def reset_accuracy_stats():
    """重置准确率统计"""
    AccuracyTracker.reset()
    return {"success": True, "message": "准确率统计已重置"}


@router.get("/cache")
async def get_cache_stats():
    """获取缓存统计"""
    stats = memory_cache.get_stats()
    return {"success": True, "data": stats}


@router.post("/cache/clear")
async def clear_cache():
    """清空缓存"""
    memory_cache.clear()
    return {"success": True, "message": "缓存已清空"}


@router.post("/quality/response")
async def assess_response_quality(response: dict):
    """评估响应质量"""
    result = QualityAssessment.assess_response_quality(response)
    return {"success": True, "data": result}


@router.post("/quality/data")
async def assess_data_quality(data: dict):
    """评估数据质量"""
    result = QualityAssessment.assess_data_quality(data)
    return {"success": True, "data": result}


@router.get("/dashboard")
async def get_monitoring_dashboard():
    """获取监控仪表盘"""
    performance = PerformanceMonitor.get_stats()
    accuracy = AccuracyTracker.get_accuracy()
    cache = memory_cache.get_stats()

    return {
        "success": True,
        "data": {
            "performance": performance,
            "accuracy": accuracy,
            "cache": cache,
        },
    }
