# -*- coding: utf-8 -*-
"""向量仓库 (Repository / DAL) - 重构版

职责（仅数据访问层，原子操作）：
- 封装与 ChromaDB 的底层交互
- 提供原子性的“存/取/删/查”接口（一次只做一件事）
- 只处理向量、文档、元数据；不负责生成向量、不负责编排业务流程

设计原则：
- 单一职责：仅数据库读写
- 低耦合：不依赖任何业务服务（如 DocumentIngestService 或 EmbeddingService）
- 高内聚：所有 ChromaDB 操作聚合在此
- 原子性：每个方法完成单一明确的数据库操作

[关键架构变更]
此 Repository 被设计为由更高层的 "IndexerService" 和 "SyncService" 调用。
- IndexerService: 负责调用 IngestService, EmbeddingService, 然后调用本仓库的 upsert_batch。
- SyncService: 负责调用本仓库的 get_indexed_file_state 和 delete_by_source 来实现增量同步。
"""

import logging
import os
import math
from .. import config
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection

# [新增导入] 为 RAG 链查询提供 LangChain "便利" 包装器
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever


logger = logging.getLogger(__name__)


class VectorStoreRepository:
    """ChromaDB 向量库的纯仓库（Repository）

    这是一个“仓库管理员”，只执行原子性的数据库操作。
    """

    def __init__(
        self, persist_path: Optional[str] = None, collection_name: Optional[str] = None
    ):
        """初始化向量仓库

        Args:
                persist_path: 持久化路径，默认使用配置文件中的路径
                collection_name: 集合名称，默认使用配置文件中的名称
        """
        self.persist_path = persist_path or config.VECTOR_STORE_PATH
        self.collection_name = collection_name or config.VECTOR_COLLECTION_NAME

        os.makedirs(self.persist_path, exist_ok=True)

        # 初始化 ChromaDB 客户端和集合
        # [说明] 使用 chromadb 原生客户端，而不是 LangChain 包装器，
        # 以便完全控制增量更新所需的原子操作 (upsert, delete, get)。
        self._client = chromadb.PersistentClient(path=self.persist_path)
        self._collection: Collection = self._client.get_or_create_collection(
            name=self.collection_name
        )

        logger.info(
            "向量仓库初始化成功 - path: %s, collection: %s",
            self.persist_path,
            self.collection_name,
        )

    @property
    def collection(self) -> Collection:
        """获取当前集合对象 (供内部或高级用法使用)"""
        return self._collection

    # -----------------------------------------------------------------
    # 核心 CUD (Create, Update, Delete) 方法
    # -----------------------------------------------------------------

    def upsert_batch(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """
        [重大变更] 原子操作：批量 更新或插入 (Upsert)。


        DocumentIngestService (创建 id, metadata, content) 和
        IndexerService (创建 embedding) 完成。

        Args:
                ids: 确定性 ID 列表 (来自 IngestService)
                documents: 文本内容列表 (来自 IngestService)
                embeddings: 向量列表 (来自 EmbeddingService)
                metadatas: 元数据字典列表 (来自 IngestService)
        """
        if not ids:
            logger.warning("upsert_batch 调用时未提供任何 ID，跳过操作。")
            return

        try:
            # ChromaDB 的 upsert 利用 ID 自动处理“更新”或“插入”
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info(
                f"成功 Upsert {len(ids)} 个文档块到集合 '{self.collection_name}'"
            )

        except Exception as e:
            logger.error(f"批量 Upsert 失败: {e}")
            raise

    def delete_by_source(self, source: str) -> int:
        """
        [关键方法] 原子操作：根据 'source' (文件路径) 删除所有关联的 chunks。

        这是增量同步 "修改" 和 "删除" 逻辑的必需方法。

        Args:
                source: 文件的绝对路径 (存储在 metadata['source'])

        Returns:
                被删除的 chunk 数量
        """
        try:
            # 1. [安全操作] 先根据 'where' 过滤器找出所有要删除的 chunk IDs
            # 只 include=[] 因为只需要 'ids'
            ids_to_delete = self._collection.get(
                where={"source": source}, include=[]
            ).get("ids", [])

            if not ids_to_delete:
                logger.info(f"未在向量库中找到源文件 {source} 的记录，无需删除。")
                return 0

            # 2. [原子操作] 根据 ID 列表精确删除
            self._collection.delete(ids=ids_to_delete)

            logger.info(f"已删除源文件 {source} 的 {len(ids_to_delete)} 个文档块。")
            return len(ids_to_delete)

        except Exception as e:
            logger.error(f"删除文档失败 {source}: {e}")
            raise

    def delete_by_ids(self, ids: List[str]) -> int:
        """
         原子操作：根据ID列表删除文档块。

        Args:
                ids: 文档块ID列表

        Returns:
                删除的文档块数量
        """
        if not ids:
            logger.warning("delete_documents_by_ids 调用时未提供任何 ID")
            return 0

        try:
            self._collection.delete(ids=ids)
            logger.info(f"已删除 {len(ids)} 个文档块")
            return len(ids)
        except Exception as e:
            logger.error(f"删除文档块失败: {e}")
            raise

    # -----------------------------------------------------------------
    # 核心 R (Read) 方法
    # -----------------------------------------------------------------

    # 在 VectorStoreRepository 类中
    def get_documents_by_source(self, source: str) -> List[Dict[str, Any]]:
        """根据源文件路径获取其所有文档块。"""
        try:
            results = self._collection.get(
                where={"source": source}, include=["metadatas", "documents"]
            )
            # ... (格式化并返回结果)
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            formatted_results = []
            for doc, metadata in zip(documents, metadatas):
                formatted_results.append({"content": doc, "metadata": metadata})
            return formatted_results
        except Exception as e:
            logger.error(f"根据源文件 {source} 获取文档块失败: {e}")
            raise

    def get_indexed_file_state(self) -> Dict[str, Dict[str, Any]]:
        """
        [ 关键方法] 原子操作：读取数据库中所有文件的 "状态 Map"。

        此方法是增量同步 "状态对比" 逻辑的必需方法。

        它查询数据库并返回 "db_state" 字典:
        {
                "文件路径": {"mtime": 123, "size": 456},
                ...
        }

        Returns:
                "db_state" 字典。
        """
        logger.info(f"正在从集合 '{self.collection_name}' 查询文件状态...")
        try:
            # 1. 只获取所有元数据 (include=["metadatas"])
            # 注意: .get() 会拉取所有数据，对于超大集合可能需要优化
            all_data = self._collection.get(include=["metadatas"])
            all_metadatas = all_data.get("metadatas", [])
            db_state = {}
            if not all_metadatas:
                logger.info("集合为空，未找到任何文件状态。")
                return db_state

            # 2. 遍历并去重，构建状态 Map
            # (使用字典赋值来自动处理重复的 chunk 元数据)
            for meta in all_metadatas:
                source = meta.get("source")
                mtime = meta.get("file_mtime")
                size = meta.get("file_size")

                # 确保元数据完整，才将其视为有效状态
                if source and mtime is not None and size is not None:
                    db_state[source] = {"mtime": mtime, "size": size}

            logger.info(f"查询到 {len(db_state)} 个唯一文件的状态。")
            return db_state

        except Exception as e:
            logger.error(f"获取集合文件状态失败: {e}")
            raise

    def query_similar(
        self,
        query_vector: List[float],
        top_k: int = 5,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
         原子操作：基于向量的相似度检索。
        这是 RAG 链查询的核心。

        Args:
                query_vector: 查询向量(必须是已计算好的浮点数列表)
                top_k: 返回的最相似块数量
                where_filter: 元数据过滤条件(可选)
                        例如: {'source_type': '.pdf'} 只在特定类型文件中搜索

        Returns:
                相似文档块列表,每个元素包含:
                {
                        'content': str,
                        'metadata': { ...原有元数据... }
                        'similarity': float  (Chroma 默认返回)
                }
        """
        if not query_vector:
            raise ValueError("query_vector 不能为空")
        if top_k <= 0:
            raise ValueError("top_k 必须是非负数")

        try:
            #  明确指定 include 列表
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where_filter,
                include=["metadatas", "documents", "distances"],
            )

            # --- 解析结果
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            if not documents:
                logger.info("未检索到相关文档块")
                return []

            formatted_results: List[Dict[str, Any]] = []

            for doc, metadata, distance in zip(documents, metadatas, distances):

                # Chroma 返回的距离是越小越相似，转换为相似度分数 (0-1)
                similarity = math.exp(-distance)

                formatted_results.append(
                    {"content": doc, "metadata": metadata, "similarity": similarity}
                )

            logger.info(f"检索完成 - 返回 {len(formatted_results)}/{top_k} 个结果")
            return formatted_results

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            raise

    # -----------------------------------------------------------------
    # 辅助与便利方法
    # -----------------------------------------------------------------

    def as_langchain_retriever(
        self,
        embedding_instance: Embeddings,
        search_type: str = "similarity",
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> BaseRetriever:
        """
        [新增 - 便利方法]
        将此 Repository 包装为 LangChain Retriever 供 RAG 链使用。

        这是“桥梁”，它允许 RAG 链 (读操作)
        方便地使用 LangChain，而索引服务 (写操作)
        继续使用健壮的原生 API。

        Args:
                embedding_instance: 一个实现了 LangChain Embeddings 接口的实例
                search_type: 检索类型 (例如 "similarity", "mmr")
                search_kwargs: 传递给 as_retriever 的参数 (例如 {"k": 5})

        Returns:
                一个 LangChain BaseRetriever 实例
        """
        if search_kwargs is None:
            search_kwargs = {"k": config.RAG_TOP_K}

        try:
            # LangChain 的 Chroma 包装器 *可以* 附加到现有的集合
            # 这是“方便”和“健壮”的完美结合点
            langchain_chroma_store = Chroma(
                client=self._client,
                collection_name=self.collection_name,
                embedding_function=embedding_instance,
            )

            return langchain_chroma_store.as_retriever(
                search_type=search_type, search_kwargs=search_kwargs
            )
        except Exception as e:
            logger.error(f"创建 LangChain Retriever 失败: {e}")
            raise
