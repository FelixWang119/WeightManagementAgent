"""
Agent 对话 API 路由（优化版）
解决 AI 超时问题：异步处理 + 流式响应 + 重试机制
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    Body,
    UploadFile,
    File,
    Body,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timedelta
import json
import asyncio
import httpx
import logging

from models.database import (
    get_db,
    User,
    ChatHistory,
    ConversationSummary,
    UserProfile,
    AgentConfig,
    MessageRole,
    MessageType,
)
from api.routes.user import get_current_user
from config.settings import fastapi_settings
from services.ai_service import ai_service, AIResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# ============ 配置 ============
AI_TIMEOUT = 60.0  # AI 请求超时时间（秒）
MAX_RETRIES = 2  # 最大重试次数


async def build_system_prompt(user: User, db: AsyncSession) -> str:
    """构建系统 Prompt（包含用户画像数据）- 使用公共UserProfileService"""
    from services.user_profile_service import UserProfileService

    try:
        # 使用UserProfileService获取完整画像
        profile_data = await UserProfileService.get_complete_profile(user.id, db)

        # 使用公共方法构建基础prompt（async方法需要await）
        base_prompt = await UserProfileService.format_system_prompt(profile_data)

        # 添加额外的回复原则（API场景需要更详细的回复）
        additional_rules = """
【回复原则】
1. 根据用户画像个性化回复（如：知道用户是夜猫子，可以提醒不要熬夜）
2. 关心用户情绪和状态，给予情感支持
3. 给出具体可操作的建议，不要只说空话
4. 解释'为什么'，让用户理解原理
5. 适时鼓励，但不要过度，保持真诚
6. 回复详细充实，控制在300-400字左右
7. 结构化回复，使用段落分隔，提高可读性
8. 避免敷衍的回复，每句话都要有价值
9. 如果用户分享成果，要具体赞美，不要只说'真棒'
10. 如果用户遇到困难，要给出具体解决方案"""

        return base_prompt + additional_rules

    except Exception as e:
        logger.warning(f"使用UserProfileService构建prompt失败: %s", e)
        # Fallback到基础版本
        return f"你是{user.nickname or '小助'}，用户的专属体重管理助手。"


async def get_recent_context(
    user_id: int, limit: int = 10, db: Optional[AsyncSession] = None
) -> List[Dict]:
    """获取最近的对话上下文"""
    if db is None:
        return []
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(desc(ChatHistory.created_at))
        .limit(limit)
    )

    records = result.scalars().all()

    # 转换为 OpenAI 格式并反转顺序（从旧到新）
    context = []
    for record in reversed(records):
        context.append({"role": record.role.value, "content": record.content})

    return context


async def save_message_to_db(
    user_id: int,
    role: MessageRole,
    content: str,
    msg_type: MessageType = MessageType.TEXT,
    meta_data: Optional[Dict] = None,
):
    """后台任务：保存消息到数据库"""
    # 创建新的会话用于后台任务
    from models.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            message = ChatHistory(
                user_id=user_id,
                role=role,
                content=content,
                msg_type=msg_type,
                meta_data=meta_data or {},
                created_at=datetime.utcnow(),
            )
            db.add(message)
            await db.commit()
        except Exception as e:
            logger.warning("保存消息失败: %s", e)
            await db.rollback()


async def call_ai_with_retry(
    messages: List[Dict[str, str]], max_retries: int = MAX_RETRIES
) -> AIResponse:
    """带重试机制的 AI 调用"""
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            # 使用 asyncio.wait_for 包装 AI 调用，设置超时
            response = await asyncio.wait_for(
                ai_service.chat(messages, max_tokens=500),  # 限制token数，加快响应
                timeout=AI_TIMEOUT,
            )

            if not response.error:
                return response

            last_error = response.error

            # 如果是最后一次尝试，返回错误
            if attempt == max_retries:
                return response

            # 等待后重试
            await asyncio.sleep(1 * (attempt + 1))

        except asyncio.TimeoutError:
            last_error = f"AI 请求超时（{AI_TIMEOUT}秒）"
            if attempt == max_retries:
                return AIResponse(
                    content="", model=ai_service.provider, error=last_error
                )
            await asyncio.sleep(1 * (attempt + 1))

        except Exception as e:
            last_error = str(e)
            if attempt == max_retries:
                return AIResponse(
                    content="", model=ai_service.provider, error=last_error
                )
            await asyncio.sleep(1 * (attempt + 1))

    return AIResponse(
        content="", model=ai_service.provider, error=last_error or "未知错误"
    )


@router.post("/send")
async def send_message(
    request_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    发送消息给 Agent（优化版，使用 LangChain ReAct Agent）

    - **content**: 消息内容
    - **image_url**: 图片URL（可选，用于食物识别等）
    - **msg_type**: 消息类型（text/image/form 等）

    返回 Agent 的回复（最大等待60秒，带重试机制）
    使用 LangChain ReAct Agent，支持工具调用和用户画像记忆
    """
    try:
        # 从请求数据中提取参数
        content = request_data.get("content", "")
        image_url = request_data.get("image_url", "")
        msg_type = request_data.get("msg_type", "text")

        # 如果没有文本内容但有图片，使用默认提示
        if not content and image_url:
            content = "请帮我分析这张图片中的食物"

        if not content:
            raise HTTPException(status_code=400, detail="消息内容不能为空")

        # 用户ID
        user_id = int(current_user.id)  # type: ignore[arg-type]

        # 构建消息内容（包含图片信息）
        full_content = content
        if image_url:
            full_content = f"{content}\n[图片:{image_url}]"

        # 1. 保存用户消息
        message = ChatHistory(
            user_id=user_id,
            role=MessageRole.USER,
            content=full_content,
            msg_type=MessageType(msg_type),
            meta_data={"image_url": image_url} if image_url else None,
            created_at=datetime.utcnow(),
        )
        db.add(message)
        await db.commit()

        # 2. 调用 LangChain Agent（带 fallback）
        try:
            from services.langchain.agents import AgentFactory

            logger.info(f"Calling AgentFactory.get_agent for user {user_id}")

            # 使用 AgentFactory 获取 Agent 实例
            agent = await AgentFactory.get_agent(user_id, db)
            result = await agent.chat(full_content)

            logger.info(f"Agent completed for user {user_id}")

            assistant_reply = result.get("response", "抱歉，我现在有点忙。")
            structured_response = result.get(
                "structured_response",
                {"type": "text", "content": assistant_reply, "actions": []},
            )
            intermediate_steps = result.get("intermediate_steps", [])

            # 记录日志
            logger.info(
                f"Agent - User: {user_id}, Steps: {len(intermediate_steps)}, Type: {structured_response.get('type')}"
            )

        except Exception as agent_error:
            # Fallback 到旧系统（兼容性保障）
            logger.warning(
                f"LangChain failed, falling back to legacy AI: {agent_error}"
            )
            logger.exception(f"LangChain agent error details:")

            # 构建对话上下文
            system_prompt = await build_system_prompt(current_user, db)
            recent_context = await get_recent_context(current_user.id, limit=5, db=db)

            messages = [
                {"role": "system", "content": system_prompt},
                *recent_context,
                {"role": "user", "content": content},
            ]

            # 调用旧 AI 服务
            response = await call_ai_with_retry(messages)

            if response.error:
                # AI 调用失败，返回友好错误
                error_msg = response.error
                if "timeout" in error_msg.lower():
                    error_msg = "AI 思考时间有点长，请稍后再试"
                elif "rate limit" in error_msg.lower():
                    error_msg = "请求太频繁了，请稍后再试"

                return {
                    "success": False,
                    "error": error_msg,
                    "data": {
                        "content": "抱歉，我现在有点忙，请稍后再试~",
                        "role": "assistant",
                        "timestamp": datetime.utcnow().isoformat(),
                        "is_error": True,
                    },
                }

            assistant_reply = response.content
            # 在 fallback 逻辑中定义 structured_response
            structured_response = {
                "type": "text",
                "content": assistant_reply,
                "actions": [],
            }
            intermediate_steps = []

        # 3. 保存 Agent 回复
        reply_message = ChatHistory(
            user_id=current_user.id,
            role=MessageRole.ASSISTANT,
            content=assistant_reply,
            msg_type=MessageType.TEXT,
            created_at=datetime.utcnow(),
        )
        db.add(reply_message)
        await db.commit()

        # 4. 返回响应（支持结构化消息）
        return {
            "success": True,
            "data": {
                "content": assistant_reply,
                "role": "assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "model": "langchain-agent-v2",
                "message_type": structured_response.get("type", "text"),
                "actions": structured_response.get("actions", []),
                "intermediate_steps": intermediate_steps if intermediate_steps else [],
            },
        }

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理消息时出错: {str(e)}",
        )


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...), current_user: User = Depends(get_current_user)
):
    """
    上传图片用于聊天
    返回图片的访问URL
    """
    import os
    import uuid
    from pathlib import Path

    try:
        # 1. 验证文件类型（白名单）
        allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="不支持的图片类型")

        # 2. 验证文件扩展名（白名单）
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="不支持的文件扩展名")

        # 3. 限制文件大小（最大5MB）
        max_size = 5 * 1024 * 1024  # 5MB
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="文件大小不能超过5MB")

        # 4. 生成安全文件名（防止路径遍历攻击）
        safe_ext = ext.lstrip(".")  # 移除可能的前导点
        filename = f"{current_user.id}_{uuid.uuid4().hex}.{safe_ext}"

        # 5. 保存文件到 uploads 目录
        upload_dir = fastapi_settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)

        # 6. 使用绝对路径并验证路径安全
        filepath = os.path.abspath(os.path.join(upload_dir, filename))
        if not filepath.startswith(os.path.abspath(upload_dir)):
            raise HTTPException(status_code=400, detail="无效的文件路径")

        # 7. 写入文件
        with open(filepath, "wb") as f:
            f.write(content)

        # 返回图片URL
        image_url = f"/uploads/{filename}"

        return {"success": True, "url": image_url, "filename": filename}

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("上传图片失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传图片失败: {str(e)}",
        )


@router.post("/send-async")
async def send_message_async(
    content: str,
    msg_type: str = "text",
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    异步发送消息（立即返回，后台处理 AI）

    适合不需要立即得到回复的场景，如：
    - 用户只是想记录信息
    - 批量处理消息
    - 非即时对话

    返回：消息已接收，正在处理
    """
    try:
        # 保存用户消息
        message = ChatHistory(
            user_id=current_user.id,
            role=MessageRole.USER,
            content=content,
            msg_type=MessageType(msg_type),
            created_at=datetime.utcnow(),
        )
        db.add(message)
        await db.commit()

        # 触发后台 AI 处理
        # TODO: 可以在这里添加真正的后台处理逻辑

        return {
            "success": True,
            "message": "消息已接收，AI 正在思考中...",
            "data": {
                "status": "processing",
                "check_url": f"/api/chat/history?limit=1",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送消息时出错: {str(e)}",
        )


@router.get("/stream")
async def stream_chat(
    content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    流式对话（SSE - Server-Sent Events）

    AI 逐字返回，用户可以实时看到生成过程
    适合需要即时反馈的场景

    使用方式：
    ```javascript
    const eventSource = new EventSource('/api/chat/stream?content=你好');
    eventSource.onmessage = (event) => {
        console.log(event.data);
    };
    ```

    注意：目前仅支持 OpenAI，Qwen 暂不支持流式
    """
    # 保存用户消息
    message = ChatHistory(
        user_id=current_user.id,
        role=MessageRole.USER,
        content=content,
        msg_type=MessageType.TEXT,
        created_at=datetime.utcnow(),
    )
    db.add(message)
    await db.commit()

    # 构建上下文
    system_prompt = await build_system_prompt(current_user, db)
    recent_context = await get_recent_context(current_user.id, limit=5, db=db)

    messages = [
        {"role": "system", "content": system_prompt},
        *recent_context,
        {"role": "user", "content": content},
    ]

    async def generate_stream() -> AsyncGenerator[str, None]:
        """生成流式响应"""
        full_content = ""

        try:
            # 使用 OpenAI 流式 API
            if ai_service.provider == "openai":
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    api_key=fastapi_settings.OPENAI_API_KEY,
                    base_url=fastapi_settings.OPENAI_API_BASE,
                )

                stream = await client.chat.completions.create(
                    model=fastapi_settings.OPENAI_MODEL,
                    messages=messages,
                    max_tokens=500,
                    stream=True,
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content_chunk = chunk.choices[0].delta.content
                        full_content += content_chunk
                        yield f"data: {json.dumps({'content': content_chunk, 'done': False})}\n\n"

                # 保存完整回复
                await save_message_to_db(
                    user_id=current_user.id,
                    role=MessageRole.ASSISTANT,
                    content=full_content,
                    msg_type=MessageType.TEXT,
                )

                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

            else:
                # Qwen 暂不支持流式，使用普通模式
                yield f"data: {json.dumps({'content': '流式响应当前仅支持 OpenAI 模型', 'done': False})}\n\n"

                response = await call_ai_with_retry(messages)
                if response.content:
                    yield f"data: {json.dumps({'content': response.content, 'done': False})}\n\n"

                    await save_message_to_db(
                        user_id=current_user.id,
                        role=MessageRole.ASSISTANT,
                        content=response.content,
                        msg_type=MessageType.TEXT,
                    )

                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/stream")
async def stream_chat_post(
    content: str = Body(..., description="用户消息内容"),
    images: Optional[List[str]] = Body(None, description="图片URL列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    流式对话（POST版本 - 更好的支持图片和内容类型）

    使用方式：
    ```javascript
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            content: '用户消息',
            images: ['image_url_1', 'image_url_2']  // 可选
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        console.log(chunk); // 处理流式数据
    }
    ```

    支持的内容类型：
    - text: 普通文本
    - image: 图片
    - card: 卡片（图表、数据展示）
    - quick_actions: 快捷操作按钮
    """

    # 构建用户消息内容
    user_content = content
    if images:
        # 图片以 markdown 格式嵌入
        image_markdown = "\n".join([f"![图片]({img})" for img in images])
        user_content = f"{content}\n\n{image_markdown}"

    # 保存用户消息
    message = ChatHistory(
        user_id=current_user.id,
        role=MessageRole.USER,
        content=user_content,
        msg_type=MessageType.TEXT,
        meta_data={"images": images} if images else None,
        created_at=datetime.utcnow(),
    )
    db.add(message)
    await db.commit()

    # 构建上下文
    system_prompt = await build_system_prompt(current_user, db)
    recent_context = await get_recent_context(current_user.id, limit=5, db=db)

    messages = [
        {"role": "system", "content": system_prompt},
        *recent_context,
        {"role": "user", "content": user_content},
    ]

    async def generate_stream() -> AsyncGenerator[str, None]:
        """生成流式响应，支持多种内容类型"""
        full_content = ""
        current_type = "text"

        try:
            if ai_service.provider == "openai":
                from openai import AsyncOpenAI

                client = AsyncOpenAI(
                    api_key=fastapi_settings.OPENAI_API_KEY,
                    base_url=fastapi_settings.OPENAI_API_BASE,
                )

                stream = await client.chat.completions.create(
                    model=fastapi_settings.OPENAI_MODEL,
                    messages=messages,
                    max_tokens=1000,
                    stream=True,
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content_chunk = chunk.choices[0].delta.content
                        full_content += content_chunk

                        # 检查是否是特殊标记（用于识别内容类型）
                        if content_chunk.startswith("[IMAGE:"):
                            # 图片标记
                            image_url = content_chunk[7:-1].strip()
                            yield f"data: {json.dumps({'type': 'image', 'content': image_url, 'done': False})}\n\n"
                        elif content_chunk.startswith("[CARD:"):
                            # 卡片标记
                            card_data = content_chunk[6:-1].strip()
                            yield f"data: {json.dumps({'type': 'card', 'content': card_data, 'done': False})}\n\n"
                        elif content_chunk.startswith("[ACTIONS:"):
                            # 快捷操作
                            actions = content_chunk[9:-1].strip()
                            yield f"data: {json.dumps({'type': 'quick_actions', 'content': actions, 'done': False})}\n\n"
                        else:
                            # 普通文本
                            yield f"data: {json.dumps({'type': 'text', 'content': content_chunk, 'done': False})}\n\n"

                # 保存完整回复
                await save_message_to_db(
                    user_id=current_user.id,
                    role=MessageRole.ASSISTANT,
                    content=full_content,
                    msg_type=MessageType.TEXT,
                )

                yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True})}\n\n"

            else:
                # Qwen 或其他模型
                yield f"data: {json.dumps({'type': 'info', 'content': '流式响应当前仅支持 OpenAI 模型，将使用普通模式', 'done': False})}\n\n"

                response = await call_ai_with_retry(messages)
                if response.content:
                    full_content = response.content
                    yield f"data: {json.dumps({'type': 'text', 'content': full_content, 'done': False})}\n\n"

                    await save_message_to_db(
                        user_id=current_user.id,
                        role=MessageRole.ASSISTANT,
                        content=full_content,
                        msg_type=MessageType.TEXT,
                    )

                yield f"data: {json.dumps({'type': 'done', 'content': '', 'done': True})}\n\n"

        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg, 'done': True})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    before_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取对话历史"""
    query = select(ChatHistory).where(ChatHistory.user_id == current_user.id)

    if before_id:
        query = query.where(ChatHistory.id < before_id)

    query = query.order_by(desc(ChatHistory.created_at)).limit(limit)

    result = await db.execute(query)
    records = result.scalars().all()

    return {
        "success": True,
        "count": len(records),
        "data": [
            {
                "id": r.id,
                "role": r.role.value,
                "content": r.content,
                "msg_type": r.msg_type.value,
                "created_at": r.created_at.isoformat(),
            }
            for r in reversed(records)
        ],
    }


@router.post("/clear")
async def clear_chat_history(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """清空对话历史"""
    result = await db.execute(
        select(ChatHistory).where(ChatHistory.user_id == current_user.id)
    )
    records = result.scalars().all()

    for record in records:
        await db.delete(record)

    await db.commit()

    return {
        "success": True,
        "message": f"已清空 {len(records)} 条对话记录",
        "deleted_count": len(records),
    }


@router.get("/context")
async def get_context_info(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """获取当前对话上下文信息"""
    result = await db.execute(
        select(func.count(ChatHistory.id)).where(ChatHistory.user_id == current_user.id)
    )
    total_messages = result.scalar()

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(ChatHistory.id)).where(
            and_(
                ChatHistory.user_id == current_user.id, ChatHistory.created_at >= today
            )
        )
    )
    today_messages = result.scalar()

    system_prompt = await build_system_prompt(current_user, db)

    return {
        "success": True,
        "data": {
            "total_messages": total_messages,
            "today_messages": today_messages,
            "ai_provider": ai_service.provider,
            "ai_timeout": AI_TIMEOUT,
            "max_retries": MAX_RETRIES,
            "system_prompt_preview": system_prompt[:300] + "..."
            if len(system_prompt) > 300
            else system_prompt,
        },
    }


# ============ 每日建议功能 ============

from datetime import timedelta
from functools import lru_cache
from typing import Optional
import time

# 缓存用户的每日建议（带过期机制）
_suggestion_cache: Dict[int, Dict[str, Any]] = {}
_CACHE_MAX_SIZE = 100  # 最大缓存用户数
_CACHE_EXPIRE_SECONDS = 3600  # 缓存过期时间（1小时）


def _get_cached_suggestion(user_id: int) -> Optional[Dict[str, Any]]:
    """获取缓存的建议（带过期检查）"""
    if user_id not in _suggestion_cache:
        return None

    cached = _suggestion_cache[user_id]
    # 检查是否过期
    cached_time = cached.get("_cached_at", 0)
    if time.time() - cached_time > _CACHE_EXPIRE_SECONDS:
        del _suggestion_cache[user_id]
        return None

    return cached.get("suggestion")


def _set_cached_suggestion(user_id: int, suggestion: Dict[str, Any]) -> None:
    """设置缓存的建议（带大小限制）"""
    # 简单的缓存清理：如果超过最大size，删除最早的缓存
    if len(_suggestion_cache) >= _CACHE_MAX_SIZE:
        oldest_key = min(
            _suggestion_cache.keys(),
            key=lambda k: _suggestion_cache[k].get("_cached_at", 0),
        )
        del _suggestion_cache[oldest_key]

    _suggestion_cache[user_id] = {
        "suggestion": suggestion,
        "date": suggestion.get("created_at", "")[:10],  # 提取日期
        "_cached_at": time.time(),
    }


@router.get("/daily-suggestion")
async def get_daily_suggestion(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取AI生成的每日1条建议

    - **refresh**: 是否强制刷新获取新建议
    - 返回1条个性化建议，包含建议文本、类型、相关操作
    """
    from datetime import date
    from models.database import (
        WeightRecord,
        MealRecord,
        ExerciseRecord,
        WaterRecord,
        MealType,
    )

    today = date.today()
    cache_key = current_user.id

    # 检查缓存（除非强制刷新）- 使用带过期检查的新函数
    if not refresh:
        cached = _get_cached_suggestion(cache_key)
        if cached is not None:
            return {"success": True, "suggestion": cached, "cached": True}

    try:
        # 1. 获取今日体重记录
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        weight_result = await db.execute(
            select(WeightRecord)
            .where(
                and_(
                    WeightRecord.user_id == current_user.id,
                    WeightRecord.record_time >= today_start,
                    WeightRecord.record_time <= today_end,
                )
            )
            .order_by(WeightRecord.record_time.desc())
        )
        today_weight = weight_result.scalar_one_or_none()

        # 2. 获取今日餐食记录
        meal_result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.user_id == current_user.id,
                    MealRecord.record_time >= today_start,
                    MealRecord.record_time <= today_end,
                )
            )
        )
        today_meals = meal_result.scalars().all()

        meal_summary = {
            "breakfast": False,
            "lunch": False,
            "dinner": False,
            "snack": False,
            "total_calories": 0,
        }
        for meal in today_meals:
            meal_type = meal.meal_type.value if meal.meal_type else None
            if meal_type:
                meal_summary[meal_type] = True
                meal_summary["total_calories"] += meal.total_calories or 0

        # 3. 获取今日运动记录
        exercise_result = await db.execute(
            select(ExerciseRecord).where(
                and_(
                    ExerciseRecord.user_id == current_user.id,
                    ExerciseRecord.record_time >= today_start,
                    ExerciseRecord.record_time <= today_end,
                )
            )
        )
        today_exercises = exercise_result.scalars().all()
        total_exercise_minutes = sum(e.duration_minutes or 0 for e in today_exercises)

        # 4. 获取今日饮水记录
        water_result = await db.execute(
            select(WaterRecord).where(
                and_(
                    WaterRecord.user_id == current_user.id,
                    WaterRecord.record_time >= today_start,
                    WaterRecord.record_time <= today_end,
                )
            )
        )
        today_waters = water_result.scalars().all()
        total_water_ml = sum(w.amount_ml or 0 for w in today_waters)

        # 5. 构建AI提示词
        current_hour = datetime.now().hour
        time_of_day = (
            "早上"
            if 5 <= current_hour < 11
            else "中午"
            if 11 <= current_hour < 14
            else "下午"
            if 14 <= current_hour < 18
            else "晚上"
        )

        prompt = f"""你是用户的专属健康顾问。请根据以下数据，为{time_of_day}的他/她生成1条轻松有趣的建议（30-50字）。

【用户今日数据】
- 体重: {f"{today_weight.weight}kg" if today_weight else "未记录📝"}
- 饮食: {"✅ 已记录" if meal_summary["total_calories"] > 0 else "待记录🍽️"}
- 运动: {f"{total_exercise_minutes}分钟🏃" if total_exercise_minutes > 0 else "待记录💪"}
- 饮水: {f"{total_water_ml}ml💧" if total_water_ml > 0 else "待记录🥛"}
- 当前时间: {time_of_day}

【请选择以下风格之一，每次随机选，不要重复】（必须选1种）：
1️⃣ 轻松科普 - 分享1个有趣的小知识（不要说教）
2️⃣ 温暖鼓励 - 一句打气的话（不要鸡汤）
3️⃣ 生活技巧 - 1个实用小妙招
4️⃣ 冷知识 - 意想不到的健康冷知识
5️⃣ 今日小事 - 建议做1件简单小事（不超过5个字的动作）
6️⃣ 趣味问答 - 问1个有趣的选择题

【不同风格示例】：
- 轻松科普: "你知道吗？咀嚼20次以上能让大脑及时收到饱腹信号~"
- 温暖鼓励: "今天也在努力的你，真的很棒！🌟"
- 生活技巧: "饭前喝一小杯水，可以少吃约50kcal哦~"
- 冷知识: "睡不够会让人更想吃高热量食物，这就是'睡眠债务'😴"
- 今日小事: "站起来伸个懒腰"
- 趣味问答: "今天吃咸还是吃淡？🥗"

【重要规则】：
⚠️ 不要每次都选"打卡提醒"
⚠️ 不要连续2次选同一种风格
⚠️ 不要说"记得记录""要加油哦"这类话
⚠️ 30-50字，简洁有力
⚠️ 用emoji增加趣味性（1-2个）

直接输出建议内容，不需要解释。"""

        # 6. 调用AI生成建议
        ai_response = await ai_service.chat(
            [
                {
                    "role": "system",
                    "content": "你是专业的体重管理顾问，善于给出简洁实用的建议。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.8,
        )

        if ai_response.error:
            raise Exception(ai_response.error)

        suggestion_content = ai_response.content.strip()

        # 7. 确定建议类型和操作
        suggestion_type = "general"
        action_text = "知道了"
        action_target = ""

        # 根据内容和数据状态确定类型和建议操作
        if not today_weight and "体重" in suggestion_content:
            suggestion_type = "weight"
            action_text = "记录体重"
            action_target = "weight.html"
        elif not meal_summary["breakfast"] and "早餐" in suggestion_content:
            suggestion_type = "meal"
            action_text = "记录早餐"
            action_target = "meal.html?type=breakfast"
        elif not meal_summary["lunch"] and "午餐" in suggestion_content:
            suggestion_type = "meal"
            action_text = "记录午餐"
            action_target = "meal.html?type=lunch"
        elif not meal_summary["dinner"] and "晚餐" in suggestion_content:
            suggestion_type = "meal"
            action_text = "记录晚餐"
            action_target = "meal.html?type=dinner"
        elif total_water_ml < 1000 and (
            "水" in suggestion_content or "饮水" in suggestion_content
        ):
            suggestion_type = "water"
            action_text = "记录饮水"
            action_target = "water.html"
        elif total_exercise_minutes < 30 and (
            "运动" in suggestion_content or "活动" in suggestion_content
        ):
            suggestion_type = "exercise"
            action_text = "记录运动"
            action_target = "exercise.html"

        # 8. 构建建议对象
        suggestion = {
            "id": f"sugg_{current_user.id}_{today.isoformat()}_{datetime.now().timestamp()}",
            "content": suggestion_content,
            "type": suggestion_type,
            "priority": "high"
            if not today_weight or meal_summary["total_calories"] < 500
            else "medium",
            "action_text": action_text,
            "action_type": "navigate" if action_target else "none",
            "action_target": action_target,
            "created_at": datetime.utcnow().isoformat(),
            "data_summary": {
                "weight_recorded": today_weight is not None,
                "meals_recorded": sum(
                    [
                        meal_summary["breakfast"],
                        meal_summary["lunch"],
                        meal_summary["dinner"],
                    ]
                ),
                "total_calories": meal_summary["total_calories"],
                "exercise_minutes": total_exercise_minutes,
                "water_ml": total_water_ml,
            },
        }

        # 9. 缓存建议（使用带大小限制的新函数）
        _set_cached_suggestion(cache_key, suggestion)

        return {"success": True, "suggestion": suggestion, "cached": False}

    except Exception as e:
        logger.warning("生成每日建议失败: %s", e)
        # 返回默认建议
        return {
            "success": True,
            "suggestion": {
                "id": f"default_{current_user.id}",
                "content": "坚持记录是减重的第一步，今天也要记得记录体重哦！💪",
                "type": "general",
                "priority": "medium",
                "action_text": "记录体重",
                "action_type": "navigate",
                "action_target": "weight.html",
                "created_at": datetime.utcnow().isoformat(),
            },
            "cached": False,
            "fallback": True,
        }


# ============ LangChain 集成路由 ============


@router.post("/send-langchain")
async def send_message_langchain(
    request_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    使用 LangChain ReAct Agent 发送消息（已弃用，请使用 /send 端点）

    ⚠️ DEPRECATED: 此端点已弃用，请使用 /send 端点。
    /send 端点现在使用相同的 LangChain Agent 实现。

    新架构：
    - 支持工具调用（记录体重、分析餐食等）
    - 三层记忆管理
    - 向量检索长期记忆

    返回 Agent 的回复（带工具调用追踪）
    """
    try:
        # 从请求数据中提取参数
        content = request_data.get("content", "")
        image_url = request_data.get("image_url", "")
        msg_type = request_data.get("msg_type", "text")

        # 如果没有文本内容但有图片，使用默认提示
        if not content and image_url:
            content = "请帮我分析这张图片中的食物"

        if not content:
            raise HTTPException(status_code=400, detail="消息内容不能为空")

        # 构建消息内容
        full_content = content
        if image_url:
            full_content = f"{content}\n[图片:{image_url}]"

        # 1. 保存用户消息
        message = ChatHistory(
            user_id=current_user.id,
            role=MessageRole.USER,
            content=full_content,
            msg_type=MessageType(msg_type),
            meta_data={"image_url": image_url} if image_url else None,
            created_at=datetime.utcnow(),
        )
        db.add(message)
        await db.commit()

        # 2. 调用 LangChain Agent（带 fallback）
        try:
            from services.langchain.agents import chat_with_agent
            from services.langchain.memory import save_to_memory

            # 调用 Agent
            result = await chat_with_agent(
                user_id=current_user.id, db=db, message=full_content
            )

            assistant_reply = result.get("response", "抱歉，我现在有点忙。")
            intermediate_steps = result.get("intermediate_steps", [])

            # 记录日志
            logger.info(
                f"LangChain Agent - User: {current_user.id}, Steps: {len(intermediate_steps)}"
            )

        except Exception as agent_error:
            # Fallback 到旧系统
            logger.warning(f"LangChain failed, falling back: {agent_error}")

            # 构建对话上下文
            system_prompt = await build_system_prompt(current_user, db)
            recent_context = await get_recent_context(current_user.id, limit=5, db=db)

            messages = [
                {"role": "system", "content": system_prompt},
                *recent_context,
                {"role": "user", "content": content},
            ]

            # 调用旧 AI 服务
            response = await call_ai_with_retry(messages)

            if response.error:
                raise Exception(response.error)

            assistant_reply = response.content
            intermediate_steps = [{"type": "fallback", "from": "legacy_ai"}]

        # 3. 保存 Agent 回复
        reply_message = ChatHistory(
            user_id=current_user.id,
            role=MessageRole.ASSISTANT,
            content=assistant_reply,
            msg_type=MessageType.TEXT,
            created_at=datetime.utcnow(),
        )
        db.add(reply_message)
        await db.commit()

        def format_step(step):
            """格式化中间步骤"""
            if hasattr(step, "tool") and hasattr(step, "tool_input"):
                return {
                    "tool": step.tool,
                    "input": step.tool_input,
                    "output": getattr(step, "tool_output", "")
                    or getattr(step, "log", ""),
                }
            elif hasattr(step, "return_values"):
                return {
                    "tool": "final",
                    "input": "",
                    "output": step.return_values.get("output", ""),
                }
            else:
                return {
                    "tool": str(type(step).__name__),
                    "input": "",
                    "output": str(step),
                }

        return {
            "success": True,
            "data": {
                "content": assistant_reply,
                "role": "assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "model": "langchain-react-agent",
                "intermediate_steps": [format_step(step) for step in intermediate_steps]
                if intermediate_steps
                else [],
            },
        }

    except Exception as e:
        logger.error(f"LangChain chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理消息时出错: {str(e)}",
        )


@router.post("/memory/search")
async def search_user_memory(
    request_data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索用户长期记忆（向量检索）

    Body:
    - query: 查询文本
    - category: 可选，按类别过滤
    - k: 返回数量，默认5
    """
    try:
        query = request_data.get("query", "")
        category = request_data.get("category")
        k = request_data.get("k", 5)

        if not query:
            raise HTTPException(status_code=400, detail="查询内容不能为空")

        # 搜索记忆
        from services.langchain.memory import get_user_memory

        memory = await get_user_memory(current_user.id, db)
        results = await memory.search_memory(query, k=k)

        return {"success": True, "query": query, "results": results}

    except Exception as e:
        logger.error(f"Memory search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索记忆时出错: {str(e)}",
        )


@router.post("/memory/clear")
async def clear_user_memory(current_user: User = Depends(get_current_user)):
    """
    清空用户记忆（短期+中期+长期）
    """
    try:
        from services.langchain.memory import MemoryManager

        MemoryManager.clear_user_memory(current_user.id)

        return {"success": True, "message": "记忆已清空"}

    except Exception as e:
        logger.error(f"Clear memory error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空记忆时出错: {str(e)}",
        )


@router.get("/memory/stats")
async def get_memory_stats(current_user: User = Depends(get_current_user)):
    """
    获取用户记忆统计
    """
    try:
        from services.vectorstore.chroma_store import get_user_vector_store

        store = get_user_vector_store(current_user.id)

        return {
            "success": True,
            "stats": {
                "vector_documents": store.count_documents(),
                "user_id": current_user.id,
            },
        }

    except Exception as e:
        logger.error(f"Memory stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取记忆统计时出错: {str(e)}",
        )
