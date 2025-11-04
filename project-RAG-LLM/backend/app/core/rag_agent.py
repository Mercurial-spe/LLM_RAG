"""
RAG Agent 服务层
================
职责：
- 构建并缓存 LangChain Retriever（附着到现有 Chroma 集合，仅读取）。
- 注册检索工具并创建 Agent（create_agent）。
- 集成短期记忆（checkpointer）和自动 Summarization。
- 对外暴露标准调用接口：invoke（一次性）、stream_updates（步骤流）、stream_messages（仅模型文本）。

用法：
- 在 API 层调用 `stream_messages(question, thread_id="1")` 直接向前端推流模型文本；
- 或调用 `stream_updates(question, thread_id="1")` 查看 model → tools → model 的步骤进展；
- 或调用 `invoke(question, thread_id="1")` 获取完整回答字符串。

记忆管理：
- 使用 SQLite 数据库持久化对话历史（存储在 data/chat_memory.db）。
- 当 token 数超过阈值时，自动触发 Summarization 压缩历史消息。
- thread_id 用于区分不同会话，默认使用 "1"。
"""

import logging
import os
from typing import Iterator, List, Optional

from langchain_core.embeddings import Embeddings
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from .. import config
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
_checkpointer = None


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


def _get_checkpointer():
    """构建或返回缓存的 Checkpointer（用于短期记忆持久化）。"""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    # 确保目录存在
    db_dir = os.path.dirname(config.CHAT_MEMORY_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    # 尝试使用 SQLite Checkpointer（需要 langgraph-checkpoint-sqlite）
    # 如果不可用，降级到 MemorySaver（内存存储）
    try:
        # 注意：SQLite checkpointer 可能需要额外安装 langgraph-checkpoint-sqlite
        # 或者使用 langgraph.checkpoint.sqlite.SqliteSaver
        # 先尝试从标准包导入
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3
            # 直接使用 sqlite3.connect，不走 from_conn_string 的上下文管理器
            conn = sqlite3.connect(config.CHAT_MEMORY_DB_PATH, check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            # 创建表结构（若不存在）
            _checkpointer.setup()
            logger.info(f"使用 SQLite Checkpointer，数据库路径: {config.CHAT_MEMORY_DB_PATH}")
        except Exception as e:
            # 捕获并打印详细异常，再降级到 MemorySaver
            logger.error(
                "初始化 SqliteSaver 失败，将降级为 MemorySaver。错误: %s: %s",
                type(e).__name__, str(e), exc_info=True
            )
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
            logger.warning(
                "已切换为 MemorySaver（内存存储，重启后丢失）。"
            )
    except Exception as e:
        # 兜底：使用 MemorySaver
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
        logger.warning(f"初始化 Checkpointer 失败: {e}，使用 MemorySaver（内存存储）")
    
    return _checkpointer


def _get_agent():
    """构建或返回缓存的 Agent（集成短期记忆和 Summarization）。"""
    global _agent
    if _agent is not None:
        return _agent

    llm = LLMHandler.get_instance().get_model()
    checkpointer = _get_checkpointer()
    
    # 创建 Summarization Middleware（自动压缩历史）
    summarization_middleware = SummarizationMiddleware(
        model=llm,  # 使用同一个 LLM 进行 summarization
        max_tokens_before_summary=config.MEMORY_MAX_TOKENS_BEFORE_SUMMARY,
        messages_to_keep=config.MEMORY_MESSAGES_TO_KEEP,
    )
    
    system_prompt = (
        "你有一个用于检索上下文的工具 retrieve_context。"
        "请在需要外部知识时调用该工具，并基于返回的内容回答用户问题。"
        "无法从上下文确定答案时请明确说明。\n\n"
        "回答格式要求：\n"
        "1. 使用规范的 Markdown 格式，确保段落之间有空行分隔。\n"
        "2. 列表项前后要有空行，使用 `-` 或 `1.` 开头。\n"
        "3. 代码块使用三个反引号包裹，并标注语言。\n"
        "4. 长段落要适当分段，提高可读性。"
    )
    
    _agent = create_agent(
        llm,
        [retrieve_context],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        middleware=[summarization_middleware],
    )
    logger.info("RAG agent 已创建并缓存（含短期记忆和 Summarization）。")
    return _agent


# ---------------------------- 对外接口 ----------------------------
def invoke(question: str, thread_id: str = "1", timeout_s: Optional[float] = None) -> str:
    """
    一次性调用，返回完整回答文本。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话（默认 "1"）
        timeout_s: 超时时间（暂未使用）
    
    Returns:
        完整回答文本
    """
    agent = _get_agent()
    config_dict = {"configurable": {"thread_id": thread_id}}
    
    # 采用 messages 流，只拼接模型文本块
    parts: List[str] = []
    for token, meta in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="messages",
        config=config_dict,
    ):
        if isinstance(meta, dict) and meta.get("langgraph_node") != "model":
            continue
        for block in getattr(token, "content_blocks", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    parts.append(text)
    return "".join(parts)


def stream_updates(question: str, thread_id: str = "1"):
    """
    步骤级流（model → tools → model）。产出 dict，便于调试与观测。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话（默认 "1"）
    
    Yields:
        步骤更新字典
    """
    agent = _get_agent()
    config_dict = {"configurable": {"thread_id": thread_id}}
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="updates",
        config=config_dict,
    ):
        yield chunk


def stream_messages(question: str, thread_id: str = "1"):
    """
    仅流式输出模型文本块（逐段）。产出 str。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话（默认 "1"）
    
    Yields:
        文本块字符串
    """
    agent = _get_agent()
    config_dict = {"configurable": {"thread_id": thread_id}}
    for token, meta in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="messages",
        config=config_dict,
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


