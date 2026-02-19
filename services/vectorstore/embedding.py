"""
本地嵌入服务

使用简单的文本哈希 + 平均词向量作为降级方案
或使用 OpenAI 兼容的嵌入 API
"""

from typing import List, Any, Optional, Union
import numpy as np
import hashlib
import json


class SimpleEmbedding:
    """简单文本嵌入（基于词频哈希）"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vocab = {}
        self._cache = {}
        self._cache_maxsize = 1000
        self._cache_keys = []  # LRU 顺序

    def _text_to_vector(self, text: str) -> np.ndarray:
        """将文本转换为向量"""
        words = text.lower().split()
        vector = np.zeros(self.dimension)
        for i, word in enumerate(words):
            # 使用Python内置hash()替代MD5，性能更高
            hash_val = hash(word) & 0xFFFFFFFF  # 32位无符号整数
            vector[hash_val % self.dimension] += 1.0 / (i + 1)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def embed(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量（带LRU缓存）"""
        # 检查缓存
        if text in self._cache:
            # 更新LRU顺序
            self._cache_keys.remove(text)
            self._cache_keys.append(text)
            return self._cache[text]

        # 计算嵌入向量
        vector = self._text_to_vector(text).tolist()

        # 添加到缓存
        if len(self._cache) >= self._cache_maxsize:
            # 移除最久未使用的
            oldest = self._cache_keys.pop(0)
            del self._cache[oldest]

        self._cache[text] = vector
        self._cache_keys.append(text)

        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入向量（批量缓存优化）"""
        results = []
        to_compute = []
        to_compute_indices = []

        # 先检查缓存
        for i, text in enumerate(texts):
            if text in self._cache:
                # 更新LRU顺序
                self._cache_keys.remove(text)
                self._cache_keys.append(text)
                results.append(self._cache[text])
            else:
                results.append(None)  # 占位符
                to_compute.append(text)
                to_compute_indices.append(i)

        # 计算缺失的嵌入向量
        if to_compute:
            computed_vectors = []
            for text in to_compute:
                vector = self._text_to_vector(text).tolist()
                computed_vectors.append(vector)

                # 添加到缓存
                if len(self._cache) >= self._cache_maxsize:
                    oldest = self._cache_keys.pop(0)
                    del self._cache[oldest]

                self._cache[text] = vector
                self._cache_keys.append(text)

            # 填充结果
            for i, idx in enumerate(to_compute_indices):
                results[idx] = computed_vectors[i]

        return results


class OpenAIEmbedding:
    """OpenAI 兼容的嵌入 API"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
    ):
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
        response = client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取嵌入向量"""
        client = self._get_client()
        response = client.embeddings.create(model=self.model, input=texts)
        return [data.embedding for data in response.data]


_embedding_service: Union[SimpleEmbedding, OpenAIEmbedding, None] = None


def get_embedding_service() -> Union[SimpleEmbedding, OpenAIEmbedding]:
    """获取嵌入服务"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = SimpleEmbedding()
    return _embedding_service


def use_openai_embedding(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "text-embedding-3-small",
):
    """切换到 OpenAI 嵌入"""
    global _embedding_service
    _embedding_service = OpenAIEmbedding(
        api_key=api_key, base_url=base_url, model=model
    )
