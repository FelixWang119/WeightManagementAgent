"""
LangChain 基础配置

提供统一的模型配置，支持 OpenAI / Qwen 等多种 LLM

开发环境：Qwen（已对接）
生产环境：可切换到 OpenAI / Claude
"""

from typing import Optional, Dict, Any
from enum import Enum

# 读取配置
from config.settings import fastapi_settings


class AIProvider(str, Enum):
    """AI 服务提供商"""
    OPENAI = "openai"
    QWEN = "qwen"


class LangChainConfig:
    """
    LangChain 配置中心
    
    统一管理不同 AI 提供商的配置
    
    使用示例：
    ```python
    from services.langchain.base import LangChainConfig
    
    # 获取聊天模型
    llm = LangChainConfig.get_chat_model()
    
    # 获取配置信息
    info = LangChainConfig.get_provider_info()
    ```
    """
    
    @staticmethod
    def get_chat_model(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        获取聊天模型
        
        Args:
            provider: 提供商，默认从配置读取
            model_name: 模型名称，默认从配置读取
            temperature: 温度参数
            max_tokens: 最大输出 tokens
            
        Returns:
            LangChain ChatModel 实例
        """
        provider = provider or fastapi_settings.DEFAULT_AI_PROVIDER
        
        if provider == AIProvider.OPENAI:
            return LangChainConfig._get_openai_model(model_name, temperature, max_tokens)
        elif provider == AIProvider.QWEN:
            return LangChainConfig._get_qwen_model(model_name, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    @staticmethod
    def _get_openai_model(
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        获取 OpenAI 模型
        
        生产环境建议：
        - 使用 GPT-4 或 GPT-4 Turbo
        - 配置 API Key 和 Base URL
        """
        from langchain_community.chat_models import ChatOpenAI
        
        model_name = model_name or fastapi_settings.OPENAI_MODEL or "gpt-4"
        
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=fastapi_settings.OPENAI_API_KEY,
            openai_api_base=fastapi_settings.OPENAI_API_BASE,
        )
    
    @staticmethod
    def _get_qwen_model(
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        获取 Qwen 模型（通义千问）
        
        使用 OpenAI 兼容接口
        """
        from langchain_community.chat_models import ChatOpenAI as QwenChatOpenAI
        
        model_name = model_name or fastapi_settings.QWEN_MODEL or "qwen-turbo"
        
        return QwenChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=fastapi_settings.QWEN_API_KEY,
            openai_api_base=fastapi_settings.QWEN_API_BASE,
        )
    
    @staticmethod
    def get_embeddings():
        """
        获取嵌入模型
        
        开发环境：本地 Sentence-Transformers
        生产环境：OpenAI Embeddings
        
        使用示例：
        ```python
        embeddings = LangChainConfig.get_embeddings()
        vectorstore = Chroma(embedding_function=embeddings)
        ```
        """
        # 生产环境切换到此配置
        # from langchain_openai import OpenAIEmbeddings
        # return OpenAIEmbeddings(model="text-embedding-3-small")
        
        # 开发环境使用本地模型
        from services.vectorstore.embedding import get_embedding_service
        return get_embedding_service()
    
    @staticmethod
    def get_provider_info() -> Dict[str, Any]:
        """
        获取当前提供商信息
        
        Returns:
            提供商配置信息
        """
        provider = fastapi_settings.DEFAULT_AI_PROVIDER
        
        if provider == AIProvider.OPENAI:
            return {
                "provider": "openai",
                "model": fastapi_settings.OPENAI_MODEL,
                "temperature": fastapi_settings.OPENAI_TEMPERATURE,
            }
        elif provider == AIProvider.QWEN:
            return {
                "provider": "qwen",
                "model": fastapi_settings.QWEN_MODEL,
                "temperature": fastapi_settings.QWEN_TEMPERATURE,
            }
        
        return {
            "provider": provider,
            "model": None,
            "temperature": 0.7,
        }
    
    @staticmethod
    def get_default_temperature() -> float:
        """获取默认温度参数"""
        provider = fastapi_settings.DEFAULT_AI_PROVIDER
        
        if provider == AIProvider.OPENAI:
            return fastapi_settings.OPENAI_TEMPERATURE
        elif provider == AIProvider.QWEN:
            return fastapi_settings.QWEN_TEMPERATURE
        
        return 0.7
    
    @staticmethod
    def get_max_tokens() -> int:
        """获取默认最大输出 tokens"""
        provider = fastapi_settings.DEFAULT_AI_PROVIDER
        
        if provider == AIProvider.OPENAI:
            return fastapi_settings.OPENAI_MAX_TOKENS
        elif provider == AIProvider.QWEN:
            return fastapi_settings.QWEN_MAX_TOKENS
        
        return 2000


# 便捷函数
def get_chat_model(**kwargs) -> Any:
    """获取聊天模型"""
    return LangChainConfig.get_chat_model(**kwargs)


def get_embeddings():
    """获取嵌入模型"""
    return LangChainConfig.get_embeddings()


def get_provider_info() -> Dict[str, Any]:
    """获取提供商信息"""
    return LangChainConfig.get_provider_info()
