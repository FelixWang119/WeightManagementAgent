# 向量存储服务模块
# 支持 ChromaDB 本地存储，未来可迁移到云端服务

from .embedding import SimpleEmbedding, get_embedding_service, OpenAIEmbedding
from .chroma_store import ChromaVectorStore

__all__ = ["SimpleEmbedding", "get_embedding_service", "OpenAIEmbedding", "ChromaVectorStore"]
