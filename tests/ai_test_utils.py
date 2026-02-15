"""
千问API测试工具

提供千问API的测试封装、监控和工具函数
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class QwenAPICall:
    """千问API调用记录"""

    timestamp: datetime
    endpoint: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time: float  # 秒
    success: bool
    error_message: Optional[str] = None


class QwenAPIMonitor:
    """千问API监控器"""

    def __init__(self, daily_limit: int = 500):
        self.daily_limit = daily_limit
        self.calls_today: List[QwenAPICall] = []
        self.reset_time = datetime.now()
        self.total_calls = 0
        self.total_tokens = 0

    def record_call(self, call: QwenAPICall):
        """记录API调用"""
        # 检查是否需要重置计数器（新的一天）
        if datetime.now().date() > self.reset_time.date():
            self.calls_today.clear()
            self.reset_time = datetime.now()

        self.calls_today.append(call)
        self.total_calls += 1
        self.total_tokens += call.total_tokens

    def get_today_stats(self) -> Dict[str, Any]:
        """获取今日统计"""
        calls_today = len(self.calls_today)
        tokens_today = sum(call.total_tokens for call in self.calls_today)

        return {
            "calls_today": calls_today,
            "tokens_today": tokens_today,
            "remaining_calls": max(0, self.daily_limit - calls_today),
            "reset_time": self.reset_time,
            "average_response_time": self._calculate_average_response_time(),
            "success_rate": self._calculate_success_rate(),
        }

    def check_limit(self) -> bool:
        """检查是否超过每日限制"""
        stats = self.get_today_stats()
        return stats["calls_today"] < self.daily_limit

    def get_remaining_calls(self) -> int:
        """获取剩余调用次数"""
        stats = self.get_today_stats()
        return stats["remaining_calls"]

    def _calculate_average_response_time(self) -> float:
        """计算平均响应时间"""
        if not self.calls_today:
            return 0.0
        return sum(call.response_time for call in self.calls_today) / len(
            self.calls_today
        )

    def _calculate_success_rate(self) -> float:
        """计算成功率"""
        if not self.calls_today:
            return 100.0
        successful_calls = sum(1 for call in self.calls_today if call.success)
        return (successful_calls / len(self.calls_today)) * 100

    def print_daily_report(self):
        """打印每日报告"""
        stats = self.get_today_stats()
        print("\n" + "=" * 60)
        print("千问API使用报告")
        print("=" * 60)
        print(f"今日调用次数: {stats['calls_today']}/{self.daily_limit}")
        print(f"剩余调用次数: {stats['remaining_calls']}")
        print(f"今日token使用: {stats['tokens_today']}")
        print(f"平均响应时间: {stats['average_response_time']:.2f}秒")
        print(f"调用成功率: {stats['success_rate']:.1f}%")
        print(f"计数器重置时间: {stats['reset_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)


# 全局监控器实例
qwen_monitor = QwenAPIMonitor(daily_limit=500)


def monitor_qwen_api(func: Callable) -> Callable:
    """千问API监控装饰器"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = False
        error_message = None

        try:
            # 检查调用限制
            if not qwen_monitor.check_limit():
                raise Exception(
                    f"已达到千问API每日调用限制: {qwen_monitor.daily_limit}"
                )

            # 调用原始函数
            result = await func(*args, **kwargs)
            success = True

            # 提取token使用信息
            prompt_tokens = kwargs.get("prompt_tokens", 0)
            completion_tokens = (
                result.get("usage", {}).get("completion_tokens", 0)
                if isinstance(result, dict)
                else 0
            )
            total_tokens = prompt_tokens + completion_tokens

            return result

        except Exception as e:
            error_message = str(e)
            logger.error(f"千问API调用失败: {error_message}")
            raise

        finally:
            # 记录调用信息
            end_time = time.time()
            response_time = end_time - start_time

            call = QwenAPICall(
                timestamp=datetime.now(),
                endpoint=func.__name__,
                model=kwargs.get("model", "unknown"),
                prompt_tokens=kwargs.get("prompt_tokens", 0),
                completion_tokens=completion_tokens if success else 0,
                total_tokens=total_tokens if success else 0,
                response_time=response_time,
                success=success,
                error_message=error_message,
            )

            qwen_monitor.record_call(call)

            # 如果接近限制，打印警告
            remaining = qwen_monitor.get_remaining_calls()
            if remaining <= 10:
                logger.warning(f"千问API调用接近限制，剩余{remaining}次")

    return wrapper


class QwenTestClient:
    """千问测试客户端"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("QWEN_API_KEY")
        if not self.api_key:
            logger.warning("未找到千问API密钥，相关测试将被跳过")

        # 导入千问客户端
        try:
            from services.ai_service import QwenClient

            self.client = QwenClient() if self.api_key else None
        except ImportError:
            logger.warning("无法导入QwenClient，确保ai_service.py中存在QwenClient类")
            self.client = None

    @monitor_qwen_api
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> Dict[str, Any]:
        """聊天完成（带监控）"""
        if not self.client:
            raise Exception("千问客户端未初始化，请检查API密钥配置")

        # 估算prompt tokens（简单估算：每个中文字符约1.5个token）
        prompt_text = " ".join(msg.get("content", "") for msg in messages)
        prompt_tokens = int(len(prompt_text) * 1.5)

        response = await self.client.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

        # 转换为字典格式
        result = {
            "content": response.content,
            "model": response.model,
            "usage": response.usage or {"total_tokens": prompt_tokens + 50},
            "success": True,
        }

        return result

    @monitor_qwen_api
    async def analyze_meal(
        self,
        meal_description: str,
        user_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """分析餐食（带监控）"""
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的营养师，请分析用户描述的餐食，估算热量和营养成分，并提供健康建议。",
            },
            {"role": "user", "content": f"请分析以下餐食：{meal_description}"},
        ]

        if user_context:
            context_str = json.dumps(user_context, ensure_ascii=False)
            messages[0]["content"] += f"\n用户背景信息：{context_str}"

        return await self.chat_completion(messages=messages, **kwargs)

    @monitor_qwen_api
    async def generate_weight_advice(
        self, weight_data: List[Dict[str, Any]], user_goal: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """生成体重建议（带监控）"""
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的体重管理顾问，请根据用户的体重数据和目标，提供个性化的建议。",
            },
            {
                "role": "user",
                "content": f"体重数据：{json.dumps(weight_data, ensure_ascii=False)}\n用户目标：{json.dumps(user_goal, ensure_ascii=False)}",
            },
        ]

        return await self.chat_completion(messages=messages, **kwargs)


class MockQwenClient:
    """模拟千问客户端（用于测试）"""

    def __init__(self):
        self.mock_responses = {
            "meal_analysis": "根据您的描述，这餐大约含有500-600卡路里。主要包含碳水化合物和蛋白质，建议增加蔬菜摄入。",
            "weight_advice": "您的体重呈现下降趋势，继续保持当前的饮食和运动计划。建议每天喝足2000毫升水。",
            "general_advice": "保持均衡饮食，适量运动，充足睡眠是健康减重的关键。",
        }

    async def chat_completion(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Dict[str, Any]:
        """模拟聊天完成"""
        # 模拟响应时间
        time.sleep(0.1)

        user_message = next(
            (msg["content"] for msg in messages if msg["role"] == "user"), ""
        )

        # 根据消息内容选择响应
        if "餐食" in user_message or "吃了" in user_message:
            content = self.mock_responses["meal_analysis"]
        elif "体重" in user_message or "减重" in user_message:
            content = self.mock_responses["weight_advice"]
        else:
            content = self.mock_responses["general_advice"]

        return {
            "content": content,
            "model": "qwen-turbo-mock",
            "usage": {
                "total_tokens": 100,
                "completion_tokens": 50,
                "prompt_tokens": 50,
            },
            "success": True,
        }


# 测试工具函数
def create_test_messages(
    role: str = "user", content: str = "测试消息"
) -> List[Dict[str, str]]:
    """创建测试消息"""
    return [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": role, "content": content},
    ]


def validate_ai_response(response: Dict[str, Any]) -> bool:
    """验证AI响应"""
    required_fields = ["content", "model", "usage", "success"]

    if not all(field in response for field in required_fields):
        return False

    if not isinstance(response["content"], str) or len(response["content"]) < 1:
        return False

    if not isinstance(response["usage"], dict):
        return False

    return response.get("success", False)


def extract_calories_from_response(response: Dict[str, Any]) -> Optional[int]:
    """从响应中提取热量信息"""
    content = response.get("content", "")

    # 简单的正则匹配（实际应该更复杂）
    import re

    # 匹配数字模式
    calorie_patterns = [
        r"(\d+)[-\s]*(\d+)\s*卡路里",
        r"(\d+)\s*卡",
        r"热量.*?(\d+)\s*大卡",
        r"calories.*?(\d+)",
    ]

    for pattern in calorie_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            try:
                # 取第一个匹配的数字
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    return None


def create_meal_analysis_prompt(
    meal_description: str, user_info: Optional[Dict[str, Any]] = None
) -> str:
    """创建餐食分析prompt"""
    base_prompt = f"""请分析以下餐食：
{meal_description}

请提供：
1. 估算总热量（卡路里）
2. 主要营养成分（蛋白质、碳水化合物、脂肪）
3. 健康评价
4. 改进建议

请用中文回答，格式清晰。"""

    if user_info:
        user_str = "\n".join(f"{k}: {v}" for k, v in user_info.items())
        base_prompt += f"\n\n用户信息：\n{user_str}"

    return base_prompt


# 测试配置
TEST_QWEN_CONFIG = {
    "model": "qwen-turbo",
    "max_tokens": 1000,
    "temperature": 0.7,
    "timeout": 30.0,
    "max_retries": 3,
    "retry_delay": 1.0,
}
