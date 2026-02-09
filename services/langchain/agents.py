"""
Agent 实现（简化版）

使用 LangChain 工具调用，但不依赖复杂的 Agent API
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.langchain.base import get_chat_model
from services.langchain.memory import WeightManagementMemory
from services.langchain.tools import create_tools_for_user
from services.user_profile_service import UserProfileService


class SimpleAgent:
    """
    Simple Agent for Weight Management

    使用 LLM 直接调用工具的简化 Agent
    """

    def __init__(
        self,
        user_id: int,
        db: AsyncSession,
        agent_name: Optional[str] = None,
        personality_type: Optional[str] = "warm",
        enable_memory: bool = True,
        history_injection_rounds: int = 5
    ):
        self.user_id = user_id
        self.db = db
        self.agent_name = agent_name or "小助"
        self.personality_type = personality_type
        self.enable_memory = enable_memory
        self.history_injection_rounds = history_injection_rounds

        self.llm = get_chat_model()
        self.tools = create_tools_for_user(db, user_id)
        
        # 用户画像数据（懒加载）
        self.user_profile_data: Optional[Dict[str, Any]] = None
        self._profile_loaded: bool = False

        if enable_memory:
            self.memory = WeightManagementMemory(
                user_id=user_id,
                short_term_limit=20
            )
        else:
            self.memory = None
    
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

    async def _build_system_prompt(self, conversation_context: str = "") -> str:
        """
        构建完整的系统提示（用户画像 + 详细风格 + 对话上下文）
        
        Args:
            conversation_context: 对话上下文（内存注入）
            
        Returns:
            完整的系统提示字符串
        """
        # 1. 加载用户画像数据（带缓存）
        profile_data = await self.load_user_profile()
        
        # 2. 使用 UserProfileService 格式化系统提示
        # 注意：UserProfileService.format_system_prompt 已经包含了：
        # - 用户基础信息
        # - 用户画像（问卷回答分类）
        # - 详细风格配置（从 assistant_styles.py）
        # - 当前时间
        # - 对话上下文（传入的 conversation_context）
        # - 通用回复格式
        return await UserProfileService.format_system_prompt(profile_data, conversation_context)

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
        for msg in recent_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # 转换为中文角色标签
            if role == "user":
                role_label = "用户"
            elif role == "assistant":
                role_label = "助手"
            else:
                role_label = role
            
            # 截断过长的消息（前100字符 + ...）
            if len(content) > 100:
                content = content[:100] + "..."
            
            formatted_messages.append(f"{role_label}: {content}")
        
        return "\n".join(formatted_messages)

    async def chat(self, message: str) -> Dict[str, Any]:
        """对话入口"""
        try:
            conversation_context = ""
            if self.memory:
                await self.memory.load_context()
                # 获取对话历史并构建上下文
                chat_history = self.memory.get_chat_history()
                conversation_context = self._build_conversation_context(chat_history)

            messages = [
                ("system", await self._build_system_prompt(conversation_context)),
                ("human", message),
            ]

            response = await self.llm.ainvoke(messages)
            assistant_reply = response.content if hasattr(response, 'content') else str(response)

            if self.memory:
                await self.memory.save_message("user", message)
                await self.memory.save_message("assistant", assistant_reply)

            return {
                "response": assistant_reply,
                "intermediate_steps": [],
            }

        except Exception as e:
            print(f"Agent Error: {e}")
            simple_response = await self._simple_reply(message)
            return {
                "response": simple_response,
                "error": str(e),
            }

    async def _simple_reply(self, message: str) -> str:
        from services.ai_service import ai_service
        simplified_prompt = [
            {"role": "system", "content": f"你是{self.agent_name}，用户的体重管理助手。请简洁回复。"},
            {"role": "user", "content": message}
        ]
        try:
            response = await ai_service.chat(simplified_prompt, max_tokens=500)
            if not response.error:
                return response.content
        except:
            pass
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
                enable_memory=True
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
