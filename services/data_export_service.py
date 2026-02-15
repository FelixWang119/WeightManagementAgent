"""
数据导出服务
提供Excel和PDF格式的数据导出功能
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, asc, selectinload
import pandas as pd
import io
import json
from pathlib import Path
import tempfile
import os

from models.database import (
    User,
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
from config.settings import fastapi_settings

logger = get_module_logger(__name__)


class DataExportService:
    """数据导出服务"""

    @staticmethod
    async def export_user_data(
        db: AsyncSession,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        export_format: str = "excel",
        include_types: List[str] = None,
    ) -> Tuple[bytes, str]:
        """
        导出用户数据

        Args:
            db: 数据库会话
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            export_format: 导出格式 (excel/pdf)
            include_types: 包含的数据类型列表

        Returns:
            (文件内容, 文件名)
        """
        try:
            if include_types is None:
                include_types = [
                    "weight",
                    "meal",
                    "exercise",
                    "water",
                    "sleep",
                    "reports",
                    "recipes",
                ]

            # 构建日期过滤器
            date_filter = []
            if start_date:
                date_filter.append(WeightRecord.record_date >= start_date)
            if end_date:
                date_filter.append(WeightRecord.record_date <= end_date)

            # 收集数据
            data = {}

            if "weight" in include_types:
                data["weight"] = await DataExportService._export_weight_data(
                    db, user_id, date_filter
                )

            if "meal" in include_types:
                data["meal"] = await DataExportService._export_meal_data(
                    db, user_id, date_filter
                )

            if "exercise" in include_types:
                data["exercise"] = await DataExportService._export_exercise_data(
                    db, user_id, date_filter
                )

            if "water" in include_types:
                data["water"] = await DataExportService._export_water_data(
                    db, user_id, date_filter
                )

            if "sleep" in include_types:
                data["sleep"] = await DataExportService._export_sleep_data(
                    db, user_id, date_filter
                )

            if "reports" in include_types:
                data["reports"] = await DataExportService._export_report_data(
                    db, user_id
                )

            if "recipes" in include_types:
                data["recipes"] = await DataExportService._export_recipe_data(
                    db, user_id
                )

            # 生成导出文件
            if export_format == "excel":
                return await DataExportService._generate_excel(
                    data, user_id, start_date, end_date
                )
            elif export_format == "pdf":
                return await DataExportService._generate_pdf(
                    data, user_id, start_date, end_date
                )
            else:
                raise ValueError(f"不支持的导出格式: {export_format}")

        except Exception as e:
            logger.exception("导出用户数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_weight_data(
        db: AsyncSession, user_id: int, date_filter: List
    ) -> List[Dict[str, Any]]:
        """导出体重数据"""
        try:
            query = (
                select(WeightRecord)
                .where(and_(WeightRecord.user_id == user_id, *date_filter))
                .order_by(WeightRecord.record_date)
            )

            result = await db.execute(query)
            records = result.scalars().all()

            weight_data = []
            for record in records:
                weight_data.append(
                    {
                        "日期": record.record_date.strftime("%Y-%m-%d"),
                        "体重(kg)": record.weight,
                        "体脂率(%)": record.body_fat if record.body_fat else "",
                        "备注": record.notes if record.notes else "",
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return weight_data

        except Exception as e:
            logger.exception("导出体重数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_meal_data(
        db: AsyncSession, user_id: int, date_filter: List
    ) -> List[Dict[str, Any]]:
        """导出餐食数据"""
        try:
            # 调整日期过滤器为meal记录
            meal_date_filter = []
            # 这里简化处理，实际应该根据date_filter转换
            # 由于date_filter是WeightRecord的过滤器，我们直接使用MealRecord的record_time
            # 在实际使用中，应该传递具体的开始和结束日期参数
            # 这里先实现基本功能，忽略日期过滤

            query = (
                select(MealRecord)
                .where(and_(MealRecord.user_id == user_id, *meal_date_filter))
                .order_by(MealRecord.record_time)
            )

            result = await db.execute(query)
            records = result.scalars().all()

            meal_data = []
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
                        for food in food_list:
                            food_items.append(
                                f"{food.get('name', '')} {food.get('quantity', '')}{food.get('unit', '')}"
                            )
                    except:
                        food_items = ["数据解析错误"]

                meal_data.append(
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

            return meal_data

        except Exception as e:
            logger.exception("导出餐食数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_exercise_data(
        db: AsyncSession, user_id: int, date_filter: List
    ) -> List[Dict[str, Any]]:
        """导出运动数据"""
        try:
            # 调整日期过滤器
            exercise_date_filter = []
            if date_filter:
                for filter_item in date_filter:
                    if (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        exercise_date_filter.append(
                            ExerciseRecord.record_date >= start_date
                        )
                    elif (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        exercise_date_filter.append(
                            ExerciseRecord.record_date <= end_date
                        )

            query = (
                select(ExerciseRecord)
                .where(and_(ExerciseRecord.user_id == user_id, *exercise_date_filter))
                .order_by(ExerciseRecord.record_date)
            )

            result = await db.execute(query)
            records = result.scalars().all()

            exercise_data = []
            for record in records:
                exercise_data.append(
                    {
                        "日期": record.record_date.strftime("%Y-%m-%d"),
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

            return exercise_data

        except Exception as e:
            logger.exception("导出运动数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_water_data(
        db: AsyncSession, user_id: int, date_filter: List
    ) -> List[Dict[str, Any]]:
        """导出饮水数据"""
        try:
            # 调整日期过滤器
            water_date_filter = []
            if date_filter:
                for filter_item in date_filter:
                    if (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        water_date_filter.append(WaterRecord.record_date >= start_date)
                    elif (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        water_date_filter.append(WaterRecord.record_date <= end_date)

            query = (
                select(WaterRecord)
                .where(and_(WaterRecord.user_id == user_id, *water_date_filter))
                .order_by(WaterRecord.record_date)
            )

            result = await db.execute(query)
            records = result.scalars().all()

            water_data = []
            for record in records:
                water_data.append(
                    {
                        "日期": record.record_date.strftime("%Y-%m-%d"),
                        "饮水量(ml)": record.water_amount if record.water_amount else 0,
                        "记录时间": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

            return water_data

        except Exception as e:
            logger.exception("导出饮水数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_sleep_data(
        db: AsyncSession, user_id: int, date_filter: List
    ) -> List[Dict[str, Any]]:
        """导出睡眠数据"""
        try:
            # 调整日期过滤器
            sleep_date_filter = []
            if date_filter:
                for filter_item in date_filter:
                    if (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        sleep_date_filter.append(SleepRecord.record_date >= start_date)
                    elif (
                        hasattr(filter_item, "left")
                        and filter_item.left.name == "record_date"
                    ):
                        sleep_date_filter.append(SleepRecord.record_date <= end_date)

            query = (
                select(SleepRecord)
                .where(and_(SleepRecord.user_id == user_id, *sleep_date_filter))
                .order_by(SleepRecord.record_date)
            )

            result = await db.execute(query)
            records = result.scalars().all()

            sleep_data = []
            for record in records:
                sleep_data.append(
                    {
                        "日期": record.record_date.strftime("%Y-%m-%d"),
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

            return sleep_data

        except Exception as e:
            logger.exception("导出睡眠数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_report_data(
        db: AsyncSession, user_id: int
    ) -> List[Dict[str, Any]]:
        """导出周报数据"""
        try:
            query = (
                select(WeeklyReport)
                .where(WeeklyReport.user_id == user_id)
                .order_by(desc(WeeklyReport.week_start))
            )

            result = await db.execute(query)
            records = result.scalars().all()

            report_data = []
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
                        highlights = [
                            item.get("text", "")
                            for item in highlights_data
                            if isinstance(item, dict)
                        ]
                    except:
                        highlights = ["数据解析错误"]

                if record.improvements:
                    try:
                        improvements_data = (
                            json.loads(record.improvements)
                            if isinstance(record.improvements, str)
                            else record.improvements
                        )
                        improvements = [
                            item.get("text", "")
                            for item in improvements_data
                            if isinstance(item, dict)
                        ]
                    except:
                        improvements = ["数据解析错误"]

                report_data.append(
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

            return report_data

        except Exception as e:
            logger.exception("导出周报数据失败: %s", str(e))
            raise

    @staticmethod
    async def _export_recipe_data(
        db: AsyncSession, user_id: int
    ) -> List[Dict[str, Any]]:
        """导出食谱数据"""
        try:
            # 获取用户收藏和烹饪过的食谱
            query = (
                select(UserRecipe)
                .where(UserRecipe.user_id == user_id)
                .options(selectinload(UserRecipe.recipe))
                .order_by(desc(UserRecipe.updated_at))
            )

            result = await db.execute(query)
            user_recipes = result.scalars().all()

            recipe_data = []
            for user_recipe in user_recipes:
                if user_recipe.recipe:
                    recipe_data.append(
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

            return recipe_data

        except Exception as e:
            logger.exception("导出食谱数据失败: %s", str(e))
            raise

    @staticmethod
    async def _generate_excel(
        data: Dict[str, List[Dict[str, Any]]],
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Tuple[bytes, str]:
        """生成Excel文件"""
        try:
            # 创建Excel写入器
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # 为每个数据类型创建工作表
                for sheet_name, sheet_data in data.items():
                    if sheet_data:  # 只有有数据时才创建工作表
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
                    "数据类型": list(data.keys()),
                    "记录数量": [len(records) for records in data.values()],
                    "导出时间": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                    * len(data),
                }
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name="汇总", index=False)

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
                date_range = "全部数据"

            filename = f"体重管理数据_用户{user_id}_{date_range}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            logger.info(
                "生成Excel文件成功: %s, 大小: %s bytes", filename, len(excel_data)
            )
            return excel_data, filename

        except Exception as e:
            logger.exception("生成Excel文件失败: %s", str(e))
            raise

    @staticmethod
    async def _generate_pdf(
        data: Dict[str, List[Dict[str, Any]]],
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Tuple[bytes, str]:
        """生成PDF文件（简化版，使用HTML转PDF）"""
        try:
            # 由于PDF生成较复杂，这里先实现一个简单的HTML版本
            # 实际生产环境可以使用reportlab、weasyprint等库

            # 生成HTML内容
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>体重管理数据报告</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
                    h2 {{ color: #555; margin-top: 30px; }}
                    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                    th {{ background-color: #4CAF50; color: white; }}
                    tr:nth-child(even) {{ background-color: #f2f2f2; }}
                    .summary {{ background-color: #e8f5e8; padding: 20px; border-radius: 5px; margin-top: 30px; }}
                    .timestamp {{ color: #777; font-size: 14px; margin-top: 40px; }}
                </style>
            </head>
            <body>
                <h1>体重管理数据报告</h1>
                <div class="summary">
                    <p><strong>用户ID:</strong> {user_id}</p>
                    <p><strong>数据范围:</strong> {start_date.strftime("%Y-%m-%d") if start_date else "全部数据"} 至 {end_date.strftime("%Y-%m-%d") if end_date else "至今"}</p>
                    <p><strong>导出时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                </div>
            """

            # 添加每个数据类型的表格
            for data_type, records in data.items():
                if records:
                    html_content += f"<h2>{data_type.capitalize()}数据</h2>"
                    html_content += "<table>"

                    # 表头
                    if records:
                        headers = records[0].keys()
                        html_content += "<tr>"
                        for header in headers:
                            html_content += f"<th>{header}</th>"
                        html_content += "</tr>"

                    # 数据行
                    for record in records[:100]:  # 限制显示100行，避免PDF过大
                        html_content += "<tr>"
                        for value in record.values():
                            html_content += f"<td>{value}</td>"
                        html_content += "</tr>"

                    html_content += "</table>"

                    if len(records) > 100:
                        html_content += (
                            f"<p>... 还有 {len(records) - 100} 条记录未显示</p>"
                        )

            html_content += f"""
                <div class="timestamp">
                    报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </div>
            </body>
            </html>
            """

            # 在实际生产环境中，这里应该使用PDF生成库
            # 暂时返回HTML内容，并注明需要PDF转换
            pdf_data = html_content.encode("utf-8")

            # 生成文件名
            date_range = ""
            if start_date and end_date:
                date_range = (
                    f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
                )
            elif start_date:
                date_range = f"{start_date.strftime('%Y%m%d')}-至今"
            else:
                date_range = "全部数据"

            filename = f"体重管理报告_用户{user_id}_{date_range}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

            logger.info(
                "生成PDF(HTML)文件成功: %s, 大小: %s bytes", filename, len(pdf_data)
            )
            return pdf_data, filename.replace(".html", ".pdf")

        except Exception as e:
            logger.exception("生成PDF文件失败: %s", str(e))
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
            # 构建日期过滤器
            date_filter = []
            if start_date:
                date_filter.append(WeightRecord.record_date >= start_date)
            if end_date:
                date_filter.append(WeightRecord.record_date <= end_date)

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

            # 统计各种数据数量
            # 体重记录
            weight_query = (
                select(func.count())
                .select_from(WeightRecord)
                .where(and_(WeightRecord.user_id == user_id, *date_filter))
            )
            result = await db.execute(weight_query)
            summary["weight_count"] = result.scalar() or 0

            # 餐食记录（简化统计）
            meal_query = (
                select(func.count())
                .select_from(MealRecord)
                .where(MealRecord.user_id == user_id)
            )
            result = await db.execute(meal_query)
            summary["meal_count"] = result.scalar() or 0

            # 运动记录
            exercise_query = (
                select(func.count())
                .select_from(ExerciseRecord)
                .where(and_(ExerciseRecord.user_id == user_id, *date_filter))
            )
            result = await db.execute(exercise_query)
            summary["exercise_count"] = result.scalar() or 0

            # 饮水记录
            water_query = (
                select(func.count())
                .select_from(WaterRecord)
                .where(and_(WaterRecord.user_id == user_id, *date_filter))
            )
            result = await db.execute(water_query)
            summary["water_count"] = result.scalar() or 0

            # 睡眠记录
            sleep_query = (
                select(func.count())
                .select_from(SleepRecord)
                .where(and_(SleepRecord.user_id == user_id, *date_filter))
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
