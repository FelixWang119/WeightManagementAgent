"""
智能通知服务
基于用户行为分析的个性化通知优化
"""

import asyncio
import logging
import json
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from collections import defaultdict
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, desc, between
from sqlalchemy.orm import selectinload

from models.database import (
    User,
    UserProfile,
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    Goal,
    GoalStatus,
    ReminderSetting,
    NotificationQueue,
    ProfilingAnswer,
)
from config.logging_config import get_module_logger
from utils.exceptions import retry_on_error
from services.notification_service import (
    NotificationService,
    NotificationPriority,
    NotificationTrigger,
    NotificationChannel,
)

logger = get_module_logger(__name__)


class UserEngagementLevel(str, Enum):
    """用户参与度级别"""

    HIGH = "high"  # 高参与度：频繁使用、积极互动
    MEDIUM = "medium"  # 中等参与度：规律使用
    LOW = "low"  # 低参与度：偶尔使用
    INACTIVE = "inactive"  # 不活跃：长期未使用


class NotificationEffectiveness(str, Enum):
    """通知效果"""

    HIGH = "high"  # 高效果：用户积极回应
    MEDIUM = "medium"  # 中等效果：用户偶尔回应
    LOW = "low"  # 低效果：用户很少回应
    NEGATIVE = "negative"  # 负面效果：用户反感或关闭通知


class SmartNotificationService:
    """智能通知服务"""

    def __init__(self, notification_service: Optional[NotificationService] = None):
        self.notification_service = notification_service or NotificationService()
        self.user_profiles_cache: Dict[int, Dict[str, Any]] = {}
        self.engagement_cache: Dict[int, UserEngagementLevel] = {}
        self.effectiveness_cache: Dict[int, Dict[str, NotificationEffectiveness]] = {}

    async def analyze_user_engagement(
        self, user_id: int, db: AsyncSession
    ) -> UserEngagementLevel:
        """分析用户参与度"""
        if user_id in self.engagement_cache:
            return self.engagement_cache[user_id]

        try:
            # 分析最近30天的用户行为
            thirty_days_ago = datetime.now() - timedelta(days=30)

            # 1. 登录频率分析 - 使用数据记录作为代理
            # 统计最近30天的数据记录总数作为活跃度指标
            weight_query = select(func.count(WeightRecord.id)).where(
                and_(
                    WeightRecord.user_id == user_id,
                    WeightRecord.record_date >= thirty_days_ago.date(),
                )
            )
            weight_count = (await db.execute(weight_query)).scalar() or 0

            exercise_query = select(func.count(ExerciseRecord.id)).where(
                and_(
                    ExerciseRecord.user_id == user_id,
                    ExerciseRecord.record_date >= thirty_days_ago.date(),
                )
            )
            exercise_count = (await db.execute(exercise_query)).scalar() or 0

            meal_query = select(func.count(MealRecord.id)).where(
                and_(
                    MealRecord.user_id == user_id,
                    MealRecord.record_date >= thirty_days_ago.date(),
                )
            )
            meal_count = (await db.execute(meal_query)).scalar() or 0

            water_query = select(func.count(WaterRecord.id)).where(
                and_(
                    WaterRecord.user_id == user_id,
                    WaterRecord.record_date >= thirty_days_ago.date(),
                )
            )
            water_count = (await db.execute(water_query)).scalar() or 0

            # 总数据记录数作为活跃度指标
            total_data_records = (
                weight_count + exercise_count + meal_count + water_count
            )
            login_count = min(total_data_records / 4, 30)  # 假设每天最多4条记录

            # 2. 数据记录频率分析 - 使用上面已经计算的值

            # 3. 目标进度分析
            goal_query = select(Goal).where(
                and_(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
            )
            goals = (await db.execute(goal_query)).scalars().all()
            goal_progress = sum(1 for goal in goals if goal.current_progress > 0) / max(
                len(goals), 1
            )

            # 4. 通知互动分析
            notification_query = select(NotificationQueue).where(
                and_(
                    NotificationQueue.user_id == user_id,
                    NotificationQueue.created_at >= thirty_days_ago,
                    NotificationQueue.status.in_(["sent", "read", "clicked"]),
                )
            )
            notifications = (await db.execute(notification_query)).scalars().all()

            read_count = sum(1 for n in notifications if n.status == "read")
            clicked_count = sum(1 for n in notifications if n.status == "clicked")
            total_notifications = len(notifications)

            interaction_rate = (read_count + clicked_count) / max(
                total_notifications, 1
            )

            # 计算参与度分数
            engagement_score = 0
            engagement_score += min(login_count / 30, 1.0) * 25  # 登录频率权重25%
            engagement_score += (
                min((weight_count + exercise_count) / 60, 1.0) * 25
            )  # 数据记录权重25%
            engagement_score += goal_progress * 25  # 目标进度权重25%
            engagement_score += interaction_rate * 25  # 通知互动权重25%

            # 确定参与度级别
            if engagement_score >= 70:
                level = UserEngagementLevel.HIGH
            elif engagement_score >= 40:
                level = UserEngagementLevel.MEDIUM
            elif engagement_score >= 15:
                level = UserEngagementLevel.LOW
            else:
                level = UserEngagementLevel.INACTIVE

            self.engagement_cache[user_id] = level
            logger.info(
                "用户 %s 参与度分析: 分数=%.1f, 级别=%s",
                user_id,
                engagement_score,
                level,
            )

            return level

        except Exception as e:
            logger.error("分析用户参与度失败: %s", e)
            return UserEngagementLevel.MEDIUM  # 默认中等参与度

    async def analyze_notification_effectiveness(
        self, user_id: int, notification_type: str, db: AsyncSession
    ) -> NotificationEffectiveness:
        """分析通知效果"""
        cache_key = f"{user_id}_{notification_type}"
        if cache_key in self.effectiveness_cache:
            return self.effectiveness_cache[user_id][notification_type]

        try:
            # 分析最近90天的通知效果
            ninety_days_ago = datetime.now() - timedelta(days=90)

            query = (
                select(NotificationQueue)
                .where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.reminder_type == notification_type,
                        NotificationQueue.created_at >= ninety_days_ago,
                        NotificationQueue.status.in_(
                            ["sent", "read", "clicked", "dismissed"]
                        ),
                    )
                )
                .order_by(desc(NotificationQueue.created_at))
            )

            notifications = (await db.execute(query)).scalars().all()

            if not notifications:
                return NotificationEffectiveness.MEDIUM  # 默认中等效果

            total_count = len(notifications)
            read_count = sum(1 for n in notifications if n.status == "read")
            clicked_count = sum(1 for n in notifications if n.status == "clicked")
            dismissed_count = sum(1 for n in notifications if n.status == "dismissed")

            # 计算效果指标
            read_rate = read_count / total_count
            click_rate = clicked_count / total_count
            dismiss_rate = dismissed_count / total_count

            # 时间衰减分析（最近的通知权重更高）
            recent_notifications = [
                n
                for n in notifications
                if n.created_at >= datetime.now() - timedelta(days=30)
            ]
            recent_read_rate = sum(
                1 for n in recent_notifications if n.status == "read"
            ) / max(len(recent_notifications), 1)

            # 综合效果评分
            effectiveness_score = (
                read_rate * 0.4  # 阅读率权重40%
                + click_rate * 0.4  # 点击率权重40%
                + (1 - dismiss_rate) * 0.2  # 非关闭率权重20%
            )

            # 考虑时间衰减
            if recent_notifications:
                recent_score = recent_read_rate * 0.5 + click_rate * 0.5
                effectiveness_score = effectiveness_score * 0.6 + recent_score * 0.4

            # 确定效果级别
            if effectiveness_score >= 0.6:
                level = NotificationEffectiveness.HIGH
            elif effectiveness_score >= 0.3:
                level = NotificationEffectiveness.MEDIUM
            elif effectiveness_score >= 0.1:
                level = NotificationEffectiveness.LOW
            else:
                level = NotificationEffectiveness.NEGATIVE

            # 更新缓存
            if user_id not in self.effectiveness_cache:
                self.effectiveness_cache[user_id] = {}
            self.effectiveness_cache[user_id][notification_type] = level

            logger.info(
                "通知效果分析: 用户=%s, 类型=%s, 分数=%.2f, 级别=%s",
                user_id,
                notification_type,
                effectiveness_score,
                level,
            )

            return level

        except Exception as e:
            logger.error("分析通知效果失败: %s", e)
            return NotificationEffectiveness.MEDIUM

    async def get_optimal_notification_time(
        self, user_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """获取用户最佳通知时间"""
        try:
            # 分析用户历史互动时间模式
            thirty_days_ago = datetime.now() - timedelta(days=30)

            # 获取用户有互动的通知时间
            query = select(NotificationQueue).where(
                and_(
                    NotificationQueue.user_id == user_id,
                    NotificationQueue.created_at >= thirty_days_ago,
                    NotificationQueue.status.in_(["read", "clicked"]),
                )
            )

            notifications = (await db.execute(query)).scalars().all()

            if notifications:
                # 分析互动时间分布
                interaction_hours = [n.created_at.hour for n in notifications]

                if interaction_hours:
                    # 计算最活跃的小时
                    hour_counts = defaultdict(int)
                    for hour in interaction_hours:
                        hour_counts[hour] += 1

                    # 找到最活跃的3个小时
                    best_hours = sorted(
                        hour_counts.items(), key=lambda x: x[1], reverse=True
                    )[:3]

                    return {
                        "best_hours": [hour for hour, _ in best_hours],
                        "analysis_method": "historical_interaction",
                        "confidence": min(len(notifications) / 30, 1.0),
                    }

            # 如果没有历史数据，使用用户画像信息
            profile_query = select(UserProfile).where(UserProfile.user_id == user_id)
            profile = (await db.execute(profile_query)).scalar_one_or_none()

            if profile and profile.sleep_pattern:
                # 根据睡眠模式推断最佳时间
                try:
                    sleep_data = json.loads(profile.sleep_pattern)
                    wake_up_time = sleep_data.get("wake_up_time", "07:00")

                    # 解析起床时间
                    wake_hour = int(wake_up_time.split(":")[0])

                    # 最佳通知时间：起床后1-3小时，午休后，下班后
                    best_hours = [
                        (wake_hour + 1) % 24,  # 起床后1小时
                        (wake_hour + 2) % 24,  # 起床后2小时
                        14,  # 下午2点
                        19,  # 晚上7点
                    ]

                    return {
                        "best_hours": best_hours[:3],
                        "analysis_method": "sleep_pattern",
                        "confidence": 0.7,
                    }
                except (json.JSONDecodeError, ValueError):
                    pass

            # 默认最佳时间：上午10点，下午3点，晚上8点
            return {
                "best_hours": [10, 15, 20],
                "analysis_method": "default",
                "confidence": 0.5,
            }

        except Exception as e:
            logger.error("获取最佳通知时间失败: %s", e)
            return {
                "best_hours": [10, 15, 20],
                "analysis_method": "error_fallback",
                "confidence": 0.3,
            }

    async def personalize_notification_content(
        self, user_id: int, notification_type: str, base_content: str, db: AsyncSession
    ) -> str:
        """个性化通知内容"""
        try:
            # 获取用户画像
            profile_query = select(UserProfile).where(UserProfile.user_id == user_id)
            profile = (await db.execute(profile_query)).scalar_one_or_none()

            if not profile:
                return base_content

            # 根据用户画像调整语气和内容
            personalized_content = base_content

            # 根据动力类型调整
            if profile.motivation_type:
                if profile.motivation_type.value == "data_driven":
                    # 数据驱动型：添加具体数据
                    if "体重" in base_content:
                        # 获取最新体重数据
                        weight_query = (
                            select(WeightRecord)
                            .where(WeightRecord.user_id == user_id)
                            .order_by(desc(WeightRecord.record_date))
                            .limit(1)
                        )

                        latest_weight = (
                            await db.execute(weight_query)
                        ).scalar_one_or_none()
                        if latest_weight:
                            personalized_content += (
                                f"\n当前体重: {latest_weight.weight}kg"
                            )

                elif profile.motivation_type.value == "emotional_support":
                    # 情感支持型：添加鼓励性语言
                    encouragement_phrases = [
                        "加油！你做得很好！",
                        "坚持就是胜利！",
                        "相信自己，你可以的！",
                        "每天进步一点点！",
                    ]
                    import random

                    personalized_content += f"\n{random.choice(encouragement_phrases)}"

            # 根据沟通风格调整
            if profile.communication_style:
                if profile.communication_style.value == "direct":
                    # 直接型：简洁明了
                    personalized_content = personalized_content.replace(
                        "温馨提示：", ""
                    )
                    personalized_content = personalized_content.replace("建议您", "请")
                elif profile.communication_style.value == "encouraging":
                    # 鼓励型：添加表情符号
                    personalized_content = personalized_content.replace("。", "！😊")

            # 根据参与度调整
            engagement_level = await self.analyze_user_engagement(user_id, db)

            if engagement_level == UserEngagementLevel.LOW:
                # 低参与度用户：更简洁、更有吸引力的内容
                personalized_content = personalized_content.split("\n")[0]
                personalized_content += " 💪"
            elif engagement_level == UserEngagementLevel.HIGH:
                # 高参与度用户：提供更多详细信息
                pass  # 保持原内容

            return personalized_content

        except Exception as e:
            logger.error("个性化通知内容失败: %s", e)
            return base_content

    async def should_send_notification(
        self, user_id: int, notification_type: str, db: AsyncSession
    ) -> Tuple[bool, str]:
        """判断是否应该发送通知"""
        try:
            # 1. 检查用户参与度
            engagement_level = await self.analyze_user_engagement(user_id, db)

            if engagement_level == UserEngagementLevel.INACTIVE:
                return False, "用户不活跃"

            # 2. 检查通知效果
            effectiveness = await self.analyze_notification_effectiveness(
                user_id, notification_type, db
            )

            if effectiveness == NotificationEffectiveness.NEGATIVE:
                return False, "通知效果负面"
            elif effectiveness == NotificationEffectiveness.LOW:
                # 低效果通知：减少频率
                # 检查最近是否发送过同类通知
                twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

                recent_query = select(func.count(NotificationQueue.id)).where(
                    and_(
                        NotificationQueue.user_id == user_id,
                        NotificationQueue.reminder_type == notification_type,
                        NotificationQueue.created_at >= twenty_four_hours_ago,
                        NotificationQueue.status.in_(["sent", "pending"]),
                    )
                )

                recent_count = (await db.execute(recent_query)).scalar() or 0

                if recent_count > 0:
                    return False, "同类通知24小时内已发送"

            # 3. 检查最佳通知时间
            optimal_time = await self.get_optimal_notification_time(user_id, db)
            current_hour = datetime.now().hour

            if current_hour not in optimal_time["best_hours"]:
                # 如果不是最佳时间，检查时间差
                time_diffs = [abs(current_hour - h) for h in optimal_time["best_hours"]]
                min_diff = min(time_diffs)

                if min_diff > 2:  # 距离最佳时间超过2小时
                    return (
                        False,
                        f"非最佳通知时间（最佳时间: {optimal_time['best_hours']}）",
                    )

            # 4. 检查免打扰时段
            profile_query = select(UserProfile).where(UserProfile.user_id == user_id)
            profile = (await db.execute(profile_query)).scalar_one_or_none()

            if profile and profile.notification_preferences:
                try:
                    prefs = json.loads(profile.notification_preferences)
                    quiet_hours = prefs.get("quiet_hours", {})

                    if quiet_hours.get("enabled", False):
                        start_time = quiet_hours.get("start_time", "22:00")
                        end_time = quiet_hours.get("end_time", "07:00")

                        start_hour = int(start_time.split(":")[0])
                        end_hour = int(end_time.split(":")[0])

                        current_hour = datetime.now().hour

                        if start_hour <= end_hour:
                            # 同一天内的免打扰时段
                            if start_hour <= current_hour < end_hour:
                                return False, "免打扰时段"
                        else:
                            # 跨天的免打扰时段
                            if current_hour >= start_hour or current_hour < end_hour:
                                return False, "免打扰时段"
                except (json.JSONDecodeError, ValueError):
                    pass

            # 5. 检查通知频率限制
            if engagement_level == UserEngagementLevel.LOW:
                max_daily = 2  # 低参与度用户每天最多2条
            elif engagement_level == UserEngagementLevel.MEDIUM:
                max_daily = 4  # 中等参与度用户每天最多4条
            else:
                max_daily = 6  # 高参与度用户每天最多6条

            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            daily_query = select(func.count(NotificationQueue.id)).where(
                and_(
                    NotificationQueue.user_id == user_id,
                    NotificationQueue.created_at >= today_start,
                    NotificationQueue.status.in_(["sent", "pending"]),
                )
            )

            daily_count = (await db.execute(daily_query)).scalar() or 0

            if daily_count >= max_daily:
                return False, f"达到每日通知上限（{max_daily}条）"

            return True, "可以发送通知"

        except Exception as e:
            logger.error("判断是否发送通知失败: %s", e)
            return True, f"判断失败，默认发送: {str(e)}"

    async def create_smart_notification(
        self,
        user_id: int,
        notification_type: str,
        base_title: str,
        base_message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        trigger_type: NotificationTrigger = NotificationTrigger.SYSTEM,
        metadata: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None,
    ) -> Optional[NotificationQueue]:
        """创建智能通知"""
        if db is None:
            return None

        try:
            # 判断是否应该发送通知
            should_send, reason = await self.should_send_notification(
                user_id, notification_type, db
            )

            if not should_send:
                logger.info(
                    "跳过通知: 用户=%s, 类型=%s, 原因=%s",
                    user_id,
                    notification_type,
                    reason,
                )
                return None

            # 个性化通知内容
            personalized_message = await self.personalize_notification_content(
                user_id, notification_type, base_message, db
            )

            # 确定最佳渠道
            optimal_channel = await self._determine_optimal_channel(
                user_id, notification_type, db
            )

            # 创建通知
            notification = NotificationQueue(
                user_id=user_id,
                reminder_type=notification_type,
                message=personalized_message,
                scheduled_at=datetime.now(),
                status="pending",
                channel=optimal_channel.value,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            logger.info(
                "创建智能通知: ID=%s, 用户=%s, 类型=%s, 渠道=%s",
                notification.id,
                user_id,
                notification_type,
                optimal_channel.value,
            )

            # 记录通知创建行为
            await self._record_notification_creation(
                user_id, notification_type, reason, db
            )

            return notification

        except Exception as e:
            logger.error("创建智能通知失败: %s", e)
            await db.rollback()
            return None

    async def _determine_optimal_channel(
        self, user_id: int, notification_type: str, db: AsyncSession
    ) -> NotificationChannel:
        """确定最佳通知渠道"""
        try:
            # 获取用户渠道偏好
            profile_query = select(UserProfile).where(UserProfile.user_id == user_id)
            profile = (await db.execute(profile_query)).scalar_one_or_none()

            if profile and profile.notification_preferences:
                try:
                    prefs = json.loads(profile.notification_preferences)
                    channels = prefs.get("channels", {})

                    # 检查用户偏好的渠道
                    for channel_name, enabled in channels.items():
                        if enabled:
                            try:
                                channel = NotificationChannel(channel_name)
                                return channel
                            except ValueError:
                                continue
                except (json.JSONDecodeError, ValueError):
                    pass

            # 根据通知类型选择默认渠道
            if notification_type in [
                "weight_reminder",
                "water_reminder",
                "exercise_reminder",
            ]:
                return NotificationChannel.PUSH  # 提醒类用推送
            elif notification_type in ["achievement", "goal_progress"]:
                return NotificationChannel.CHAT  # 成就类用聊天
            else:
                return NotificationChannel.CHAT  # 默认用聊天

        except Exception as e:
            logger.error("确定最佳渠道失败: %s", e)
            return NotificationChannel.CHAT

    async def _record_notification_creation(
        self,
        user_id: int,
        notification_type: str,
        decision_reason: str,
        db: AsyncSession,
    ):
        """记录通知创建决策"""
        try:
            # 这里可以记录到用户行为表或专门的决策日志表
            # 暂时只记录日志
            logger.debug(
                "通知决策记录: 用户=%s, 类型=%s, 原因=%s",
                user_id,
                notification_type,
                decision_reason,
            )

        except Exception as e:
            logger.error("记录通知决策失败: %s", e)

    async def analyze_and_optimize_notifications(
        self, db: AsyncSession
    ) -> Dict[str, Any]:
        """分析和优化通知策略"""
        try:
            analysis_results = {
                "total_users": 0,
                "high_engagement_users": 0,
                "low_engagement_users": 0,
                "notification_effectiveness": {},
                "recommendations": [],
            }

            # 获取所有用户
            user_query = select(User.id)
            users = (await db.execute(user_query)).scalars().all()
            analysis_results["total_users"] = len(users)

            engagement_counts = defaultdict(int)
            effectiveness_summary = defaultdict(lambda: defaultdict(int))

            for user_id in users:
                # 分析用户参与度
                engagement = await self.analyze_user_engagement(user_id, db)
                engagement_counts[engagement.value] += 1

                if engagement == UserEngagementLevel.HIGH:
                    analysis_results["high_engagement_users"] += 1
                elif engagement in [
                    UserEngagementLevel.LOW,
                    UserEngagementLevel.INACTIVE,
                ]:
                    analysis_results["low_engagement_users"] += 1

                # 分析各种通知类型的效果
                notification_types = [
                    "weight_reminder",
                    "water_reminder",
                    "exercise_reminder",
                    "achievement",
                    "goal_progress",
                    "system",
                ]

                for n_type in notification_types:
                    effectiveness = await self.analyze_notification_effectiveness(
                        user_id, n_type, db
                    )
                    effectiveness_summary[n_type][effectiveness.value] += 1

            # 汇总效果分析
            for n_type, counts in effectiveness_summary.items():
                total = sum(counts.values())
                if total > 0:
                    analysis_results["notification_effectiveness"][n_type] = {
                        level: count / total for level, count in counts.items()
                    }

            # 生成优化建议
            recommendations = []

            # 1. 低参与度用户建议
            low_engagement_ratio = analysis_results["low_engagement_users"] / max(
                analysis_results["total_users"], 1
            )
            if low_engagement_ratio > 0.3:
                recommendations.append(
                    {
                        "type": "engagement",
                        "priority": "high",
                        "description": f"低参与度用户比例较高 ({low_engagement_ratio:.1%})，建议优化用户留存策略",
                        "suggestions": [
                            "减少对低参与度用户的通知频率",
                            "发送更具吸引力的欢迎通知",
                            "提供个性化激励",
                        ],
                    }
                )

            # 2. 通知效果建议
            for n_type, effectiveness in analysis_results[
                "notification_effectiveness"
            ].items():
                negative_ratio = effectiveness.get("negative", 0)
                if negative_ratio > 0.2:
                    recommendations.append(
                        {
                            "type": "effectiveness",
                            "priority": "medium",
                            "description": f"{n_type} 类型通知负面效果比例较高 ({negative_ratio:.1%})",
                            "suggestions": [
                                f"优化 {n_type} 通知的内容和时机",
                                "考虑减少发送频率",
                                "进行A/B测试优化",
                            ],
                        }
                    )

            analysis_results["recommendations"] = recommendations

            logger.info("通知策略分析完成: %s", analysis_results)
            return analysis_results

        except Exception as e:
            logger.error("通知策略分析失败: %s", e)
            return {"error": str(e)}

    def clear_cache(self):
        """清空缓存"""
        self.user_profiles_cache.clear()
        self.engagement_cache.clear()
        self.effectiveness_cache.clear()
        logger.info("智能通知服务缓存已清空")
