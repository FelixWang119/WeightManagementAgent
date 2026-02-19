"""
简单体重Agent实现
示例Agent，展示如何使用记忆系统
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from services.ai_service import AIService
from .base import BaseAgent


class SimpleWeightAgent(BaseAgent):
    """
    简单体重Agent
    专注于体重管理和健康建议
    """

    def __init__(self, user_id: int, **kwargs):
        """
        初始化体重Agent

        Args:
            user_id: 用户ID
            **kwargs: 额外参数
        """
        super().__init__(user_id, **kwargs)
        self.ai_service = AIService()
        self.agent_name = "SimpleWeightAgent"

    def get_system_prompt(self) -> str:
        """
        获取系统提示

        Returns:
            系统提示文本
        """
        base_prompt = """你是一个专业的体重管理助手，专注于帮助用户管理体重和健康。

你的职责：
1. 分析用户的体重变化趋势
2. 提供科学的减肥/增重建议
3. 结合用户的饮食和运动记录给出综合建议
4. 鼓励用户保持健康习惯
5. 回答与体重管理相关的问题

请保持专业、友好、鼓励的态度。"""

        return base_prompt

    async def chat(self, message: str, **kwargs) -> Dict[str, Any]:
        """
        处理用户消息

        Args:
            message: 用户消息
            **kwargs: 额外参数

        Returns:
            响应结果
        """
        # 1. 获取上下文
        context = self.get_context(query=message, **kwargs)

        # 2. 构建系统提示
        system_prompt = self.get_system_prompt()

        # 3. 获取用户画像
        user_profile = self.memory_manager.get_user_profile()

        # 4. 构建完整的提示
        full_prompt = f"""{system_prompt}

用户画像：
{self._format_user_profile(user_profile)}

相关上下文：
{context}

当前对话：
用户：{message}

请根据以上信息，以专业体重管理助手的身份回复用户。"""

        # 5. 调用AI服务
        try:
            # 构建消息格式
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt},
            ]

            ai_response = await self.ai_service.chat(messages)
            response = ai_response.content

            # 6. 添加到记忆
            memory_result = self.add_to_memory(message, response)

            # 7. 构建响应
            result = {
                "response": response,
                "structured_response": {
                    "type": "text",
                    "content": response,
                    "actions": self._extract_actions(response),
                },
                "intermediate_steps": [
                    {"step": "get_context", "data": {"context_length": len(context)}},
                    {
                        "step": "build_prompt",
                        "data": {"prompt_length": len(full_prompt)},
                    },
                    {"step": "call_ai", "data": {"response_length": len(response)}},
                ],
                "memory_result": memory_result,
                "agent_name": self.agent_name,
            }

            # 8. 检查是否需要特殊处理（如体重记录）
            if self._is_weight_related(message):
                weight_analysis = await self._analyze_weight_trends()
                if weight_analysis:
                    result["weight_analysis"] = weight_analysis

            return result

        except Exception as e:
            # 错误处理
            error_response = (
                "抱歉，我在处理您的体重问题时遇到了一些困难。请稍后再试或联系技术支持。"
            )

            return {
                "response": error_response,
                "structured_response": {
                    "type": "text",
                    "content": error_response,
                    "actions": [],
                },
                "intermediate_steps": [{"step": "error", "data": {"error": str(e)}}],
                "error": str(e),
                "agent_name": self.agent_name,
            }

    def _format_user_profile(self, profile: Dict[str, Any]) -> str:
        """
        格式化用户画像

        Args:
            profile: 用户画像

        Returns:
            格式化后的文本
        """
        if not profile or len(profile) <= 1:
            return "用户尚未设置完整的健康画像。"

        lines = []
        for key, value in profile.items():
            if value and key != "状态":
                lines.append(f"{key}: {value}")

        return "\n".join(lines) if lines else "用户画像信息不完整。"

    def _extract_actions(self, response: str) -> list:
        """
        从响应中提取建议的行动

        Args:
            response: AI响应

        Returns:
            行动列表
        """
        actions = []

        # 简单的关键词匹配（实际应用中可以使用更复杂的方法）
        keywords = {
            "记录体重": "weight_record",
            "记录饮食": "meal_record",
            "记录运动": "exercise_record",
            "查看历史": "view_history",
            "设置目标": "set_goal",
            "分析趋势": "analyze_trend",
        }

        for keyword, action_type in keywords.items():
            if keyword in response:
                actions.append(
                    {
                        "type": action_type,
                        "label": keyword,
                        "description": f"执行{keyword}操作",
                    }
                )

        return actions

    def _is_weight_related(self, message: str) -> bool:
        """
        判断消息是否与体重相关

        Args:
            message: 用户消息

        Returns:
            是否与体重相关
        """
        weight_keywords = [
            "体重",
            "减肥",
            "增重",
            "胖",
            "瘦",
            "公斤",
            "斤",
            "bmi",
            "体脂",
        ]
        return any(keyword in message.lower() for keyword in weight_keywords)

    async def _analyze_weight_trends(self) -> Optional[Dict[str, Any]]:
        """
        分析体重趋势

        Returns:
            体重分析结果
        """
        try:
            # 获取体重记录
            weight_history = self.get_checkin_history(checkin_type="weight", limit=10)

            if not weight_history:
                return None

            # 提取体重数据
            weight_data = []
            for record in weight_history:
                if "metadata" in record and "weight" in record["metadata"]:
                    weight_data.append(
                        {
                            "weight": record["metadata"]["weight"],
                            "timestamp": record["timestamp"],
                        }
                    )

            if len(weight_data) < 2:
                return None

            # 简单趋势分析
            weights = [data["weight"] for data in weight_data]
            latest_weight = weights[0]
            previous_weight = weights[1] if len(weights) > 1 else latest_weight
            weight_change = latest_weight - previous_weight

            # 判断趋势
            if weight_change > 0.5:
                trend = "上升"
                suggestion = "建议关注饮食控制和增加运动。"
            elif weight_change < -0.5:
                trend = "下降"
                suggestion = "继续保持健康习惯！"
            else:
                trend = "稳定"
                suggestion = "体重保持稳定，继续保持。"

            return {
                "latest_weight": latest_weight,
                "previous_weight": previous_weight,
                "weight_change": weight_change,
                "trend": trend,
                "suggestion": suggestion,
                "data_points": len(weight_data),
            }

        except Exception as e:
            # 分析失败，返回None
            return None

    async def get_weight_summary(self) -> Dict[str, Any]:
        """
        获取体重摘要

        Returns:
            体重摘要信息
        """
        weight_history = self.get_checkin_history(checkin_type="weight", limit=20)

        if not weight_history:
            return {"has_data": False, "message": "暂无体重记录"}

        # 提取体重数据
        weights = []
        for record in weight_history:
            if "metadata" in record and "weight" in record["metadata"]:
                weights.append(record["metadata"]["weight"])

        if not weights:
            return {"has_data": False, "message": "体重数据格式错误"}

        # 计算统计信息
        latest_weight = weights[0]
        min_weight = min(weights)
        max_weight = max(weights)
        avg_weight = sum(weights) / len(weights)

        # 计算变化
        if len(weights) >= 2:
            weight_change = latest_weight - weights[1]
            change_percentage = (
                (weight_change / weights[1]) * 100 if weights[1] > 0 else 0
            )
        else:
            weight_change = 0
            change_percentage = 0

        return {
            "has_data": True,
            "latest_weight": latest_weight,
            "min_weight": min_weight,
            "max_weight": max_weight,
            "avg_weight": round(avg_weight, 1),
            "weight_change": round(weight_change, 1),
            "change_percentage": round(change_percentage, 1),
            "total_records": len(weights),
            "last_record_time": weight_history[0].get("timestamp"),
        }

    async def provide_weight_advice(
        self, target_weight: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        提供体重建议

        Args:
            target_weight: 目标体重（可选）

        Returns:
            建议信息
        """
        # 获取当前体重摘要
        summary = await self.get_weight_summary()

        if not summary["has_data"]:
            return {"success": False, "message": "需要先记录体重数据才能提供建议"}

        # 获取用户画像
        user_profile = self.memory_manager.get_user_profile()
        height = None

        # 从用户画像中提取身高
        if user_profile and "身高" in user_profile:
            height_str = user_profile["身高"]
            if "厘米" in height_str:
                try:
                    height = float(height_str.replace("厘米", "").strip())
                except:
                    pass

        # 构建建议
        latest_weight = summary["latest_weight"]

        if target_weight:
            # 有目标体重的情况
            weight_diff = target_weight - latest_weight
            weeks_to_goal = abs(weight_diff) / 0.5  # 假设每周减0.5公斤是安全的

            if weight_diff < 0:
                # 需要减重
                advice = f"您当前体重{latest_weight}公斤，目标体重{target_weight}公斤，需要减重{abs(weight_diff):.1f}公斤。"
                advice += (
                    f"建议每周减重0.5公斤，大约需要{weeks_to_goal:.0f}周达到目标。"
                )
                advice += "建议：控制每日热量摄入，增加有氧运动，保证充足睡眠。"
            else:
                # 需要增重
                advice = f"您当前体重{latest_weight}公斤，目标体重{target_weight}公斤，需要增重{weight_diff:.1f}公斤。"
                advice += (
                    f"建议每周增重0.25公斤，大约需要{weeks_to_goal * 2:.0f}周达到目标。"
                )
                advice += "建议：增加蛋白质摄入，进行力量训练，保证营养均衡。"
        else:
            # 没有目标体重，基于当前数据提供建议
            if summary["weight_change"] > 0.5:
                advice = (
                    f"您的体重最近有所上升（+{summary['weight_change']:.1f}公斤）。"
                )
                advice += "建议检查最近的饮食和运动习惯，适当调整。"
            elif summary["weight_change"] < -0.5:
                advice = f"您的体重最近有所下降（{summary['weight_change']:.1f}公斤）。"
                advice += "继续保持健康习惯！如果下降过快，请确保营养充足。"
            else:
                advice = "您的体重保持稳定，这是很好的状态！"
                advice += "继续保持均衡饮食和规律运动。"

        # 如果有身高信息，计算BMI
        if height:
            bmi = latest_weight / ((height / 100) ** 2)
            bmi_category = self._get_bmi_category(bmi)
            advice += f"\n\n您的BMI为{bmi:.1f}，属于{bmi_category}范围。"

        return {
            "success": True,
            "advice": advice,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }

    def _get_bmi_category(self, bmi: float) -> str:
        """
        获取BMI分类

        Args:
            bmi: BMI值

        Returns:
            BMI分类
        """
        if bmi < 18.5:
            return "偏瘦"
        elif bmi < 24:
            return "正常"
        elif bmi < 28:
            return "超重"
        else:
            return "肥胖"
