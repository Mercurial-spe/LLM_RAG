"""
Agent Runtime
=============
职责：
- 对外提供 invoke/stream_messages 接口
- 适配 SSE/Streaming
- 集成 Checkpointer 管理会话记忆
- 支持动态参数传递（temperature、top_k、max_tokens 等）

实现：
- 使用 LangGraph StateGraph 执行 Agent 流程
- 支持流式输出（stream_messages）
- 集成 SQLite Checkpointer 持久化对话历史
"""

import logging
from typing import Any, Dict, Iterator, Optional, List
from .graph import build_graph
from .state import AgentState, ToolResult
from ..core.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    Agent 运行时

    提供统一的 Agent 调用接口，封装 StateGraph 的执行逻辑。
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        messages_to_keep: Optional[int] = None,
        max_tokens: Optional[int] = None,
        use_web_search: bool = False,
        llm_model: Optional[str] = None,
    ):
        """
        初始化 Runtime

        Args:
            session_id: 会话 ID（用于文档检索过滤）
            temperature: LLM 温度参数
            top_k: RAG 检索的 K 值
            messages_to_keep: 记忆压缩后保留的消息数
            max_tokens: 最大生成 token 数
            use_web_search: 是否启用网络搜索
            llm_model: 指定使用的 LLM 模型
        """
        self.session_id = session_id
        self.temperature = temperature
        self.top_k = top_k
        self.messages_to_keep = messages_to_keep
        self.max_tokens = max_tokens
        self.use_web_search = use_web_search
        self.llm_model = llm_model

        # 构建 Graph（带 Checkpointer）
        checkpointer = get_checkpointer()
        self.graph = build_graph(checkpointer=checkpointer)

        logger.info(
            f"AgentRuntime 初始化完成: session_id={session_id}, "
            f"temperature={temperature}, top_k={top_k}, "
            f"max_tokens={max_tokens}, use_web_search={use_web_search}, "
            f"llm_model={llm_model}"
        )

    def invoke(
        self,
        question: str,
        thread_id: str = "1",
        **kwargs
    ) -> str:
        """
        一次性调用，返回完整回答文本

        Args:
            question: 用户问题
            thread_id: 对话线程 ID
            **kwargs: 其他参数

        Returns:
            完整回答文本
        """
        logger.info("invoke: thread_id=%s, question_len=%s", thread_id, len(question or ""))

        # 构建初始状态
        initial_state: AgentState = {
            "messages": [
                {"role": "user", "content": question}
            ],
            "artifacts": {
                "session_id": self.session_id or thread_id,
                "temperature": self.temperature,
                "top_k": self.top_k,
                "max_tokens": self.max_tokens,
                "use_web_search": self.use_web_search,
                "llm_model": self.llm_model,
            }
        }

        # 配置 thread_id
        config = {"configurable": {"thread_id": thread_id}}

        # 执行 Graph
        try:
            result = self.graph.invoke(initial_state, config=config)
            logger.info("invoke: Graph 执行完成")

            # 提取最后一条 assistant 消息
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    return msg.get("content", "")

            logger.warning("invoke: 没有找到 assistant 消息")
            return "抱歉，我无法生成回复。"

        except Exception as e:
            logger.error(f"invoke: Graph 执行失败: {e}", exc_info=True)
            return f"抱歉，处理您的问题时出现错误：{str(e)}"

    def stream_messages(
        self,
        question: str,
        thread_id: str = "1",
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        流式输出（单次 Graph 执行 + 流式生成回复）

        Args:
            question: 用户问题
            thread_id: 对话线程 ID
            **kwargs: 其他参数

        Yields:
            消息块字典
        """
        logger.info("stream_messages: thread_id=%s, question_len=%s", thread_id, len(question or ""))

        initial_state: AgentState = {
            "messages": [
                {"role": "user", "content": question}
            ],
            "artifacts": {
                "session_id": self.session_id or thread_id,
                "temperature": self.temperature,
                "top_k": self.top_k,
                "max_tokens": self.max_tokens,
                "use_web_search": self.use_web_search,
                "llm_model": self.llm_model,
                "streaming": True,
            }
        }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            final_state = None
            for chunk in self.graph.stream(initial_state, config=config):
                for node_name in chunk.keys():
                    logger.debug(f"stream: node={node_name}")
                    if node_name == "respond":
                        final_state = self.graph.get_state(config)
                        break
                if final_state:
                    break

            if not final_state:
                logger.warning("stream_messages: 未能获取到 respond 后状态")
                yield {"type": "error", "content": "抱歉，我无法生成回复。"}
                return

            yield from self._stream_respond(final_state.values)
            logger.info("stream_messages: 输出完成")

        except Exception as e:
            logger.error(f"stream_messages: 流式输出失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"抱歉，处理您的问题时出现错误：{str(e)}"
            }

    def _stream_respond(self, state: AgentState) -> Iterator[Dict[str, Any]]:
        """
        流式生成回复（逐 token 返回）

        Args:
            state: 当前 Agent 状态

        Yields:
            消息块字典
        """
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from ..core.llm_handler import LLMHandler
        from ..prompts.loader import load_prompt

        messages = state.get("messages", [])
        tool_results = state.get("tool_results", [])
        artifacts = state.get("artifacts", {})

        # 获取最后一条用户消息
        last_user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        if not last_user_message:
            logger.warning("_stream_respond: 没有找到用户消息")
            return

        try:
            # 加载系统提示词
            system_prompt = load_prompt("rag_system")

            # 获取 LLM 实例
            llm_handler = LLMHandler.get_instance()
            llm_model = artifacts.get("llm_model")
            temperature = artifacts.get("temperature")

            llm = llm_handler.get_model(model_name=llm_model)
            if temperature is not None:
                llm = llm.bind(temperature=temperature)

            # 构建对话历史
            recent_messages = messages[-10:] if len(messages) > 10 else messages
            llm_messages = [SystemMessage(content=system_prompt)]

            for msg in recent_messages[:-1]:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    llm_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    llm_messages.append(AIMessage(content=content))

            # 构建当前用户消息
            if tool_results:
                # 构建包含工具结果的提示词
                user_prompt = self._build_prompt_with_tools_internal(last_user_message, tool_results)
            else:
                user_prompt = last_user_message

            llm_messages.append(HumanMessage(content=user_prompt))

            # 流式调用 LLM
            logger.info("_stream_respond: 开始流式生成回复")
            for chunk in llm.stream(llm_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield {"type": "text", "content": chunk.content}

        except Exception as e:
            logger.error(f"_stream_respond: 流式生成失败: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"生成回复时出错：{str(e)}"
            }

    def _build_prompt_with_tools_internal(
        self,
        user_message: str,
        tool_results: List[ToolResult]
    ) -> str:
        """
        构建包含工具结果的提示词（内部方法）

        Args:
            user_message: 用户问题
            tool_results: 工具结果列表

        Returns:
            包含检索内容的提示词
        """
        prompt_parts = [f"用户问题: {user_message}\n"]

        for result in tool_results:
            tool_name = result.get("name", "unknown")
            ok = result.get("ok", False)

            if ok:
                sources = result.get("sources", [])
                if sources:
                    prompt_parts.append(f"\n## {tool_name} 检索结果:\n")
                    for i, source in enumerate(sources, 1):
                        snippet = source.get("snippet", "")
                        source_name = source.get("source") or source.get("url") or source.get("title", "未知来源")
                        score = source.get("score", 0)

                        prompt_parts.append(f"### 来源 {i} (相关度: {score:.2f})")
                        prompt_parts.append(f"**出处**: {source_name}")
                        if snippet:
                            prompt_parts.append(f"**内容**:\n{snippet}\n")
                else:
                    prompt_parts.append(f"\n{tool_name} 执行成功，但没有找到相关信息。\n")
            else:
                error = result.get("error", "未知错误")
                prompt_parts.append(f"\n{tool_name} 执行失败: {error}\n")

        prompt_parts.append("\n请基于以上检索结果回答用户问题。如果检索结果中有相关信息，请引用来源；如果没有相关信息，请如实告知用户。")

        return "\n".join(prompt_parts)


# 全局单例（已废弃，改为按需创建）
_runtime_instance: Optional[AgentRuntime] = None


def get_runtime(**kwargs) -> AgentRuntime:
    """
    获取 Runtime 实例（按需创建）

    Args:
        **kwargs: Runtime 初始化参数

    Returns:
        AgentRuntime 实例
    """
    # 不再使用全局单例，每次调用都创建新实例
    # 这样可以支持不同的动态参数
    return AgentRuntime(**kwargs)
