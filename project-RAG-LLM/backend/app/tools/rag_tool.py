"""
RAG Tool
========
RAG 检索工具接口

职责：
- 参数校验
- 调用 retriever_service 执行检索
- 返回统一的 ToolResult
"""

import logging
import time
from typing import Any, Dict
from ..agents.state import ToolResult

logger = logging.getLogger(__name__)


def execute_rag_tool(args: Dict[str, Any]) -> ToolResult:
    """
    执行 RAG 工具（调用 retriever_service）

    Args:
        args: 工具参数
            - query: 查询文本
            - session_id: 会话 ID
            - top_k: 返回文档数量

    Returns:
        ToolResult
    """
    from app.services.retriever_service import build_retriever

    query = args.get("query", "")
    session_id = args.get("session_id", "1")
    top_k = args.get("top_k", 5)

    logger.info(f"rag_tool: query={query}, session_id={session_id}, top_k={top_k}")

    # 参数校验
    if not query or not query.strip():
        logger.error("rag_tool: query 为空")
        return {
            "ok": False,
            "name": "rag",
            "data": None,
            "error": "查询不能为空"
        }

    # 记录开始时间
    start_time = time.time()

    try:
        # 构建 Retriever（不传 llm，使用基础检索）
        retriever = build_retriever(
            session_id=session_id,
            top_k=top_k,
            llm=None  # 暂时不使用 MultiQueryRetriever
        )

        # 执行检索
        documents = retriever.invoke(query)

        # 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)

        # 构建 ToolResult
        if documents:
            logger.info(f"rag_tool: 检索成功，找到 {len(documents)} 个文档，耗时 {latency_ms}ms")

            # 提取文档信息
            doc_list = []
            sources = []

            for doc in documents:
                content = doc.page_content
                metadata = doc.metadata

                doc_list.append({
                    "content": content,
                    "metadata": metadata
                })

                sources.append({
                    "source": metadata.get("source", "unknown"),
                    "session_id": metadata.get("session_id", "unknown"),
                    "snippet": content[:200] if len(content) > 200 else content,
                    "title": metadata.get("title") or metadata.get("source", "未知文档")
                })

            return {
                "ok": True,
                "name": "rag",
                "data": {
                    "documents": doc_list,
                    "query": query,
                    "count": len(documents)
                },
                "sources": sources,
                "latency_ms": latency_ms
            }
        else:
            logger.info(f"rag_tool: 检索完成，但没有找到相关文档，耗时 {latency_ms}ms")
            return {
                "ok": True,
                "name": "rag",
                "data": {
                    "documents": [],
                    "query": query,
                    "count": 0
                },
                "sources": [],
                "latency_ms": latency_ms
            }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"rag_tool: 检索失败: {e}", exc_info=True)
        return {
            "ok": False,
            "name": "rag",
            "data": None,
            "error": f"检索失败: {str(e)}",
            "latency_ms": latency_ms
        }
