"""
智能话术生成器
基于用户画像、事件信息和沟通风格生成个性化通知消息
"""

import logging
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ToneStyle(Enum):
    """语气风格枚举"""
    GENTLE = "gentle"           # 温和体贴
    PROFESSIONAL = "professional"  # 专业正式
    ENCOURAGING = "encouraging"   # 鼓励激励
    DIRECT = "direct"            # 直接简洁
    PLAYFUL = "playful"          # 活泼有趣


class MessageType(Enum):
    """消息类型枚举"""
    STANDARD_REMINDER = "standard_reminder"      # 标准提醒
    ADJUSTED_REMINDER = "adjusted_reminder"      # 调整后提醒
    ENCOURAGEMENT = "encouragement"             # 鼓励消息
    CELEBRATION = "celebration"                  # 庆祝消息
    CONCERN = "concern"                          # 关心消息


class IntelligentMessageGenerator:
    """智能话术生成器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates = self._initialize_templates()
        self.emojis = self._initialize_emojis()
    
    def _initialize_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """初始化话术模板库"""
        return {
            # 标准提醒模板
            "standard_reminder": {
                ToneStyle.GENTLE: [
                    "记得完成今天的{plan}哦~",
                    "该{plan}的时间到啦！",
                    "别忘了今天的{plan}计划~",
                    "{plan}时间到，记得完成哦！"
                ],
                ToneStyle.PROFESSIONAL: [
                    "提醒：请完成今日{plan}记录",
                    "{plan}计划时间已到",
                    "请按时完成{plan}任务",
                    "{plan}提醒：请及时记录"
                ],
                ToneStyle.ENCOURAGING: [
                    "加油！记得完成{plan}哦！",
                    "{plan}时间到，你可以的！",
                    "坚持就是胜利，别忘了{plan}~",
                    "行动起来！完成今天的{plan}！"
                ],
                ToneStyle.DIRECT: [
                    "{plan}时间",
                    "请完成{plan}",
                    "{plan}提醒",
                    "记录{plan}"
                ],
                ToneStyle.PLAYFUL: [
                    "叮咚！{plan}时间到啦~",
                    "嗨~ 该{plan}啦！",
                    "别忘了{plan}这个小目标哦！",
                    "{plan}召唤中~"
                ]
            },
            
            # 调整后提醒模板（有冲突事件）
            "adjusted_reminder": {
                ToneStyle.GENTLE: {
                    "business_dinner": [
                        "了解到您今晚有应酬，{plan}计划可以调整到{suggested_times}哦~",
                        "应酬辛苦啦！{plan}可以等您有空时再完成",
                        "今晚有应酬的话，{plan}可以灵活安排时间哦",
                        "商务应酬重要，{plan}可以适当调整安排"
                    ],
                    "illness": [
                        "听说您身体不适，先好好休息，{plan}计划可以等康复后再安排~",
                        "健康第一！{plan}等您感觉好些了再继续",
                        "身体不舒服的话，{plan}可以暂时放一放",
                        "先照顾好自己，{plan}不急的"
                    ],
                    "travel": [
                        "旅途辛苦了，{plan}计划可以等您安顿好再继续！",
                        "外出期间，{plan}可以适当调整节奏",
                        "旅行愉快！{plan}等您回来再继续",
                        "旅途中的{plan}可以灵活安排"
                    ],
                    "overtime": [
                        "加班辛苦啦！{plan}可以在您方便的时候完成",
                        "工作重要，{plan}可以适当调整时间",
                        "加班期间，{plan}安排可以更灵活些",
                        "工作繁忙，{plan}可以等您有空时记录"
                    ],
                    "family_event": [
                        "家庭聚会重要，{plan}可以灵活安排时间~",
                        "享受家庭时光！{plan}可以稍后完成",
                        "家人团聚重要，{plan}可以适当调整",
                        "家庭活动期间，{plan}安排可以更灵活"
                    ]
                },
                ToneStyle.PROFESSIONAL: {
                    "business_dinner": [
                        "检测到商务应酬安排，建议将{plan}计划调整至{suggested_times}",
                        "应酬期间，{plan}计划可适当延后",
                        "商务活动优先，{plan}可灵活安排"
                    ],
                    "illness": [
                        "健康优先，建议暂停{plan}计划直至康复",
                        "身体不适期间，{plan}计划可暂缓执行",
                        "健康问题，{plan}可等康复后继续"
                    ]
                }
            },
            
            # 鼓励消息模板
            "encouragement": {
                ToneStyle.GENTLE: [
                    "坚持得真棒！继续加油哦~",
                    "看到您的坚持，为您感到骄傲！",
                    "每一天的坚持都是进步，真棒！",
                    "您的自律让人钦佩，继续保持！"
                ],
                ToneStyle.ENCOURAGING: [
                    "太棒了！继续保持这个势头！",
                    "坚持就是胜利，您做得很好！",
                    "为您点赞！继续保持哦！",
                    "棒棒的！继续坚持就是胜利！"
                ]
            },
            
            # 庆祝消息模板
            "celebration": {
                ToneStyle.GENTLE: [
                    "恭喜您连续{days}天完成{plan}！太棒了！",
                    "{days}天的坚持，为您喝彩！",
                    "达成{goal}目标，值得庆祝！",
                    "里程碑达成！继续加油！"
                ],
                ToneStyle.PLAYFUL: [
                    "🎉 恭喜！连续{days}天{plan}达成！",
                    "✨ 太厉害了！{goal}目标完成！",
                    "🌟 里程碑解锁！继续前进！",
                    "💪 坚持{days}天，您是最棒的！"
                ]
            }
        }
    
    def _initialize_emojis(self) -> Dict[str, List[str]]:
        """初始化表情符号库"""
        return {
            "gentle": ["💖", "✨", "🌸", "🌙", "🌟"],
            "professional": ["📊", "✅", "📝", "🔔"],
            "encouraging": ["💪", "🔥", "🚀", "⭐", "🏆"],
            "direct": ["⏰", "📋", "🔔"],
            "playful": ["🎉", "✨", "🌟", "💫", "🎯"]
        }
    
    async def generate_message(self,
                             message_type: MessageType,
                             tone_style: ToneStyle,
                             plan_type: str,
                             user_data: Optional[Dict[str, Any]] = None,
                             event_data: Optional[Dict[str, Any]] = None) -> str:
        """
        生成个性化消息
        
        Args:
            message_type: 消息类型
            tone_style: 语气风格
            plan_type: 计划类型
            user_data: 用户数据
            event_data: 事件数据
            
        Returns:
            str: 生成的消息文本
        """
        self.logger.info(f"生成{message_type.value}消息，风格: {tone_style.value}")
        
        try:
            # 获取基础模板
            base_template = self._get_base_template(message_type, tone_style, event_data)
            
            # 选择具体模板
            template = self._select_template(base_template, tone_style)
            
            # 填充模板变量
            filled_template = self._fill_template(
                template, plan_type, user_data, event_data
            )
            
            # 添加表情符号
            final_message = self._add_emoji(filled_template, tone_style)
            
            # 个性化调整
            final_message = self._personalize_message(final_message, user_data)
            
            self.logger.info(f"消息生成完成: {final_message}")
            return final_message
            
        except Exception as e:
            self.logger.error(f"消息生成失败: {e}")
            return self._get_fallback_message(plan_type)
    
    def _get_base_template(self, 
                          message_type: MessageType,
                          tone_style: ToneStyle,
                          event_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """获取基础模板"""
        
        # 处理调整提醒的特殊情况
        if message_type == MessageType.ADJUSTED_REMINDER and event_data:
            event_type = event_data.get("type")
            tone_templates = self.templates["adjusted_reminder"].get(tone_style, {})
            
            if event_type in tone_templates:
                return tone_templates[event_type]
            
            # 如果没有特定事件模板，使用通用调整模板
            return ["{plan}计划因{event}需要调整。"]
        
        # 标准情况
        message_type_key = message_type.value
        if message_type_key in self.templates:
            tone_templates = self.templates[message_type_key].get(tone_style, [])
            if tone_templates:
                return tone_templates
        
        # 默认模板
        return ["提醒：请完成{plan}"]
    
    def _select_template(self, templates: List[str], tone_style: ToneStyle) -> str:
        """从模板列表中选择一个模板"""
        if not templates:
            return "提醒：请完成{plan}"
        
        # 基于语气风格选择策略
        if tone_style in [ToneStyle.GENTLE, ToneStyle.PLAYFUL]:
            # 温和和活泼风格使用随机选择增加变化性
            return random.choice(templates)
        else:
            # 专业和直接风格使用固定选择确保一致性
            return templates[0]
    
    def _fill_template(self, 
                      template: str,
                      plan_type: str,
                      user_data: Optional[Dict[str, Any]],
                      event_data: Optional[Dict[str, Any]]) -> str:
        """填充模板变量"""
        
        # 计划类型映射
        plan_names = {
            "exercise": "运动",
            "diet": "饮食记录",
            "weight": "体重记录", 
            "sleep": "睡眠记录"
        }
        
        # 事件类型映射
        event_names = {
            "business_dinner": "应酬",
            "illness": "身体不适",
            "travel": "旅行",
            "overtime": "加班",
            "family_event": "家庭事务"
        }
        
        # 基本变量替换
        filled = template.replace("{plan}", plan_names.get(plan_type, "计划"))
        
        # 事件相关变量替换
        if event_data:
            event_type = event_data.get("type")
            filled = filled.replace("{event}", event_names.get(event_type, "特殊事件"))
            
            # 建议时间替换
            suggested_times = event_data.get("suggested_times", ["合适的时间"])
            if isinstance(suggested_times, list):
                time_str = "、".join(suggested_times[:2])
                filled = filled.replace("{suggested_times}", time_str)
        
        # 用户数据相关替换
        if user_data:
            # 连续天数
            if "continuous_days" in user_data:
                filled = filled.replace("{days}", str(user_data["continuous_days"]))
            
            # 目标达成
            if "goal_achieved" in user_data:
                filled = filled.replace("{goal}", user_data["goal_achieved"])
        
        return filled
    
    def _add_emoji(self, message: str, tone_style: ToneStyle) -> str:
        """添加表情符号"""
        style_key = tone_style.value
        available_emojis = self.emojis.get(style_key, [])
        
        if not available_emojis:
            return message
        
        # 基于风格决定是否添加表情符号
        add_emoji_probability = {
            ToneStyle.PLAYFUL: 0.9,    # 活泼风格高概率
            ToneStyle.ENCOURAGING: 0.7, # 鼓励风格中等概率
            ToneStyle.GENTLE: 0.5,     # 温和风格中等概率
            ToneStyle.PROFESSIONAL: 0.2, # 专业风格低概率
            ToneStyle.DIRECT: 0.1       # 直接风格很低概率
        }
        
        probability = add_emoji_probability.get(tone_style, 0.3)
        
        if random.random() < probability:
            emoji = random.choice(available_emojis)
            
            # 决定表情符号位置
            position_strategy = {
                ToneStyle.PLAYFUL: "both",      # 前后都加
                ToneStyle.ENCOURAGING: "end",   # 加在结尾
                ToneStyle.GENTLE: "end",        # 加在结尾
                ToneStyle.PROFESSIONAL: "none", # 不加
                ToneStyle.DIRECT: "none"        # 不加
            }
            
            strategy = position_strategy.get(tone_style, "end")
            
            if strategy == "both":
                return f"{emoji} {message} {emoji}"
            elif strategy == "end":
                return f"{message} {emoji}"
            elif strategy == "start":
                return f"{emoji} {message}"
        
        return message
    
    def _personalize_message(self, message: str, user_data: Optional[Dict[str, Any]]) -> str:
        """个性化消息调整"""
        if not user_data:
            return message
        
        # 基于用户压力水平调整语气
        stress_level = user_data.get("stress_level", 0)
        
        if stress_level > 0.7:
            # 高压力用户，使用更温和的语气
            if "加油" in message:
                message = message.replace("加油", "慢慢来")
            if "坚持" in message:
                message = message.replace("坚持", "适当休息")
        
        # 基于用户灵活性偏好调整
        flexibility = user_data.get("flexibility_preference", 0.5)
        if flexibility > 0.8:
            # 高灵活性用户，可以添加更多选择
            if "可以" in message and "或者" not in message:
                message = message.replace("可以", "可以灵活选择")
        
        return message
    
    def _get_fallback_message(self, plan_type: str) -> str:
        """获取降级消息"""
        plan_names = {
            "exercise": "运动",
            "diet": "饮食记录",
            "weight": "体重记录",
            "sleep": "睡眠记录"
        }
        
        plan_name = plan_names.get(plan_type, "计划")
        return f"提醒：请完成{plan_name}"
    
    async def generate_complex_message(self,
                                     user_id: int,
                                     message_type: MessageType,
                                     plan_type: str,
                                     user_profile: Dict[str, Any],
                                     event_info: Optional[Dict[str, Any]] = None,
                                     achievement_data: Optional[Dict[str, Any]] = None) -> str:
        """
        生成复杂个性化消息（集成用户画像和成就数据）
        
        Args:
            user_id: 用户ID
            message_type: 消息类型
            plan_type: 计划类型
            user_profile: 用户画像
            event_info: 事件信息
            achievement_data: 成就数据
            
        Returns:
            str: 生成的复杂消息
        """
        
        # 合并用户数据
        user_data = {
            "user_id": user_id,
            "stress_level": user_profile.get("stress_level", 0),
            "flexibility_preference": user_profile.get("flexibility_preference", 0.5)
        }
        
        if achievement_data:
            user_data.update(achievement_data)
        
        # 确定语气风格
        tone_style = self._determine_tone_style(user_profile, event_info)
        
        # 生成消息
        return await self.generate_message(
            message_type=message_type,
            tone_style=tone_style,
            plan_type=plan_type,
            user_data=user_data,
            event_data=event_info
        )
    
    def _determine_tone_style(self, 
                            user_profile: Dict[str, Any],
                            event_info: Optional[Dict[str, Any]]) -> ToneStyle:
        """确定语气风格"""
        
        # 默认风格
        default_style = ToneStyle.GENTLE
        
        # 基于用户沟通风格
        user_style = user_profile.get("communication_style")
        if user_style:
            style_mapping = {
                "gentle": ToneStyle.GENTLE,
                "professional": ToneStyle.PROFESSIONAL,
                "encouraging": ToneStyle.ENCOURAGING,
                "direct": ToneStyle.DIRECT,
                "playful": ToneStyle.PLAYFUL
            }
            return style_mapping.get(user_style, default_style)
        
        # 基于事件类型调整
        if event_info:
            event_type = event_info.get("type")
            if event_type in ["illness", "business_dinner"]:
                # 健康问题和应酬事件使用更温和的语气
                return ToneStyle.GENTLE
            elif event_type == "travel":
                # 旅行事件可以使用鼓励语气
                return ToneStyle.ENCOURAGING
        
        # 基于用户压力水平
        stress_level = user_profile.get("stress_level", 0)
        if stress_level > 0.7:
            return ToneStyle.GENTLE
        elif stress_level < 0.3:
            return ToneStyle.ENCOURAGING
        
        return default_style


# 使用示例
async def demo():
    """演示使用方法"""
    generator = IntelligentMessageGenerator()
    
    # 测试标准提醒
    message = await generator.generate_message(
        message_type=MessageType.STANDARD_REMINDER,
        tone_style=ToneStyle.GENTLE,
        plan_type="exercise"
    )
    print(f"标准提醒: {message}")
    
    # 测试调整后提醒
    message = await generator.generate_message(
        message_type=MessageType.ADJUSTED_REMINDER,
        tone_style=ToneStyle.GENTLE,
        plan_type="exercise",
        event_data={
            "type": "business_dinner",
            "suggested_times": ["明早", "后天晚上"]
        }
    )
    print(f"调整提醒: {message}")
    
    # 测试复杂消息生成
    user_profile = {
        "communication_style": "gentle",
        "stress_level": 0.3,
        "flexibility_preference": 0.8
    }
    
    message = await generator.generate_complex_message(
        user_id=1,
        message_type=MessageType.STANDARD_REMINDER,
        plan_type="diet",
        user_profile=user_profile
    )
    print(f"复杂消息: {message}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())