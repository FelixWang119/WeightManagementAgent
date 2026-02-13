"""
Agent 实现（工具调用版）

支持自然语言记录和富媒体消息返回
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.langchain.base import get_chat_model
from services.langchain.memory import WeightManagementMemory
from services.langchain.tools import create_tools_for_user, execute_tool
from services.user_profile_service import UserProfileService
from config.settings import fastapi_settings


class SimpleAgent:
    """
    Simple Agent for Weight Management

    支持工具调用的Agent，可以：
    1. 识别自然语言意图并自动记录数据
    2. 返回结构化消息（支持富媒体）
    """

    def __init__(
        self,
        user_id: int,
        db: AsyncSession,
        agent_name: Optional[str] = None,
        personality_type: Optional[str] = "warm",
        enable_memory: bool = True,
        history_injection_rounds: int = 5,
        enable_midterm_memory: bool = True,
        debug: Optional[bool] = None
    ):
        self.user_id = user_id
        self.db = db
        self.agent_name = agent_name or "小助"
        self.personality_type = personality_type
        self.enable_memory = enable_memory
        self.history_injection_rounds = history_injection_rounds
        self.enable_midterm_memory = enable_midterm_memory
        self.DEBUG = debug if debug is not None else fastapi_settings.DEBUG

        self.llm = get_chat_model()
        self.tool_definitions = create_tools_for_user(db, user_id)
        self.tools = self._create_langchain_tools()

        # 用户画像数据（带TTL缓存）
        self.user_profile_data: Optional[Dict[str, Any]] = None
        self._profile_loaded: bool = False
        self._profile_loaded_at: Optional[datetime] = None
        self._profile_cache_ttl: timedelta = timedelta(minutes=10)  # 10分钟缓存

        if enable_memory:
            self.memory = WeightManagementMemory(
                user_id=user_id,
                short_term_limit=200
            )
        else:
            self.memory = None
    
    def _create_langchain_tools(self):
        """Convert custom tool definitions to LangChain Tool objects"""
        from langchain_core.tools import Tool
        
        tools = []
        for tool_def in self.tool_definitions:
            # Create a closure to capture the tool_name
            def make_tool_func(tool_name):
                async def tool_func(**kwargs):
                    from services.langchain.tools import execute_tool
                    return await execute_tool(tool_name, kwargs, self.user_id, self.db)
                return tool_func
            
            tool = Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                func=make_tool_func(tool_def["name"]),
                args_schema=None,  # We'll handle validation in execute_tool
            )
            tools.append(tool)
        
        return tools
    
    async def load_user_profile(self) -> Dict[str, Any]:
        """
        懒加载用户画像数据
        
        使用 UserProfileService 获取带缓存的数据
        """
        if not self._profile_loaded:
            try:
                self.user_profile_data = await UserProfileService.get_complete_profile(
                    self.user_id, self.db
                )
                # 更新agent_name和personality_type（如果从数据库获取到）
                if self.user_profile_data:
                    self.agent_name = self.user_profile_data.get("agent_name", self.agent_name)
                    self.personality_type = self.user_profile_data.get("personality_type", self.personality_type)
                self._profile_loaded = True
            except Exception as e:
                print(f"加载用户画像失败: {e}")
                # 返回空数据，不影响主流程
                self.user_profile_data = {
                    "user_id": self.user_id,
                    "agent_name": self.agent_name,
                    "personality_type": self.personality_type,
                    "basic_info": {},
                    "profile_desc": {},
                    "style_addition": ""
                }
                self._profile_loaded = True
        
        return self.user_profile_data or {}

    async def _build_system_prompt(self, conversation_context: str = "", user_message: str = "") -> str:
        """
        构建完整的系统提示（用户画像 + 详细风格 + 对话上下文 + 中期记忆）

        Args:
            conversation_context: 对话上下文（内存注入）
            user_message: 当前用户消息（用于检索中期记忆）

        Returns:
            完整的系统提示字符串
        """
        # 1. 加载用户画像数据（带缓存）
        profile_data = await self.load_user_profile()

        # 2. 如果启用中期记忆，从向量库检索相关历史记忆
        memory_context = ""
        if self.enable_midterm_memory and self.memory and user_message:
            try:
                relevant_memories = await self.memory.search_memory(user_message, k=3)
                if relevant_memories:
                    memory_lines = []
                    for mem in relevant_memories:
                        content = mem.get('content', '')[:100]  # 限制长度
                        memory_lines.append(f"- {content}")
                    memory_context = "\n【相关历史记忆】\n" + "\n".join(memory_lines) + "\n"
            except Exception as e:
                print(f"检索中期记忆失败: {e}")
                # 中期记忆检索失败不影响主流程

        # 3. 组合对话上下文和中期记忆
        full_context = conversation_context + memory_context

        # 4. 使用 UserProfileService 格式化系统提示
        # 注意：UserProfileService.format_system_prompt 已经包含了：
        # - 用户基础信息
        # - 用户画像（问卷回答分类）
        # - 详细风格配置（从 assistant_styles.py）
        # - 当前时间
        # - 对话上下文（传入的 full_context）
        # - 通用回复格式
        return await UserProfileService.format_system_prompt(profile_data, full_context)

    def _build_conversation_context(self, chat_history: List[Dict[str, str]]) -> str:
        """构建对话上下文字符串

        Args:
            chat_history: 对话历史列表，每个元素包含 'role' 和 'content'

        Returns:
            格式化后的对话上下文字符串
        """
        if not chat_history:
            return ""

        # 只取最近 N 轮对话（每轮包含用户消息和助手消息）
        # history_injection_rounds 控制注入多少轮完整对话
        recent_history = chat_history[-(self.history_injection_rounds * 2):]

        formatted_messages = []
        for i, msg in enumerate(recent_history):
            role = msg.get("role", "")
            content = msg.get("content", "")

            # 转换为中文角色标签
            if role == "user":
                role_label = "用户"
            elif role == "assistant":
                role_label = "助手"
            else:
                role_label = role

            # 对于最后1轮对话（最近的用户+助手消息），保留完整内容
            # 对于较早的对话，截断到100字符以节省 token
            is_last_two_messages = i >= len(recent_history) - 2
            if not is_last_two_messages and len(content) > 100:
                content = content[:100] + "..."

            formatted_messages.append(f"{role_label}: {content}")

        return "\n".join(formatted_messages)

    async def chat(self, message: str) -> Dict[str, Any]:
        """对话入口 - 支持工具调用和多轮对话"""
        try:
            conversation_context = ""
            chat_history = []
            if self.memory:
                await self.memory.load_context()
                chat_history = self.memory.get_chat_history()
                conversation_context = self._build_conversation_context(chat_history)

            # 检查是否需要继续上一轮对话的工具调用
            pending_tool_call = await self._check_pending_tool_call(message, chat_history)

            if pending_tool_call:
                # 执行上一轮对话中未完成的工具调用
                return await self._handle_pending_tool_call(pending_tool_call, message)

            # 构建系统提示（包含工具说明）
            system_prompt = await self._build_system_prompt_with_tools(conversation_context, message)

            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]

            # 添加历史对话（作为 user/assistant 消息，而不是 system prompt）
            if chat_history:
                # 只取最近 N 轮对话（由 history_injection_rounds 控制）
                # 注意：不要包含当前用户消息，因为它会被单独添加
                recent_history = chat_history[-(self.history_injection_rounds * 2):]
                
                # 增强对简短回答的理解：当用户简短回答时，主动提醒AI注意上下文
                if message.strip() in ["需要", "是的", "好的", "对", "可以", "要", "行"]:
                    # 检查最近的助手消息是否包含询问句
                    last_assistant_msg = ""
                    for msg in reversed(recent_history):
                        if msg.get("role") == "assistant":
                            last_assistant_msg = msg.get("content", "")
                            break
                    
                    # 如果助手最近询问了"需要制定计划吗？"，那么"需要"就是肯定回答
                    if "需要我" in last_assistant_msg and "吗？" in last_assistant_msg:
                        system_prompt += "\n\n【重要提示】用户刚刚给出了简短的肯定回答'需要'，这是在确认您刚才的提议'需要我帮您制定具体的运动计划吗？'。请直接开始制定计划，无需再次确认。"
                    else:
                        system_prompt += "\n\n【重要提示】用户刚刚给出了简短的肯定回答，请结合最近的对话历史，理解用户是在确认之前的提议。"
                    
                for msg in recent_history:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    # 转换为 OpenAI 格式的角色名称
                    if role == "user":
                        messages.append({"role": "user", "content": content})
                    elif role == "assistant":
                        messages.append({"role": "assistant", "content": content})

            # 添加当前用户消息
            messages.append({"role": "user", "content": message})

            # 调试：只在特定情况下打印消息结构
            if self.DEBUG and message.strip() in ["需要", "是的", "好的", "对", "可以"]:
                print(f"[DEBUG] 传递给 AI 的消息数量: {len(messages)}")
                print(f"[DEBUG] 历史对话消息: {len(messages) - 2} 条（system + 当前消息除外）")
                for i, msg in enumerate(messages):
                    role = msg.get("role", "")
                    content_preview = msg.get("content", "")[:80]
                    print(f"[DEBUG]   {i+1}. {role}: {content_preview}...")

            # 第一次调用：让AI决定是否使用工具
            response = await self.llm.ainvoke(messages)
            ai_content = response.content if hasattr(response, 'content') else str(response)
            
            if self.DEBUG:
                print(f"[DEBUG] AI原始响应: {ai_content[:500]}...")
            
            # 检查是否需要调用工具（通过解析AI返回的JSON）
            tool_calls = self._parse_tool_calls(ai_content)
            
            if self.DEBUG:
                print(f"[DEBUG] AI内容: {ai_content[:500]}...")
                print(f"[DEBUG] 解析到的工具调用: {tool_calls}")
            
            if tool_calls:
                # 检查是否需要更多信息（如饮品类型）
                if await self._need_more_info_for_tool_call(tool_calls[0], ai_content):
                    # 保存AI的问题到记忆
                    if self.memory:
                        await self.memory.save_message("user", message)
                        await self.memory.save_message("assistant", ai_content)
                    
                    # 标记为待处理工具调用，等待用户补充信息
                    await self._mark_pending_tool_call(tool_calls[0], ai_content)
                    return {
                        "response": ai_content,
                        "structured_response": {"type": "text", "content": ai_content, "actions": []},
                        "intermediate_steps": [],
                        "pending_tool_call": True
                    }
                
                # 执行工具调用
                tool_results = []
                if self.DEBUG:
                    print(f"[DEBUG] 开始执行 {len(tool_calls)} 个工具调用")
                
                for tool_call in tool_calls:
                    if self.DEBUG:
                        print(f"[DEBUG] 执行工具: {tool_call['name']}, 参数: {tool_call['arguments']}")
                    
                    result = await execute_tool(
                        tool_call["name"], 
                        tool_call["arguments"], 
                        self.user_id, 
                        self.db
                    )
                    
                    if self.DEBUG:
                        print(f"[DEBUG] 工具执行结果: {result}")
                    
                    tool_results.append(result)
                
                # 第二次调用：让AI基于工具结果生成回复
                tool_context = self._format_tool_results(tool_results)
                messages.append({"role": "assistant", "content": ai_content})
                messages.append({"role": "user", "content": f"工具执行结果：\n{tool_context}\n\n请基于以上结果，用友好自然的语气回复用户。如果成功记录了数据，请明确告知用户，并可提供相关建议。"})
                
                final_response = await self.llm.ainvoke(messages)
                assistant_reply = final_response.content if hasattr(final_response, 'content') else str(final_response)
                
                # 构建结构化响应
                structured_response = self._build_structured_response(assistant_reply, tool_results)
                
            else:
                # 没有工具调用，直接返回AI回复
                assistant_reply = ai_content
                structured_response = {
                    "type": "text",
                    "content": assistant_reply,
                    "actions": []
                }

            # 保存到记忆
            if self.memory:
                if self.DEBUG:
                    print(f"[DEBUG] 保存到记忆 - 用户消息: {message[:50]}...")
                    print(f"[DEBUG] 保存到记忆 - 助手回复: {assistant_reply[:50]}...")
                await self.memory.save_message("user", message)
                await self.memory.save_message("assistant", assistant_reply)

            # 清除待处理工具调用标记
            await self._clear_pending_tool_call()

            return {
                "response": assistant_reply,
                "structured_response": structured_response,
                "intermediate_steps": tool_calls if tool_calls else [],
            }

        except Exception as e:
            print(f"Agent Error: {e}")
            import traceback
            traceback.print_exc()

            # 即使出错也要保存到记忆
            if self.memory:
                await self.memory.save_message("user", message)

            simple_response = await self._simple_reply(message)

            # 保存助手回复到记忆
            if self.memory:
                await self.memory.save_message("assistant", simple_response)

            return {
                "response": simple_response,
                "structured_response": {"type": "text", "content": simple_response, "actions": []},
                "error": str(e),
            }
    
    async def _build_system_prompt_with_tools(self, conversation_context: str = "", user_message: str = "") -> str:
        """构建包含工具说明的系统提示"""
        base_prompt = await self._build_system_prompt(conversation_context, user_message)
        
        # 添加工具使用说明 - 使用优化后的提示词
        tools_description = """

【工具使用说明】
你可以调用以下工具来帮助用户记录数据。当用户提到体重、饮食、运动、饮水时，请使用对应工具：

1. record_weight - 记录体重
   使用场景：用户提到"体重65kg"、"今天称重66.5公斤"
   参数：{"weight": 65.5, "note": "可选备注"}

2. record_meal - 记录餐食
   使用场景：用户提到"吃了牛肉面"、"早餐吃了豆浆油条"
   参数：{"meal_type": "breakfast/lunch/dinner/snack", "food_description": "食物描述", "estimated_calories": 400}

3. record_exercise - 记录运动
   使用场景：用户提到"跑步30分钟"、"游泳一小时"
   参数：{"exercise_type": "运动类型", "duration_minutes": 30, "calories_burned": 300}

4. record_water - 记录饮水
   使用场景：用户提到"喝了500ml水"、"喝了两杯水"
   参数：{"amount_ml": 500}

5. get_today_data - 获取今日数据
   使用场景：用户问"今天记录了多少"、"今天吃了什么"

【重要提示】
你必须以 JSON 格式输出工具调用。分析用户意图后，如果用户提到体重、饮食、运动、饮水相关的内容，请调用对应工具。

【工具调用格式】
如果需要调用工具，请以以下 JSON 格式输出：
{
  "tool_calls": [
    {
      "name": "工具名",
      "args": {
        "参数1": "值1",
        "参数2": "值2"
      }
    }
  ]
}

示例：
用户说："我今天体重是70.5公斤"
输出：{"tool_calls": [{"name": "record_weight", "args": {"weight": 70.5, "note": "今日体重"}}]}

用户说："我早餐吃了面包和牛奶"
输出：{"tool_calls": [{"name": "record_meal", "args": {"meal_type": "breakfast", "food_description": "面包和牛奶", "estimated_calories": 300}}]}

用户说："我今天喝了2000毫升水"
输出：{"tool_calls": [{"name": "record_water", "args": {"amount_ml": 2000}}]}

【输出规则】
1. 只输出 JSON，不要有其他文字
2. 如果没有需要调用的工具，直接正常回复即可
3. 如果调用工具，必须严格按照上述 JSON 格式
"""
        
        return base_prompt + tools_description
    
    def _parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """解析AI回复中的工具调用（支持多种格式）"""
        import re
        import json
        
        tool_calls = []
        
        if self.DEBUG:
            print(f"[DEBUG] 开始解析工具调用，内容长度: {len(content)}")
        
        # 尝试多种JSON格式
        json_patterns = [
            r'\{"tools":\s*\[.*?\]\}',        # {"tools": [...]}
            r'\{"tool_calls":\s*\[.*?\]\}',   # {"tool_calls": [...]}
            r'\{"actions":\s*\[.*?\]\}',      # {"actions": [...]}
            r'```json\n.*?\n```',             # ```json ... ```
            r'```\n.*?\n```',                 # ``` ... ``` (无json标记)
        ]
        
        for pattern_idx, pattern in enumerate(json_patterns):
            try:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    
                    if self.DEBUG:
                        print(f"[DEBUG] 找到模式 {pattern_idx}: {pattern}")
                        print(f"[DEBUG] 匹配到的JSON字符串: {json_str[:200]}...")
                    
                    # 清理JSON字符串
                    json_str = json_str.replace('```json', '').replace('```', '').strip()
                    data = json.loads(json_str)
                    
                    # 提取工具调用
                    if "tools" in data and isinstance(data["tools"], list):
                        tool_calls = data["tools"]
                    elif "tool_calls" in data and isinstance(data["tool_calls"], list):
                        tool_calls = data["tool_calls"]
                    elif "actions" in data and isinstance(data["actions"], list):
                        tool_calls = data["actions"]
                    
                    if tool_calls:
                        if self.DEBUG:
                            print(f"✅ 成功解析工具调用（模式 {pattern_idx}）: {tool_calls}")
                        break
            except json.JSONDecodeError as e:
                if self.DEBUG:
                    print(f"[DEBUG] 模式 {pattern_idx} JSON解析失败: {e}")
                continue
            except KeyError as e:
                if self.DEBUG:
                    print(f"[DEBUG] 模式 {pattern_idx} 缺少键: {e}")
                continue
            except Exception as e:
                if self.DEBUG:
                    print(f"[DEBUG] 模式 {pattern_idx} 解析失败: {e}")
                continue
        
        # 如果没有找到标准格式，尝试查找简单的工具调用指示
        if not tool_calls:
            # 查找可能的工具调用模式
            simple_patterns = [
                r'record_weight.*?\{.*?"weight".*?:.*?\d+',
                r'record_meal.*?\{.*?"meal_type".*?:.*?".*?"',
                r'record_exercise.*?\{.*?"exercise_type".*?:.*?".*?"',
                r'record_water.*?\{.*?"amount_ml".*?:.*?\d+',
            ]
            
            for pattern in simple_patterns:
                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                    if self.DEBUG:
                        print(f"[DEBUG] 找到可能的工具调用模式: {pattern}")
                    # 这里可以添加更复杂的解析逻辑
                    break
        
        # 规范化工具调用格式：将 "args" 转换为 "arguments"
        normalized_tool_calls = []
        for tool_call in tool_calls:
            normalized = tool_call.copy()
            
            # 如果使用 "args" 键，重命名为 "arguments"
            if "args" in normalized and "arguments" not in normalized:
                normalized["arguments"] = normalized.pop("args")
            
            # 确保有 "name" 和 "arguments" 键
            if "name" in normalized and "arguments" in normalized:
                normalized_tool_calls.append(normalized)
            elif "tool" in normalized and "args" in normalized:
                # 处理 {"tool": "record_weight", "args": {...}} 格式
                normalized_tool_calls.append({
                    "name": normalized["tool"],
                    "arguments": normalized["args"]
                })
        
        if self.DEBUG and not normalized_tool_calls:
            print(f"⚠️ 未找到工具调用，AI响应预览: {content[:300]}...")
        
        return normalized_tool_calls
    
    def _format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化工具执行结果"""
        formatted = []
        for result in results:
            formatted.append(f"- {result.get('message', '')}")
        return "\n".join(formatted)
    
    def _build_structured_response(self, assistant_reply: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建结构化响应（支持富媒体）"""
        structured = {
            "type": "text",
            "content": assistant_reply,
            "actions": []
        }
        
        # 根据工具执行结果添加快捷操作
        for result in tool_results:
            if result.get("success"):
                action_type = result.get("action_type")
                if action_type == "weight_recorded":
                    structured["actions"].append({
                        "type": "button",
                        "text": "查看体重趋势",
                        "action": "navigate",
                        "target": "weight.html"
                    })
                elif action_type == "meal_recorded":
                    structured["actions"].append({
                        "type": "button",
                        "text": "查看今日饮食",
                        "action": "navigate",
                        "target": "meal.html"
                    })
                elif action_type == "exercise_recorded":
                    structured["actions"].append({
                        "type": "button",
                        "text": "查看运动记录",
                        "action": "navigate",
                        "target": "exercise.html"
                    })
        
        # 如果有快捷操作，标记为rich类型
        if structured["actions"]:
            structured["type"] = "rich"
        
        return structured

    async def _check_pending_tool_call(self, current_message: str, chat_history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """检查是否有待处理的工具调用需要继续"""
        # 首先检查内存中是否有待处理工具调用
        if self.memory:
            pending_info = await self.memory.get_tool_call_info()
            if pending_info:
                return pending_info.get("pending_tool_call")
                
        # 如果没有内存中的待处理调用，再检查对话历史
        if not chat_history or len(chat_history) < 2:
            return None
            
        # 检查最后一条助手消息是否在询问额外信息
        last_assistant_msg = None
        for i in range(len(chat_history)-1, -1, -1):
            if chat_history[i].get("role") == "assistant":
                last_assistant_msg = chat_history[i].get("content", "")
                break
        
        if not last_assistant_msg:
            return None
            
        # 检查是否在询问饮品类型、运动类型等信息
        if any(keyword in last_assistant_msg for keyword in ["饮品", "饮料", "什么水", "运动类型", "什么运动", "什么食物"]):
            # 检查当前消息是否提供了相关答案
            # 饮品类型关键词（包含常见水类和饮料）
            water_keywords = [
                "白水", "水", "矿泉水", "纯净水", "凉白开", "苏打水", "汽水", 
                "可乐", "果汁", "茶水", "奶茶", "咖啡", "饮料", "牛奶", "酸奶",
                "运动饮料", "功能饮料", "汤水", "温水", "热水", "冷水", "冰水",
                "碳酸饮料", "能量饮料", "酒", "啤酒", "红酒", "白酒"
            ]
            # 运动类型关键词
            exercise_keywords = ["跑步", "散步", "游泳", "健身", "骑车", "瑜伽", "篮球", "足球"]
            # 食物关键词（用于餐食记录）
            food_keywords = ["米饭", "面", "肉", "菜", "水果", "零食", "汤", "粥", "面包"]
            
            # 合并所有关键词
            answer_keywords = water_keywords + exercise_keywords + food_keywords
            
            # 判断是否是合理的回答：要么包含关键词，要么是简短合理的回答（2-10个字符）
            is_valid_answer = any(keyword in current_message.lower() for keyword in answer_keywords)
            is_short_answer = len(current_message.strip()) >= 2 and len(current_message.strip()) <= 15
            
            if is_valid_answer or is_short_answer:
                # 查找前一条用户消息中的工具调用信息
                prev_user_msg = None
                for i in range(len(chat_history)-1, -1, -1):
                    if chat_history[i].get("role") == "user":
                        prev_user_msg = chat_history[i].get("content", "")
                        break
                
                if prev_user_msg and any(quantity in prev_user_msg for quantity in ["ml", "毫升", "升", "杯"]):
                    # 提取饮水量信息
                    import re
                    amount_ml = None
                    
                    # 尝试匹配 ml 或 毫升
                    ml_match = re.search(r'(\d+)\s*(ml|毫升)', prev_user_msg.lower())
                    if ml_match:
                        amount_ml = int(ml_match.group(1))
                    
                    # 尝试匹配 杯（假设1杯 = 200ml）
                    if amount_ml is None:
                        cup_match = re.search(r'(\d+)\s*杯', prev_user_msg)
                        if cup_match:
                            cups = int(cup_match.group(1))
                            amount_ml = cups * 200
                    
                    # 尝试匹配 升（1升 = 1000ml）
                    if amount_ml is None:
                        liter_match = re.search(r'(\d+)\s*升', prev_user_msg)
                        if liter_match:
                            liters = float(liter_match.group(1))
                            amount_ml = int(liters * 1000)
                    
                    # 尝试匹配"两杯"这种中文表达
                    if amount_ml is None:
                        chinese_num_match = re.search(r'(一|两|二|三|四|五|六|七|八|九|十)\s*杯', prev_user_msg)
                        if chinese_num_match:
                            chinese_num_map = {
                                '一': 1, '两': 2, '二': 2, '三': 3, '四': 4,
                                '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
                            }
                            cups = chinese_num_map.get(chinese_num_match.group(1), 1)
                            amount_ml = cups * 200
                    
                    if amount_ml:
                        return {
                            "name": "record_water",
                            "arguments": {"amount_ml": amount_ml},
                            "original_message": prev_user_msg,
                            "question": last_assistant_msg,
                            "answer": current_message
                        }
        
        return None

    async def _need_more_info_for_tool_call(self, tool_call: Dict[str, Any], ai_content: str) -> bool:
        """检查是否需要更多信息才能执行工具调用"""
        if tool_call.get("name") == "record_water":
            # 检查AI是否在询问饮品类型
            return any(keyword in ai_content for keyword in ["饮品", "饮料", "什么水", "喝的是什么"])
        elif tool_call.get("name") == "record_exercise":
            # 检查AI是否在询问运动类型
            return any(keyword in ai_content for keyword in ["运动类型", "什么运动", "哪种运动"])
        elif tool_call.get("name") == "record_meal":
            # 检查AI是否在询问食物详情
            return any(keyword in ai_content for keyword in ["什么食物", "吃了什么", "食物描述"])
        
        return False

    async def _mark_pending_tool_call(self, tool_call: Dict[str, Any], ai_content: str):
        """标记待处理的工具调用"""
        if self.memory:
            # 使用内存保存待处理工具调用信息
            await self.memory.save_tool_call_info({
                "pending_tool_call": tool_call,
                "ai_content": ai_content,
                "timestamp": datetime.utcnow().isoformat()
            })

    async def _handle_pending_tool_call(self, pending_tool_call: Dict[str, Any], user_answer: str) -> Dict[str, Any]:
        """处理待处理的工具调用"""
        try:
            # 执行工具调用
            result = await execute_tool(
                pending_tool_call["name"],
                pending_tool_call["arguments"],
                self.user_id,
                self.db
            )

            # 构建回复消息
            if result.get("success"):
                reply_message = f"✅ {result.get('message', '记录成功！')} "
                if "water" in pending_tool_call["name"]:
                    reply_message += f"感谢你告诉我喝的是{user_answer}，保持良好的饮水习惯对体重管理很重要！💧"
                else:
                    reply_message += "感谢你的信息！"
            else:
                reply_message = f"❌ {result.get('message', '记录失败，请稍后重试。')}"

            # 保存到记忆 - 注意：AI的问题已经在标记pending时保存过了，这里只保存用户的回答和AI的回复
            if self.memory:
                await self.memory.save_message("user", user_answer)
                await self.memory.save_message("assistant", reply_message)

            # 清除待处理标记
            await self._clear_pending_tool_call()

            return {
                "response": reply_message,
                "structured_response": {
                    "type": "text",
                    "content": reply_message,
                    "actions": []
                },
                "intermediate_steps": [pending_tool_call],
            }
            
        except Exception as e:
            error_reply = f"抱歉，处理记录时出现错误：{str(e)}"
            return {
                "response": error_reply,
                "structured_response": {"type": "text", "content": error_reply, "actions": []},
                "error": str(e),
            }

    async def _clear_pending_tool_call(self):
        """清除待处理工具调用标记"""
        if self.memory:
            await self.memory.clear_tool_call_info()

    async def _simple_reply(self, message: str) -> str:
        from services.ai_service import ai_service

        # 构建包含记忆的提示
        memory_context = ""
        if self.memory:
            # 检索相关记忆
            relevant_memories = await self.memory.search_memory(message, k=3)
            if relevant_memories:
                memory_context = "\n\n【相关历史记忆】\n" + "\n".join([
                    f"- {m['document']}" for m in relevant_memories
                ])

        # 获取对话历史
        chat_history = []
        if self.memory:
            chat_history = self.memory.get_chat_history()

        # 构建对话上下文
        conversation_context = self._build_conversation_context(chat_history)

        system_prompt = f"""你是{self.agent_name}，用户的体重管理助手。

【最近对话】
{conversation_context}
{memory_context}

【回复原则】
1. 如果历史对话中有相关信息，请优先使用这些信息回答
2. 保持简洁、友好
3. 如果不知道答案，可以询问用户
"""

        simplified_prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        try:
            response = await ai_service.chat(simplified_prompt, max_tokens=500)
            if not response.error:
                return response.content
        except Exception as e:
            print(f"_simple_reply error: {e}")
        return "抱歉，我现在有点忙，请稍后再试。"

    async def get_chat_history(self) -> List[Dict[str, str]]:
        if not self.memory:
            return []
        return self.memory.get_chat_history()

    async def clear_memory(self):
        if self.memory:
            await self.memory.clear()


class AgentFactory:
    _instances: Dict[int, SimpleAgent] = {}

    @classmethod
    async def get_agent(
        cls,
        user_id: int,
        db: AsyncSession,
        force_new: bool = False
    ) -> SimpleAgent:
        if force_new or user_id not in cls._instances:
            agent_config = await cls._get_agent_config(user_id, db)
            cls._instances[user_id] = SimpleAgent(
                user_id=user_id,
                db=db,
                agent_name=agent_config.get("name"),
                personality_type=agent_config.get("personality_type", "warm"),
                enable_memory=True,
                enable_midterm_memory=True
            )
        cls._instances[user_id].db = db
        return cls._instances[user_id]

    @classmethod
    async def _get_agent_config(
        cls,
        user_id: int,
        db: AsyncSession
    ) -> Dict[str, Any]:
        from models.database import AgentConfig
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.user_id == user_id)
        )
        config = result.scalar_one_or_none()
        if config:
            return {
                "name": config.agent_name or "小助",
                "personality_type": config.personality_type.value if config.personality_type else "warm",
            }
        return {"name": "小助", "personality_type": "warm"}

    @classmethod
    async def close_agent(cls, user_id: int):
        if user_id in cls._instances:
            if cls._instances[user_id].memory:
                await cls._instances[user_id].memory.clear()
            del cls._instances[user_id]

    @classmethod
    async def close_all(cls):
        for agent in cls._instances.values():
            if agent.memory:
                await agent.memory.clear()
        cls._instances.clear()


async def get_agent(user_id: int, db: AsyncSession) -> SimpleAgent:
    return await AgentFactory.get_agent(user_id, db)


async def chat_with_agent(
    user_id: int,
    db: AsyncSession,
    message: str
) -> Dict[str, Any]:
    """使用带记忆的对话功能"""
    try:
        from services.ai_service import ai_service
        from services.user_profile_service import UserProfileService
        from services.langchain.memory import get_user_memory
        
        # 1. 获取用户记忆
        memory = await get_user_memory(user_id, db)
        
        # 2. 获取用户画像数据（用于系统提示）
        profile_data = await UserProfileService.get_complete_profile(user_id, db)
        
        # 3. 获取对话历史（从记忆）
        chat_history = memory.get_chat_history()
        
        # 4. 构建完整的系统提示（不包含对话上下文，对话历史会作为独立消息）
        system_prompt = await UserProfileService.format_system_prompt(profile_data, "")
        
        # 5. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 6. 添加对话历史（最近5轮对话）
        if chat_history:
            # 只取最近5轮对话（每轮包含用户消息和助手消息）
            # 注意：不要包含当前用户消息，因为它会被单独添加
            recent_history = chat_history[-10:]  # 10条消息 = 5轮对话
            for msg in recent_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                # 使用 OpenAI 格式的角色名称
                if role == "user":
                    messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    messages.append({"role": "assistant", "content": content})
        
        # 7. 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        # 8. 调用AI服务
        response = await ai_service.chat(messages, max_tokens=500)
        if response.error:
            return {"response": "抱歉，我现在有点忙，请稍后再试。", "intermediate_steps": []}
        
        assistant_reply = response.content
        
        # 9. 保存用户消息和助手回复到记忆（如果失败，只记录错误，不影响主流程）
        try:
            await memory.save_message("user", message)
            await memory.save_message("assistant", assistant_reply)
        except Exception as mem_error:
            print(f"Memory save error (non-critical): {mem_error}")
            # 继续执行，记忆保存失败不影响聊天功能
        
        return {"response": assistant_reply, "intermediate_steps": []}
        
    except Exception as e:
        print(f"Chat with agent error: {e}")
        # 降级到简单回复（无记忆）
        try:
            from services.ai_service import ai_service
            
            system_prompt = """你是用户的体重管理助手，帮助用户管理体重、记录饮食、运动和睡眠。
请用简洁、友好的方式回复，每次回复控制在100字以内。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = await ai_service.chat(messages, max_tokens=500)
            if response.error:
                return {"response": "抱歉，我现在有点忙，请稍后再试。", "intermediate_steps": []}
            
            return {"response": response.content, "intermediate_steps": []}
        except Exception as inner_e:
            print(f"Fallback AI Error: {inner_e}")
            return {"response": "抱歉，我现在有点忙，请稍后再试。", "intermediate_steps": []}
