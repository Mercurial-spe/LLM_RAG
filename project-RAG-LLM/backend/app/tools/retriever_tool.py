# backend/app/tools/retriever_tool.py

"""
RAG 检索工具
使用 LangChain 的 create_retriever_tool 封装 Retriever
"""

import logging
from typing import List
from langchain.tools.retriever import create_retriever_tool
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def build_retriever_tool(retriever: BaseRetriever) -> BaseTool:
    """
    构建 RAG 检索工具

    Args:
        retriever: LangChain Retriever 实例

    Returns:
        BaseTool: 可用于 Agent 的检索工具
    """
    return create_retriever_tool(
        retriever=retriever,
        name="search_knowledge_base",
        description=(
            "从课程知识库检索相关笔记和文档。"
            "优先用于课程内容相关问题。"
            "返回系统文档和用户上传的文档。"
        ),
    )
