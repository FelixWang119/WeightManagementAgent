"""
睡眠分析服务
提供睡眠规律性分析、质量趋势、睡眠-体重关联分析
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
import statistics

from models.database import SleepRecord, WeightRecord


class SleepAnalysisService:
    """睡眠分析服务类"""

    @staticmethod
    async def get_sleep_pattern_analysis(
        user_id: int, days: int = 30, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取睡眠规律性分析

        分析维度：
        - 入睡时间规律性
        - 起床时间规律性
        - 睡眠时长规律性
        - 整体睡眠评分

        Returns:
            包含规律性分析结果的字典
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取指定时间范围内的睡眠记录
        result = await db.execute(
            select(SleepRecord)
            .where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(
                        end_date + timedelta(days=1), datetime.min.time()
                    ),
                )
            )
            .order_by(SleepRecord.bed_time.desc())
        )

        records = result.scalars().all()

        if len(records) < 3:
            return {
                "success": False,
                "message": "睡眠记录不足，至少需要3天数据才能分析规律性",
                "data": None,
            }

        # 提取数据
        bed_times = []
        wake_times = []
        durations = []
        qualities = []
        record_dates = []

        for record in records:
            # 入睡时间（转换为小时，处理跨天情况）
            bed_hour = record.bed_time.hour + record.bed_time.minute / 60
            if bed_hour < 12:  # 假设凌晨0-12点是前一晚的睡眠
                bed_hour += 24
            bed_times.append(bed_hour)

            # 起床时间
            wake_hour = record.wake_time.hour + record.wake_time.minute / 60
            wake_times.append(wake_hour)

            # 睡眠时长（小时）
            duration_hours = record.total_minutes / 60
            durations.append(duration_hours)

            # 睡眠质量
            if record.quality:
                qualities.append(record.quality)

            record_dates.append(record.bed_time.date())

        # 计算规律性指标
        analysis = {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "record_count": len(records),
            },
            "bedtime_regularity": SleepAnalysisService._calculate_regularity(
                bed_times, "入睡时间"
            ),
            "waketime_regularity": SleepAnalysisService._calculate_regularity(
                wake_times, "起床时间"
            ),
            "duration_regularity": SleepAnalysisService._calculate_regularity(
                durations, "睡眠时长"
            ),
            "overall_score": 0,
            "classification": "",
            "recommendations": [],
        }

        # 计算综合评分（满分100）
        bedtime_score = analysis["bedtime_regularity"]["score"]
        waketime_score = analysis["waketime_regularity"]["score"]
        duration_score = analysis["duration_regularity"]["score"]

        analysis["overall_score"] = int(
            (bedtime_score * 0.4 + waketime_score * 0.4 + duration_score * 0.2)
        )

        # 规律性等级
        if analysis["overall_score"] >= 80:
            analysis["classification"] = "优秀"
        elif analysis["overall_score"] >= 60:
            analysis["classification"] = "良好"
        elif analysis["overall_score"] >= 40:
            analysis["classification"] = "一般"
        else:
            analysis["classification"] = "需改善"

        # 生成建议
        analysis["recommendations"] = (
            SleepAnalysisService._generate_regularity_recommendations(analysis)
        )

        # 添加详细数据
        analysis["details"] = {
            "avg_bedtime": SleepAnalysisService._format_time(
                analysis["bedtime_regularity"]["mean"]
            ),
            "avg_waketime": SleepAnalysisService._format_time(
                analysis["waketime_regularity"]["mean"]
            ),
            "avg_duration": round(sum(durations) / len(durations), 1),
            "avg_quality": round(sum(qualities) / len(qualities), 1)
            if qualities
            else None,
            "earliest_bedtime": SleepAnalysisService._format_time(min(bed_times)),
            "latest_bedtime": SleepAnalysisService._format_time(max(bed_times)),
            "earliest_waketime": SleepAnalysisService._format_time(min(wake_times)),
            "latest_waketime": SleepAnalysisService._format_time(max(wake_times)),
            "shortest_sleep": round(min(durations), 1),
            "longest_sleep": round(max(durations), 1),
        }

        return {"success": True, "data": analysis}

    @staticmethod
    async def get_sleep_quality_trend(
        user_id: int, days: int = 30, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        获取睡眠质量趋势分析

        Returns:
            包含质量趋势图表数据的字典
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取睡眠记录（包含质量评分）
        result = await db.execute(
            select(SleepRecord)
            .where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(
                        end_date + timedelta(days=1), datetime.min.time()
                    ),
                    SleepRecord.quality.isnot(None),
                )
            )
            .order_by(SleepRecord.bed_time.asc())
        )

        records = result.scalars().all()

        if len(records) < 3:
            return {
                "success": False,
                "message": "质量评分记录不足，至少需要3天数据",
                "data": None,
            }

        # 构建趋势数据
        trend_data = []
        quality_scores = []
        duration_data = []

        for record in records:
            date_str = record.bed_time.date().isoformat()
            display_date = record.bed_time.strftime("%m-%d")

            trend_data.append(
                {
                    "date": date_str,
                    "display_date": display_date,
                    "quality": record.quality,
                    "duration_hours": round(record.total_minutes / 60, 1),
                    "bed_time": record.bed_time.strftime("%H:%M"),
                    "wake_time": record.wake_time.strftime("%H:%M"),
                }
            )

            quality_scores.append(record.quality)
            duration_data.append(record.total_minutes / 60)

        # 计算趋势
        trend = {
            "direction": "stable",
            "strength": "weak",
            "description": "质量保持稳定",
        }

        if len(quality_scores) >= 7:
            # 比较前半段和后半段
            mid = len(quality_scores) // 2
            first_half = sum(quality_scores[:mid]) / mid
            second_half = sum(quality_scores[mid:]) / (len(quality_scores) - mid)

            diff = second_half - first_half

            if abs(diff) < 0.3:
                trend["direction"] = "stable"
                trend["strength"] = "weak"
                trend["description"] = "质量保持稳定"
            elif diff > 0.5:
                trend["direction"] = "improving"
                trend["strength"] = "strong" if diff > 1 else "moderate"
                trend["description"] = "睡眠质量在提升"
            elif diff > 0:
                trend["direction"] = "improving"
                trend["strength"] = "weak"
                trend["description"] = "质量略有提升"
            elif diff < -0.5:
                trend["direction"] = "declining"
                trend["strength"] = "strong" if diff < -1 else "moderate"
                trend["description"] = "睡眠质量在下降"
            else:
                trend["direction"] = "declining"
                trend["strength"] = "weak"
                trend["description"] = "质量略有下降"

        # 质量分布统计
        quality_distribution = {
            "excellent": sum(1 for q in quality_scores if q >= 4.5),
            "good": sum(1 for q in quality_scores if 3.5 <= q < 4.5),
            "average": sum(1 for q in quality_scores if 2.5 <= q < 3.5),
            "poor": sum(1 for q in quality_scores if q < 2.5),
        }

        return {
            "success": True,
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "record_count": len(records),
            },
            "summary": {
                "avg_quality": round(sum(quality_scores) / len(quality_scores), 2),
                "max_quality": max(quality_scores),
                "min_quality": min(quality_scores),
                "quality_distribution": quality_distribution,
            },
            "trend": trend,
            "trend_data": trend_data,
            "chart_data": {
                "labels": [d["display_date"] for d in trend_data],
                "datasets": [
                    {
                        "label": "睡眠质量",
                        "data": quality_scores,
                        "borderColor": "rgba(75, 192, 192, 1)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)",
                        "type": "line",
                        "yAxisID": "y",
                        "fill": True,
                    },
                    {
                        "label": "睡眠时长(小时)",
                        "data": duration_data,
                        "backgroundColor": "rgba(153, 102, 255, 0.5)",
                        "type": "bar",
                        "yAxisID": "y1",
                    },
                ],
            },
        }

    @staticmethod
    async def analyze_sleep_weight_correlation(
        user_id: int, days: int = 30, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        分析睡眠与体重的关联性

        检测指标：
        - 睡眠时长与体重变化的相关性
        - 睡眠质量与体重变化的相关性
        - 睡眠不足对体重的影响

        Returns:
            关联性分析结果
        """
        if not db:
            raise ValueError("数据库会话不能为空")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # 获取睡眠和体重记录
        sleep_result = await db.execute(
            select(SleepRecord)
            .where(
                and_(
                    SleepRecord.user_id == user_id,
                    SleepRecord.bed_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    SleepRecord.bed_time
                    <= datetime.combine(
                        end_date + timedelta(days=1), datetime.min.time()
                    ),
                )
            )
            .order_by(SleepRecord.bed_time.asc())
        )
        sleep_records = sleep_result.scalars().all()

        weight_result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time()),
                    WeightRecord.record_time
                    <= datetime.combine(
                        end_date + timedelta(days=1), datetime.min.time()
                    ),
                )
            )
            .order_by(WeightRecord.record_time.asc())
        )
        weight_records = weight_result.scalars().all()

        if len(sleep_records) < 5 or len(weight_records) < 5:
            return {
                "success": False,
                "message": "数据不足，需要至少5天的睡眠和体重记录",
                "data": None,
            }

        # 构建日期映射
        sleep_by_date = {}
        for record in sleep_records:
            record_date = record.bed_time.date()
            sleep_by_date[record_date] = {
                "duration": record.total_minutes / 60,
                "quality": record.quality or 3,
                "bed_time": record.bed_time.hour + record.bed_time.minute / 60,
            }

        weight_by_date = {}
        for record in weight_records:
            record_date = record.record_time.date()
            weight_by_date[record_date] = record.weight

        # 计算睡眠对体重的影响
        sleep_impact_data = []
        dates_with_both = sorted(set(sleep_by_date.keys()) & set(weight_by_date.keys()))

        if len(dates_with_both) < 5:
            return {
                "success": False,
                "message": "同时有睡眠和体重记录的日期不足5天",
                "data": None,
            }

        # 分析睡眠不足的影响
        short_sleep_impact = {"count": 0, "avg_weight_change": 0, "dates": []}

        normal_sleep_impact = {"count": 0, "avg_weight_change": 0, "dates": []}

        for i, date_obj in enumerate(
            dates_with_both[:-1]
        ):  # 不包括最后一天（没有次日数据）
            next_date = dates_with_both[i + 1] if i + 1 < len(dates_with_both) else None

            if not next_date:
                continue

            sleep_data = sleep_by_date[date_obj]
            weight_today = weight_by_date[date_obj]

            # 查找次日的体重记录
            next_weight = weight_by_date.get(next_date)
            if not next_weight:
                continue

            weight_change = next_weight - weight_today

            sleep_impact_data.append(
                {
                    "date": date_obj.isoformat(),
                    "sleep_duration": sleep_data["duration"],
                    "sleep_quality": sleep_data["quality"],
                    "weight": weight_today,
                    "next_day_weight": next_weight,
                    "weight_change": weight_change,
                }
            )

            # 分类统计
            if sleep_data["duration"] < 7:
                short_sleep_impact["count"] += 1
                short_sleep_impact["dates"].append(
                    {
                        "date": date_obj.isoformat(),
                        "duration": sleep_data["duration"],
                        "weight_change": weight_change,
                    }
                )
            else:
                normal_sleep_impact["count"] += 1
                normal_sleep_impact["dates"].append(
                    {
                        "date": date_obj.isoformat(),
                        "duration": sleep_data["duration"],
                        "weight_change": weight_change,
                    }
                )

        # 计算平均体重变化
        if short_sleep_impact["count"] > 0:
            changes = [d["weight_change"] for d in short_sleep_impact["dates"]]
            short_sleep_impact["avg_weight_change"] = round(
                sum(changes) / len(changes), 2
            )

        if normal_sleep_impact["count"] > 0:
            changes = [d["weight_change"] for d in normal_sleep_impact["dates"]]
            normal_sleep_impact["avg_weight_change"] = round(
                sum(changes) / len(changes), 2
            )

        # 计算相关性系数
        correlation = {
            "duration_vs_weight": 0,
            "quality_vs_weight": 0,
            "strength": "none",
            "interpretation": "",
        }

        if len(sleep_impact_data) >= 5:
            durations = [d["sleep_duration"] for d in sleep_impact_data]
            qualities = [d["sleep_quality"] for d in sleep_impact_data]
            weight_changes = [d["weight_change"] for d in sleep_impact_data]

            try:
                if len(durations) == len(weight_changes) and len(durations) > 1:
                    correlation["duration_vs_weight"] = round(
                        statistics.correlation(durations, weight_changes), 2
                    )
                if len(qualities) == len(weight_changes) and len(qualities) > 1:
                    correlation["quality_vs_weight"] = round(
                        statistics.correlation(qualities, weight_changes), 2
                    )
            except:
                pass

            # 解释相关性
            duration_corr = abs(correlation["duration_vs_weight"])
            if duration_corr >= 0.7:
                correlation["strength"] = "strong"
                correlation["interpretation"] = "睡眠时长与体重变化有较强的关联"
            elif duration_corr >= 0.4:
                correlation["strength"] = "moderate"
                correlation["interpretation"] = "睡眠时长与体重变化有一定关联"
            elif duration_corr >= 0.2:
                correlation["strength"] = "weak"
                correlation["interpretation"] = "睡眠时长与体重变化关联较弱"
            else:
                correlation["strength"] = "none"
                correlation["interpretation"] = "未发现明显的睡眠-体重关联"

        # 生成洞察
        insights = []

        if short_sleep_impact["count"] > 0 and normal_sleep_impact["count"] > 0:
            diff = (
                short_sleep_impact["avg_weight_change"]
                - normal_sleep_impact["avg_weight_change"]
            )

            if diff > 0.1:
                insights.append(
                    f"睡眠不足(<7小时)后的次日，体重平均增加{short_sleep_impact['avg_weight_change']}kg，"
                    f"比正常睡眠多增加{round(diff, 2)}kg"
                )
            elif diff < -0.1:
                insights.append(
                    f"有趣的是，睡眠不足(<7小时)后的次日，体重平均变化{short_sleep_impact['avg_weight_change']}kg，"
                    f"比正常睡眠少{abs(round(diff, 2))}kg"
                )

        if correlation["strength"] in ["strong", "moderate"]:
            if correlation["duration_vs_weight"] > 0:
                insights.append("睡眠时长与次日体重呈正相关，睡得多体重可能略有增加")
            else:
                insights.append("睡眠时长与次日体重呈负相关，充足的睡眠有助于控制体重")

        if not insights:
            insights.append("继续记录数据，我们将发现更多睡眠与体重的关联模式")

        return {
            "success": True,
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "analysis_days": len(sleep_impact_data),
            },
            "correlation": correlation,
            "sleep_impact": {
                "short_sleep": short_sleep_impact,
                "normal_sleep": normal_sleep_impact,
            },
            "insights": insights,
            "recommendations": [
                "保持每晚7-8小时的充足睡眠，有助于体重管理",
                "尽量在固定时间入睡和起床，维持生物钟稳定",
                "睡前避免使用电子设备，提高睡眠质量",
            ]
            if short_sleep_impact["avg_weight_change"]
            > normal_sleep_impact["avg_weight_change"]
            else [
                "您的睡眠习惯良好，请继续保持",
                "可以尝试优化睡眠环境，进一步提升睡眠质量",
            ],
        }

    # ============ 私有辅助方法 ============

    @staticmethod
    def _calculate_regularity(values: List[float], metric_name: str) -> Dict[str, Any]:
        """
        计算规律性指标

        Args:
            values: 数值列表
            metric_name: 指标名称（用于描述）

        Returns:
            规律性分析结果
        """
        if len(values) < 2:
            return {
                "mean": values[0] if values else 0,
                "std": 0,
                "cv": 0,
                "score": 50,
                "description": f"{metric_name}数据不足",
            }

        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0

        # 变异系数 (CV) = 标准差 / 平均值
        cv = std / mean if mean > 0 else 0

        # 计算规律性评分（满分100）
        # CV越小越规律，CV < 0.05 为优秀，CV > 0.2 为差
        if cv < 0.05:
            score = 90 + int((0.05 - cv) * 200)  # 90-100分
        elif cv < 0.1:
            score = 70 + int((0.1 - cv) * 400)  # 70-90分
        elif cv < 0.2:
            score = 50 + int((0.2 - cv) * 200)  # 50-70分
        else:
            score = max(0, 50 - int((cv - 0.2) * 100))  # 0-50分

        score = min(100, max(0, score))

        if cv < 0.05:
            description = f"{metric_name}非常规律"
        elif cv < 0.1:
            description = f"{metric_name}较为规律"
        elif cv < 0.2:
            description = f"{metric_name}一般"
        else:
            description = f"{metric_name}不规律"

        return {
            "mean": round(mean, 2),
            "std": round(std, 2),
            "cv": round(cv, 3),
            "score": score,
            "description": description,
        }

    @staticmethod
    def _generate_regularity_recommendations(analysis: Dict) -> List[str]:
        """生成规律性改善建议"""
        recommendations = []

        bedtime_score = analysis["bedtime_regularity"]["score"]
        waketime_score = analysis["waketime_regularity"]["score"]
        duration_score = analysis["duration_regularity"]["score"]

        if bedtime_score < 60:
            recommendations.append("建议固定入睡时间，每天在同一时间准备睡觉")

        if waketime_score < 60:
            recommendations.append("建议固定起床时间，包括周末也保持相同的起床时间")

        if duration_score < 60:
            recommendations.append("建议保持稳定的睡眠时长，避免工作日和周末差异过大")

        if analysis["overall_score"] >= 80:
            recommendations.append("您的睡眠规律性很好，请继续保持！")
        elif not recommendations:
            recommendations.append("整体睡眠规律性良好，可以进一步优化细节")

        return recommendations

    @staticmethod
    def _format_time(hour_float: float) -> str:
        """将小时浮点数格式化为时间字符串"""
        # 处理跨天的情况（超过24小时）
        if hour_float >= 24:
            hour_float -= 24

        hour = int(hour_float)
        minute = int((hour_float % 1) * 60)

        return f"{hour:02d}:{minute:02d}"
