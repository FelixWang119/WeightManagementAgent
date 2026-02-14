"""
提醒对话管理器
处理用户关于提醒设置的自然语言对话
"""

import logging
from dataclasses import dataclass
from datetime import time as dt_time
from typing import Optional, Dict, Any

from services.nlp.intent_classifier import classifier, ReminderIntent, IntentResult
from services.nlp.time_parser import parser

logger = logging.getLogger(__name__)


@dataclass
class ReminderAction:
    """提醒操作"""

    action: str  # set, update, disable, enable, query
    reminder_type: Optional[str] = None
    time: Optional[str] = None
    enabled: Optional[bool] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class ReminderDialogManager:
    """提醒对话管理器"""

    # 提醒类型显示名称
    TYPE_DISPLAY_NAMES = {
        "weight": "体重记录",
        "breakfast": "早餐记录",
        "lunch": "午餐记录",
        "dinner": "晚餐记录",
        "exercise": "运动提醒",
        "water": "饮水提醒",
        "sleep": "睡眠提醒",
    }

    def process_message(self, text: str) -> ReminderAction:
        """
        处理用户消息

        Args:
            text: 用户消息

        Returns:
            ReminderAction: 解析后的操作
        """
        # 1. 意图识别
        intent_result = classifier.classify(text)

        # 2. 检查是否需要澄清
        action = self._build_action(intent_result)

        # 3. 如果需要澄清，返回澄清问题
        if action.needs_clarification:
            return action

        # 4. 解析时间
        if intent_result.time:
            parsed_time = parser.parse(intent_result.time)
            if parsed_time:
                action.time = parser.format_time(parsed_time)

        return action

    def _build_action(self, intent_result: IntentResult) -> ReminderAction:
        """构建操作对象"""

        # 情况1：没有检测到提醒类型，需要澄清
        if intent_result.reminder_type is None and intent_result.intent in [
            ReminderIntent.SET,
            ReminderIntent.UPDATE,
            ReminderIntent.DISABLE,
            ReminderIntent.ENABLE,
        ]:
            return ReminderAction(
                action="clarify_type",
                needs_clarification=True,
                clarification_question="请问您想设置哪种提醒呢？可以告诉我：体重记录、早餐、午餐、晚餐、运动、饮水或睡眠提醒~",
            )

        # 情况2：检测到提醒类型但没有时间，需要澄清（设置/更新时）
        if intent_result.reminder_type and intent_result.time is None:
            if intent_result.intent in [ReminderIntent.SET, ReminderIntent.UPDATE]:
                type_name = self.TYPE_DISPLAY_NAMES.get(
                    intent_result.reminder_type, intent_result.reminder_type
                )
                return ReminderAction(
                    action="clarify_time",
                    reminder_type=intent_result.reminder_type,
                    needs_clarification=True,
                    clarification_question=f"请问您想每天几点提醒{type_name}呢？比如：早上8点、中午12点、晚上7点~",
                )

        # 情况3：完整信息
        action_map = {
            ReminderIntent.SET: "set",
            ReminderIntent.UPDATE: "update",
            ReminderIntent.DISABLE: "disable",
            ReminderIntent.ENABLE: "enable",
            ReminderIntent.QUERY: "query",
            ReminderIntent.CANCEL: "cancel",
        }

        return ReminderAction(
            action=action_map.get(intent_result.intent, "unknown"),
            reminder_type=intent_result.reminder_type,
            enabled=intent_result.enabled,
        )

    def format_response(
        self, action: ReminderAction, current_settings: Dict[str, Any] = None
    ) -> str:
        """
        格式化响应消息

        Args:
            action: 提醒操作
            current_settings: 当前设置

        Returns:
            str: 响应消息
        """
        if action.needs_clarification:
            return action.clarification_question

        type_name = self.TYPE_DISPLAY_NAMES.get(
            action.reminder_type or "", action.reminder_type or "提醒"
        )

        if action.action == "set":
            return f"好的，我已为您设置每天 {action.time} 的{type_name}提醒~"

        elif action.action == "update":
            return f"好的，我已将{type_name}提醒时间修改为 {action.time}~"

        elif action.action == "disable":
            return f"好的，我已关闭{type_name}提醒~"

        elif action.action == "enable":
            return f"好的，我已开启{type_name}提醒~"

        elif action.action == "query":
            if current_settings and action.reminder_type:
                settings = current_settings.get(action.reminder_type, {})
                enabled = settings.get("enabled", False)
                time_val = settings.get("time", "未设置")
                status = "已开启" if enabled else "已关闭"
                return f"{type_name}提醒：{status}，时间：{time_val}"
            return f"请问您想查询哪种提醒的设置？"

        elif action.action == "cancel":
            return f"好的，已取消{type_name}提醒~"

        return "抱歉，我没有理解您的意思~"

    def suggest_clarification_options(self) -> list[str]:
        """提供澄清选项"""
        return [
            "设置体重记录提醒",
            "设置早餐提醒",
            "设置午餐提醒",
            "设置晚餐提醒",
            "设置运动提醒",
            "设置饮水提醒",
            "设置睡眠提醒",
        ]


dialog_manager = ReminderDialogManager()
