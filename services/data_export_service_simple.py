"""
简化版数据导出服务
提供Excel格式的数据导出功能
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
import pandas as pd
import io
import json

from models.database import (
    WeightRecord,
    MealRecord,
    ExerciseRecord,
    WaterRecord,
    SleepRecord,
    WeeklyReport,
    UserRecipe,
    Recipe,
)
from config.logging_config import get_module_logger

logger = get_module_logger(__name__)


class SimpleDataExportService:
    """简化版数据导出服务"""

    @staticmethod
    async def export_user_data_to_excel(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[bytes, str]:
        """
        导出用户数据到Excel

        Args:
            db: 数据库会话
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            (Excel文件内容, 文件名)
        """
        try:
            # 收集所有数据
            data_sheets = {}

            # 1. 体重数据
            weight_data = await SimpleDataExportService._get_weight_data(
                db, user_id, start_date, end_date
            )
            if weight_data:
                data_sheets["体重记录"] = weight_data

            # 2. 餐食数据
            meal_data = await SimpleDataExportService._get_meal_data(
                db, user_id, start_date, end_date
            )
            if meal_data:
                data_sheets["餐食记录"] = meal_data

            # 3. 运动数据
            exercise_data = await SimpleDataExportService._get_exercise_data(
                db, user_id, start_date, end_date
            )
            if exercise_data:
                data_sheets["运动记录"] = exercise_data

            # 4. 饮水数据
            water_data = await SimpleDataExportService._get_water_data(
                db, user_id, start_date, end_date
            )
            if water_data:
                data_sheets["饮水记录"] = water_data

            # 5. 睡眠数据
            sleep_data = await SimpleDataExportService._get_sleep_data(
                db, user_id, start_date, end_date
            )
            if sleep_data:
                data_sheets["睡眠记录"] = sleep_data

            # 6. 周报数据
            report_data = await SimpleDataExportService._get_report_data(db, user_id)
            if report_data:
                data_sheets["周报记录"] = report_data

            # 7. 食谱数据
            recipe_data = await SimpleDataExportService._get_recipe_data(db, user_id)
            if recipe_data:
                data_sheets["食谱记录"] = recipe_data

            # 生成Excel文件
            return await SimpleDataExportService._create_excel_file(
                data_sheets, user_id, start_date, end_date
            )

        except Exception as e:
            logger.exception("导出用户数据失败: %s", str(e))
            raise

    @staticmethod
    async def _get_weight_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """获取体重数据"""
        try:
            query = select(WeightRecord).where(WeightRecord.user_id == user_id)

            if start_date:
                query = query.where(WeightRecord.record_date >= start_date)
            if end_date:
                query = query.where(WeightRecord.record_date <= end_date)

            query = query.order_by(WeightRecord.record_date)

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                data.append(
                    {
                        "日期": record.record_date.strftime("%Y-%m-%d"),
                        "体重(kg)": record.weight,
                        "体脂率(%)": record.body_fat if record.body_fat else "",
                        "备注": record.notes if record.notes else "",
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取体重数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_meal_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """获取餐食数据"""
        try:
            query = select(MealRecord).where(MealRecord.user_id == user_id)

            if start_date:
                query = query.where(
                    MealRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time())
                )
            if end_date:
                query = query.where(
                    MealRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time())
                )

            query = query.order_by(MealRecord.record_time)

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                # 解析食物项
                food_items = []
                if record.food_items:
                    try:
                        food_list = (
                            json.loads(record.food_items)
                            if isinstance(record.food_items, str)
                            else record.food_items
                        )
                        if isinstance(food_list, list):
                            for food in food_list:
                                if isinstance(food, dict):
                                    food_items.append(
                                        f"{food.get('name', '')} {food.get('quantity', '')}{food.get('unit', '')}"
                                    )
                    except:
                        food_items = ["数据解析错误"]

                data.append(
                    {
                        "日期": record.record_time.strftime("%Y-%m-%d"),
                        "时间": record.record_time.strftime("%H:%M"),
                        "餐食类型": record.meal_type.value if record.meal_type else "",
                        "食物": ", ".join(food_items),
                        "总热量(千卡)": record.total_calories
                        if record.total_calories
                        else 0,
                        "备注": record.notes if record.notes else "",
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取餐食数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_exercise_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """获取运动数据"""
        try:
            query = select(ExerciseRecord).where(ExerciseRecord.user_id == user_id)

            if start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                query = query.where(ExerciseRecord.record_time >= start_datetime)
            if end_date:
                end_datetime = datetime.combine(end_date, datetime.max.time())
                query = query.where(ExerciseRecord.record_time <= end_datetime)

            query = query.order_by(ExerciseRecord.record_time.desc())

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                data.append(
                    {
                        "日期": record.record_time.strftime("%Y-%m-%d")
                        if record.record_time
                        else "",
                        "运动类型": record.exercise_type
                        if record.exercise_type
                        else "",
                        "时长(分钟)": record.duration_minutes
                        if record.duration_minutes
                        else 0,
                        "强度": record.intensity.value if record.intensity else "",
                        "消耗热量(千卡)": record.calories_burned
                        if record.calories_burned
                        else 0,
                        "备注": record.notes if record.notes else "",
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取运动数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_water_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """获取饮水数据"""
        try:
            query = select(WaterRecord).where(WaterRecord.user_id == user_id)

            if start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                query = query.where(WaterRecord.record_time >= start_datetime)
            if end_date:
                end_datetime = datetime.combine(end_date, datetime.max.time())
                query = query.where(WaterRecord.record_time <= end_datetime)

            query = query.order_by(WaterRecord.record_time.desc())

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                data.append(
                    {
                        "日期": record.record_time.strftime("%Y-%m-%d")
                        if record.record_time
                        else "",
                        "饮水量(ml)": record.amount_ml if record.amount_ml else 0,
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取饮水数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_sleep_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """获取睡眠数据"""
        try:
            query = select(SleepRecord).where(SleepRecord.user_id == user_id)

            if start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                query = query.where(SleepRecord.bed_time >= start_datetime)
            if end_date:
                end_datetime = datetime.combine(end_date, datetime.max.time())
                query = query.where(SleepRecord.bed_time <= end_datetime)

            query = query.order_by(SleepRecord.bed_time.desc())

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                data.append(
                    {
                        "日期": record.bed_time.strftime("%Y-%m-%d")
                        if record.bed_time
                        else "",
                        "入睡时间": record.bed_time.strftime("%H:%M")
                        if record.bed_time
                        else "",
                        "起床时间": record.wake_time.strftime("%H:%M")
                        if record.wake_time
                        else "",
                        "睡眠时长(分钟)": record.total_minutes
                        if record.total_minutes
                        else 0,
                        "睡眠质量(1-5)": record.quality if record.quality else "",
                        "备注": record.notes if record.notes else "",
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取睡眠数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_report_data(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
        """获取周报数据"""
        try:
            query = (
                select(WeeklyReport)
                .where(WeeklyReport.user_id == user_id)
                .order_by(desc(WeeklyReport.week_start))
            )

            result = await db.execute(query)
            records = result.scalars().all()

            data = []
            for record in records:
                # 解析JSON数据
                highlights = []
                improvements = []

                if record.highlights:
                    try:
                        highlights_data = (
                            json.loads(record.highlights)
                            if isinstance(record.highlights, str)
                            else record.highlights
                        )
                        if isinstance(highlights_data, list):
                            for item in highlights_data:
                                if isinstance(item, dict):
                                    highlights.append(item.get("text", ""))
                    except:
                        highlights = ["数据解析错误"]

                if record.improvements:
                    try:
                        improvements_data = (
                            json.loads(record.improvements)
                            if isinstance(record.improvements, str)
                            else record.improvements
                        )
                        if isinstance(improvements_data, list):
                            for item in improvements_data:
                                if isinstance(item, dict):
                                    improvements.append(item.get("text", ""))
                    except:
                        improvements = ["数据解析错误"]

                data.append(
                    {
                        "周开始日期": record.week_start.strftime("%Y-%m-%d"),
                        "体重变化(kg)": record.weight_change
                        if record.weight_change
                        else 0,
                        "平均体重(kg)": record.avg_weight if record.avg_weight else 0,
                        "平均摄入热量(千卡/天)": record.avg_calories_in
                        if record.avg_calories_in
                        else 0,
                        "平均消耗热量(千卡/天)": record.avg_calories_out
                        if record.avg_calories_out
                        else 0,
                        "运动天数": record.exercise_days if record.exercise_days else 0,
                        "本周亮点": "; ".join(highlights),
                        "改进建议": "; ".join(improvements),
                        "生成时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return data

        except Exception as e:
            logger.exception("获取周报数据失败: %s", str(e))
            return []

    @staticmethod
    async def _get_recipe_data(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
        """获取食谱数据"""
        try:
            query = (
                select(UserRecipe)
                .where(UserRecipe.user_id == user_id)
                .order_by(desc(UserRecipe.updated_at))
            )

            result = await db.execute(query)
            user_recipes = result.scalars().all()

            data = []
            for user_recipe in user_recipes:
                if user_recipe.recipe:
                    data.append(
                        {
                            "食谱名称": user_recipe.recipe.name,
                            "分类": user_recipe.recipe.category.value
                            if user_recipe.recipe.category
                            else "",
                            "菜系": user_recipe.recipe.cuisine.value
                            if user_recipe.recipe.cuisine
                            else "",
                            "难度": user_recipe.recipe.difficulty.value
                            if user_recipe.recipe.difficulty
                            else "",
                            "每份热量(千卡)": user_recipe.recipe.calories_per_serving
                            if user_recipe.recipe.calories_per_serving
                            else 0,
                            "是否收藏": "是" if user_recipe.is_favorite else "否",
                            "烹饪次数": user_recipe.cooked_count
                            if user_recipe.cooked_count
                            else 0,
                            "最后烹饪时间": user_recipe.last_cooked.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            if user_recipe.last_cooked
                            else "",
                            "评分": user_recipe.rating if user_recipe.rating else "",
                            "用户笔记": user_recipe.notes if user_recipe.notes else "",
                        }
                    )

            return data

        except Exception as e:
            logger.exception("获取食谱数据失败: %s", str(e))
            return []

    @staticmethod
    async def _create_excel_file(
        data_sheets: Dict[str, List[Dict[str, Any]]],
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Tuple[bytes, str]:
        """创建Excel文件"""
        try:
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # 为每个数据类型创建工作表
                for sheet_name, sheet_data in data_sheets.items():
                    if sheet_data:
                        df = pd.DataFrame(sheet_data)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)

                        # 调整列宽
                        worksheet = writer.sheets[sheet_name]
                        for column in df:
                            column_length = max(
                                df[column].astype(str).map(len).max(), len(column)
                            )
                            col_idx = df.columns.get_loc(column)
                            worksheet.column_dimensions[chr(65 + col_idx)].width = min(
                                column_length + 2, 50
                            )

                # 添加汇总工作表
                summary_data = {
                    "数据类型": list(data_sheets.keys()),
                    "记录数量": [len(records) for records in data_sheets.values()],
                    "数据范围": f"{start_date.strftime('%Y-%m-%d') if start_date else '全部'} 至 {end_date.strftime('%Y-%m-%d') if end_date else '至今'}",
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name="数据汇总", index=False)

            output.seek(0)
            excel_data = output.getvalue()

            # 生成文件名
            date_range = ""
            if start_date and end_date:
                date_range = (
                    f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
                )
            elif start_date:
                date_range = f"{start_date.strftime('%Y%m%d')}-至今"
            else:
                date_range = "all"

            filename = f"weight_mgmt_user{user_id}_{date_range}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            logger.info(
                "生成Excel文件成功: %s, 大小: %s bytes", filename, len(excel_data)
            )
            return excel_data, filename

        except Exception as e:
            logger.exception("生成Excel文件失败: %s", str(e))
            raise

    @staticmethod
    async def get_export_summary(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        获取导出数据摘要

        Args:
            db: 数据库会话
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            数据摘要
        """
        try:
            summary = {
                "weight_count": 0,
                "meal_count": 0,
                "exercise_count": 0,
                "water_count": 0,
                "sleep_count": 0,
                "report_count": 0,
                "recipe_count": 0,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None,
                },
                "export_time": datetime.now().isoformat(),
            }

            # 构建日期过滤器
            date_filters = []
            if start_date:
                date_filters.append(WeightRecord.record_date >= start_date)
            if end_date:
                date_filters.append(WeightRecord.record_date <= end_date)

            # 统计各种数据数量
            # 体重记录
            weight_query = (
                select(func.count())
                .select_from(WeightRecord)
                .where(and_(WeightRecord.user_id == user_id, *date_filters))
            )
            result = await db.execute(weight_query)
            summary["weight_count"] = result.scalar() or 0

            # 餐食记录
            meal_filters = [MealRecord.user_id == user_id]
            if start_date:
                meal_filters.append(
                    MealRecord.record_time
                    >= datetime.combine(start_date, datetime.min.time())
                )
            if end_date:
                meal_filters.append(
                    MealRecord.record_time
                    <= datetime.combine(end_date, datetime.max.time())
                )

            meal_query = (
                select(func.count()).select_from(MealRecord).where(and_(*meal_filters))
            )
            result = await db.execute(meal_query)
            summary["meal_count"] = result.scalar() or 0

            # 运动记录
            exercise_query = (
                select(func.count())
                .select_from(ExerciseRecord)
                .where(and_(ExerciseRecord.user_id == user_id, *date_filters))
            )
            result = await db.execute(exercise_query)
            summary["exercise_count"] = result.scalar() or 0

            # 饮水记录
            water_query = (
                select(func.count())
                .select_from(WaterRecord)
                .where(and_(WaterRecord.user_id == user_id, *date_filters))
            )
            result = await db.execute(water_query)
            summary["water_count"] = result.scalar() or 0

            # 睡眠记录
            sleep_query = (
                select(func.count())
                .select_from(SleepRecord)
                .where(and_(SleepRecord.user_id == user_id, *date_filters))
            )
            result = await db.execute(sleep_query)
            summary["sleep_count"] = result.scalar() or 0

            # 周报
            report_query = (
                select(func.count())
                .select_from(WeeklyReport)
                .where(WeeklyReport.user_id == user_id)
            )
            result = await db.execute(report_query)
            summary["report_count"] = result.scalar() or 0

            # 食谱交互
            recipe_query = (
                select(func.count())
                .select_from(UserRecipe)
                .where(UserRecipe.user_id == user_id)
            )
            result = await db.execute(recipe_query)
            summary["recipe_count"] = result.scalar() or 0

            return summary

        except Exception as e:
            logger.exception("获取导出摘要失败: %s", str(e))
            raise
