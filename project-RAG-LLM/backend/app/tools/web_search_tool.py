"""
Web Search Tool
===============
网络搜索工具接口

职责：
- 参数校验
- 调用 web_search_service 执行搜索
- 返回统一的 ToolResult
"""

import logging
import time
from typing import Any, Dict
from ..agents.state import ToolResult

logger = logging.getLogger(__name__)


def execute_web_search_tool(args: Dict[str, Any]) -> ToolResult:
    """
    执行 WebSearch 工具（调用 web_search_service）

    Args:
        args: 工具参数
            - query: 查询文本
            - max_results: 最大结果数

    Returns:
        ToolResult
    """
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
