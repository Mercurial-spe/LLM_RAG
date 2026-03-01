# backend/app/tools/web_search_tool.py

"""
Web 搜索工具
使用 Tavily API 进行互联网搜索
"""

import logging
from typing import List
from langchain_core.tools import tool
from langchain_core.documents import Document
from ..services.web_search_service import WebSearchService
from .. import config

logger = logging.getLogger(__name__)


def build_web_search_tool(service: WebSearchService):
    """
    构建 Web 搜索工具

    Args:
        service: WebSearchService 实例

    Returns:
        BaseTool: 可用于 Agent 的 Web 搜索工具
    """
    @tool("web_search", response_format="content_and_artifact")
    def web_search(query: str):
        """
        搜索互联网获取最新信息。
        用于知识库未覆盖或需要实时数据的问题。
        返回搜索结果的标题、URL 和摘要。
        """
        if not service.is_available():
            logger.warning("Web 搜索服务不可用(缺少 Tavily API Key)")
            return "Web 搜索服务当前不可用", []

        try:
            results = service.search(query, max_results=config.WEB_SEARCH_RESULT_LIMIT)

            if not results:
                return "未找到相关的网络搜索结果", []

            # 转换为 Document 对象
            docs = []
            for item in results:
                snippet = item.get("snippet") or ""
                if snippet:
                    docs.append(
                        Document(
                            page_content=snippet,
                            metadata={
                                "source": item.get("url") or item.get("source") or "web",
                                "title": item.get("title") or item.get("url") or "Web Result",
                                "source_type": "web",
                            },
                        )
                    )

            # 格式化文本输出
            formatted = "\n\n".join(
                f"标题: {r['title']}\n来源: {r['url']}\n内容: {r['snippet']}"
                for r in results
            )

            logger.info(f"Web 搜索成功: 查询='{query}', 结果数={len(results)}")
            return formatted, docs

        except Exception as e:
            logger.error(f"Web 搜索失败: {e}", exc_info=True)
            return f"Web 搜索出错: {str(e)}", []

    return web_search
