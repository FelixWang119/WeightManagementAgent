"""
意图识别器
识别用户消息中与提醒相关的意图
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReminderIntent(str, Enum):
    """提醒相关意图"""

    SET = "set"  # 设置提醒
    UPDATE = "update"  # 修改提醒
    DISABLE = "disable"  # 关闭提醒
    ENABLE = "enable"  # 开启提醒
    QUERY = "query"  # 查询提醒
    CANCEL = "cancel"  # 取消提醒
    UNKNOWN = "unknown"  # 未知意图


@dataclass
class IntentResult:
    """意图识别结果"""

    intent: ReminderIntent
    reminder_type: Optional[str] = None
    time: Optional[str] = None
    enabled: Optional[bool] = None
    confidence: float = 1.0
    original_text: str = ""


class ReminderIntentClassifier:
    """提醒意图分类器"""

    # 提醒类型关键词
    TYPE_KEYWORDS = {
        "weight": ["体重", "称重", "体重记录"],
        "breakfast": ["早餐", "早饭", "早点"],
        "lunch": ["午餐", "午饭", "中饭"],
        "dinner": ["晚餐", "晚饭", "晚饭"],
        "exercise": ["运动", "锻炼", "健身", "跑步"],
        "water": ["喝水", "饮水", "喝水", "补水"],
        "sleep": ["睡眠", "睡觉", "休息", "早睡"],
    }

    # 意图关键词
    INTENT_PATTERNS = {
        ReminderIntent.SET: [
            r"设置.*提醒",
            r"提醒.*设置",
            r"开启.*提醒",
            r"启用.*提醒",
            r"要.*提醒",
            r"帮我.*提醒",
            r"设置.*时间",
            r"每天.*提醒",
        ],
        ReminderIntent.UPDATE: [
            r"修改.*提醒",
            r"更改.*提醒",
            r"调整.*提醒",
            r"改.*时间",
            r"换个.*时间",
            r"改成.*时间",
        ],
        ReminderIntent.DISABLE: [
            r"关闭.*提醒",
            r"取消.*提醒",
            r"不要.*提醒",
            r"停止.*提醒",
            r"禁用.*提醒",
            r"别.*提醒",
        ],
        ReminderIntent.ENABLE: [
            r"开启.*提醒",
            r"启用.*提醒",
            r"打开.*提醒",
            r"启动.*提醒",
        ],
        ReminderIntent.QUERY: [
            r"查看.*提醒",
            r"看看.*提醒",
            r"我的.*提醒",
            r"有哪些.*提醒",
            r"提醒.*设置",
            r"提醒.*时间",
        ],
        ReminderIntent.CANCEL: [r"取消.*提醒", r"不要.*提醒", r"关闭.*提醒"],
    }

    def classify(self, text: str) -> IntentResult:
        """
        识别用户消息的意图

        Args:
            text: 用户消息

        Returns:
            IntentResult: 识别结果
        """
        text = text.lower().strip()

        # 1. 检测提醒类型
        reminder_type = self._detect_reminder_type(text)

        # 2. 检测意图
        intent = self._detect_intent(text)

        # 3. 检测时间表达式
        time_expr = self._detect_time(text)

        # 4. 检测启用/禁用
        enabled = self._detect_enabled(text)

        return IntentResult(
            intent=intent,
            reminder_type=reminder_type,
            time=time_expr,
            enabled=enabled,
            original_text=text,
        )

    def _detect_reminder_type(self, text: str) -> Optional[str]:
        """检测提醒类型"""
        for reminder_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return reminder_type
        return None

    def _detect_intent(self, text: str) -> ReminderIntent:
        """检测意图"""
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent
        return ReminderIntent.UNKNOWN

    def _detect_time(self, text: str) -> Optional[str]:
        """检测时间表达式"""
        time_patterns = [
            (r"(\d{1,2})[点时](\d{0,2})?", "time"),
            (r"早上(\d{1,2})", "morning"),
            (r"中午(\d{1,2})", "noon"),
            (r"下午(\d{1,2})", "afternoon"),
            (r"晚上(\d{1,2})", "evening"),
            (r"(\d{1,2})点半", "half"),
        ]

        for pattern, _ in time_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def _detect_enabled(self, text: str) -> Optional[bool]:
        """检测启用/禁用"""
        enable_words = ["开启", "启用", "打开", "启动", "开启"]
        disable_words = ["关闭", "取消", "不要", "停止", "禁用"]

        for word in enable_words:
            if word in text:
                return True
        for word in disable_words:
            if word in text:
                return False

        return None

    def is_reminder_related(self, text: str) -> bool:
        """判断消息是否与提醒相关"""
        result = self.classify(text)
        return (
            result.intent != ReminderIntent.UNKNOWN or result.reminder_type is not None
        )


classifier = ReminderIntentClassifier()
