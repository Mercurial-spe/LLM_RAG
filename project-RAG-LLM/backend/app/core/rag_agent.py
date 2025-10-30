"""
RAG Agent 服务层
================
职责：
- 构建并缓存 LangChain Retriever（附着到现有 Chroma 集合，仅读取）。
- 注册检索工具并创建 Agent（create_agent）。
- 对外暴露标准调用接口：invoke（一次性）、stream_updates（步骤流）、stream_messages（仅模型文本）。

用法：
- 在 API 层调用 `stream_messages(question)` 直接向前端推流模型文本；
- 或调用 `stream_updates(question)` 查看 model → tools → model 的步骤进展；
- 或调用 `invoke(question)` 获取完整回答字符串。
"""

import logging
from typing import Iterator, List, Optional

from langchain_core.embeddings import Embeddings
from langchain.tools import tool
from langchain.agents import create_agent

from ..services.embedding_service import EmbeddingService
from ..services.vector_store_repository import VectorStoreRepository
from .llm_handler import LLMHandler


logger = logging.getLogger(__name__)


# ---------------------------- Embeddings 适配器 ----------------------------
class LCEmbeddingAdapter(Embeddings):
    """将项目内的 EmbeddingService 适配为 LangChain Embeddings 接口。"""

    def __init__(self, service: EmbeddingService):
        self._service = service

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._service.embed_texts(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._service.embed_text(text)


# ---------------------------- 模块级缓存 ----------------------------
_retriever = None
_agent = None


def _get_retriever():
    """构建或返回缓存的 LangChain Retriever。"""
    global _retriever
    if _retriever is not None:
        return _retriever

    embedding_service = EmbeddingService.get_instance()
    vector_repo = VectorStoreRepository()
    lc_embeddings = LCEmbeddingAdapter(embedding_service)

    # 仅附着到本地 Chroma 集合，负责“读”
    _retriever = vector_repo.as_langchain_retriever(
        embedding_instance=lc_embeddings,
        search_type="similarity",
        search_kwargs={"k": 5},
    )
    logger.info("RAG retriever 已创建并缓存。")
    return _retriever


@tool("retrieve_context", response_format="content_and_artifact")
def retrieve_context(query: str):
    """检索与问题相关的上下文内容。返回拼接文本以及原始文档列表。"""
    retriever = _get_retriever()
    docs = retriever.invoke(query)
    serialized = "\n\n".join(
        (
            f"Source: {d.metadata.get('source', '<unknown>')}\nContent: {d.page_content}"
            for d in docs
        )
    )
    return serialized, docs


def _get_agent():
    """构建或返回缓存的 Agent。"""
    global _agent
    if _agent is not None:
        return _agent

    llm = LLMHandler.get_instance().get_model()
    system_prompt = (
        "你有一个用于检索上下文的工具 retrieve_context。"
        "请在需要外部知识时调用该工具，并基于返回的内容回答用户问题。"
        "无法从上下文确定答案时请明确说明。"
    )
    _agent = create_agent(llm, [retrieve_context], system_prompt=system_prompt)
    logger.info("RAG agent 已创建并缓存。")
    return _agent


# ---------------------------- 对外接口 ----------------------------
def invoke(question: str, timeout_s: Optional[float] = None) -> str:
    """一次性调用，返回完整回答文本。"""
    agent = _get_agent()
    # 采用 messages 流，只拼接模型文本块
    parts: List[str] = []
    for token, meta in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="messages",
    ):
        if isinstance(meta, dict) and meta.get("langgraph_node") != "model":
            continue
        for block in getattr(token, "content_blocks", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    parts.append(text)
    return "".join(parts)


def stream_updates(question: str):
    """步骤级流（model → tools → model）。产出 dict，便于调试与观测。"""
    agent = _get_agent()
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="updates",
    ):
        yield chunk


def stream_messages(question: str):
    """仅流式输出模型文本块（逐段）。产出 str。"""
    agent = _get_agent()
    for token, meta in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="messages",
    ):
        if isinstance(meta, dict) and meta.get("langgraph_node") != "model":
            continue
        blocks = getattr(token, "content_blocks", None)
        if not blocks:
            continue
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    yield text


