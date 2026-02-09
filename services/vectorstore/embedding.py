"""
本地嵌入服务

使用简单的文本哈希 + 平均词向量作为降级方案
或使用 OpenAI 兼容的嵌入 API
"""

from typing import List, Any
import numpy as np
import hashlib
import json


class SimpleEmbedding:
    """简单文本嵌入（基于词频哈希）"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vocab = {}

    def _text_to_vector(self, text: str) -> np.ndarray:
        """将文本转换为向量"""
        words = text.lower().split()
        vector = np.zeros(self.dimension)
        for i, word in enumerate(words):
            hash_val = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            vector[hash_val % self.dimension] += 1.0 / (i + 1)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def embed(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量"""
        return self._text_to_vector(text).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入向量"""
        return [self.embed(text) for text in texts]


class OpenAIEmbedding:
    """OpenAI 兼容的嵌入 API"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def embed(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入向量"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [data.embedding for data in response.data]


_embedding_service = None


def get_embedding_service() -> SimpleEmbedding:
    """获取嵌入服务"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = SimpleEmbedding()
    return _embedding_service


def use_openai_embedding(api_key: str = None, base_url: str = None, model: str = "text-embedding-3-small"):
    """切换到 OpenAI 嵌入"""
    global _embedding_service
    _embedding_service = OpenAIEmbedding(api_key=api_key, base_url=base_url, model=model)
