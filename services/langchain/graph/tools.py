"""
LangGraph Tools实现
4个初始工具：体重趋势分析、长期记忆搜索、BMI计算、打卡历史获取
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time

from .monitor import monitor_tool, performance_monitor
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


# ============ Tool 1: 分析体重趋势 ============


@monitor_tool(graph_id="coach_graph")
async def analyze_weight_trends_tool(
    user_id: int,
    checkins: List[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """
    分析体重趋势工具

    Args:
        user_id: 用户ID
        checkins: 打卡记录列表
        profile: 用户画像（可选）
        days: 分析天数，默认30天

    Returns:
        体重分析结果
    """
    start_time = time.time()
    logger.info("调用体重趋势分析工具: user_id=%s, days=%d", user_id, days)

    try:
        # 1. 过滤体重记录
        weight_checkins = [
            checkin for checkin in checkins if checkin.get("type") == "weight"
        ]

        if not weight_checkins:
            return {
                "success": True,
                "has_data": False,
                "message": "暂无体重记录数据",
                "recommendation": "建议开始记录体重，以便跟踪变化趋势。",
                "timestamp": datetime.now().isoformat(),
            }

        # 2. 提取体重数据
        weight_data = []
        for checkin in weight_checkins:
            data = checkin.get("data", {})
            weight = data.get("weight")
            timestamp = checkin.get("timestamp")

            if weight and timestamp:
                try:
                    if isinstance(timestamp, str):
                        timestamp_dt = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    else:
                        timestamp_dt = timestamp

                    weight_data.append(
                        {
                            "weight": float(weight),
                            "timestamp": timestamp_dt,
                            "date": timestamp_dt.date().isoformat(),
                        }
                    )
                except (ValueError, TypeError) as e:
                    logger.warning("解析体重数据失败: %s", e)

        if not weight_data:
            return {
                "success": True,
                "has_data": False,
                "message": "体重数据格式错误",
                "timestamp": datetime.now().isoformat(),
            }

        # 3. 按时间排序
        weight_data.sort(key=lambda x: x["timestamp"])

        # 4. 计算基础统计
        weights = [item["weight"] for item in weight_data]
        latest_weight = weights[-1]
        earliest_weight = weights[0]
        min_weight = min(weights)
        max_weight = max(weights)
        avg_weight = sum(weights) / len(weights)

        # 5. 计算变化趋势
        weight_change = latest_weight - earliest_weight
        change_percentage = (
            (weight_change / earliest_weight * 100) if earliest_weight > 0 else 0
        )

        # 6. 判断趋势
        if weight_change > 0.5:
            trend = "上升"
            trend_direction = "up"
            suggestion = "体重有所上升，建议关注饮食控制和增加运动。"
        elif weight_change < -0.5:
            trend = "下降"
            trend_direction = "down"
            suggestion = "体重有所下降，继续保持健康习惯！"
        else:
            trend = "稳定"
            trend_direction = "stable"
            suggestion = "体重保持稳定，这是很好的状态。"

        # 7. 计算近期变化（最近7天）
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_weights = [
            item["weight"] for item in weight_data if item["timestamp"] >= recent_cutoff
        ]

        recent_change = 0
        if len(recent_weights) >= 2:
            recent_change = recent_weights[-1] - recent_weights[0]

        # 8. 构建返回结果
        result = {
            "success": True,
            "has_data": True,
            "summary": {
                "latest_weight": round(latest_weight, 1),
                "earliest_weight": round(earliest_weight, 1),
                "min_weight": round(min_weight, 1),
                "max_weight": round(max_weight, 1),
                "avg_weight": round(avg_weight, 1),
                "total_records": len(weight_data),
                "recording_days": (
                    weight_data[-1]["timestamp"] - weight_data[0]["timestamp"]
                ).days,
            },
            "trend": {
                "direction": trend_direction,
                "description": trend,
                "weight_change": round(weight_change, 1),
                "change_percentage": round(change_percentage, 1),
                "recent_change": round(recent_change, 1) if recent_weights else 0,
                "suggestion": suggestion,
            },
            "data_points": [
                {
                    "date": item["date"],
                    "weight": round(item["weight"], 1),
                }
                for item in weight_data[-10:]  # 只返回最近10个点
            ],
            "timestamp": datetime.now().isoformat(),
        }

        # 9. 如果有用户画像，提供个性化建议
        if profile:
            height = profile.get("height")
            target_weight = profile.get("target_weight")

            if height and latest_weight:
                # 计算BMI
                height_m = float(height) / 100  # 假设身高是厘米
                bmi = latest_weight / (height_m**2)

                result["bmi"] = {
                    "value": round(bmi, 1),
                    "category": _get_bmi_category(bmi),
                }

            if target_weight:
                weight_to_goal = target_weight - latest_weight
                result["goal"] = {
                    "target_weight": target_weight,
                    "weight_to_goal": round(weight_to_goal, 1),
                    "progress_percentage": round(
                        (1 - abs(weight_to_goal) / abs(target_weight - earliest_weight))
                        * 100,
                        1,
                    )
                    if target_weight != earliest_weight
                    else 100,
                }

        # 10. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "analyze_weight_trends_tool",
            duration_ms,
            True,
            user_id=user_id,
            data_points=len(weight_data),
        )

        logger.info(
            "体重趋势分析完成: user_id=%s, 耗时=%.2fms, 记录数=%d",
            user_id,
            duration_ms,
            len(weight_data),
        )

        return result

    except Exception as e:
        logger.exception("体重趋势分析失败: user_id=%s, 错误=%s", user_id, e)

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "analyze_weight_trends_tool",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return {
            "success": False,
            "error": f"体重趋势分析失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ============ Tool 2: 搜索长期记忆 ============


@monitor_tool(graph_id="coach_graph")
async def search_long_term_memory_tool(
    user_id: int,
    query: str,
    checkins: Optional[List[Dict[str, Any]]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    搜索长期记忆工具

    Args:
        user_id: 用户ID
        query: 搜索查询
        checkins: 打卡记录列表（可选，用于本地搜索）
        limit: 返回结果数量

    Returns:
        记忆搜索结果
    """
    start_time = time.time()
    logger.info("调用长期记忆搜索工具: user_id=%s, query=%s", user_id, query)

    try:
        results = []

        # 1. 尝试使用ChromaDB向量搜索
        try:
            from services.vectorstore.chroma_store import get_user_vector_store

            vector_store = get_user_vector_store(user_id)
            vector_results = vector_store.similarity_search(query, k=limit)

            for result in vector_results:
                results.append(
                    {
                        "source": "vector_store",
                        "content": result.get("document", ""),
                        "metadata": result.get("metadata", {}),
                        "score": result.get("score", 0.0),
                    }
                )

        except ImportError as e:
            logger.warning("ChromaDB不可用: %s", e)
        except Exception as e:
            logger.warning("向量搜索失败: %s", e)

        # 2. 在打卡记录中搜索（备用方案）
        if checkins and len(results) < limit:
            for checkin in checkins:
                checkin_type = checkin.get("type", "")
                checkin_data = checkin.get("data", {})
                timestamp = checkin.get("timestamp", "")

                # 简单的内容匹配
                content_parts = []
                if checkin_type:
                    content_parts.append(f"类型: {checkin_type}")
                if isinstance(checkin_data, dict):
                    for key, value in checkin_data.items():
                        if value and isinstance(value, (str, int, float)):
                            content_parts.append(f"{key}: {value}")

                content = "，".join(content_parts)

                # 简单关键词匹配
                if query.lower() in content.lower():
                    results.append(
                        {
                            "source": "checkin_database",
                            "content": content,
                            "metadata": {
                                "type": checkin_type,
                                "timestamp": timestamp,
                                "data": checkin_data,
                            },
                            "score": 0.8,  # 人工评分
                        }
                    )

                if len(results) >= limit:
                    break

        # 3. 如果没有结果，返回默认信息
        if not results:
            return {
                "success": True,
                "has_results": False,
                "query": query,
                "message": f"未找到与'{query}'相关的记忆记录",
                "suggestion": "尝试使用更具体的关键词，或开始记录相关数据。",
                "results": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 4. 按分数排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # 5. 构建返回结果
        result = {
            "success": True,
            "has_results": True,
            "query": query,
            "total_results": len(results),
            "results": results[:limit],
            "timestamp": datetime.now().isoformat(),
        }

        # 6. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "search_long_term_memory_tool",
            duration_ms,
            True,
            user_id=user_id,
            query_length=len(query),
            result_count=len(results),
        )

        logger.info(
            "长期记忆搜索完成: user_id=%s, 耗时=%.2fms, 结果数=%d",
            user_id,
            duration_ms,
            len(results),
        )

        return result

    except Exception as e:
        logger.exception("长期记忆搜索失败: user_id=%s, 错误=%s", user_id, e)

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "search_long_term_memory_tool",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return {
            "success": False,
            "error": f"长期记忆搜索失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ============ Tool 3: 计算BMI ============


@monitor_tool(graph_id="coach_graph")
async def calculate_bmi_tool(
    user_id: int,
    checkins: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    计算BMI工具

    Args:
        user_id: 用户ID
        checkins: 打卡记录列表
        profile: 用户画像

    Returns:
        BMI计算结果
    """
    start_time = time.time()
    logger.info("调用BMI计算工具: user_id=%s", user_id)

    try:
        # 1. 获取身高信息
        height = profile.get("height")
        if not height:
            return {
                "success": True,
                "has_data": False,
                "message": "缺少身高信息",
                "recommendation": "请先完善个人资料中的身高信息。",
                "timestamp": datetime.now().isoformat(),
            }

        # 2. 获取最新体重
        weight_checkins = [
            checkin for checkin in checkins if checkin.get("type") == "weight"
        ]

        if not weight_checkins:
            return {
                "success": True,
                "has_data": False,
                "message": "暂无体重记录",
                "recommendation": "请先记录体重数据。",
                "timestamp": datetime.now().isoformat(),
            }

        latest_weight_checkin = weight_checkins[-1]
        weight_data = latest_weight_checkin.get("data", {})
        weight = weight_data.get("weight")

        if not weight:
            return {
                "success": True,
                "has_data": False,
                "message": "体重数据格式错误",
                "timestamp": datetime.now().isoformat(),
            }

        # 3. 解析身高和体重
        try:
            # 假设身高是字符串，如 "170厘米" 或 "170"
            if isinstance(height, str):
                if "厘米" in height:
                    height_cm = float(height.replace("厘米", "").strip())
                else:
                    height_cm = float(height.strip())
            else:
                height_cm = float(height)

            weight_kg = float(weight)

        except (ValueError, TypeError) as e:
            logger.warning("解析身高体重数据失败: %s", e)
            return {
                "success": True,
                "has_data": False,
                "message": "身高或体重数据格式错误",
                "timestamp": datetime.now().isoformat(),
            }

        # 4. 计算BMI
        height_m = height_cm / 100
        bmi = weight_kg / (height_m**2)

        # 5. 获取BMI分类和建议
        bmi_category = _get_bmi_category(bmi)
        bmi_advice = _get_bmi_advice(bmi_category, weight_kg, height_cm)

        # 6. 构建返回结果
        result = {
            "success": True,
            "has_data": True,
            "bmi": {
                "value": round(bmi, 1),
                "category": bmi_category,
                "interpretation": _get_bmi_interpretation(bmi_category),
            },
            "physical_data": {
                "height_cm": round(height_cm, 1),
                "weight_kg": round(weight_kg, 1),
                "ideal_weight_range": _get_ideal_weight_range(height_cm),
            },
            "advice": bmi_advice,
            "timestamp": datetime.now().isoformat(),
        }

        # 7. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "calculate_bmi_tool",
            duration_ms,
            True,
            user_id=user_id,
            bmi_value=bmi,
        )

        logger.info(
            "BMI计算完成: user_id=%s, 耗时=%.2fms, BMI=%.1f", user_id, duration_ms, bmi
        )

        return result

    except Exception as e:
        logger.exception("BMI计算失败: user_id=%s, 错误=%s", user_id, e)

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "calculate_bmi_tool",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return {
            "success": False,
            "error": f"BMI计算失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ============ Tool 4: 获取打卡历史 ============


@monitor_tool(graph_id="coach_graph")
async def get_checkin_history_tool(
    user_id: int,
    checkins: List[Dict[str, Any]],
    checkin_type: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    获取打卡历史工具

    Args:
        user_id: 用户ID
        checkins: 打卡记录列表
        checkin_type: 打卡类型（可选）
        days: 查询天数，默认7天
        limit: 返回数量限制

    Returns:
        打卡历史结果
    """
    start_time = time.time()
    logger.info(
        "调用打卡历史工具: user_id=%s, type=%s, days=%d",
        user_id,
        checkin_type or "all",
        days,
    )

    try:
        # 1. 过滤打卡记录
        filtered_checkins = checkins.copy()

        # 按类型过滤
        if checkin_type:
            filtered_checkins = [
                checkin
                for checkin in filtered_checkins
                if checkin.get("type") == checkin_type
            ]

        # 按时间过滤
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_checkins = [
            checkin
            for checkin in filtered_checkins
            if checkin.get("timestamp")
            and datetime.fromisoformat(checkin["timestamp"].replace("Z", "+00:00"))
            >= cutoff_date
        ]

        # 2. 按时间排序（最新的在前）
        filtered_checkins.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        # 3. 应用数量限制
        filtered_checkins = filtered_checkins[:limit]

        # 4. 统计信息
        type_counts = {}
        for checkin in checkins:
            checkin_type_key = checkin.get("type", "unknown")
            type_counts[checkin_type_key] = type_counts.get(checkin_type_key, 0) + 1

        # 5. 构建返回结果
        result = {
            "success": True,
            "query": {
                "type": checkin_type,
                "days": days,
                "limit": limit,
            },
            "summary": {
                "total_checkins": len(checkins),
                "filtered_checkins": len(filtered_checkins),
                "type_distribution": type_counts,
                "date_range": {
                    "start": cutoff_date.isoformat(),
                    "end": datetime.now().isoformat(),
                },
            },
            "checkins": filtered_checkins,
            "timestamp": datetime.now().isoformat(),
        }

        # 6. 记录性能指标
        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "get_checkin_history_tool",
            duration_ms,
            True,
            user_id=user_id,
            checkin_type=checkin_type,
            result_count=len(filtered_checkins),
        )

        logger.info(
            "打卡历史获取完成: user_id=%s, 耗时=%.2fms, 记录数=%d",
            user_id,
            duration_ms,
            len(filtered_checkins),
        )

        return result

    except Exception as e:
        logger.exception("打卡历史获取失败: user_id=%s, 错误=%s", user_id, e)

        duration_ms = (time.time() - start_time) * 1000
        performance_monitor.record_tool_call(
            "coach_graph",
            "get_checkin_history_tool",
            duration_ms,
            False,
            user_id=user_id,
            error=str(e),
        )

        return {
            "success": False,
            "error": f"打卡历史获取失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ============ 辅助函数 ============


def _get_bmi_category(bmi: float) -> str:
    """获取BMI分类"""
    if bmi < 18.5:
        return "偏瘦"
    elif bmi < 24:
        return "正常"
    elif bmi < 28:
        return "超重"
    else:
        return "肥胖"


def _get_bmi_interpretation(category: str) -> str:
    """获取BMI分类解释"""
    interpretations = {
        "偏瘦": "体重过轻，可能影响健康，建议适当增加营养摄入和肌肉锻炼。",
        "正常": "体重在健康范围内，继续保持良好的生活习惯。",
        "超重": "体重超过健康范围，建议调整饮食结构，增加运动。",
        "肥胖": "体重显著超标，对健康有较大风险，建议咨询专业医生并制定减重计划。",
    }
    return interpretations.get(category, "无法确定BMI分类。")


def _get_bmi_advice(
    category: str, weight_kg: float, height_cm: float
) -> Dict[str, str]:
    """获取BMI相关建议"""
    height_m = height_cm / 100
    ideal_min = 18.5 * (height_m**2)
    ideal_max = 24 * (height_m**2)

    advice_templates = {
        "偏瘦": {
            "饮食": f"建议增加蛋白质摄入，目标体重范围：{ideal_min:.1f} - {ideal_max:.1f}公斤",
            "运动": "建议进行力量训练增加肌肉量",
            "生活习惯": "保证充足睡眠，避免过度消耗",
        },
        "正常": {
            "饮食": f"保持均衡饮食，当前体重{weight_kg:.1f}公斤在理想范围{ideal_min:.1f} - {ideal_max:.1f}公斤内",
            "运动": "每周保持150分钟中等强度运动",
            "生活习惯": "保持规律作息，监测体重变化",
        },
        "超重": {
            "饮食": f"建议控制热量摄入，目标减重到{ideal_max:.1f}公斤以下",
            "运动": "增加有氧运动，每周300分钟以上",
            "生活习惯": "减少久坐，增加日常活动量",
        },
        "肥胖": {
            "饮食": "严格控制热量摄入，咨询营养师制定个性化饮食计划",
            "运动": "在医生指导下进行适当运动，避免受伤",
            "生活习惯": "建立健康生活习惯，考虑专业减重指导",
        },
    }

    return advice_templates.get(
        category,
        {
            "饮食": "请咨询专业医生获取个性化建议",
            "运动": "请咨询专业医生获取个性化建议",
            "生活习惯": "请咨询专业医生获取个性化建议",
        },
    )


def _get_ideal_weight_range(height_cm: float) -> Dict[str, float]:
    """获取理想体重范围"""
    height_m = height_cm / 100
    min_weight = 18.5 * (height_m**2)
    max_weight = 24 * (height_m**2)

    return {
        "min_kg": round(min_weight, 1),
        "max_kg": round(max_weight, 1),
        "range_kg": round(max_weight - min_weight, 1),
    }
