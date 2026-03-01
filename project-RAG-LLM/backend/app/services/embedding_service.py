# backend/app/services/embedding_service.py

"""
文本嵌入服务
使用 LangChain OpenAIEmbeddings 封装阿里云百炼 text-embedding-v4 API
"""

import logging
from langchain_openai import OpenAIEmbeddings
from .. import config

logger = logging.getLogger(__name__)

# 全局单例实例
_embeddings: OpenAIEmbeddings | None = None


def get_embeddings() -> OpenAIEmbeddings:
    """
    获取全局共享的 Embeddings 实例(懒加载单例)

    Returns:
        OpenAIEmbeddings 实例,已配置阿里云百炼 API
    """
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME,
            openai_api_key=config.EMBEDDING_API_KEY,
            openai_api_base=config.EMBEDDING_API_BASE_URL,
            dimensions=config.EMBEDDING_DIMENSION,
            chunk_size=config.EMBEDDING_BATCH_SIZE,
        )
        logger.info(
            f"嵌入服务初始化成功 - 模型: {config.EMBEDDING_MODEL_NAME}, "
            f"维度: {config.EMBEDDING_DIMENSION}"
        )
    return _embeddings
