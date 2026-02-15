"""
数据导出 API 路由
提供Excel格式的数据导出功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import io

from models.database import get_db, User
from api.routes.user import get_current_user
from services.data_export_service_simple import SimpleDataExportService

router = APIRouter()


# ============ 请求/响应模型 ============


class ExportRequest(BaseModel):
    """导出请求"""

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    include_types: List[str] = Field(
        default=["weight", "meal", "exercise", "water", "sleep", "reports", "recipes"],
        description="包含的数据类型",
    )


class ExportSummaryResponse(BaseModel):
    """导出摘要响应"""

    weight_count: int
    meal_count: int
    exercise_count: int
    water_count: int
    sleep_count: int
    report_count: int
    recipe_count: int
    date_range: Dict[str, Optional[str]]
    export_time: str


# ============ API 端点 ============


@router.get("/export/summary", response_model=ExportSummaryResponse)
async def get_export_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取导出数据摘要

    - **start_date**: 开始日期 (YYYY-MM-DD)
    - **end_date**: 结束日期 (YYYY-MM-DD)
    """
    try:
        summary = await SimpleDataExportService.get_export_summary(
            db, current_user.id, start_date, end_date
        )

        return ExportSummaryResponse(**summary)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取导出摘要失败: {str(e)}",
        )


@router.post("/export/excel")
async def export_to_excel(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出数据到Excel文件

    - **start_date**: 开始日期
    - **end_date**: 结束日期
    - **include_types**: 包含的数据类型列表
    """
    try:
        # 验证日期范围
        if export_request.start_date and export_request.end_date:
            if export_request.start_date > export_request.end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="开始日期不能晚于结束日期",
                )

        # 验证包含的数据类型
        valid_types = [
            "weight",
            "meal",
            "exercise",
            "water",
            "sleep",
            "reports",
            "recipes",
        ]
        for data_type in export_request.include_types:
            if data_type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的数据类型: {data_type}。有效类型: {', '.join(valid_types)}",
                )

        # 导出数据
        excel_data, filename = await SimpleDataExportService.export_user_data_to_excel(
            db,
            current_user.id,
            export_request.start_date,
            export_request.end_date,
        )

        # 创建流式响应
        return StreamingResponse(
            io.BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_data)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出数据失败: {str(e)}",
        )


@router.get("/export/excel/quick")
async def quick_export_to_excel(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    快速导出数据到Excel文件

    - **start_date**: 开始日期 (YYYY-MM-DD)
    - **end_date**: 结束日期 (YYYY-MM-DD)
    """
    try:
        # 验证日期范围
        if start_date and end_date:
            if start_date > end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="开始日期不能晚于结束日期",
                )

        # 导出数据（包含所有类型）
        excel_data, filename = await SimpleDataExportService.export_user_data_to_excel(
            db,
            current_user.id,
            start_date,
            end_date,
        )

        # 创建流式响应
        return StreamingResponse(
            io.BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_data)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"快速导出数据失败: {str(e)}",
        )


@router.get("/export/test")
async def test_export(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    测试导出功能

    - 导出最近7天的数据
    - 用于测试和演示
    """
    try:
        # 计算最近7天的日期范围
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        # 导出数据
        excel_data, filename = await SimpleDataExportService.export_user_data_to_excel(
            db,
            current_user.id,
            start_date,
            end_date,
        )

        # 创建流式响应
        return StreamingResponse(
            io.BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_data)),
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试导出失败: {str(e)}",
        )
