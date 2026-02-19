"""
ChromaDB 向量存储实现

开发环境：本地文件存储
生产环境：可迁移到 Pinecone / Milvus / Weaviate 等云端服务

特点：
- 本地持久化存储
- 支持相似性搜索
- 支持元数据过滤
- 自动持久化到磁盘
"""

from typing import List, Dict, Optional, Any
import os
import json
from datetime import datetime

import chromadb
from chromadb.config import Settings

# 默认配置
DEFAULT_PERSIST_DIR = "./data/vector_db"


class ChromaVectorStore:
    """
    ChromaDB 向量存储封装

    用于存储用户对话历史、画像数据等，支持相似性检索

    使用示例：
    ```python
    store = ChromaVectorStore(collection_name="user_1")

    # 添加文档
    store.add_documents(
        documents=["用户说：我今天吃了米饭"],
        metadatas=[{"type": "meal", "date": "2024-01-01"}]
    )

    # 相似性搜索
    results = store.similarity_search("今天吃了什么", k=5)
    ```
    """

    def __init__(
        self,
        collection_name: str,
        persist_dir: str = DEFAULT_PERSIST_DIR,
        embedding_function: Optional[Any] = None,
    ):
        """
        初始化 ChromaDB

        Args:
            collection_name: 集合名称（通常用 user_id 命名）
            persist_dir: 持久化目录
            embedding_function: 嵌入函数，默认使用 LocalEmbedding
        """
        self.collection_name = collection_name
        self.persist_dir = persist_dir

        # 初始化嵌入函数
        if embedding_function is None:
            from .embedding import get_embedding_service

            self._embedding_function = get_embedding_service().embed
        else:
            self._embedding_function = embedding_function

        # 确保目录存在
        os.makedirs(persist_dir, exist_ok=True)

        # 初始化 ChromaDB 客户端（使用持久化存储）
        self._client = chromadb.PersistentClient(path=persist_dir)

        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": f"Vector store for {collection_name}"},
        )

    @property
    def collection(self):
        """获取集合"""
        return self._collection

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        添加文档到向量库

        Args:
            documents: 文档内容列表
            metadatas: 元数据列表（可选）
            ids: 文档ID列表（可选，自动生成）

        Returns:
            生成的文档ID列表
        """
        if not documents:
            return []

        # 自动生成ID
        if ids is None:
            ids = [
                f"doc_{i}_{datetime.now().timestamp()}" for i in range(len(documents))
            ]

        # 如果没有提供元数据，创建空元数据
        if metadatas is None:
            metadatas = [{}] * len(documents)

        # 添加到集合
        self._collection.add(documents=documents, metadatas=metadatas, ids=ids)

        return ids

    def similarity_search(
        self, query: str, k: int = 5, filter_metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        相似性搜索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter_metadata: 元数据过滤条件（可选）

        Returns:
            搜索结果列表，每个结果包含 document, metadata, distance, id

        示例：
        ```python
        results = store.similarity_search(
            "用户说我最近体重下降了",
            k=5,
            filter_metadata={"type": "weight_record"}
        )
        ```
        """
        # 执行查询
        where_clause = None
        if filter_metadata:
            # 检查是否已经是ChromaDB的where格式（包含操作符）
            # 如果filter_metadata已经包含$and, $or等操作符，直接使用
            if any(key.startswith("$") for key in filter_metadata.keys()):
                where_clause = filter_metadata
            else:
                # 转换为 ChromaDB 的 where 格式
                # 如果有多个条件，需要使用 $and 操作符
                conditions = []
                for key, value in filter_metadata.items():
                    # 如果value已经是包含操作符的字典，直接使用
                    if isinstance(value, dict) and any(
                        k.startswith("$") for k in value.keys()
                    ):
                        # 对于日期范围这样的复合操作符，需要特殊处理
                        if len(value) > 1:
                            # 多个操作符需要包装在$and中
                            sub_conditions = []
                            for op, op_value in value.items():
                                sub_conditions.append({key: {op: op_value}})
                            conditions.append({"$and": sub_conditions})
                        else:
                            # 单个操作符
                            conditions.append({key: value})
                    else:
                        # 否则转换为 $eq 操作符
                        conditions.append({key: {"$eq": value}})

                # 根据条件数量构建where子句
                if len(conditions) == 1:
                    where_clause = conditions[0]
                elif len(conditions) > 1:
                    where_clause = {"$and": conditions}

        results = self._collection.query(
            query_texts=[query], n_results=k, where=where_clause
        )

        # 格式化结果
        formatted_results = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append(
                    {
                        "document": doc,
                        "metadata": results.get("metadatas", [[{}]])[0][i],
                        "distance": results.get("distances", [[]])[0][i]
                        if results.get("distances")
                        else None,
                        "id": results.get("ids", [[]])[0][i],
                    }
                )

        return formatted_results

    def search_by_category(
        self, query: str, category: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        按类别搜索

        Args:
            query: 查询文本
            category: 类别（如 "meal", "weight", "exercise"）
            k: 返回数量

        Returns:
            搜索结果列表
        """
        return self.similarity_search(
            query=query, k=k, filter_metadata={"category": category}
        )

    def delete_by_id(self, doc_id: str) -> bool:
        """
        根据ID删除文档

        Args:
            doc_id: 文档ID

        Returns:
            是否删除成功
        """
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def delete_by_metadata(self, metadata: Dict) -> int:
        """
        根据元数据删除文档

        Args:
            metadata: 元数据条件

        Returns:
            删除的文档数量
        """
        # 查找匹配的文档
        results = self.similarity_search(
            query="*",  # 查询所有
            k=100,
            filter_metadata=metadata,
        )

        # 删除匹配的文档
        count = 0
        for result in results:
            if self.delete_by_id(result["id"]):
                count += 1

        return count

    def get_all_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取所有文档

        Args:
            limit: 最大数量

        Returns:
            文档列表
        """
        results = self._collection.get(limit=limit)

        documents = []
        if results.get("documents"):
            for i, doc in enumerate(results["documents"]):
                documents.append(
                    {
                        "id": results["ids"][i],
                        "document": doc,
                        "metadata": results.get("metadatas", [{}])[i],
                    }
                )

        return documents

    def count_documents(self) -> int:
        """
        获取文档数量

        Returns:
            文档数量
        """
        return self._collection.count()

    def clear(self):
        """清空集合"""
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": f"Vector store for {self.collection_name}"},
            )
        except Exception as e:
            print(f"Failed to clear collection: {e}")

    def close(self):
        """关闭连接"""
        pass


# 向量存储管理器（支持多用户）
class VectorStoreManager:
    """
    向量存储管理器

    为每个用户创建独立的向量存储集合

    集合命名规则：user_{user_id}
    """

    _instances: Dict[int, ChromaVectorStore] = {}

    @classmethod
    def get_store(
        cls, user_id: int, persist_dir: str = DEFAULT_PERSIST_DIR
    ) -> ChromaVectorStore:
        """
        获取用户的向量存储实例

        Args:
            user_id: 用户ID
            persist_dir: 存储目录

        Returns:
            ChromaVectorStore 实例
        """
        if user_id not in cls._instances:
            collection_name = f"user_{user_id}"
            cls._instances[user_id] = ChromaVectorStore(
                collection_name=collection_name, persist_dir=persist_dir
            )
        return cls._instances[user_id]

    @classmethod
    def close_store(cls, user_id: int):
        """关闭用户的向量存储"""
        if user_id in cls._instances:
            cls._instances[user_id].close()
            del cls._instances[user_id]

    @classmethod
    def close_all(cls):
        """关闭所有向量存储"""
        for store in cls._instances.values():
            store.close()
        cls._instances.clear()


# 便捷函数
def get_user_vector_store(user_id: int) -> ChromaVectorStore:
    """获取用户的向量存储"""
    return VectorStoreManager.get_store(user_id)


async def add_user_memory(
    user_id: int, content: str, category: str, metadata: Optional[Dict] = None
) -> str:
    """
    便捷函数：添加用户记忆

    Args:
        user_id: 用户ID
        content: 记忆内容
        category: 类别（meal/weight/exercise/sleep 等）
        metadata: 其他元数据

    Returns:
        文档ID
    """
    store = get_user_vector_store(user_id)

    meta = {
        "category": category,
        "created_at": datetime.now().isoformat(),
        **(metadata or {}),
    }

    ids = store.add_documents(documents=[content], metadatas=[meta])

    return ids[0]


def search_user_memory(
    user_id: int, query: str, category: Optional[str] = None, k: int = 5
) -> List[Dict[str, Any]]:
    """
    便捷函数：搜索用户记忆

    Args:
        user_id: 用户ID
        query: 查询文本
        category: 过滤类别
        k: 返回数量

    Returns:
        搜索结果列表
    """
    store = get_user_vector_store(user_id)

    if category:
        return store.search_by_category(query, category, k)
    else:
        return store.similarity_search(query, k)
