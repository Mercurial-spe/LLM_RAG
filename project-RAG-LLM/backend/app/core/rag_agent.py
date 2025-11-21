"""
RAG Agent 服务层（重构版）
==========================
职责：
- 按需创建 LangChain Retriever 和 Agent（不再使用缓存）。
- 支持动态参数配置（temperature, top_k, messages_to_keep等）。
- 集成短期记忆（checkpointer）和自动 Summarization。
- 对外暴露标准调用接口：invoke（一次性）、stream_updates（步骤流）、stream_messages（仅模型文本）。

记忆管理：
- 使用 SQLite 数据库持久化对话历史（存储在 data/chat_memory.db）。
- 当 token 数超过阈值时，自动触发 Summarization 压缩历史消息。
- thread_id 用于区分不同会话，默认使用 "1"。

重构改进：
- 移除了 _retriever_cache 和 _agent_cache，解除过度耦合。
- Agent 参数可动态传递，不再被静态配置锁定。
- 每次请求按需创建 Agent，支持不同的 LLM 参数。
"""

import logging
import os
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.agents.middleware.model_fallback import ModelFallbackMiddleware
from .. import config
from ..services.embedding_service import EmbeddingService
from ..services.web_search_service import WebSearchService
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
# 只保留 Checkpointer 缓存（真正昂贵且共享的资源）
_checkpointer = None


def _create_retriever_with_filter(session_id: str = "1", top_k: int = None ):
    """
    构建一个带 session_id 过滤和动态 K 值的 Retriever（按需创建，不再缓存）。
    
    Args:
        session_id: 当前会话ID，默认 "1"
        top_k: 检索文档数量，若为 None 则使用配置文件默认值
        
    检索范围：
        - session_id = "system" 的文档（全局系统文档）
        - session_id = 当前会话ID 的文档（用户上传的文档）
    """
    # 使用传入的 top_k，若未指定则使用配置文件默认值
    if top_k is None:
        top_k = config.RAG_TOP_K
    
    embedding_service = EmbeddingService.get_instance()
    vector_repo = VectorStoreRepository()
    lc_embeddings = LCEmbeddingAdapter(embedding_service)
    
    # 构建过滤条件：检索 system 文档 + 当前会话文档
    search_kwargs = {
        "k": top_k,
        "filter": {
            "$or": [
                {"session_id": "system"},      # 系统全局文档
                {"session_id": session_id}     # 当前会话文档
            ]
        }
    }
    
    logger.info(f"🔨 创建新的 retriever，session_id={session_id}, top_k={top_k}")
    retriever = vector_repo.as_langchain_retriever(
        embedding_instance=lc_embeddings,
        search_type="similarity",
        search_kwargs=search_kwargs,
    )
    
    return retriever


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
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3
            conn = sqlite3.connect(config.CHAT_MEMORY_DB_PATH, check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            _checkpointer.setup()
            logger.info(f"使用 SQLite Checkpointer，数据库路径: {config.CHAT_MEMORY_DB_PATH}")
        except Exception as e:
            logger.error(
                "初始化 SqliteSaver 失败，将降级为 MemorySaver。错误: %s: %s",
                type(e).__name__, str(e), exc_info=True
            )
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
            logger.warning("已切换为 MemorySaver（内存存储，重启后丢失）。")
    except Exception as e:
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
        logger.warning(f"初始化 Checkpointer 失败: {e}，使用 MemorySaver（内存存储）")
    
    return _checkpointer


def _create_dynamic_agent(
    session_id: str,
    temperature: float = None,
    top_k: int = None,
    messages_to_keep: int = None,
    max_tokens: int = None,
    use_web_search: bool = False,
    llm_model: Optional[str] = None,
):
    """
    根据传入的动态参数，按需创建一个新的 Agent 实例（不再缓存）。
    
    Args:
        session_id: 会话ID，用于文档检索过滤
        temperature: LLM 温度参数，若为 None 则使用配置文件默认值
        top_k: RAG 检索的 K 值，若为 None 则使用配置文件默认值
        messages_to_keep: 记忆压缩后保留的消息数，若为 None 则使用配置文件默认值
        max_tokens: 最大生成token数，若为 None 则使用配置文件默认值
    
    Returns:
        配置好的 Agent 实例
    """
    # --- 1. 处理动态参数，设置默认值 ---
    
    # LLM 参数
    effective_temperature = temperature if temperature is not None else getattr(config, 'RAG_TEMPERATURE', 0.2)
    
    # Retriever 参数
    effective_top_k = top_k if top_k is not None else config.RAG_TOP_K
    
    #Max Tokens 参数
    effective_max_tokens = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS
    
    # Memory (Summarization) 参数
    effective_messages_to_keep = messages_to_keep if messages_to_keep is not None else config.MEMORY_MESSAGES_TO_KEEP
    
    # 【修正】摘要阈值 *必须* 始终来自 config，它不是一个动态参数
    summarization_threshold = config.MEMORY_MAX_TOKENS_BEFORE_SUMMARY
    
    # --- 2. 获取基础 LLM 并绑定动态参数 ---
    resolved_llm_model = config.resolve_llm_model(llm_model)
    llm_handler = LLMHandler.get_instance()
    base_llm = llm_handler.get_model(model_name=resolved_llm_model)
    
    # 【修正1】收集所有要绑定的 LLM 参数
    llm_params_to_bind = {
        "temperature": effective_temperature,
        "max_tokens": effective_max_tokens
    }

    llm = base_llm.bind(**llm_params_to_bind)
    # Build fallback model list so LangChain middleware can switch on errors
    fallback_models = []
    if len(config.LLM_SUPPORTED_MODELS) > 1:
        for candidate_model in config.LLM_SUPPORTED_MODELS:
            if candidate_model == resolved_llm_model:
                continue
            try:
                fallback_base = llm_handler.get_model(model_name=candidate_model)
                fallback_models.append(fallback_base.bind(**llm_params_to_bind))
            except Exception as exc:
                logger.warning("Skip fallback model %s due to init error: %s", candidate_model, exc)
    
    # --- 3. 获取共享的 Checkpointer ---
    checkpointer = _get_checkpointer()
    
    # --- 4. 创建动态 Summarization Middleware ---
    # 【修正2】使用正确的配置项
    summarization_middleware = SummarizationMiddleware(
        model=llm,
        max_tokens_before_summary=summarization_threshold,  #记忆摘要阈值
        messages_to_keep=effective_messages_to_keep,#用于控制记忆压缩后保留的消息数
    )

    logger.info(
        f"🔨 创建新的 Agent，session_id={session_id}, "
        f"temperature={effective_temperature}, top_k={effective_top_k}, "
        f"max_generation_tokens={max_tokens}, "
        f"summary_threshold={summarization_threshold}, "
        f"messages_to_keep={effective_messages_to_keep}, "
        f"llm_model={resolved_llm_model}"
    )
    
    # --- 5. 创建动态 Retriever ---
    retriever = _create_retriever_with_filter(
        session_id=session_id,
        top_k=effective_top_k
    )
    web_search_service = WebSearchService.get_instance()
    search_state: Dict[str, Any] = {
        "web_sources": [],
        "web_search_used": False,
    }
    
    # --- 6.  ---
    @tool("retrieve_context", response_format="content_and_artifact")
    def retrieve_context_filtered(query: str):
        """Fetch context for the query from system docs + user uploads (+ optional web search)."""
        docs = retriever.invoke(query)

        if use_web_search:
            if web_search_service.is_available():
                logger.info("web_search: trigger query=%r", query)
                search_state["web_search_used"] = True
                web_results = web_search_service.search(
                    query,
                    max_results=config.WEB_SEARCH_RESULT_LIMIT,
                )
                if web_results:
                    logger.info("web_search: got %s results", len(web_results))
                    search_state["web_sources"] = web_results
                    for item in web_results:
                        snippet = item.get("snippet") or ""
                        if not snippet:
                            continue
                        docs.append(
                            Document(
                                page_content=snippet,
                                metadata={
                                    "source": item.get("url") or item.get("source") or "web",
                                    "session_id": "external",
                                    "title": item.get("title") or item.get("url") or "Web Result",
                                    "source_type": "web",
                                },
                            )
                        )
                else:
                    logger.info("web_search: no results")
            else:
                logger.debug("web_search: requested but Tavily API Key not available")

        serialized = "\n\n".join(
            (
                f"Source: {doc.metadata.get('source', '<unknown>')}\n"
                f"Session: {doc.metadata.get('session_id', 'unknown')}\n"
                f"Content: {doc.page_content}"
                for doc in docs
            )
        )
        return serialized, docs

    # --- 7. System Prompt ---
    system_prompt = (
        "你通过扮演一门计算机网络课程的助教以及一个‘检索优先’的智能体。\n"
        "工具：`retrieve_context`（返回内部知识库 KB + 网络搜索结果）。当 `use_web_search=True` 时，必须在每一轮回答**之前**先调用一次 `retrieve_context`。\n"
        "如果用户的查询中包含 web/online/最新/实时/当前/最近/年份 等关键词，必须调用 `retrieve_context` 并引用公开来源。\n"
        "如果内部知识库 (KB) 与网络搜索结果存在冲突，请明确指出差异（如时间、版本不同），并同时展示这两个视角的观点。\n"
        "\n"
        "回答规则：\n"
        "1) 务必先调用 `retrieve_context`，然后基于检索到的内容进行回答。\n"
        "2) 如果使用了外部来源，请在回答末尾添加引用模块，格式为——来源：[链接或出处]；内容：[约50字的摘要]。\n"
        "3) 使用 Markdown 格式（标题、列表）组织内容。如果信息不足，请直接说明，并建议用户进行更多搜索或上传资料。\n"
        "4) 关于冲突处理：明确标记“内部资料 vs 网络信息”的差异，然后给出一个平衡的观点。\n"
        "\n"
        "语气与教学风格：\n"
        "-以此深入浅出的方式开场，避免一开始就堆砌生涩的术语。\n"
        "- 针对关键主题（如链路层、路由协议、TCP 拥塞控制、DNS、ARP 等），适时提供额外的具体示例或实验场景。\n"
        "- 如果学生看起来不确定或有困惑，主动提供辅助选项（如：、更简化的场景类比、或考试风格的练习题）。\n"
        "- 保持鼓励、支持和乐于助人的态度。\n"
        "\n"
        "目标：帮助学生真正理解知识点，并顺利通过课程考试。"
    )

    # --- 8. 创建 Agent ---
    middleware_stack = [summarization_middleware]
    if fallback_models:
        middleware_stack.append(ModelFallbackMiddleware(*fallback_models))

    agent = create_agent(
        llm,
        tools=[retrieve_context_filtered],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        middleware=middleware_stack,
    )

    logger.info('agent created: session_id=%s use_web_search=%s', session_id, use_web_search)
    
    
    return agent, search_state



# ---------------------------- 对外接口 ----------------------------
def invoke(
    question: str, 
    thread_id: str = "1", 
    timeout_s: Optional[float] = None,
    temperature: float = None,
    top_k: int = None,
    messages_to_keep: int = None,
    max_tokens: int = None,
    use_web_search: bool = False,
    llm_model: Optional[str] = None,
) -> str:
    """
    一次性调用，返回完整回答文本。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话和文档检索范围（默认 "1"）
        timeout_s: 超时时间（暂未使用）
        temperature: LLM 温度参数
        top_k: RAG 检索的 K 值
        messages_to_keep: 记忆压缩后保留的消息数
        max_tokens: 最大生成token数
        llm_model: 指定使用的 LLM 模型名称
    
    Returns:
        完整回答文本
    """
    agent, _ = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep,
        max_tokens=max_tokens,
        use_web_search=use_web_search,
        llm_model=llm_model,
    )
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


def stream_updates(
    question: str, 
    thread_id: str = "1",
    temperature: float = None,
    top_k: int = None,
    messages_to_keep: int = None,
    llm_model: Optional[str] = None,
):
    """
    步骤级流（model → tools → model）。产出 dict，便于调试与观测。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话和文档检索范围（默认 "1"）
        temperature: LLM 温度参数
        top_k: RAG 检索的 K 值
        messages_to_keep: 记忆压缩后保留的消息数
        llm_model: 指定使用的 LLM 模型
    
    Yields:
        步骤更新字典
    """
    agent, _ = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep,
        llm_model=llm_model,
    )
    config_dict = {"configurable": {"thread_id": thread_id}}
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="updates",
        config=config_dict,
    ):
        yield chunk


def stream_messages(
    question: str, 
    thread_id: str = "1",
    temperature: float = None,
    top_k: int = None,
    messages_to_keep: int = None,
    max_tokens: int = None,
    use_web_search: bool = False,
    llm_model: Optional[str] = None,
):
    """
    仅流式输出模型文本块（逐段）。产出 str。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话和文档检索范围（默认 "1"）
        temperature: LLM 温度参数
        top_k: RAG 检索的 K 值
        messages_to_keep: 记忆压缩后保留的消息数
        max_tokens: 最大生成token数
        llm_model: 指定使用的 LLM 模型
    
    Yields:
        文本块字符串
    """
    agent, search_state = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep,
        max_tokens=max_tokens,
        use_web_search=use_web_search,
        llm_model=llm_model,
    )
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
                    yield {"type": "text", "content": text}
    if use_web_search:
        yield {
            "type": "sources",
            "sources": search_state.get("web_sources", []),
            "web_search_used": bool(search_state.get("web_search_used")),
        }
