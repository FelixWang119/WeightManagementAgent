"""
时间表达式解析器
将自然语言时间转换为标准时间格式
"""

import re
from datetime import time as dt_time
from typing import Optional, Tuple


class TimeParser:
    """时间表达式解析器"""

    # 时间段映射
    PERIOD_MAP = {
        "早上": (5, 12),
        "上午": (5, 12),
        "中午": (11, 14),
        "下午": (12, 18),
        "晚上": (18, 23),
        "凌晨": (0, 6),
        "傍晚": (17, 20),
    }

    # 常见时间词
    TIME_WORDS = {
        "早上": 8,
        "早晨": 8,
        "上午": 10,
        "中午": 12,
        "下午": 15,
        "傍晚": 18,
        "晚上": 20,
        "深夜": 22,
        "凌晨": 6,
    }

    def parse(self, text: str) -> Optional[dt_time]:
        """
        解析时间表达式

        Args:
            text: 时间文本

        Returns:
            datetime.time: 解析结果，解析失败返回None
        """
        text = text.strip().lower()

        # 尝试各种模式
        patterns = [
            self._parse_exact_time,
            self._parse_period_time,
            self._parse_relative_time,
            self._parse_chinese_time,
        ]

        for pattern in patterns:
            result = pattern(text)
            if result:
                return result

        return None

    def _parse_exact_time(self, text: str) -> Optional[dt_time]:
        """解析精确时间：8点、8:30、08:30"""
        patterns = [
            r"(\d{1,2})[点时]:(\d{2})",
            r"(\d{1,2})[点时](\d{2})?",
            r"(\d{1,2}):(\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] else 0

                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return dt_time(hour, minute)

        return None

    def _parse_period_time(self, text: str) -> Optional[dt_time]:
        """解析时间段时间：早上8点、晚上9点"""
        for period, (start_hour, end_hour) in self.PERIOD_MAP.items():
            if period in text:
                # 提取数字
                match = re.search(r"(\d{1,2})", text)
                if match:
                    hour = int(match.group(1))
                    # 根据时间段调整小时
                    if period in ["早上", "上午"]:
                        hour = max(hour, 6)
                    elif period in ["晚上"]:
                        hour = max(hour, 18)
                    elif period in ["中午"]:
                        hour = max(hour, 11)
                    return dt_time(hour, 0)

        return None

    def _parse_relative_time(self, text: str) -> Optional[dt_time]:
        """解析相对时间：半小时、1小时30分钟"""
        # 暂时不支持复杂相对时间
        return None

    def _parse_chinese_time(self, text: str) -> Optional[dt_time]:
        """解析中文时间词：早上好、上午10点"""
        for word, default_hour in self.TIME_WORDS.items():
            if word in text:
                # 尝试提取具体时间
                match = re.search(r"(\d{1,2})", text)
                if match:
                    hour = int(match.group(1))
                else:
                    hour = default_hour
                return dt_time(hour, 0)

        return None

    def parse_range(self, text: str) -> Optional[Tuple[dt_time, dt_time]]:
        """解析时间范围：9点到18点"""
        match = re.search(r"(\d{1,2})[点时]?\s*[到至]\s*(\d{1,2})[点时]?", text)
        if match:
            start_hour = int(match.group(1))
            end_hour = int(match.group(2))
            return (dt_time(start_hour, 0), dt_time(end_hour, 0))

        return None

    def format_time(self, t: dt_time) -> str:
        """格式化时间为 HH:MM 字符串"""
        return f"{t.hour:02d}:{t.minute:02d}"


parser = TimeParser()
