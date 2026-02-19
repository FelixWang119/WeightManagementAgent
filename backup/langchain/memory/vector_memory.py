"""
增强版向量存储检索记忆
长期记忆：向量存储 + 摘要生成

注意：由于LangChain 1.x版本变化，这里实现一个简化的向量记忆系统
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from services.vectorstore.chroma_store import ChromaVectorStore
from services.ai_service import AIService
from .typed_buffer import MemoryType, BaseMessage, HumanMessage, AIMessage


class EnhancedVectorStoreRetrieverMemory:
    """
    增强版向量存储检索记忆
    支持摘要生成、元数据过滤、批量操作
    """

    def __init__(
        self,
        user_id: int,
        vector_store: Optional[ChromaVectorStore] = None,
        ai_service: Optional[AIService] = None,
        **kwargs,
    ):
        """
        初始化增强向量记忆

        Args:
            user_id: 用户ID
            vector_store: 向量存储实例
            ai_service: AI服务实例
        """
        self.user_id = user_id
        self.ai_service = ai_service or AIService()

        # 初始化向量存储
        if vector_store is None:
            collection_name = f"user_{user_id}_memory"
            self.vector_store = ChromaVectorStore(collection_name=collection_name)
        else:
            self.vector_store = vector_store

        # 简化实现，不调用父类
        self.memory_key = "long_term_memory"

    async def add_message(
        self,
        message: BaseMessage,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        添加消息到向量存储

        Args:
            message: 消息对象
            memory_type: 记忆类型
            metadata: 附加元数据

        Returns:
            存储的文档ID
        """
        content = message.content
        timestamp = datetime.now().isoformat()

        # 构建元数据
        base_metadata = {
            "user_id": self.user_id,
            "type": memory_type.value,
            "timestamp": timestamp,
            "role": "human" if isinstance(message, HumanMessage) else "ai",
        }

        if metadata:
            base_metadata.update(metadata)

        # 如果是对话记录，生成摘要
        if memory_type == MemoryType.CONVERSATION:
            summary = await self._generate_summary(content)
            base_metadata["summary"] = summary
            # 存储摘要而不是原始内容
            content_to_store = summary
        else:
            # 打卡记录存储原始内容
            content_to_store = content

        # 添加到向量存储
        doc_id = f"{memory_type.value}_{timestamp}"
        self.vector_store.add_documents(
            documents=[content_to_store], metadatas=[base_metadata], ids=[doc_id]
        )

        return doc_id

    async def _generate_summary(self, content: str) -> str:
        """
        生成对话摘要

        Args:
            content: 原始对话内容

        Returns:
            摘要文本
        """
        try:
            # 使用AI服务生成摘要
            prompt = f"请将以下对话内容总结为简洁的摘要（不超过50字）：\n\n{content}"
            response = await self.ai_service.generate_text(prompt, max_tokens=100)
            return response.strip()
        except Exception as e:
            # 如果生成摘要失败，返回截断的原始内容
            return content[:100] + "..." if len(content) > 100 else content

    def search_memories(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            memory_type: 记忆类型过滤
            limit: 返回结果数量
            date_range: 日期范围过滤 (start_date, end_date)

        Returns:
            记忆结果列表
        """
        # 构建过滤条件
        filter_metadata = {}
        if memory_type:
            filter_metadata["type"] = memory_type.value

        if date_range:
            start_date, end_date = date_range
            filter_metadata["timestamp"] = {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat(),
            }

        # 执行相似性搜索
        results = self.vector_store.similarity_search(
            query=query,
            k=limit,
            filter_metadata=filter_metadata if filter_metadata else None,
        )

        # 格式化结果
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "id": result.get("id"),
                    "content": result.get("document"),
                    "metadata": result.get("metadata", {}),
                    "distance": result.get("distance", 0.0),
                }
            )

        return formatted_results

    def get_relevant_memories(
        self, query: str, memory_type: Optional[MemoryType] = None
    ) -> List[str]:
        """
        获取相关记忆（LangChain接口兼容）

        Args:
            query: 查询文本
            memory_type: 记忆类型过滤

        Returns:
            相关记忆内容列表
        """
        memories = self.search_memories(query, memory_type=memory_type, limit=5)
        return [mem["content"] for mem in memories]

    def get_checkin_history(
        self, checkin_type: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取打卡历史

        Args:
            checkin_type: 打卡类型（weight/meal/exercise/water/sleep）
            limit: 返回数量

        Returns:
            打卡记录列表
        """
        filter_metadata = {"type": MemoryType.CHECKIN.value}
        if checkin_type:
            filter_metadata["checkin_type"] = checkin_type

        # 按时间倒序获取最近的记录
        query = "打卡记录"
        results = self.vector_store.similarity_search(
            query=query, k=limit, filter_metadata=filter_metadata
        )

        # 按时间排序（最新的在前）
        results.sort(
            key=lambda x: x.get("metadata", {}).get("timestamp", ""), reverse=True
        )

        formatted_results = []
        for result in results:
            metadata = result.get("metadata", {})
            formatted_results.append(
                {
                    "id": result.get("id"),
                    "content": result.get("document"),
                    "type": metadata.get("checkin_type", "unknown"),
                    "timestamp": metadata.get("timestamp"),
                    "metadata": metadata,
                }
            )

        return formatted_results

    def get_conversation_summaries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取对话摘要

        Args:
            limit: 返回数量

        Returns:
            对话摘要列表
        """
        filter_metadata = {"type": MemoryType.CONVERSATION.value}

        query = "对话摘要"
        results = self.vector_store.similarity_search(
            query=query, k=limit, filter_metadata=filter_metadata
        )

        # 按时间排序（最新的在前）
        results.sort(
            key=lambda x: x.get("metadata", {}).get("timestamp", ""), reverse=True
        )

        formatted_results = []
        for result in results:
            metadata = result.get("metadata", {})
            formatted_results.append(
                {
                    "id": result.get("id"),
                    "summary": result.get("document"),
                    "original_length": metadata.get("original_length", 0),
                    "timestamp": metadata.get("timestamp"),
                    "metadata": metadata,
                }
            )

        return formatted_results

    def clear_memories(self, memory_type: Optional[MemoryType] = None) -> int:
        """
        清理记忆

        Args:
            memory_type: 记忆类型，如果为None则清理所有

        Returns:
            清理的记录数量
        """
        # 注意：ChromaDB的删除操作需要具体实现
        # 这里返回0表示功能待实现
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取向量存储统计信息

        Returns:
            统计信息字典
        """
        # 获取集合信息
        collection_info = self.vector_store.collection.get()

        # 按类型统计
        type_counts = {}
        for metadata in collection_info.get("metadatas", []):
            mem_type = metadata.get("type", "unknown")
            type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

        return {
            "total_documents": len(collection_info.get("ids", [])),
            "type_counts": type_counts,
            "user_id": self.user_id,
            "collection_name": self.vector_store.collection_name,
        }
