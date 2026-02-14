"""
NLP提醒管理服务
整合意图识别、时间解析和对话管理
"""

import logging
from typing import Optional, Dict, Any

from services.nlp.dialog_manager import dialog_manager, ReminderAction
from services.nlp.intent_classifier import classifier
from services.nlp.time_parser import parser

logger = logging.getLogger(__name__)


class ReminderNLPService:
    """提醒NLP服务"""

    def __init__(self):
        self.dialog_manager = dialog_manager
        self.classifier = classifier

    def is_reminder_request(self, text: str) -> bool:
        """判断是否是提醒相关请求"""
        return self.classifier.is_reminder_related(text)

    def process(
        self, text: str, current_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息

        Args:
            text: 用户消息
            current_settings: 当前提醒设置

        Returns:
            dict: 处理结果
        """
        # 1. 解析意图
        action = self.dialog_manager.process_message(text)

        # 2. 如果需要澄清，返回澄清请求
        if action.needs_clarification:
            return {
                "needs_clarification": True,
                "question": action.clarification_question,
                "suggestions": self.dialog_manager.suggest_clarification_options(),
                "action": action.action,
            }

        # 3. 执行操作并生成响应
        response = self.dialog_manager.format_response(action, current_settings)

        return {
            "needs_clarification": False,
            "action": action.action,
            "reminder_type": action.reminder_type,
            "time": action.time,
            "enabled": action.enabled,
            "response": response,
        }

    def suggest_reply(self, current_settings: Dict[str, Any]) -> list[str]:
        """生成建议回复"""
        suggestions = []

        # 检查哪些提醒未设置
        for reminder_type, settings in current_settings.items():
            if not settings.get("enabled", False):
                type_name = self.dialog_manager.TYPE_DISPLAY_NAMES.get(
                    reminder_type, reminder_type
                )
                suggestions.append(f"开启{type_name}提醒")

        return suggestions[:3]


service = ReminderNLPService()
