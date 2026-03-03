"""
Tool Execution Node
===================
职责：根据 Decision 执行工具调用，追加 ToolResult

输入：AgentState（包含 decision）
输出：追加 tool_results

支持的工具：
- rag: RAG 检索工具
- web_search: 网络搜索工具
"""

import logging
import time
from typing import Any, Dict
from ..state import AgentState, ToolResult
from ...tools import execute_rag_tool, execute_web_search_tool

logger = logging.getLogger(__name__)


def tool_exec_node(state: AgentState) -> Dict[str, Any]:
    """
    Tool Execution 节点：执行工具调用

    Args:
        state: 当前 Agent 状态

    Returns:
        包含 tool_results 的字典（用于追加到 state）
    """
    decision = state.get("decision")
    if not decision:
        logger.error("tool_exec: decision 为空，无法执行工具")
        return {"last_error": "decision 为空"}

    tool_name = decision.get("tool_name")
    tool_args = decision.get("tool_args", {})

    if not tool_name:
        logger.error("tool_exec: tool_name 为空")
        return {"last_error": "tool_name 为空"}

    # 从 artifacts 中读取动态参数
    artifacts = state.get("artifacts", {})
    session_id = artifacts.get("session_id", "1")
    top_k = artifacts.get("top_k", 5)

    # 将动态参数注入到 tool_args 中
    tool_args.setdefault("session_id", session_id)
    tool_args.setdefault("top_k", top_k)

    logger.info(f"tool_exec: 执行工具 {tool_name}，参数: {tool_args}")

    # 记录开始时间
    start_time = time.time()

    # 调用工具层
    try:
        if tool_name == "rag":
            result = execute_rag_tool(tool_args)
        elif tool_name == "web_search":
            result = execute_web_search_tool(tool_args)
        else:
            logger.error(f"tool_exec: 未知的工具 {tool_name}")
            result: ToolResult = {
                "ok": False,
                "name": tool_name,
                "data": None,
                "error": f"未知的工具: {tool_name}"
            }
    except Exception as e:
        logger.error(f"tool_exec: 工具执行失败: {e}", exc_info=True)
        result: ToolResult = {
            "ok": False,
            "name": tool_name,
            "data": None,
            "error": str(e)
        }

    # 计算延迟
    latency_ms = int((time.time() - start_time) * 1000)
    result["latency_ms"] = latency_ms

    # 追加到 tool_results
    existing_results = state.get("tool_results", [])
    updated_results = existing_results + [result]

    logger.info(f"tool_exec: 工具 {tool_name} 执行完成，耗时 {latency_ms}ms")

    return {"tool_results": updated_results}
    """
    执行 RAG 工具（直接调用 retriever_service）

    Args:
        args: 工具参数

    Returns:
        ToolResult
    """
    import time
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


def _execute_web_search_tool(args: Dict[str, Any]) -> ToolResult:
    """
    执行 WebSearch 工具（直接调用 web_search_service）

    Args:
        args: 工具参数

    Returns:
        ToolResult
    """
    import time
    from app.services.web_search_service import WebSearchService

    query = args.get("query", "")
    max_results = args.get("max_results", 5)

    logger.info(f"web_search_tool: query={query}, max_results={max_results}")

    # 参数校验
    if not query or not query.strip():
        logger.error("web_search_tool: query 为空")
        return {
            "ok": False,
            "name": "web_search",
            "data": None,
            "error": "查询不能为空"
        }

    # 记录开始时间
    start_time = time.time()

    try:
        # 获取 WebSearchService 实例
        web_search_service = WebSearchService.get_instance()

        # 检查服务是否可用
        if not web_search_service.is_available():
            logger.warning("web_search_tool: WebSearchService 不可用")
            return {
                "ok": False,
                "name": "web_search",
                "data": None,
                "error": "网络搜索服务不可用（可能缺少 Tavily API Key）"
            }

        # 执行搜索
        results = web_search_service.search(query, max_results=max_results)

        # 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)

        # 构建 ToolResult
        if results:
            logger.info(f"web_search_tool: 搜索成功，找到 {len(results)} 个结果，耗时 {latency_ms}ms")
            return {
                "ok": True,
                "name": "web_search",
                "data": {"results": results, "query": query},
                "sources": [
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                        "score": item.get("score")
                    }
                    for item in results
                ],
                "latency_ms": latency_ms
            }
        else:
            logger.info(f"web_search_tool: 搜索完成，但没有找到结果，耗时 {latency_ms}ms")
            return {
                "ok": True,
                "name": "web_search",
                "data": {"results": [], "query": query},
                "sources": [],
                "latency_ms": latency_ms
            }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"web_search_tool: 搜索失败: {e}", exc_info=True)
        return {
            "ok": False,
            "name": "web_search",
            "data": None,
            "error": f"搜索失败: {str(e)}",
            "latency_ms": latency_ms
        }
