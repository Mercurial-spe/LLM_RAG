import logging
from typing import Any, Dict, List, Optional

import requests

from .. import config

logger = logging.getLogger(__name__)


class WebSearchService:
    """封装 Tavily Web Search API 的简单客户端。"""

    _instance: Optional["WebSearchService"] = None

    def __init__(self) -> None:
        # 开关由 config 决定，env 只存储 KEY
        self._enabled = bool(config.TAVILY_API_KEY) and config.WEB_SEARCH_ENABLED
        self._api_key = config.TAVILY_API_KEY
        self._base_url = config.TAVILY_API_BASE_URL
        self._max_results = max(1, config.TAVILY_MAX_RESULTS)
        self._timeout = config.TAVILY_TIMEOUT
        self._search_depth = config.TAVILY_SEARCH_DEPTH
        logger.info(
            "WebSearchService init: enabled=%s, key_present=%s, base_url=%s, depth=%s, max_results=%s",
            self._enabled,
            bool(self._api_key),
            self._base_url,
            self._search_depth,
            self._max_results,
        )

    @classmethod
    def get_instance(cls) -> "WebSearchService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        return self._enabled

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """执行 Tavily 搜索，返回简化后的结果列表。"""
        if not self._enabled:
            logger.info("联网搜索被跳过：未启用或缺少 Tavily API Key")
            return []

        limit = max_results or self._max_results
        limit = max(1, min(limit, self._max_results))
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": self._search_depth,
            "max_results": limit,
        }
        logger.info("Tavily request: query=%r depth=%s max_results=%s", query, self._search_depth, limit)

        try:
            response = requests.post(
                self._base_url,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json() or {}
        except Exception as exc:  # pragma: no cover - 外部服务调用失败只记录日志
            logger.error("Tavily 搜索失败: %s", exc, exc_info=True)
            return []

        results = data.get("results") or []
        logger.info("Tavily response: status=%s results=%s", getattr(response, "status_code", "?"), len(results))
        simplified: List[Dict[str, Any]] = []
        for item in results[:limit]:
            simplified.append(
                {
                    "title": item.get("title") or item.get("url") or "Web Result",
                    "url": item.get("url"),
                    "snippet": item.get("content") or item.get("snippet") or "",
                    "score": item.get("score"),
                    "source": item.get("source"),
                }
            )
        return simplified
