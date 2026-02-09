"""
助手风格配置模块
从数据库读取风格配置，支持动态管理
"""

import logging
from enum import Enum
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class AssistantStyle(Enum):
    """助手风格类型"""
    PROFESSIONAL = "professional"  # 专业型
    WARM = "warm"                  # 温暖型
    ENERGETIC = "energetic"        # 活泼型


# 风格基础信息（不含提示词内容，提示词从数据库读取）
STYLE_BASE_CONFIGS = {
    AssistantStyle.PROFESSIONAL: {
        "name": "专业型风格助手",
        "icon": "👨‍⚕️",
        "description": "数据驱动，注重科学原理",
        "prompt_name": "专业型风格助手"  # 数据库中 SystemPrompt.name
    },
    AssistantStyle.WARM: {
        "name": "温暖型风格助手",
        "icon": "🤗",
        "description": "像朋友一样陪伴鼓励",
        "prompt_name": "温暖型风格助手"
    },
    AssistantStyle.ENERGETIC: {
        "name": "活泼型风格助手",
        "icon": "🎉",
        "description": "轻松有趣，充满活力",
        "prompt_name": "活泼型风格助手"
    }
}


# 硬编码 fallback（数据库不可用时使用）
STYLE_FALLBACK_PROMPTS = {
    AssistantStyle.PROFESSIONAL: """【沟通风格：专业型】
你是一个专业的营养师和运动健康专家，拥有深厚的营养学、运动生理学知识。

【回复要求】
1. 语气客观、严谨、有逻辑性，像医生或营养师咨询
2. 使用专业术语但要解释清楚（如BMR、TDEE、宏量营养素等）
3. 引用具体数据：热量数值、营养比例、运动时长等
4. 解释背后的科学原理，让用户理解"为什么"
5. 给出可量化的目标和指标
6. 使用分点论述，结构清晰
7. 适当使用专业图表概念的描述

【回复示例风格】
- "根据你的基础代谢率（BMR）约为1400kcal，结合日常活动系数，你的每日总能量消耗（TDEE）大约在2100kcal左右。要实现每周减重0.5kg的目标，建议每日热量摄入控制在1600-1700kcal，形成400-500kcal的热量缺口。"
- "蛋白质的食物热效应（TEF）约为20-30%，远高于碳水化合物的5-10%。这意味着摄入100kcal蛋白质，实际只有70-80kcal被吸收。因此建议每餐摄入25-30g优质蛋白质...""",

    AssistantStyle.WARM: """【沟通风格：温暖型】
你是用户最贴心的朋友，一个温暖、善解人意的健康伙伴。你理解减重路上的艰辛，愿意倾听和陪伴。

【回复要求】
1. 使用第一人称"我"和"我们"，拉近距离，像朋友聊天
2. 语气温柔、亲切、充满同理心
3. 经常给予真诚的鼓励和肯定，关注用户的情绪
4. 分享温暖的话语和小故事，传递正能量
5. 在困难时给予支持，在进步时真心庆祝
6. 用温柔的语气给出建议，不push不评判
7. 表达对用户的关心和骄傲

【回复示例风格】
- "亲爱的，我看到你今天的记录了，真的想给你一个大大的拥抱！我知道坚持不容易，有时候也会想放弃，但你还是做到了，这真的很棒。要记住，每一个小小的进步都值得庆祝，你已经比昨天的自己更棒了！"
- "我能感受到你最近可能有点疲惫，没关系的，偶尔放松一下也是爱自己的方式。重要的是我们要照顾好自己，而不是完美无缺。你已经做得很棒了，慢慢来，我会一直陪着你的~""",

    AssistantStyle.ENERGETIC: """【沟通风格：活泼型】
你是一个充满活力的健身教练，乐观、幽默、感染力十足。你相信减重可以是一件快乐的事情！

【回复要求】
1. 语气轻松愉快，像朋友一样聊天，充满活力
2. 适当使用emoji和网络流行语（如：冲鸭、yyds、绝绝子等）
3. 用有趣的比喻和幽默的方式解释概念
4. 多使用感叹号，传递正能量和热情
5. 时不时开个小玩笑，活跃气氛
6. 鼓励时用简短有力的口号
7. 让减重过程变得有趣不枯燥

【回复示例风格】
- "哇塞！！！🎉🎉🎉 今天你又瘦了0.3kg！这是什么神仙进步速度！继续保持，姐妹/兄弟你这是最棒的！冲鸭！💪✨"
- "干饭人干饭魂！但是咱们要科学地干饭😎 今天的午餐记得拍照记录哦~ 让我们看看今天吃了什么好吃的！记住，吃饱吃好也能瘦！"
- "运动打卡成功！你简直是yyds！🔥 每次看到你坚持运动我都想给你鼓掌！这意志力，绝了！继续保持，马甲线/腹肌正在向你招手！"""
}


async def get_style_config(style: AssistantStyle, db: Optional[AsyncSession] = None) -> Dict:
    """
    获取风格配置（优先从数据库读取）
    
    Args:
        style: 风格类型
        db: 数据库会话（可选）
    
    Returns:
        风格配置字典
    """
    base_config = STYLE_BASE_CONFIGS.get(style, STYLE_BASE_CONFIGS[AssistantStyle.WARM])
    prompt_name = base_config["prompt_name"]
    
    # 尝试从数据库读取提示词
    if db:
        try:
            from models.database import SystemPrompt, PromptStatus
            result = await db.execute(
                select(SystemPrompt).where(
                    SystemPrompt.name == prompt_name,
                    SystemPrompt.status == PromptStatus.ACTIVE,
                    SystemPrompt.is_current == True
                )
            )
            db_prompt = result.scalar_one_or_none()
            
            if db_prompt:
                return {
                    **base_config,
                    "system_prompt_addition": db_prompt.content,
                    "source": "database",
                    "prompt_id": db_prompt.id,
                    "version": db_prompt.version
                }
            else:
                logger.debug(f"数据库中未找到风格提示词: {prompt_name}，使用 fallback")
        except Exception as e:
            logger.warning(f"从数据库读取风格提示词失败: {e}，使用 fallback")
    
    # 使用硬编码 fallback
    return {
        **base_config,
        "system_prompt_addition": STYLE_FALLBACK_PROMPTS.get(style, STYLE_FALLBACK_PROMPTS[AssistantStyle.WARM]),
        "source": "fallback",
        "prompt_id": None,
        "version": None
    }


def get_style_by_name(prompt_name: str) -> Optional[AssistantStyle]:
    """根据 prompt_name 获取风格类型"""
    for style, config in STYLE_BASE_CONFIGS.items():
        if config["prompt_name"] == prompt_name:
            return style
    return None


async def get_all_styles(db: Optional[AsyncSession] = None) -> list:
    """获取所有可用风格"""
    styles = []
    for style in AssistantStyle:
        config = await get_style_config(style, db)
        styles.append({
            "value": style.value,
            "name": config["name"],
            "icon": config["icon"],
            "description": config["description"],
            "source": config.get("source", "fallback"),
            "prompt_id": config.get("prompt_id"),
            "version": config.get("version")
        })
    return styles


# 保持向后兼容的同步接口（不使用数据库）
def get_style_config_sync(style: AssistantStyle) -> Dict:
    """同步获取风格配置（仅使用 fallback，向后兼容）"""
    base_config = STYLE_BASE_CONFIGS.get(style, STYLE_BASE_CONFIGS[AssistantStyle.WARM])
    return {
        **base_config,
        "system_prompt_addition": STYLE_FALLBACK_PROMPTS.get(style, STYLE_FALLBACK_PROMPTS[AssistantStyle.WARM]),
        "source": "fallback"
    }


def get_all_styles_sync() -> list:
    """同步获取所有风格（向后兼容）"""
    return [
        {
            "value": style.value,
            "name": config["name"],
            "icon": config["icon"],
            "description": config["description"]
        }
        for style, config in STYLE_BASE_CONFIGS.items()
    ]