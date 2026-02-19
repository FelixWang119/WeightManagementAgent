"""
用户画像问题库模块
从配置文件加载问题，支持运行时更新
"""

import yaml
import os
from typing import Dict, List, Any, Optional
from pathlib import Path


class ProfilingQuestion:
    """单个问题"""

    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.question = data["question"]
        self.options = data.get("options", [])
        self.category = data.get("category", "general")
        self.tags = data.get("tags", [])
        self.type = data.get("type", "choice")  # "choice" 或 "form"
        self.fields = data.get("fields", [])  # 表单类型问题的字段
        self.priority = data.get("priority", 0)  # 优先级，数值越大越优先

    def is_form(self) -> bool:
        """是否为表单类型问题"""
        return self.type == "form"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "options": self.options,
            "category": self.category,
            "tags": self.tags,
            "type": self.type,
            "fields": self.fields,
            "priority": self.priority,
        }


class ProfilingQuestionBank:
    """用户画像问题库"""

    def __init__(self, config_path: Optional[str] = None):
        """加载问题配置"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "profiling_questions.yaml"
            )

        # 确保config_path不是None
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "profiling_questions.yaml"
            )
        self.config_path = Path(config_path)
        self._questions: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self) -> None:
        """从 YAML 文件加载配置"""
        if not self.config_path.exists():
            print(f"⚠️ 问题配置文件不存在: {self.config_path}")
            self._questions = []
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # 收集所有问题
            self._questions = []

            for category, questions in config.items():
                if isinstance(questions, list):
                    for q in questions:
                        q["category"] = category
                        self._questions.append(q)

            print(f"✅ 已加载 {len(self._questions)} 个画像问题")

        except Exception as e:
            print(f"❌ 加载问题配置失败: {e}")
            self._questions = []

    def reload(self) -> None:
        """重新加载配置（支持热更新）"""
        self._load_config()

    def get_all_questions(self) -> List[Dict[str, Any]]:
        """获取所有问题"""
        return self._questions.copy()

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取问题"""
        for q in self._questions:
            if q["id"] == question_id:
                return q
        return None

    def get_questions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """获取某个分类的所有问题"""
        return [q for q in self._questions if q.get("category") == category]

    def get_next_question(self, answered_ids: List[str]) -> Optional[Dict[str, Any]]:
        """获取下一个未回答的问题

        策略：
        1. 优先返回核心问题（按core_order顺序）
        2. 核心问题全部完成后，随机返回扩展问题
        """
        # 获取所有核心问题
        core_questions = [q for q in self._questions if q.get("is_core", False)]

        # 获取未回答的核心问题
        unanswered_core = [q for q in core_questions if q["id"] not in answered_ids]

        if unanswered_core:
            # 按core_order排序，返回第一个未回答的核心问题
            unanswered_core.sort(key=lambda x: x.get("core_order", 999))
            return unanswered_core[0]

        # 核心问题全部完成，获取未回答的扩展问题
        unanswered_extended = [
            q
            for q in self._questions
            if q["id"] not in answered_ids and not q.get("is_core", False)
        ]

        if not unanswered_extended:
            return None

        # 随机返回一个扩展问题
        import random

        return random.choice(unanswered_extended)

    def get_answer_count(self) -> int:
        """获取问题总数"""
        return len(self._questions)

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set()
        for q in self._questions:
            if cat := q.get("category"):
                categories.add(cat)
        return list(categories)

    def get_answered_count_by_category(
        self, category: str, answered_ids: List[str]
    ) -> int:
        """获取某个分类已回答数量"""
        count = 0
        for q in self._questions:
            if q.get("category") == category and q["id"] in answered_ids:
                count += 1
        return count


# 创建全局问题库实例
_profiling_questions: Optional[ProfilingQuestionBank] = None


def get_profiling_questions() -> ProfilingQuestionBank:
    """获取问题库单例"""
    global _profiling_questions
    if _profiling_questions is None:
        _profiling_questions = ProfilingQuestionBank()
    return _profiling_questions


class UserProfilingQuestions:
    """兼容旧接口 - 提供类方法访问"""

    @classmethod
    def get_all_questions(cls) -> List[Dict[str, Any]]:
        """获取所有问题"""
        return get_profiling_questions().get_all_questions()

    @classmethod
    def get_next_question(cls, answered_ids: List[str]) -> Optional[Dict[str, Any]]:
        """获取下一个未回答的问题"""
        return get_profiling_questions().get_next_question(answered_ids)

    @classmethod
    def get_question_by_id(cls, question_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取问题"""
        return get_profiling_questions().get_question_by_id(question_id)

    @classmethod
    def get_categories(cls) -> List[str]:
        """获取所有分类"""
        return get_profiling_questions().get_categories()


# 从配置加载默认建议
DEFAULT_SUGGESTIONS = [
    {
        "content": "今天别忘了记录体重哦，坚持就是胜利！💪",
        "action_text": "记录体重",
        "action_target": "weight.html",
    },
    {
        "content": "多喝水有助于新陈代谢，建议今天喝够2000ml~",
        "action_text": "记录饮水",
        "action_target": "water.html",
    },
    {
        "content": "运动是健康的好伙伴，今天动起来吧！",
        "action_text": "记录运动",
        "action_target": "exercise.html",
    },
    {
        "content": "💡 蛋白质是肌肉的基石，每餐摄入20-30g有助于维持代谢",
        "action_text": "知道了",
        "action_target": "",
    },
    {
        "content": "💡 低GI食物（如燕麦、糙米）能让血糖更平稳，饱腹感更持久",
        "action_text": "知道了",
        "action_target": "",
    },
    {
        "content": "💡 快走30分钟约消耗150-200kcal，相当于半碗米饭",
        "action_text": "知道了",
        "action_target": "",
    },
    {
        "content": "💡 每增加1kg肌肉，每天多消耗约100kcal",
        "action_text": "知道了",
        "action_target": "",
    },
    {
        "content": "💡 基础代谢占每日消耗的60-70%，肌肉量是代谢关键",
        "action_text": "知道了",
        "action_target": "",
    },
    {
        "content": "每一小步都是进步，今天也在变好的路上！🌟",
        "action_text": "记录体重",
        "action_target": "weight.html",
    },
    {
        "content": "坚持记录是减重的第一步，你已经做得很好了！",
        "action_text": "记录数据",
        "action_target": "index.html",
    },
]


def get_default_suggestions() -> List[Dict[str, str]]:
    """获取默认建议列表"""
    return DEFAULT_SUGGESTIONS.copy()
