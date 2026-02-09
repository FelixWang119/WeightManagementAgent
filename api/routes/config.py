"""
配置相关 API
提供配置热更新能力
"""

from fastapi import APIRouter, Depends
from config.profiling_questions import get_profiling_questions, get_default_suggestions

router = APIRouter()


@router.get("/default-suggestions")
async def get_default_suggestions_api():
    """获取默认建议列表"""
    return {
        "success": True,
        "suggestions": get_default_suggestions()
    }


@router.post("/reload-profiling-questions")
async def reload_profiling_questions():
    """重新加载画像问题库（用于热更新）"""
    qb = get_profiling_questions()
    qb.reload()
    
    return {
        "success": True,
        "message": f"已重新加载 {qb.get_answer_count()} 个问题",
        "categories": qb.get_categories()
    }


@router.get("/profiling-questions")
async def get_profiling_questions_info():
    """获取画像问题库信息"""
    qb = get_profiling_questions()
    
    return {
        "success": True,
        "total_count": qb.get_answer_count(),
        "categories": [
            {
                "name": cat,
                "count": len(qb.get_questions_by_category(cat))
            }
            for cat in qb.get_categories()
        ]
    }
