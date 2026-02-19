"""
对话摘要服务
提供对话自动摘要、关键信息提取、摘要存储与检索
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import json
import re

from models.database import ChatHistory, MessageRole, UserProfile


class ConversationSummaryService:
    """对话摘要服务"""

    # 关键信息模式
    KEY_PATTERNS = {
        "weight": r"(\d+(?:\.\d+)?)\s*(?:kg|公斤)",
        "calories": r"(\d+)\s*(?:千卡|kcal|卡)",
        "exercise_duration": r"(\d+)\s*(?:分钟|min|mins|小时|hour)",
        "exercise_type": r"(跑步|快走|游泳|健身|瑜伽|骑行|跳绳|打球)",
        "sleep_hours": r"(\d+(?:\.\d+)?)\s*(?:小时|hrs|小时)",
        "mood": r"(开心|难过|焦虑|压力|疲惫|精力充沛|累)",
        "food": r"(米饭|面条|馒头|粥|鸡胸肉|牛肉|猪肉|蔬菜|水果|牛奶|豆浆)",
        "symptom": r"(头疼|胃疼|感冒|发烧|咳嗽|失眠|头晕)",
        # 打卡记录模式
        "weight_checkin": r"【体重打卡】记录了体重：(\d+(?:\.\d+)?)公斤",
        "exercise_checkin": r"【运动打卡】(\S+)\s+(\d+)分钟",
        "water_checkin": r"【饮水打卡】喝了(\d+)毫升水",
        "sleep_checkin": r"【睡眠打卡】睡了(\d+(?:\.\d+)?)小时",
        "meal_checkin": r"【(\S+)打卡】记录了：(.+?)，热量(\d+)卡路里",
    }

    @staticmethod
    async def generate_summary(
        user_id: int, db: AsyncSession, days: int = 7
    ) -> Dict[str, Any]:
        """
        生成对话摘要

        Args:
            user_id: 用户ID
            db: 数据库会话
            days: 摘要天数（默认7天）

        Returns:
            包含摘要信息的字典
        """
        # 获取指定天数的对话
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(ChatHistory)
            .where(
                and_(
                    ChatHistory.user_id == user_id, ChatHistory.created_at >= start_date
                )
            )
            .order_by(ChatHistory.created_at.asc())
        )

        records = result.scalars().all()

        if not records:
            return {"success": True, "message": "无对话记录", "data": None}

        # 提取对话内容
        user_messages = [r.content for r in records if r.role == MessageRole.USER]
        ai_messages = [r.content for r in records if r.role == MessageRole.ASSISTANT]

        # 提取关键信息
        key_info = ConversationSummaryService._extract_key_info(user_messages)

        # 统计信息
        stats = {
            "total_conversations": len(records),
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "date_range": {
                "start": records[0].created_at.isoformat() if records else None,
                "end": records[-1].created_at.isoformat() if records else None,
            },
        }

        # 生成摘要文本
        summary_text = ConversationSummaryService._generate_summary_text(
            user_messages, key_info, stats
        )

        # 提取用户偏好
        preferences = ConversationSummaryService._extract_preferences(user_messages)

        # 提取问题类型
        question_types = ConversationSummaryService._classify_questions(user_messages)

        return {
            "success": True,
            "data": {
                "summary": summary_text,
                "key_info": key_info,
                "preferences": preferences,
                "question_types": question_types,
                "stats": stats,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

    @staticmethod
    async def save_summary(
        user_id: int, summary_data: Dict[str, Any], db: AsyncSession
    ) -> bool:
        """
        保存摘要到用户画像

        Args:
            user_id: 用户ID
            summary_data: 摘要数据
            db: 数据库会话

        Returns:
            是否成功
        """
        # 获取用户画像
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            # 创建新的用户画像
            profile = UserProfile(user_id=user_id)
            db.add(profile)

        # 更新记忆摘要
        existing_summary = profile.memory_summary or ""

        new_summary = f"""
[{datetime.utcnow().strftime("%Y-%m-%d")}]
{summary_data.get("summary", "")}

关键信息: {json.dumps(summary_data.get("key_info", {}), ensure_ascii=False)}
偏好: {json.dumps(summary_data.get("preferences", {}), ensure_ascii=False)}

"""

        profile.memory_summary = existing_summary + new_summary
        await db.commit()

        return True

    @staticmethod
    async def get_summaries(
        user_id: int, db: AsyncSession, limit: int = 10
    ) -> Dict[str, Any]:
        """
        获取历史摘要列表

        Args:
            user_id: 用户ID
            db: 数据库会话
            limit: 返回数量

        Returns:
            摘要列表
        """
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.memory_summary:
            return {"success": True, "count": 0, "summaries": []}

        # 解析历史摘要
        summaries = ConversationSummaryService._parse_summaries(profile.memory_summary)

        return {
            "success": True,
            "count": len(summaries),
            "summaries": summaries[:limit],
        }

    @staticmethod
    async def search_summaries(
        user_id: int, query: str, db: AsyncSession, limit: int = 5
    ) -> Dict[str, Any]:
        """
        搜索历史摘要

        Args:
            user_id: 用户ID
            query: 搜索关键词
            db: 数据库会话
            limit: 返回数量

        Returns:
            匹配的摘要
        """
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.memory_summary:
            return {"success": True, "count": 0, "results": []}

        # 简单关键词匹配
        summaries = ConversationSummaryService._parse_summaries(profile.memory_summary)

        query_lower = query.lower()
        matched = [s for s in summaries if query_lower in s.get("content", "").lower()][
            :limit
        ]

        return {
            "success": True,
            "count": len(matched),
            "query": query,
            "results": matched,
        }

    @staticmethod
    def _extract_key_info(messages: List[str]) -> Dict[str, Any]:
        """从消息中提取关键信息"""
        key_info = {
            "weights": [],
            "exercises": [],
            "foods": [],
            "moods": [],
            "symptoms": [],
            "goals": [],
        }

        combined_text = "\n".join(messages)

        # 提取体重
        weight_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["weight"], combined_text
        )
        key_info["weights"] = [
            {"value": float(w), "unit": "kg"} for w in weight_matches
        ]

        # 提取运动
        exercise_type_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["exercise_type"], combined_text
        )
        exercise_duration_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["exercise_duration"], combined_text
        )

        for i, ex_type in enumerate(exercise_type_matches):
            duration = None
            if i < len(exercise_duration_matches):
                duration = exercise_duration_matches[i]
            key_info["exercises"].append({"type": ex_type, "duration": duration})

        # 提取食物
        food_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["food"], combined_text
        )
        key_info["foods"] = list(set(food_matches))

        # 提取情绪
        mood_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["mood"], combined_text
        )
        key_info["moods"] = list(set(mood_matches))

        # 提取症状
        symptom_matches = re.findall(
            ConversationSummaryService.KEY_PATTERNS["symptom"], combined_text
        )
        key_info["symptoms"] = list(set(symptom_matches))

        # 提取目标（简单模式）
        goal_patterns = [
            r"想.*减.*(\d+(?:\.\d+)?)\s*(?:kg|公斤)",
            r"目标.*(\d+(?:\.\d+)?)\s*(?:kg|公斤)",
            r"打算.*瘦.*(\d+(?:\.\d+)?)\s*(?:kg|公斤)",
        ]
        for pattern in goal_patterns:
            goals = re.findall(pattern, combined_text)
            for g in goals:
                key_info["goals"].append({"value": float(g), "unit": "kg"})

        # 提取打卡记录
        checkin_records = []

        # 体重打卡
        weight_checkins = re.findall(
            ConversationSummaryService.KEY_PATTERNS["weight_checkin"], combined_text
        )
        for weight in weight_checkins:
            checkin_records.append(
                {
                    "type": "weight",
                    "value": float(weight),
                    "unit": "kg",
                    "source": "checkin",
                }
            )

        # 运动打卡
        exercise_checkins = re.findall(
            ConversationSummaryService.KEY_PATTERNS["exercise_checkin"], combined_text
        )
        for ex_type, duration in exercise_checkins:
            checkin_records.append(
                {
                    "type": "exercise",
                    "exercise_type": ex_type,
                    "duration": int(duration),
                    "unit": "分钟",
                    "source": "checkin",
                }
            )

        # 饮水打卡
        water_checkins = re.findall(
            ConversationSummaryService.KEY_PATTERNS["water_checkin"], combined_text
        )
        for amount in water_checkins:
            checkin_records.append(
                {
                    "type": "water",
                    "amount": int(amount),
                    "unit": "毫升",
                    "source": "checkin",
                }
            )

        # 睡眠打卡
        sleep_checkins = re.findall(
            ConversationSummaryService.KEY_PATTERNS["sleep_checkin"], combined_text
        )
        for hours in sleep_checkins:
            checkin_records.append(
                {
                    "type": "sleep",
                    "duration": float(hours),
                    "unit": "小时",
                    "source": "checkin",
                }
            )

        # 餐食打卡
        meal_checkins = re.findall(
            ConversationSummaryService.KEY_PATTERNS["meal_checkin"], combined_text
        )
        for meal_type, content, calories in meal_checkins:
            checkin_records.append(
                {
                    "type": "meal",
                    "meal_type": meal_type,
                    "content": content,
                    "calories": int(calories),
                    "source": "checkin",
                }
            )

        if checkin_records:
            key_info["checkins"] = checkin_records

        # 清理空列表
        key_info = {k: v for k, v in key_info.items() if v}

        return key_info

    @staticmethod
    def _generate_summary_text(
        user_messages: List[str], key_info: Dict, stats: Dict
    ) -> str:
        """生成摘要文本"""
        lines = []

        # 基本统计
        lines.append(f"本周共进行了{stats['user_messages']}次对话。")

        # 打卡记录统计
        checkin_stats = {}
        if "checkins" in key_info:
            for checkin in key_info["checkins"]:
                checkin_type = checkin["type"]
                if checkin_type not in checkin_stats:
                    checkin_stats[checkin_type] = 0
                checkin_stats[checkin_type] += 1

        if checkin_stats:
            checkin_lines = []
            for checkin_type, count in checkin_stats.items():
                type_names = {
                    "weight": "体重",
                    "exercise": "运动",
                    "water": "饮水",
                    "sleep": "睡眠",
                    "meal": "餐食",
                }
                name = type_names.get(checkin_type, checkin_type)
                checkin_lines.append(f"{name}{count}次")

            if checkin_lines:
                lines.append(f"健康打卡：{', '.join(checkin_lines)}。")

        # 体重变化（区分实际体重和目标体重）
        actual_weights = []
        goal_weights = []

        if "weights" in key_info:
            for weight in key_info["weights"]:
                # 检查是否来自打卡记录
                if "checkins" in key_info:
                    checkin_weights = [
                        c for c in key_info["checkins"] if c["type"] == "weight"
                    ]
                    if checkin_weights:
                        actual_weights.extend([c["value"] for c in checkin_weights])

        if "goals" in key_info:
            goal_weights = [g["value"] for g in key_info["goals"]]

        if actual_weights:
            if len(actual_weights) >= 2:
                diff = actual_weights[-1] - actual_weights[0]
                direction = "下降" if diff < 0 else "增加"
                lines.append(
                    f"体重从{actual_weights[0]}kg{direction}到{actual_weights[-1]}kg，"
                    f"变化{abs(diff):.1f}kg。"
                )
            elif len(actual_weights) == 1:
                lines.append(f"当前体重{actual_weights[0]}kg。")

        if goal_weights:
            lines.append(f"减重目标：{goal_weights[0]}kg。")

        # 运动情况
        if "exercises" in key_info and key_info["exercises"]:
            ex_types = [e["type"] for e in key_info["exercises"]]
            unique_types = list(set(ex_types))
            lines.append(
                f"进行了{len(key_info['exercises'])}次运动，包括{', '.join(unique_types[:3])}。"
            )

        # 饮食习惯
        if "foods" in key_info and key_info["foods"]:
            foods = key_info["foods"]
            lines.append(f"饮食包含：{', '.join(foods[:5])}。")

        # 情绪状态
        if "moods" in key_info and key_info["moods"]:
            moods = key_info["moods"]
            lines.append(f"近期情绪：{', '.join(set(moods))}。")

        if not lines or (len(lines) == 1 and "本周共进行了" in lines[0]):
            lines.append("本周主要是日常健康咨询对话。")

        return " ".join(lines)

    @staticmethod
    def _extract_preferences(messages: List[str]) -> Dict[str, Any]:
        """提取用户偏好"""
        preferences = {
            "communication_style": None,
            "preferred_topics": [],
            "health_focus": [],
        }

        combined_text = "\n".join(messages).lower()

        # 沟通风格
        if any(w in combined_text for w in ["为什么", "原理", "科学"]):
            preferences["communication_style"] = "analytical"
        elif any(w in combined_text for w in ["鼓励", "加油", "安慰"]):
            preferences["communication_style"] = "supportive"
        elif any(w in combined_text for w in ["怎么做", "方法", "技巧"]):
            preferences["communication_style"] = "practical"

        # 关注话题
        topic_keywords = {
            "饮食": ["吃", "食物", "热量", "卡路里", "饮食"],
            "运动": ["运动", "跑步", "健身", "锻炼"],
            "睡眠": ["睡眠", "睡觉", "失眠", "熬夜"],
            "体重": ["体重", "减肥", "瘦", "减重"],
        }

        for topic, keywords in topic_keywords.items():
            if any(k in combined_text for k in keywords):
                preferences["preferred_topics"].append(topic)

        return preferences

    @staticmethod
    def _classify_questions(messages: List[str]) -> Dict[str, int]:
        """分类用户问题"""
        categories = {"weight": 0, "diet": 0, "exercise": 0, "sleep": 0, "general": 0}

        for msg in messages:
            msg_lower = msg.lower()

            if any(w in msg_lower for w in ["体重", "减肥", "瘦", "体脂"]):
                categories["weight"] += 1
            elif any(w in msg_lower for w in ["吃", "食物", "热量", "饮食", "食谱"]):
                categories["diet"] += 1
            elif any(w in msg_lower for w in ["运动", "跑步", "健身", "锻炼"]):
                categories["exercise"] += 1
            elif any(w in msg_lower for w in ["睡眠", "睡觉", "失眠"]):
                categories["sleep"] += 1
            else:
                categories["general"] += 1

        return {k: v for k, v in categories.items() if v > 0}

    @staticmethod
    def _parse_summaries(memory_summary: str) -> List[Dict]:
        """解析历史摘要文本"""
        summaries = []

        # 按日期分割
        parts = re.split(r"\[(\d{4}-\d{2}-\d{2})\]", memory_summary)

        for i in range(1, len(parts), 2):
            date_str = parts[i]
            content = parts[i + 1] if i + 1 < len(parts) else ""

            # 提取关键信息
            key_info_match = re.search(r"关键信息: (.+)", content)
            preferences_match = re.search(r"偏好: (.+)", content)

            summaries.append(
                {
                    "date": date_str,
                    "content": content.split("关键信息:")[0].strip()
                    if "关键信息:" in content
                    else content.strip(),
                    "key_info": json.loads(key_info_match.group(1))
                    if key_info_match
                    else {},
                    "preferences": json.loads(preferences_match.group(1))
                    if preferences_match
                    else {},
                }
            )

        return summaries


class RichMessageRenderer:
    """富媒体消息渲染器"""

    @staticmethod
    def render_card(data: Dict) -> str:
        """渲染卡片消息"""
        card_type = data.get("type", "info")

        if card_type == "stats":
            return RichMessageRenderer._render_stats_card(data)
        elif card_type == "progress":
            return RichMessageRenderer._render_progress_card(data)
        elif card_type == "suggestion":
            return RichMessageRenderer._render_suggestion_card(data)
        else:
            return RichMessageRenderer._render_basic_card(data)

    @staticmethod
    def _render_basic_card(data: Dict) -> str:
        """基础卡片"""
        title = data.get("title", "")
        content = data.get("content", "")
        actions = data.get("actions", [])

        html = f'<div class="message-card">'
        if title:
            html += f'<div class="card-title">{title}</div>'
        html += f'<div class="card-content">{content}</div>'

        if actions:
            html += '<div class="card-actions">'
            for action in actions:
                html += f'<button class="card-action-btn" data-action="{action.get("action")}">{action.get("label")}</button>'
            html += "</div>"

        html += "</div>"
        return html

    @staticmethod
    def _render_stats_card(data: Dict) -> str:
        """数据统计卡片"""
        stats = data.get("stats", [])

        html = '<div class="message-card stats-card">'
        html += f'<div class="card-title">{data.get("title", "数据统计")}</div>'
        html += '<div class="stats-grid">'

        for stat in stats:
            html += f"""
            <div class="stat-item">
                <div class="stat-value">{stat.get("value")}</div>
                <div class="stat-label">{stat.get("label")}</div>
            </div>
            """

        html += "</div></div>"
        return html

    @staticmethod
    def _render_progress_card(data: Dict) -> str:
        """进度卡片"""
        progress = data.get("progress", 0)
        label = data.get("label", "进度")

        html = f"""
        <div class="message-card progress-card">
            <div class="card-title">{data.get("title", "目标进度")}</div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress}%"></div>
                </div>
                <div class="progress-text">{progress}% - {label}</div>
            </div>
        </div>
        """
        return html

    @staticmethod
    def _render_suggestion_card(data: Dict) -> str:
        """建议卡片"""
        suggestions = data.get("suggestions", [])

        html = '<div class="message-card suggestion-card">'
        html += f'<div class="card-title">{data.get("title", "建议")}</div>'
        html += '<ul class="suggestion-list">'

        for suggestion in suggestions:
            html += f"<li>{suggestion}</li>"

        html += "</ul></div>"
        return html


class QuickActionsRenderer:
    """快捷操作按钮渲染器"""

    @staticmethod
    def render(actions: List[Dict]) -> str:
        """渲染快捷操作按钮"""
        if not actions:
            return ""

        html = '<div class="quick-actions">'

        for action in actions:
            action_type = action.get("type", "button")
            label = action.get("label", "")
            icon = action.get("icon", "")
            payload = action.get("payload", "")

            if action_type == "button":
                html += f"""
                <button class="quick-action-btn" 
                        data-payload='{json.dumps(payload, ensure_ascii=False)}'>
                    <span class="action-icon">{icon}</span>
                    <span class="action-label">{label}</span>
                </button>
                """
            elif action_type == "link":
                html += f'''
                <a class="quick-action-link" href="{payload}">
                    <span class="action-icon">{icon}</span>
                    <span class="action-label">{label}</span>
                </a>
                '''

        html += "</div>"
        return html


class FormMessageRenderer:
    """表单消息渲染器"""

    @staticmethod
    def render(form_data: Dict) -> str:
        """渲染表单"""
        form_type = form_data.get("form_type", "input")
        fields = form_data.get("fields", [])
        submit_label = form_data.get("submit_label", "提交")

        html = f'''
        <div class="message-form" data-form-type="{form_type}">
        '''

        for field in fields:
            field_type = field.get("type", "text")
            name = field.get("name", "")
            label = field.get("label", "")
            placeholder = field.get("placeholder", "")
            options = field.get("options", [])

            if field_type == "text" or field_type == "number":
                html += f'''
                <div class="form-field">
                    <label class="form-label">{label}</label>
                    <input type="{field_type}" 
                           name="{name}" 
                           class="form-input"
                           placeholder="{placeholder}">
                </div>
                '''
            elif field_type == "select":
                html += f'''
                <div class="form-field">
                    <label class="form-label">{label}</label>
                    <select name="{name}" class="form-select">
                '''
                for opt in options:
                    html += f'<option value="{opt.get("value")}">{opt.get("label")}</option>'
                html += """
                    </select>
                </div>
                """
            elif field_type == "textarea":
                html += f'''
                <div class="form-field">
                    <label class="form-label">{label}</label>
                    <textarea name="{name}" 
                              class="form-textarea"
                              placeholder="{placeholder}"></textarea>
                </div>
                '''

        html += f"""
            <button class="form-submit-btn">{submit_label}</button>
        </div>
        """

        return html
