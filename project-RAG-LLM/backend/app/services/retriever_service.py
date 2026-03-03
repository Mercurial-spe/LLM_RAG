# backend/app/services/retriever_service.py

"""
Retriever 服务
负责创建和配置 LangChain Retriever 实例
"""

import logging
from typing import Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.retrievers import MultiQueryRetriever

from .vector_store_repository import VectorStoreRepository
from .embedding_service import get_embeddings
from .. import config

logger = logging.getLogger(__name__)


def build_retriever(
    session_id: str = "1",
    top_k: Optional[int] = None,
    llm: Optional[BaseChatModel] = None,
) -> BaseRetriever:
    """
    构建 Retriever 实例

    Args:
        session_id: 当前会话ID,默认 "1"
        top_k: 检索文档数量,若为 None 则使用配置文件默认值
        llm: 可选的 LLM 实例,用于 MultiQueryRetriever

    Returns:
        BaseRetriever: 配置好的 Retriever 实例

    检索范围:
        - session_id = "system" 的文档(全局系统文档)
        - session_id = 当前会话ID 的文档(用户上传的文档)

    MultiQueryRetriever:
        - 如果 config.USE_MULTI_QUERY_RETRIEVER=True 且提供了 llm,则启用
        - 会生成多个查询变体以提高召回率,但会增加延迟和费用
    """
    # 使用传入的 top_k,若未指定则使用配置文件默认值
    if top_k is None:
        top_k = config.RAG_TOP_K

    vector_repo = VectorStoreRepository()
    embeddings = get_embeddings()

    # 构建过滤条件:检索 system 文档 + 当前会话文档
    search_kwargs = {
        "k": top_k,
        "filter": {
            "$or": [
                {"session_id": "system"},      # 系统全局文档
                {"session_id": session_id}     # 当前会话文档
            ]
        }
    }

    # 创建基础 retriever
    base_retriever = vector_repo.as_langchain_retriever(
        embedding_instance=embeddings,
        search_type="similarity",
        search_kwargs=search_kwargs,
    )

    # 如果启用 MultiQueryRetriever 且提供了 LLM
    if config.USE_MULTI_QUERY_RETRIEVER and llm is not None:
        logger.info(
            f"🔨 创建 MultiQueryRetriever,session_id={session_id}, top_k={top_k}"
        )
        return MultiQueryRetriever.from_llm(
            retriever=base_retriever,
            llm=llm,
            include_original=True  # 包含原始查询
        )

    logger.info(f"🔨 创建基础 Retriever,session_id={session_id}, top_k={top_k}")
    return base_retriever
