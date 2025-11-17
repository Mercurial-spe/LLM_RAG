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
    base_llm = LLMHandler.get_instance().get_model()
    
    # 【修正1】收集所有要绑定的 LLM 参数
    llm_params_to_bind = {
        "temperature": effective_temperature,
        "max_tokens": effective_max_tokens
    }

    llm = base_llm.bind(**llm_params_to_bind)
    
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
        f"messages_to_keep={effective_messages_to_keep}"
    )
    
    # --- 5. 创建动态 Retriever ---
    retriever = _create_retriever_with_filter(
        session_id=session_id,
        top_k=effective_top_k
    )
    
    # --- 6. 动态创建工具（闭包） ---
    @tool("retrieve_context", response_format="content_and_artifact")
    def retrieve_context_filtered(query: str):
        """检索与问题相关的上下文内容（限定当前会话范围：系统文档+用户上传文档）。"""
        docs = retriever.invoke(query)
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
        "你是华南理工大学计算机网络课程的学习助手，同时扮演助教角色。\n"
        "你的任务是根据你所拥有的知识，以及在必要时来自工具 `retrieve_context` 的知识库内容，\n"
        "为学生提供准确、清晰、易懂的解答。\n"
        "你可以自行判断是否需要调用知识库来回答问题，而不是每次都强制调用。\n"
        "作为助教，你需要适时询问学生是否理解，例如：\n"
        "‘是否需要我举例说明？’、‘是否需要结合真实网络场景解释？’、‘是否有不懂的地方需要我进一步展开？’。\n"
        "\n"
        "==============================\n"
        "【核心规则】\n"
        "==============================\n"
        "1. 当你使用外部资料时，必须基于工具 `retrieve_context` 返回的 Content。\n"
        "2. 严禁使用内部知识或主观推测来编造资料中没有的内容。\n"
        "3. 如果资料不足以回答问题，可以直接说明：\n"
        "   ‘根据我所掌握的资料，无法提供完整答案，但我可以用已有知识给出解释。’\n"
        "\n"
        "==============================\n"
        "【引用与格式要求】\n"
        "==============================\n"
        "1. 若引用了外部资料，回答必须在结尾另起一段，以 ‘参考资料’ 为标题，按以下格式列出：\n"
        "   ```\n"
        "   Source: [工具返回的 Source]\n"
        "   Content: [引用的 Content 摘要（约 50 字）]\n"
        "   ```\n"
        "2. 必须使用规范 Markdown 格式。\n"
        "\n"
        "==============================\n"
        "【助教身份要求】\n"
        "==============================\n"
        "作为计算机网络课程的助教，你需要做到：\n"
        "- 讲解深入浅出，不堆砌术语，让学生听得懂；\n"
        "- 在关键知识点（如链路层、路由、TCP 拥塞控制、DNS、ARP 等）后，主动询问学生是否需要更详细的例子或实际网络场景对照；\n"
        "- 在发现学生疑惑时及时提出可选方向，例如：\n"
        "  ‘是否需要我给你画出流程图？’、\n"
        "  ‘要不要我用更简单的场景再解释一次？’、\n"
        "  ‘需要我讲讲考试中对应的常见题型吗？’；\n"
        "- 帮助学生真正理解，而不仅是死记硬背。\n"
        "\n"
        "你的最终目标是帮助学生掌握计算机网络知识，并顺利通过考试。"

    )
    
    # --- 8. 创建 Agent ---
    agent = create_agent(
        llm,
        tools=[retrieve_context_filtered],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        middleware=[summarization_middleware],
    )
    
    logger.info(f"✅ 动态 Agent 已创建（session_id={session_id})")
    
    return agent



# ---------------------------- 对外接口 ----------------------------
def invoke(
    question: str, 
    thread_id: str = "1", 
    timeout_s: Optional[float] = None,
    temperature: float = None,
    top_k: int = None,
    messages_to_keep: int = None,
    max_tokens: int = None
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
    
    Returns:
        完整回答文本
    """
    agent = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep,
        max_tokens=max_tokens
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
    messages_to_keep: int = None
):
    """
    步骤级流（model → tools → model）。产出 dict，便于调试与观测。
    
    Args:
        question: 用户问题
        thread_id: 对话线程ID，用于区分不同会话和文档检索范围（默认 "1"）
        temperature: LLM 温度参数
        top_k: RAG 检索的 K 值
        messages_to_keep: 记忆压缩后保留的消息数
    
    Yields:
        步骤更新字典
    """
    agent = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep
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
    
    Yields:
        文本块字符串
    """
    agent = _create_dynamic_agent(
        session_id=thread_id,
        temperature=temperature,
        top_k=top_k,
        messages_to_keep=messages_to_keep,
        max_tokens=max_tokens
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
                    yield text
