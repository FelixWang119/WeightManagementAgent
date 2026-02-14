"""
用户画像收集 API
支持主动推送问题、收集回答、完善用户档案
模拟企业微信的主动触达机制
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import random
import logging

from models.database import get_db, User, UserProfile, ProfilingAnswer
from api.routes.user import get_current_user
from config.profiling_questions import UserProfilingQuestions, get_profiling_questions
from services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ 简化的表单提交API ============

@router.post("/submit-form")
async def submit_form_answer(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """简化的表单提交API - 直接保存数据"""
    try:
        user_id = int(current_user.id)
        question_id = data.get("question_id")
        answer_value = data.get("answer_value")  # JSON string
        
        logger.info(f"[submit-form] user_id={user_id}, question_id={question_id}")
        
        # 解析答案
        if isinstance(answer_value, str):
            answers = json.loads(answer_value)
        else:
            answers = answer_value
        
        logger.info(f"[submit-form] answers={answers}")
        
        # 获取或创建用户档案
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
            logger.info(f"[submit-form] Created new profile")
        
        # 直接更新字段
        if "gender" in answers:
            profile.gender = answers["gender"]
            logger.info(f"[submit-form] Set gender={answers['gender']}")
        
        if "age" in answers:
            try:
                profile.age = int(answers["age"])
                logger.info(f"[submit-form] Set age={answers['age']}")
            except:
                pass
        
        if "height" in answers:
            try:
                profile.height = float(answers["height"])
                logger.info(f"[submit-form] Set height={answers['height']}")
            except:
                pass
        
        # 保存体重记录（如果提供了weight字段）
        if "weight" in answers:
            try:
                from models.database import WeightRecord
                weight_value = float(answers["weight"])
                weight_record = WeightRecord(
                    user_id=user_id,
                    weight=weight_value,
                    record_date=datetime.utcnow().date(),
                    record_time=datetime.utcnow(),
                    note="来自用户画像问卷"
                )
                db.add(weight_record)
                logger.info(f"[submit-form] Saved weight record: {weight_value}kg")
            except Exception as e:
                logger.warning(f"[submit-form] Failed to save weight record: {e}")
        
        await db.commit()
        logger.info(f"[submit-form] Committed to database")
        
        # 保存回答记录
        answer_text = json.dumps(answers, ensure_ascii=False)
        new_answer = ProfilingAnswer(
            user_id=user_id,
            question_id=question_id,
            question_category="basic",
            answer_value=answer_value,
            answer_text=answer_text,
            question_tags=["basic"],
            created_at=datetime.utcnow()
        )
        db.add(new_answer)
        await db.commit()
        logger.info(f"[submit-form] Saved answer record")
        
        return {
            "success": True,
            "message": "保存成功！",
            "ai_feedback": f"收到！我已经记录了你的基本信息：{answer_text}"
        }
        
    except Exception as e:
        logger.error(f"[submit-form] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer")
async def submit_profiling_answer(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提交用户画像选择题答案"""
    try:
        user_id = int(current_user.id)
        question_id = data.get("question_id")
        answer_value = data.get("answer_value")  # 单个值，如 "early_bird"
        answer_text = data.get("answer_text")    # 显示文本，如 "早起鸟"
        
        logger.info(f"[answer] user_id={user_id}, question_id={question_id}, answer_value={answer_value}")
        
        # 根据问题ID确定分类
        question_category = "basic"
        if question_id and "_" in question_id:
            prefix = question_id.split("_")[0]
            if prefix in ["diet", "exercise", "sleep", "motivation", "scenario"]:
                question_category = prefix
        
        # 保存回答记录
        new_answer = ProfilingAnswer(
            user_id=user_id,
            question_id=question_id,
            question_category=question_category,
            answer_value=answer_value,
            answer_text=answer_text,
            question_tags=[question_category],
            created_at=datetime.utcnow()
        )
        db.add(new_answer)
        await db.commit()
        logger.info(f"[answer] Saved answer record")
        
        # 生成AI反馈
        from config.profiling_questions import UserProfilingQuestions
        questions = UserProfilingQuestions.get_all_questions()
        question = next((q for q in questions if q["id"] == question_id), None)
        
        ai_feedback = "了解了！"
        if question:
            # 使用问题中的选项生成反馈
            options = question.get("options", [])
            selected_option = next((opt for opt in options if opt["value"] == answer_value), None)
            if selected_option:
                ai_feedback = f"收到！{selected_option.get('text', '')}"
            else:
                ai_feedback = f"收到！{answer_text}"
        
        return {
            "success": True,
            "message": "保存成功！",
            "ai_feedback": ai_feedback,
            "next_action": "continue"  # 提示前端可以继续下一个问题
        }
        
    except Exception as e:
        logger.error(f"[answer] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 以下是原有代码 ============


@router.get("/next-question")
async def get_next_profiling_question(
    force_new: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取下一个用户画像收集问题
    
    - 智能选择未回答的问题
    - 根据用户已有数据调整优先级
    - 支持强制获取新问题
    
     模拟企业微信的"主动推送"机制
    """
    try:
        user_id = int(current_user.id)
        
        # 获取用户已回答的问题ID
        answered_ids = await _get_answered_question_ids(user_id, db)
        
        # 获取用户当前的档案数据
        profile = await _get_user_profile(user_id, db)
        
        # 智能选择下一个问题
        next_question = UserProfilingQuestions.get_next_question(answered_ids)
        
        if not next_question:
            # 所有问题都已回答
            return {
                "success": True,
                "has_question": False,
                "message": "太棒了！我已经足够了解你了~",
                "progress": {
                    "answered": len(answered_ids),
                    "total": len(UserProfilingQuestions.get_all_questions()),
                    "percentage": 100
            }
        }
        
        # 检查是否需要推送（避免过于频繁）
        should_push = await _should_push_question(user_id, db, force_new)
        
        # 构建友好的推送消息
        push_message = _build_push_message(next_question, profile)
        
        # 构建问题返回对象
        question_obj = {
            "id": next_question["id"],
            "category": next_question["category"],
            "question_text": push_message,
            "original_question": next_question["question"],
            "tags": next_question["tags"],
            "type": next_question.get("type", "choice")
        }
        
        # 如果是选择题，添加选项；如果是表单，添加字段
        if question_obj["type"] == "form":
            question_obj["fields"] = next_question.get("fields", [])
        else:
            question_obj["options"] = next_question.get("options", [])
        
        return {
            "success": True,
            "has_question": True,
            "should_push": should_push,
            "question": question_obj,
            "progress": {
                "answered": len(answered_ids),
                "total": len(UserProfilingQuestions.get_all_questions()),
                "percentage": int(len(answered_ids) / len(UserProfilingQuestions.get_all_questions()) * 100)
            }
        }
    except Exception as e:
        logger.error(f"获取下一个画像问题失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/progress")
async def get_profiling_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户画像收集进度"""
    user_id = int(current_user.id)
    
    answered_ids = await _get_answered_question_ids(user_id, db)
    total = len(UserProfilingQuestions.get_all_questions())
    answered = len(answered_ids)
    
    # 获取档案完善度
    profile = await _get_user_profile(user_id, db)
    profile_completion = await _calculate_profile_completion(profile, user_id, db)
    
    # 获取各分类已回答数量
    qb = get_profiling_questions()
    
    return {
        "success": True,
        "progress": {
            "answered": answered,
            "total": total,
            "percentage": int(answered / total * 100) if total > 0 else 0
        },
        "profile_completion": profile_completion,
        "categories": {
            cat: qb.get_answered_count_by_category(cat, answered_ids)
            for cat in qb.get_categories()
        }
    }


@router.get("/profile-progress")
async def get_profile_completion_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取档案完善度进度（专门用于档案页面进度条）"""
    user_id = int(current_user.id)
    
    # 获取用户档案
    profile = await _get_user_profile(user_id, db)
    
    # 计算档案完善度
    profile_completion = await _calculate_profile_completion(profile, user_id, db)
    
    return {
        "success": True,
        "profile_completion": profile_completion
    }


@router.get("/summary")
async def get_user_profile_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户档案摘要（用于AI对话上下文）"""
    user_id = int(current_user.id)
    
    profile = await _get_user_profile(user_id, db)
    answers = await _get_all_answers(user_id, db)
    
    # 构建档案摘要
    summary = {
        "user_id": user_id,
        "nickname": current_user.nickname,
        "collected_at": profile.created_at if profile else None,
        "basic_info": {
            "sleep_type": _get_answer_by_category(answers, "basic", "sleep"),
            "breakfast_habit": _get_answer_by_category(answers, "basic", "breakfast"),
            "work_type": _get_answer_by_category(answers, "basic", "work")
        },
        "diet_preferences": {
            "staple_food": _get_answer_by_category(answers, "diet", "staple"),
            "cooking_way": _get_answer_by_category(answers, "diet", "cooking"),
            "sweet_tooth": _get_answer_by_category(answers, "diet", "sweet"),
            "protein_source": _get_answer_by_category(answers, "diet", "protein"),
            "drink": _get_answer_by_category(answers, "diet", "drink")
        },
        "exercise_habits": {
            "preference": _get_answer_by_category(answers, "exercise", "preference"),
            "time": _get_answer_by_category(answers, "exercise", "time"),
            "daily_activity": _get_answer_by_category(answers, "exercise", "activity")
        },
        "motivation": {
            "goal": _get_answer_by_category(answers, "motivation", "goal"),
            "obstacle": _get_answer_by_category(answers, "motivation", "obstacle"),
            "companion_style": _get_answer_by_category(answers, "motivation", "style")
        },
        "raw_answers": answers
    }
    
    return {
        "success": True,
        "summary": summary
    }


# ============ 辅助函数 ============

async def _get_answered_question_ids(user_id: int, db: AsyncSession) -> List[str]:
    """获取用户已回答的问题ID列表"""
    result = await db.execute(
        select(ProfilingAnswer.question_id).where(
            ProfilingAnswer.user_id == user_id
        )
    )
    return [row[0] for row in result.all()]


async def _get_user_profile(user_id: int, db: AsyncSession) -> Optional[UserProfile]:
    """获取用户档案"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _should_push_question(user_id: int, db: AsyncSession, force_new: bool) -> bool:
    """判断是否应该推送问题（避免过于频繁）"""
    if force_new:
        return True
    
    # 检查上次回答时间
    result = await db.execute(
        select(ProfilingAnswer.created_at).where(
            ProfilingAnswer.user_id == user_id
        ).order_by(ProfilingAnswer.created_at.desc()).limit(1)
    )
    last_time = result.scalar_one_or_none()
    
    if last_time:
        # 至少间隔5分钟
        if datetime.now() - last_time < timedelta(minutes=5):
            return False
    
    # 随机概率，避免每次请求都推送（模拟自然对话节奏）
    return random.random() > 0.3  # 70%概率推送


def _build_push_message(question: Dict, profile: Optional[UserProfile]) -> str:
    """构建友好的推送消息"""
    original = question["question"]
    
    # 根据问题类型添加自然的前缀
    prefixes = {
        "basic": ["聊个轻松的话题~", "先简单了解一下你", "好奇问下"],
        "diet": ["说到吃...", "想了解一下", "美食时间到"],
        "exercise": ["聊聊运动", "顺便问下", "想了解你的运动习惯"],
        "sleep": ["睡眠质量很重要", "好奇你的作息", "问个生活话题"],
        "motivation": ["想更好地帮你", "了解你的目标", "聊聊你的想法"],
        "scenario": ["来个有趣的", "假设一下", "做个小测试"]
    }
    
    category = question["category"]
    prefix = random.choice(prefixes.get(category, ["问个问题"]))
    
    # 如果是第一个问题，添加欢迎语
    if not profile or profile.diet_preferences is None:
        return f"👋 你好！我是你的专属健康助手。{prefix}：{original}"
    
    return f"{prefix}，{original}"


def _generate_feedback(question: Dict, option: Dict, answer_value: str) -> str:
    """生成AI反馈，让用户感受到被理解"""
    category = question["category"]
    
    feedbacks = {
        "basic": ["了解了！", "get√", "明白~"],
        "diet": ["好的，我记住了你的饮食偏好~", "原来如此，这样我就能给你更合适的建议了", "了解，会考虑进你的饮食方案"],
        "exercise": ["收到！运动习惯已记录", "了解了，会根据你的情况调整运动建议", "明白，会帮你找到最适合的运动方式"],
        "sleep": ["作息很重要，我会提醒你的", "了解了，睡眠质量也会影响减重效果哦", "收到，会关注你的睡眠情况"],
        "motivation": ["明白你的目标，我会全力支持你！", "了解你的挑战，我们一起克服", "懂了，会以你喜欢的方式陪伴你"],
        "scenario": ["哈哈，很有趣的回答！", "get到了，你是这样的性格~", "了解，会记住这个特点的"]
    }
    
    return random.choice(feedbacks.get(category, ["了解了！"]))


async def _save_answer(user_id: int, question_id: str, question_category: str, answer_value: str, answer_text: str, tags: List[str], db: AsyncSession):
    """保存用户回答到数据库"""
    answer = ProfilingAnswer(
        user_id=user_id,
        question_id=question_id,
        question_category=question_category,
        answer_value=answer_value,
        answer_text=answer_text,
        question_tags=tags
    )
    db.add(answer)
    await db.commit()


async def _update_user_profile(user_id: int, category: str, tags: List[str], answer_value: str, answer_text: str, db: AsyncSession, fields_data: Optional[Dict] = None):
    """更新用户档案"""
    if fields_data is None:
        fields_data = {}
    
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        # 创建新档案
        profile = UserProfile(user_id=user_id)
        db.add(profile)
    
    # 字段映射：根据字段名称直接更新对应属性
    field_mappings = {
        "age": ("age", int),
        "gender": ("gender", str),
        "height": ("height", float),
    }
    
    # 根据字段名称更新，而不是标签
    for field_name, field_value in fields_data.items():
        if field_name in field_mappings:
            model_field, field_type = field_mappings[field_name]
            try:
                setattr(profile, model_field, field_type(field_value))
            except (ValueError, TypeError) as e:
                print(f"Error setting {model_field}: {e}")
    
    await db.commit()


async def _calculate_profile_completion(
    profile: Optional[UserProfile], 
    user_id: Optional[int] = None, 
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """计算档案完善度"""
    if not profile:
        return {"overall": 0, "details": {}}
    
    # 必需基础字段：年龄、性别、身高、体重、BMR，各占14%（共70%）
    # 其他字段（饮食偏好、运动习惯等）占剩余30%
    base_fields = ["age", "gender", "height", "bmr"]
    base_weight = 14  # 每个基础字段占比14%
    
    # 检查体重记录（从weight_records表查询）
    has_weight_record = False
    if user_id and db:
        from sqlalchemy import select
        from models.database import WeightRecord
        result = await db.execute(
            select(WeightRecord).where(WeightRecord.user_id == user_id).limit(1)
        )
        has_weight_record = result.scalar_one_or_none() is not None
    
    # 计算基础字段完成度
    base_filled = 0
    base_details = {}
    for field in base_fields:
        has_field = bool(getattr(profile, field, None))
        base_details[field] = has_field
        if has_field:
            base_filled += 1
    
    # 添加体重字段
    base_details["weight"] = has_weight_record
    if has_weight_record:
        base_filled += 1
    
    # 计算其他字段完成度（饮食偏好、运动习惯）
    other_fields = ["diet_preferences", "exercise_habits"]
    other_filled = 0
    other_details = {}
    for field in other_fields:
        has_field = bool(getattr(profile, field, None))
        other_details[field] = has_field
        if has_field:
            other_filled += 1
    
    # 计算总分：基础字段占70%（5个字段各14%），其他字段占30%（2个字段各15%）
    base_score = (base_filled / 5) * 70 if base_filled > 0 else 0
    other_score = (other_filled / 2) * 30 if other_filled > 0 else 0
    overall_score = int(base_score + other_score)
    
    return {
        "overall": overall_score,
        "details": {**base_details, **other_details},
        "score_breakdown": {
            "base_score": base_score,
            "other_score": other_score,
            "base_fields": base_fields + ["weight"],
            "other_fields": other_fields
        }
    }


def _get_answer_by_category(answers: List[Dict], category: str, tag: str) -> Optional[str]:
    """根据分类和标签获取回答"""
    # 这里简化处理，实际应该根据question_id映射
    return None


async def _get_all_answers(user_id: int, db: AsyncSession) -> List[Dict]:
    """获取用户所有回答"""
    result = await db.execute(
        select(ProfilingAnswer).where(
            ProfilingAnswer.user_id == user_id
        ).order_by(ProfilingAnswer.created_at)
    )
    answers = result.scalars().all()
    
    return [
        {
            "question_id": a.question_id,
            "answer_value": a.answer_value,
            "answer_text": a.answer_text,
            "answered_at": a.created_at.isoformat()
        }
        for a in answers
    ]
