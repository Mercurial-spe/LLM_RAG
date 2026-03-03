"""
Respond Node
============
职责：生成最终回复，整合 messages 和 tool_results

输入：AgentState（包含 messages, tool_results）
输出：追加 assistant message

回复策略：
1. 如果有 tool_results，使用 LLM 生成引用式回答
2. 如果没有 tool_results，使用 LLM 直接回答
3. 如果工具失败，给出解释和建议
"""

import logging
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from ..state import AgentState, ToolResult
from ...core.llm_handler import LLMHandler
from ...prompts.loader import load_prompt

logger = logging.getLogger(__name__)


def respond_node(state: AgentState) -> Dict[str, Any]:
    """
    Respond 节点：使用 LLM 生成最终回复

    Args:
        state: 当前 Agent 状态

    Returns:
        包含 messages 的字典（用于追加到 state）
    """
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
        logger.warning("respond: 没有找到用户消息")
        return {}

    # 使用 LLM 生成回复
    try:
        # 加载系统提示词
        system_prompt = load_prompt("rag_system")

        # 获取 LLM 实例
        llm_handler = LLMHandler.get_instance()
        llm_model = artifacts.get("llm_model")
        temperature = artifacts.get("temperature")

        # 获取 LLM（支持动态 temperature）
        llm = llm_handler.get_model(model_name=llm_model)
        if temperature is not None:
            llm = llm.bind(temperature=temperature)

        # 构建对话历史（最近 10 条消息）
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        llm_messages = [SystemMessage(content=system_prompt)]

        # 添加历史对话
        for msg in recent_messages[:-1]:  # 排除最后一条用户消息（会单独处理）
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                llm_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                llm_messages.append(AIMessage(content=content))

        # 构建当前用户消息（包含工具结果）
        if tool_results:
            # 有工具结果，构建包含检索内容的提示
            user_prompt = _build_prompt_with_tools(last_user_message, tool_results)
        else:
            # 没有工具结果，直接使用用户问题
            user_prompt = last_user_message

        llm_messages.append(HumanMessage(content=user_prompt))

        # 检查是否需要流式输出
        streaming = artifacts.get("streaming", False)

        if streaming:
            # 流式生成（逐 token 返回）
            logger.info("respond: 使用流式模式生成回复")
            response_chunks = []
            for chunk in llm.stream(llm_messages):
                if hasattr(chunk, 'content'):
                    chunk_text = chunk.content
                    if chunk_text:
                        response_chunks.append(chunk_text)

            # 合并所有 chunks
            response_text = "".join(response_chunks)
        else:
            # 非流式生成
            logger.info("respond: 使用非流式模式生成回复")
            response = llm.invoke(llm_messages)
            response_text = response.content.strip()

        # 追加 assistant 消息
        assistant_message = {
            "role": "assistant",
            "content": response_text
        }

        logger.info("respond: LLM 回复生成完成")
        return {"messages": [assistant_message]}

    except Exception as e:
        logger.error(f"respond: LLM 回复生成失败: {e}", exc_info=True)
        # 降级到简单模板
        logger.warning("respond: 降级到简单模板回复")
        if tool_results:
            response_text = _generate_response_with_tools(last_user_message, tool_results)
        else:
            response_text = f"抱歉，我在生成回复时遇到了问题。您的问题是：{last_user_message}"

        assistant_message = {
            "role": "assistant",
            "content": response_text
        }
        return {"messages": [assistant_message]}


def _build_prompt_with_tools(
    user_message: str,
    tool_results: List[ToolResult]
) -> str:
    """
    构建包含工具结果的提示词

    Args:
        user_message: 用户问题
        tool_results: 工具结果列表

    Returns:
        包含检索内容的提示词
    """
    prompt_parts = [f"用户问题: {user_message}\n"]

    # 添加工具结果
    for result in tool_results:
        tool_name = result.get("name", "unknown")
        ok = result.get("ok", False)

        if ok:
            # 工具执行成功
            data = result.get("data", {})
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
            # 工具执行失败
            error = result.get("error", "未知错误")
            prompt_parts.append(f"\n{tool_name} 执行失败: {error}\n")

    prompt_parts.append("\n请基于以上检索结果回答用户问题。如果检索结果中有相关信息，请引用来源；如果没有相关信息，请如实告知用户。")

    return "\n".join(prompt_parts)


def _generate_response_with_tools(
    user_message: str,
    tool_results: List[ToolResult]
) -> str:
    """
    基于工具结果生成引用式回答（降级模板）

    Args:
        user_message: 用户问题
        tool_results: 工具结果列表

    Returns:
        回复文本
    """
    response_parts = [f"收到您的问题：{user_message}\n"]

    for result in tool_results:
        tool_name = result.get("name", "unknown")
        ok = result.get("ok", False)

        if ok:
            # 工具执行成功
            sources = result.get("sources", [])
            if sources:
                response_parts.append(f"\n根据 {tool_name} 检索到的信息：")
                for i, source in enumerate(sources[:3], 1):  # 最多显示 3 个来源
                    snippet = source.get("snippet", "")
                    source_name = source.get("source") or source.get("url") or source.get("title", "未知来源")
                    response_parts.append(f"{i}. 来源：{source_name}")
                    if snippet:
                        response_parts.append(f"   内容：{snippet[:100]}...")
            else:
                response_parts.append(f"\n{tool_name} 执行成功，但没有找到相关信息。")
        else:
            # 工具执行失败
            error = result.get("error", "未知错误")
            response_parts.append(f"\n{tool_name} 执行失败：{error}")

    response_parts.append("\n\n(注意: 这是降级模板回复，LLM 生成失败)")

    return "\n".join(response_parts)
