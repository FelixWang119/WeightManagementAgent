"""
A/B测试服务
用于优化通知策略的A/B测试框架
"""

import asyncio
import logging
import json
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, desc
from sqlalchemy.orm import selectinload

from models.database import (
    User,
    NotificationQueue,
    ABTest,
    ABTestVariant,
    ABTestResult,
)
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class TestStatus(str, Enum):
    """测试状态"""

    DRAFT = "draft"  # 草稿
    ACTIVE = "active"  # 进行中
    PAUSED = "paused"  # 暂停
    COMPLETED = "completed"  # 已完成
    ARCHIVED = "archived"  # 已归档


class VariantType(str, Enum):
    """变体类型"""

    CONTROL = "control"  # 控制组
    TREATMENT = "treatment"  # 实验组


class ABTestingService:
    """A/B测试服务"""

    def __init__(self):
        self.active_tests_cache: Dict[int, ABTest] = {}
        self.user_assignments_cache: Dict[
            Tuple[int, int], str
        ] = {}  # (user_id, test_id) -> variant_id

    async def create_test(
        self,
        name: str,
        description: str,
        test_type: str,
        target_metric: str,
        variants: List[Dict[str, Any]],
        target_users: Optional[List[int]] = None,
        sample_size: Optional[int] = None,
        duration_days: int = 7,
        db: AsyncSession = None,
    ) -> Optional[ABTest]:
        """创建A/B测试"""
        if db is None:
            return None

        try:
            # 创建测试
            test = ABTest(
                name=name,
                description=description,
                test_type=test_type,
                target_metric=target_metric,
                status=TestStatus.DRAFT,
                target_users=json.dumps(target_users) if target_users else None,
                sample_size=sample_size,
                start_date=None,
                end_date=None,
                duration_days=duration_days,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.add(test)
            await db.commit()
            await db.refresh(test)

            # 创建变体
            variant_objects = []
            for i, variant_data in enumerate(variants):
                variant = ABTestVariant(
                    test_id=test.id,
                    name=variant_data.get("name", f"Variant {i + 1}"),
                    variant_type=VariantType.CONTROL
                    if i == 0
                    else VariantType.TREATMENT,
                    configuration=json.dumps(variant_data.get("configuration", {})),
                    allocation_percentage=variant_data.get(
                        "allocation_percentage", 50 if i > 0 else 50
                    ),
                    is_default=i == 0,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                variant_objects.append(variant)

            db.add_all(variant_objects)
            await db.commit()

            # 刷新获取完整对象
            await db.refresh(test)
            test.variants = variant_objects

            logger.info(
                "创建A/B测试: ID=%s, 名称=%s, 类型=%s", test.id, name, test_type
            )
            return test

        except Exception as e:
            logger.error("创建A/B测试失败: %s", e)
            await db.rollback()
            return None

    async def start_test(self, test_id: int, db: AsyncSession) -> bool:
        """启动A/B测试"""
        try:
            # 获取测试
            test_query = select(ABTest).where(ABTest.id == test_id)
            test = (await db.execute(test_query)).scalar_one_or_none()

            if not test:
                logger.error("测试不存在: ID=%s", test_id)
                return False

            if test.status != TestStatus.DRAFT:
                logger.error("测试状态不允许启动: 当前状态=%s", test.status)
                return False

            # 更新测试状态
            test.status = TestStatus.ACTIVE
            test.start_date = datetime.now()
            test.end_date = datetime.now() + timedelta(days=test.duration_days)
            test.updated_at = datetime.now()

            await db.commit()

            # 更新缓存
            self.active_tests_cache[test_id] = test

            logger.info("启动A/B测试: ID=%s, 名称=%s", test_id, test.name)
            return True

        except Exception as e:
            logger.error("启动A/B测试失败: %s", e)
            await db.rollback()
            return False

    async def assign_user_to_variant(
        self, user_id: int, test_id: int, db: AsyncSession
    ) -> Optional[ABTestVariant]:
        """为用户分配测试变体"""
        cache_key = (user_id, test_id)
        if cache_key in self.user_assignments_cache:
            variant_id = self.user_assignments_cache[cache_key]
            # 从数据库获取变体
            variant_query = select(ABTestVariant).where(ABTestVariant.id == variant_id)
            return (await db.execute(variant_query)).scalar_one_or_none()

        try:
            # 获取测试
            test_query = select(ABTest).where(
                and_(ABTest.id == test_id, ABTest.status == TestStatus.ACTIVE)
            )
            test = (await db.execute(test_query)).scalar_one_or_none()

            if not test:
                logger.warning("测试不存在或未激活: ID=%s", test_id)
                return None

            # 检查用户是否已经在测试中
            existing_query = select(ABTestResult).where(
                and_(ABTestResult.test_id == test_id, ABTestResult.user_id == user_id)
            )
            existing = (await db.execute(existing_query)).scalar_one_or_none()

            if existing:
                # 用户已分配，返回原有变体
                variant_query = select(ABTestVariant).where(
                    ABTestVariant.id == existing.variant_id
                )
                variant = (await db.execute(variant_query)).scalar_one_or_none()

                if variant:
                    self.user_assignments_cache[cache_key] = variant.id
                    return variant

            # 获取所有变体
            variants_query = select(ABTestVariant).where(
                ABTestVariant.test_id == test_id
            )
            variants = (await db.execute(variants_query)).scalars().all()

            if not variants:
                logger.error("测试没有变体: ID=%s", test_id)
                return None

            # 使用一致性哈希分配变体
            variant = self._hash_based_assignment(user_id, test_id, variants)

            # 记录分配结果
            result = ABTestResult(
                test_id=test_id,
                user_id=user_id,
                variant_id=variant.id,
                assigned_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            db.add(result)
            await db.commit()

            # 更新缓存
            self.user_assignments_cache[cache_key] = variant.id

            logger.debug(
                "用户分配变体: 用户=%s, 测试=%s, 变体=%s",
                user_id,
                test_id,
                variant.name,
            )
            return variant

        except Exception as e:
            logger.error("分配用户变体失败: %s", e)
            await db.rollback()
            return None

    def _hash_based_assignment(
        self, user_id: int, test_id: int, variants: List[ABTestVariant]
    ) -> ABTestVariant:
        """基于哈希的变体分配"""
        # 创建哈希键
        hash_key = f"{user_id}_{test_id}"
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)

        # 计算分配区间
        total_percentage = sum(v.allocation_percentage for v in variants)
        if total_percentage != 100:
            # 重新归一化
            for v in variants:
                v.allocation_percentage = int(
                    v.allocation_percentage * 100 / total_percentage
                )

        # 分配变体
        hash_mod = hash_value % 100
        cumulative = 0

        for variant in variants:
            cumulative += variant.allocation_percentage
            if hash_mod < cumulative:
                return variant

        # 默认返回第一个变体
        return variants[0]

    async def record_test_event(
        self,
        test_id: int,
        user_id: int,
        event_type: str,
        event_value: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None,
    ) -> bool:
        """记录测试事件"""
        if db is None:
            return False

        try:
            # 获取用户分配的变体
            result_query = select(ABTestResult).where(
                and_(ABTestResult.test_id == test_id, ABTestResult.user_id == user_id)
            )
            result = (await db.execute(result_query)).scalar_one_or_none()

            if not result:
                logger.warning("用户未参与测试: 用户=%s, 测试=%s", user_id, test_id)
                return False

            # 更新结果
            if event_type == "exposure":
                result.exposed_at = datetime.now()
                result.exposure_count = (result.exposure_count or 0) + 1
            elif event_type == "click":
                result.clicked_at = datetime.now()
                result.click_count = (result.click_count or 0) + 1
            elif event_type == "conversion":
                result.converted_at = datetime.now()
                result.conversion_count = (result.conversion_count or 0) + 1
                if event_value is not None:
                    result.conversion_value = event_value
            elif event_type == "negative":
                result.negative_feedback_at = datetime.now()
                result.negative_feedback_count = (
                    result.negative_feedback_count or 0
                ) + 1

            # 更新元数据
            if metadata:
                current_metadata = (
                    json.loads(result.metadata) if result.metadata else {}
                )
                current_metadata.update(metadata)
                result.metadata = json.dumps(current_metadata)

            result.updated_at = datetime.now()

            await db.commit()

            logger.debug(
                "记录测试事件: 测试=%s, 用户=%s, 事件=%s", test_id, user_id, event_type
            )
            return True

        except Exception as e:
            logger.error("记录测试事件失败: %s", e)
            await db.rollback()
            return False

    async def analyze_test_results(
        self, test_id: int, db: AsyncSession
    ) -> Dict[str, Any]:
        """分析测试结果"""
        try:
            # 获取测试信息
            test_query = select(ABTest).where(ABTest.id == test_id)
            test = (await db.execute(test_query)).scalar_one_or_none()

            if not test:
                return {"error": "测试不存在"}

            # 获取所有变体
            variants_query = select(ABTestVariant).where(
                ABTestVariant.test_id == test_id
            )
            variants = (await db.execute(variants_query)).scalars().all()

            # 获取测试结果
            results_query = select(ABTestResult).where(ABTestResult.test_id == test_id)
            results = (await db.execute(results_query)).scalars().all()

            # 按变体分组结果
            variant_results = {}
            for variant in variants:
                variant_results[variant.id] = {
                    "variant": variant,
                    "results": [],
                    "summary": {
                        "total_users": 0,
                        "exposed_users": 0,
                        "clicked_users": 0,
                        "converted_users": 0,
                        "negative_feedback_users": 0,
                        "total_exposures": 0,
                        "total_clicks": 0,
                        "total_conversions": 0,
                        "total_negative_feedbacks": 0,
                        "total_conversion_value": 0,
                    },
                }

            # 填充结果数据
            for result in results:
                variant_id = result.variant_id
                if variant_id not in variant_results:
                    continue

                variant_results[variant_id]["results"].append(result)
                summary = variant_results[variant_id]["summary"]

                summary["total_users"] += 1

                if result.exposed_at:
                    summary["exposed_users"] += 1
                    summary["total_exposures"] += result.exposure_count or 0

                if result.clicked_at:
                    summary["clicked_users"] += 1
                    summary["total_clicks"] += result.click_count or 0

                if result.converted_at:
                    summary["converted_users"] += 1
                    summary["total_conversions"] += result.conversion_count or 0
                    summary["total_conversion_value"] += result.conversion_value or 0

                if result.negative_feedback_at:
                    summary["negative_feedback_users"] += 1
                    summary["total_negative_feedbacks"] += (
                        result.negative_feedback_count or 0
                    )

            # 计算指标
            analysis_results = {
                "test_id": test_id,
                "test_name": test.name,
                "test_type": test.test_type,
                "target_metric": test.target_metric,
                "status": test.status,
                "start_date": test.start_date,
                "end_date": test.end_date,
                "variants": [],
                "overall_metrics": {
                    "total_users": len(results),
                    "total_exposures": sum(
                        v["summary"]["total_exposures"]
                        for v in variant_results.values()
                    ),
                    "total_clicks": sum(
                        v["summary"]["total_clicks"] for v in variant_results.values()
                    ),
                    "total_conversions": sum(
                        v["summary"]["total_conversions"]
                        for v in variant_results.values()
                    ),
                },
                "statistical_significance": {},
                "recommendation": None,
            }

            # 计算每个变体的详细指标
            for variant_id, data in variant_results.items():
                variant = data["variant"]
                summary = data["summary"]

                # 计算率指标
                exposure_rate = summary["exposed_users"] / max(
                    summary["total_users"], 1
                )
                click_through_rate = summary["clicked_users"] / max(
                    summary["exposed_users"], 1
                )
                conversion_rate = summary["converted_users"] / max(
                    summary["exposed_users"], 1
                )
                negative_feedback_rate = summary["negative_feedback_users"] / max(
                    summary["exposed_users"], 1
                )

                variant_data = {
                    "variant_id": variant.id,
                    "variant_name": variant.name,
                    "variant_type": variant.variant_type.value,
                    "allocation_percentage": variant.allocation_percentage,
                    "user_count": summary["total_users"],
                    "metrics": {
                        "exposure_rate": exposure_rate,
                        "click_through_rate": click_through_rate,
                        "conversion_rate": conversion_rate,
                        "negative_feedback_rate": negative_feedback_rate,
                        "avg_conversion_value": summary["total_conversion_value"]
                        / max(summary["converted_users"], 1),
                    },
                    "raw_counts": summary,
                }

                analysis_results["variants"].append(variant_data)

            # 计算统计显著性（简化版）
            if len(analysis_results["variants"]) >= 2:
                control_variant = next(
                    (
                        v
                        for v in analysis_results["variants"]
                        if v["variant_type"] == "control"
                    ),
                    None,
                )
                treatment_variants = [
                    v
                    for v in analysis_results["variants"]
                    if v["variant_type"] == "treatment"
                ]

                if control_variant and treatment_variants:
                    for treatment in treatment_variants:
                        # 计算提升率
                        control_rate = control_variant["metrics"][test.target_metric]
                        treatment_rate = treatment["metrics"][test.target_metric]

                        if control_rate > 0:
                            lift = (treatment_rate - control_rate) / control_rate
                        else:
                            lift = 0 if treatment_rate == 0 else float("inf")

                        # 简化的显著性检查（基于样本量）
                        control_n = control_variant["user_count"]
                        treatment_n = treatment["user_count"]

                        # 这里应该使用真正的统计检验，这里用简化版
                        is_significant = (
                            control_n >= 100 and treatment_n >= 100 and abs(lift) > 0.1
                        )

                        analysis_results["statistical_significance"][
                            treatment["variant_id"]
                        ] = {
                            "lift": lift,
                            "is_significant": is_significant,
                            "confidence": "medium" if is_significant else "low",
                        }

            # 生成推荐
            analysis_results["recommendation"] = self._generate_recommendation(
                analysis_results
            )

            logger.info(
                "测试结果分析完成: 测试=%s, 用户数=%s",
                test_id,
                analysis_results["overall_metrics"]["total_users"],
            )
            return analysis_results

        except Exception as e:
            logger.error("分析测试结果失败: %s", e)
            return {"error": str(e)}

    def _generate_recommendation(
        self, analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成测试推荐"""
        try:
            if not analysis_results["variants"]:
                return {"action": "continue_testing", "reason": "数据不足"}

            # 找到最佳变体
            target_metric = analysis_results["target_metric"]
            variants = analysis_results["variants"]

            # 按目标指标排序
            sorted_variants = sorted(
                variants, key=lambda v: v["metrics"][target_metric], reverse=True
            )
            best_variant = sorted_variants[0]
            control_variant = next(
                (v for v in variants if v["variant_type"] == "control"), None
            )

            if not control_variant:
                return {"action": "continue_testing", "reason": "没有控制组"}

            # 检查显著性
            best_variant_id = best_variant["variant_id"]
            significance_info = analysis_results["statistical_significance"].get(
                best_variant_id
            )

            if significance_info and significance_info["is_significant"]:
                if best_variant["variant_type"] == "treatment":
                    lift = significance_info["lift"]
                    if lift > 0:
                        return {
                            "action": "implement_treatment",
                            "reason": f"实验组提升{lift:.1%}，统计显著",
                            "best_variant": best_variant["variant_name"],
                            "lift": lift,
                        }
                    else:
                        return {
                            "action": "keep_control",
                            "reason": f"控制组表现更好，实验组下降{abs(lift):.1%}",
                            "best_variant": control_variant["variant_name"],
                        }
                else:
                    return {
                        "action": "keep_control",
                        "reason": "控制组是最佳变体",
                        "best_variant": control_variant["variant_name"],
                    }
            else:
                # 检查负面反馈率
                negative_feedback_threshold = 0.1
                high_negative_variants = [
                    v
                    for v in variants
                    if v["metrics"]["negative_feedback_rate"]
                    > negative_feedback_threshold
                ]

                if high_negative_variants:
                    return {
                        "action": "pause_variants",
                        "reason": f"变体负面反馈率超过{negative_feedback_threshold:.0%}",
                        "problematic_variants": [
                            v["variant_name"] for v in high_negative_variants
                        ],
                    }

                # 数据不足，继续测试
                total_users = analysis_results["overall_metrics"]["total_users"]
                if total_users < 100:
                    return {
                        "action": "continue_testing",
                        "reason": f"样本量不足（当前{total_users}用户，建议至少100）",
                    }
                else:
                    return {
                        "action": "extend_test",
                        "reason": "数据未显示统计显著差异，建议延长测试时间",
                        "current_duration": "7天",
                    }

        except Exception as e:
            logger.error("生成推荐失败: %s", e)
            return {"action": "continue_testing", "reason": f"分析错误: {str(e)}"}

    async def complete_test(
        self,
        test_id: int,
        winning_variant_id: Optional[int] = None,
        db: AsyncSession = None,
    ) -> bool:
        """完成A/B测试"""
        if db is None:
            return False

        try:
            # 获取测试
            test_query = select(ABTest).where(ABTest.id == test_id)
            test = (await db.execute(test_query)).scalar_one_or_none()

            if not test:
                logger.error("测试不存在: ID=%s", test_id)
                return False

            if test.status != TestStatus.ACTIVE:
                logger.error("测试状态不允许完成: 当前状态=%s", test.status)
                return False

            # 分析结果
            analysis = await self.analyze_test_results(test_id, db)

            # 确定获胜变体
            if winning_variant_id:
                # 使用指定的获胜变体
                variant_query = select(ABTestVariant).where(
                    ABTestVariant.id == winning_variant_id
                )
                winning_variant = (await db.execute(variant_query)).scalar_one_or_none()
            elif (
                "recommendation" in analysis
                and analysis["recommendation"]["action"] == "implement_treatment"
            ):
                # 使用推荐的最佳变体
                best_variant_name = analysis["recommendation"]["best_variant"]
                variant_query = select(ABTestVariant).where(
                    and_(
                        ABTestVariant.test_id == test_id,
                        ABTestVariant.name == best_variant_name,
                    )
                )
                winning_variant = (await db.execute(variant_query)).scalar_one_or_none()
            else:
                winning_variant = None

            # 更新测试状态
            test.status = TestStatus.COMPLETED
            test.end_date = datetime.now()
            test.winning_variant_id = winning_variant.id if winning_variant else None
            test.results_summary = json.dumps(analysis)
            test.updated_at = datetime.now()

            await db.commit()

            # 从缓存中移除
            self.active_tests_cache.pop(test_id, None)

            # 清理用户分配缓存
            cache_keys_to_remove = [
                key for key in self.user_assignments_cache.keys() if key[1] == test_id
            ]
            for key in cache_keys_to_remove:
                self.user_assignments_cache.pop(key, None)

            logger.info(
                "完成A/B测试: ID=%s, 获胜变体=%s",
                test_id,
                winning_variant.name if winning_variant else "无",
            )
            return True

        except Exception as e:
            logger.error("完成A/B测试失败: %s", e)
            await db.rollback()
            return False

    async def get_active_tests(self, db: AsyncSession) -> List[ABTest]:
        """获取活跃的A/B测试"""
        try:
            # 检查缓存
            if self.active_tests_cache:
                return list(self.active_tests_cache.values())

            # 从数据库获取
            query = select(ABTest).where(ABTest.status == TestStatus.ACTIVE)
            tests = (await db.execute(query)).scalars().all()

            # 更新缓存
            for test in tests:
                self.active_tests_cache[test.id] = test

            return tests

        except Exception as e:
            logger.error("获取活跃测试失败: %s", e)
            return []

    async def create_notification_ab_test(
        self,
        name: str,
        description: str,
        notification_type: str,
        variants_config: List[Dict[str, Any]],
        db: AsyncSession = None,
    ) -> Optional[ABTest]:
        """创建通知A/B测试"""
        if db is None:
            return None

        try:
            # 准备变体配置
            variants = []
            for i, config in enumerate(variants_config):
                variant_name = config.get("name", f"Variant {i + 1}")
                allocation = config.get("allocation_percentage", 50 if i > 0 else 50)

                variants.append(
                    {
                        "name": variant_name,
                        "configuration": {
                            "notification_type": notification_type,
                            "content_variations": config.get("content_variations", []),
                            "timing_strategy": config.get("timing_strategy", "default"),
                            "channel_preference": config.get(
                                "channel_preference", "chat"
                            ),
                            "personalization_level": config.get(
                                "personalization_level", "medium"
                            ),
                        },
                        "allocation_percentage": allocation,
                    }
                )

            # 创建测试
            test = await self.create_test(
                name=name,
                description=description,
                test_type="notification_optimization",
                target_metric="click_through_rate",
                variants=variants,
                duration_days=14,  # 通知测试通常需要2周
                db=db,
            )

            return test

        except Exception as e:
            logger.error("创建通知A/B测试失败: %s", e)
            return None

    def clear_cache(self):
        """清空缓存"""
        self.active_tests_cache.clear()
        self.user_assignments_cache.clear()
        logger.info("A/B测试服务缓存已清空")
