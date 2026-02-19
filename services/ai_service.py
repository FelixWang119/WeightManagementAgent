"""
AI 服务模块
支持多种模型：OpenAI GPT、通义千问(Qwen)
"""

import httpx
import json
import asyncio
from typing import AsyncGenerator, Optional, List, Dict, Any, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
import openai
from openai.types.chat import ChatCompletionMessageParam
from functools import wraps

from config.settings import fastapi_settings
from utils.alert_utils import alert_error, alert_warning, AlertCategory


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """重试装饰器，带指数退避"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        break

                    # 指数退避延迟
                    delay = base_delay * (2**attempt)
                    logger = args[0].__class__.__module__  # 获取类模块作为logger
                    print(
                        f"[{logger}] 第{attempt + 1}次重试失败，等待{delay:.1f}秒后重试: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                except Exception as e:
                    # 其他异常不重试
                    raise e

            # 所有重试都失败
            if last_exception:
                raise last_exception
            else:
                raise Exception("重试失败，未知错误")

        return wrapper

    return decorator


@dataclass
class AIResponse:
    """AI 响应数据类"""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None

    def __post_init__(self):
        # 确保content始终是字符串，即使为None也转换为空字符串
        if self.content is None:
            self.content = ""


class BaseAIClient(ABC):
    """AI 客户端基类"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> AIResponse:
        """聊天完成"""
        pass

    @abstractmethod
    async def vision_analysis(
        self, image_url: str, prompt: str, model: Optional[str] = None
    ) -> AIResponse:
        """图像分析（用于餐食识别）"""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI 客户端"""

    def __init__(self):
        if not fastapi_settings.OPENAI_API_KEY:
            raise ValueError("未配置 OPENAI_API_KEY")

        self.client = openai.AsyncOpenAI(
            api_key=fastapi_settings.OPENAI_API_KEY,
            base_url=fastapi_settings.OPENAI_API_BASE,
        )
        self.default_model = fastapi_settings.OPENAI_MODEL
        self.default_max_tokens = fastapi_settings.OPENAI_MAX_TOKENS
        self.default_temperature = fastapi_settings.OPENAI_TEMPERATURE

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> AIResponse:
        """OpenAI 聊天完成"""
        try:
            # 转换消息格式为OpenAI SDK期望的类型
            openai_messages: List[ChatCompletionMessageParam] = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # 确保角色是有效的OpenAI角色
                if role in ["system", "user", "assistant"]:
                    # 使用类型断言绕过类型检查
                    message: ChatCompletionMessageParam = {
                        "role": role,
                        "content": content,
                    }  # type: ignore
                    openai_messages.append(message)
                else:
                    # 默认使用user角色
                    message: ChatCompletionMessageParam = {
                        "role": "user",
                        "content": content,
                    }  # type: ignore
                    openai_messages.append(message)

            if stream:
                # 流式响应处理
                response_stream = await self.client.chat.completions.create(
                    model=model or self.default_model,
                    messages=openai_messages,
                    max_tokens=max_tokens or self.default_max_tokens,
                    temperature=temperature or self.default_temperature,
                    stream=stream,
                )

                # 对于流式响应，我们收集所有内容
                content_parts = []
                async for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)

                content = "".join(content_parts)
                return AIResponse(
                    content=content,
                    model=model or self.default_model,
                )
            else:
                # 非流式响应
                response = await self.client.chat.completions.create(
                    model=model or self.default_model,
                    messages=openai_messages,
                    max_tokens=max_tokens or self.default_max_tokens,
                    temperature=temperature or self.default_temperature,
                    stream=stream,
                )

                return AIResponse(
                    content=response.choices[0].message.content or "",
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    if response.usage
                    else None,
                )
        except Exception as e:
            # 记录AI服务错误告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="OpenAI API调用失败",
                details={
                    "model": model or self.default_model,
                    "error": str(e),
                    "endpoint": "chat/completions",
                },
                module="ai_service.OpenAIClient",
            )
            return AIResponse(
                content="",
                model=model or self.default_model,
                error=f"OpenAI API 错误: {str(e)}",
            )

    async def vision_analysis(
        self, image_url: str, prompt: str, model: Optional[str] = None
    ) -> AIResponse:
        """OpenAI 视觉分析"""
        try:
            # 使用类型断言绕过类型检查
            messages: List[ChatCompletionMessageParam] = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }  # type: ignore
            ]

            response = await self.client.chat.completions.create(
                model=model or "gpt-4-vision-preview",
                messages=messages,
                max_tokens=1000,
            )

            return AIResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
            )
        except Exception as e:
            # 记录AI视觉服务错误告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="OpenAI Vision API调用失败",
                details={
                    "model": model or "gpt-4-vision-preview",
                    "error": str(e),
                    "endpoint": "chat/completions",
                    "feature": "vision_analysis",
                },
                module="ai_service.OpenAIClient",
            )
            return AIResponse(
                content="",
                model=model or "gpt-4-vision-preview",
                error=f"OpenAI Vision 错误: {str(e)}",
            )


class QwenClient(BaseAIClient):
    """通义千问(Qwen)客户端 - 阿里云 DashScope"""

    def __init__(self):
        if not fastapi_settings.QWEN_API_KEY:
            raise ValueError("未配置 QWEN_API_KEY")

        self.api_key = fastapi_settings.QWEN_API_KEY
        self.api_base = fastapi_settings.QWEN_API_BASE
        self.default_model = fastapi_settings.QWEN_MODEL
        self.default_max_tokens = fastapi_settings.QWEN_MAX_TOKENS
        self.default_temperature = fastapi_settings.QWEN_TEMPERATURE

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 超时设置（秒）
        self.timeout = 30.0  # 总超时
        self.connect_timeout = 10.0  # 连接超时
        self.read_timeout = 20.0  # 读取超时

    @retry_with_backoff(max_retries=2, base_delay=1.0)
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> AIResponse:
        """Qwen 聊天完成 - 使用OpenAI兼容接口"""
        try:
            # 使用OpenAI兼容接口
            # 如果base_url已经包含compatible-mode/v1，直接使用
            if "compatible-mode/v1" in self.api_base:
                url = f"{self.api_base}/chat/completions"
            else:
                # 否则添加compatible-mode/v1路径
                url = f"{self.api_base}/compatible-mode/v1/chat/completions"

            payload = {
                "model": model or self.default_model,
                "messages": messages,
                "max_tokens": max_tokens or self.default_max_tokens,
                "temperature": temperature or self.default_temperature,
            }

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.connect_timeout,
                    read=self.read_timeout,
                    write=10.0,
                    pool=5.0,
                )
            ) as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    return AIResponse(
                        content=choice["message"]["content"],
                        model=data.get("model", model or self.default_model),
                        usage=data.get("usage"),
                    )
                else:
                    return AIResponse(
                        content="",
                        model=model or self.default_model,
                        error=f"Qwen API 响应格式错误: {data}",
                    )

        except httpx.HTTPError as e:
            # 记录Qwen HTTP错误告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen HTTP API调用失败",
                details={
                    "model": model or self.default_model,
                    "error": str(e),
                    "endpoint": "chat/completions",
                    "provider": "qwen",
                },
                module="ai_service.QwenClient",
            )
            return AIResponse(
                content="",
                model=model or self.default_model,
                error=f"Qwen HTTP 错误: {str(e)}",
            )
        except Exception as e:
            # 记录Qwen API错误告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen API调用失败",
                details={
                    "model": model or self.default_model,
                    "error": str(e),
                    "endpoint": "chat/completions",
                    "provider": "qwen",
                },
                module="ai_service.QwenClient",
            )
            return AIResponse(
                content="",
                model=model or self.default_model,
                error=f"Qwen API 错误: {str(e)}",
            )

    @retry_with_backoff(max_retries=1, base_delay=2.0)
    async def vision_analysis(
        self, image_url: str, prompt: str, model: Optional[str] = None
    ) -> AIResponse:
        """Qwen 图像分析 - 使用OpenAI兼容接口"""
        try:
            # 使用OpenAI兼容接口
            # 如果base_url已经包含compatible-mode/v1，直接使用
            if "compatible-mode/v1" in self.api_base:
                url = f"{self.api_base}/chat/completions"
            else:
                # 否则添加compatible-mode/v1路径
                url = f"{self.api_base}/compatible-mode/v1/chat/completions"

            # 尝试使用支持视觉的模型，如果未指定则使用默认
            vision_model = model or "qwen-vl-plus"

            # 检查是否是base64 data URL，如果不是则转换为base64
            if image_url.startswith("data:image"):
                # 已经是data URL格式
                image_content = image_url
            else:
                # 假设是文件URL，需要下载并转换为base64
                # 这里简化处理，实际应该下载图片
                image_content = image_url

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_content}},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 1000,
            }

            print(f"Vision分析请求 - 模型: {vision_model}, URL: {url}")
            print(
                f"图片URL类型: {'data URL' if image_url.startswith('data:image') else '普通URL'}"
            )

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.connect_timeout,
                    read=self.read_timeout,
                    write=10.0,
                    pool=5.0,
                )
            ) as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()

                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    return AIResponse(
                        content=choice["message"]["content"],
                        model=data.get("model", vision_model),
                    )
                else:
                    return AIResponse(
                        content="",
                        model=vision_model,
                        error=f"Qwen Vision 响应格式错误: {data}",
                    )
        except httpx.HTTPError as e:
            # 记录Qwen Vision HTTP错误告警
            error_msg = str(e)
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen Vision API调用失败",
                details={
                    "model": model or "qwen-vl-plus",
                    "error": error_msg,
                    "endpoint": "compatible-mode/v1/chat/completions",
                    "provider": "qwen",
                    "feature": "vision_analysis",
                },
                module="ai_service.QwenClient",
            )

            # 检查是否是模型不支持的错误
            if "400" in error_msg and "model" in error_msg.lower():
                print(f"Vision模型可能不支持，错误: {error_msg}")
                return AIResponse(
                    content="",
                    model=model or "qwen-vl-plus",
                    error=f"Qwen Vision 模型不支持或配置错误: {error_msg}",
                )

            return AIResponse(
                content="",
                model=model or "qwen-vl-plus",
                error=f"Qwen Vision 错误: {error_msg}",
            )
        except Exception as e:
            # 记录Qwen Vision API错误告警
            error_msg = str(e)
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="Qwen Vision API调用失败",
                details={
                    "model": model or "qwen-vl-plus",
                    "error": error_msg,
                    "endpoint": "compatible-mode/v1/chat/completions",
                    "provider": "qwen",
                    "feature": "vision_analysis",
                },
                module="ai_service.QwenClient",
            )
            return AIResponse(
                content="",
                model=model or "qwen-vl-plus",
                error=f"Qwen Vision 错误: {error_msg}",
            )


class AIService:
    """AI 服务统一接口"""

    def __init__(self, provider: Optional[str] = None):
        """
        初始化 AI 服务

        Args:
            provider: 模型提供商，'openai' 或 'qwen'，默认从配置读取
        """
        self.provider = provider or fastapi_settings.DEFAULT_AI_PROVIDER
        self._client: Optional[BaseAIClient] = None

    def _get_client(self) -> BaseAIClient:
        """获取或创建客户端"""
        if self._client is None:
            if self.provider == "openai":
                self._client = OpenAIClient()
            elif self.provider == "qwen":
                self._client = QwenClient()
            else:
                raise ValueError(f"不支持的 AI 提供商: {self.provider}")
        return self._client

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> AIResponse:
        """
        通用聊天接口

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            **kwargs: 其他参数（max_tokens, temperature 等）

        Returns:
            AIResponse 对象
        """
        client = self._get_client()
        return await client.chat_completion(messages, **kwargs)

    async def analyze_image(self, image_url: str, prompt: str, **kwargs) -> AIResponse:
        """
        图像分析接口（用于餐食识别）

        Args:
            image_url: 图片 URL
            prompt: 分析提示词
            **kwargs: 其他参数

        Returns:
            AIResponse 对象
        """
        client = self._get_client()
        return await client.vision_analysis(image_url, prompt, **kwargs)

    async def analyze_meal(self, image_url: str) -> Dict[str, Any]:
        """
        分析餐食照片

        Args:
            image_url: 餐食照片 URL

        Returns:
            解析后的餐食信息
        """
        prompt = """请分析这张餐食照片，识别食物种类并估算热量。

请按以下格式回复：
食物名称: [具体食物名称]
主要成分: [列出主要食材]
估算重量: [克数]
估算热量: [千卡数]
营养成分: 蛋白质[X]g, 碳水[Y]g, 脂肪[Z]g
置信度: [0-1之间的小数]

注意：
1. 如果无法识别，请说明"无法清晰识别"
2. 热量估算是大概值，仅供参考
3. 如果是中餐，请尽量使用中文菜名"""

        response = await self.analyze_image(image_url, prompt)

        if response.error:
            # 记录餐食分析失败告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="餐食图片分析失败",
                details={
                    "image_url": image_url,
                    "error": response.error,
                    "model": response.model,
                },
                module="ai_service.AIService",
            )
            return {
                "success": False,
                "error": response.error,
                "raw_content": response.content,
            }

        # 解析 AI 返回的内容
        content = response.content
        result = {
            "success": True,
            "model": response.model,
            "raw_content": content,
            "parsed": {},
        }

        # 尝试解析结构化数据
        lines = content.strip().split("\n")
        for line in lines:
            if "：" in line or ":" in line:
                # 统一使用英文冒号
                line = line.replace("：", ":")
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    result["parsed"][key] = value

        return result

    async def generate_text(self, prompt: str, **kwargs) -> str:
        """
        生成文本（用于摘要生成等简单文本任务）

        Args:
            prompt: 提示词
            **kwargs: 其他参数（max_tokens, temperature 等）

        Returns:
            生成的文本内容
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat(messages, **kwargs)

        if response.error:
            # 记录文本生成失败告警
            alert_error(
                category=AlertCategory.AI_SERVICE,
                message="文本生成失败",
                details={
                    "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    "error": response.error,
                    "model": response.model,
                },
                module="ai_service.AIService",
            )
            # 返回空字符串而不是抛出异常，让调用方可以优雅降级
            return ""

        return response.content


# 全局 AI 服务实例
ai_service = AIService()


async def test_ai():
    """测试 AI 服务"""
    print("🧪 测试 AI 服务...")

    # 测试聊天
    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请介绍一下你自己"},
    ]

    print(f"\n使用模型: {fastapi_settings.DEFAULT_AI_PROVIDER}")
    response = await ai_service.chat(messages)

    if response.error:
        print(f"❌ 错误: {response.error}")
    else:
        print(f"✅ 成功!")
        print(f"模型: {response.model}")
        print(f"回复: {response.content[:100]}...")
        if response.usage:
            print(f"Token 使用: {response.usage}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_ai())
