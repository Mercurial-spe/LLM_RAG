"""
Orchestrator Node
=================
职责：分析用户输入和上下文，产出显式的 Decision（路由决策）

输入：AgentState（包含 messages, tool_results 等）
输出：更新 state.decision

决策逻辑：
1. 分析用户问题和历史对话
2. 使用 LLM 判断是否需要调用工具（RAG/WebSearch）
3. 产出结构化的 Decision
"""

import logging
import json
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import AgentState, Decision
from ...core.llm_handler import LLMHandler
from ...prompts.loader import load_prompt

logger = logging.getLogger(__name__)


def orchestrator_node(state: AgentState) -> Dict[str, Any]:
    """
    Orchestrator 节点：使用 LLM 产出 Decision

    Args:
        state: 当前 Agent 状态

    Returns:
        包含 decision 的字典（用于更新 state）
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
        logger.warning("orchestrator: 没有找到用户消息，默认返回 END")
        decision: Decision = {"action": "END"}
        return {"decision": decision}

    # 如果已经有工具结果，直接回复（避免重复调用工具）
    if tool_results:
        logger.info("orchestrator: 已有工具结果，决策为 RESPOND")
        decision: Decision = {"action": "RESPOND"}
        return {"decision": decision}

    # 使用 LLM 进行决策
    try:
        # 加载决策提示词
        system_prompt = load_prompt("orchestrator_decision")

        # 获取 LLM 实例
        llm_handler = LLMHandler.get_instance()
        llm_model = artifacts.get("llm_model")
        llm = llm_handler.get_model(model_name=llm_model)

        # 构建对话历史上下文（最近 5 条消息）
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        context = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in recent_messages
        ])

        # 构建 LLM 输入
        llm_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""当前对话历史:
{context}

最新用户问题: {last_user_message}

请分析用户问题并输出决策 JSON。""")
        ]

        # 调用 LLM
        logger.info("orchestrator: 调用 LLM 进行决策")
        response = llm.invoke(llm_messages)
        response_text = response.content.strip()

        # 解析 JSON 响应
        decision = _parse_decision_response(response_text, last_user_message, artifacts)

        logger.info(f"orchestrator: LLM 决策完成 - action={decision.get('action')}, tool={decision.get('tool_name')}")
        return {"decision": decision}

    except Exception as e:
        logger.error(f"orchestrator: LLM 决策失败: {e}", exc_info=True)
        # 降级到简单规则：默认调用 RAG
        logger.warning("orchestrator: 降级到简单规则决策")
        decision: Decision = {
            "action": "CALL_TOOL",
            "tool_name": "rag",
            "tool_args": {"query": last_user_message},
            "rationale": "LLM 决策失败，降级到默认 RAG 检索"
        }
        return {"decision": decision}


def _parse_decision_response(
    response_text: str,
    user_message: str,
    artifacts: Dict[str, Any]
) -> Decision:
    """
    解析 LLM 返回的决策 JSON

    Args:
        response_text: LLM 返回的文本
        user_message: 用户消息
        artifacts: 状态中的 artifacts

    Returns:
        Decision 对象
    """
    try:
        # 尝试提取 JSON（可能包含在 markdown 代码块中）
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0].strip()

        # 解析 JSON
        decision_data = json.loads(json_text)

        # 验证必需字段
        if "action" not in decision_data:
            raise ValueError("Decision 缺少 action 字段")

        # 构建 Decision
        decision: Decision = {
            "action": decision_data["action"]
        }

        # 添加可选字段
        if decision_data.get("tool_name"):
            decision["tool_name"] = decision_data["tool_name"]

        if decision_data.get("tool_args"):
            tool_args = decision_data["tool_args"]
            # 注入 session_id 和 top_k（如果未提供）
            tool_args.setdefault("session_id", artifacts.get("session_id", "1"))
            tool_args.setdefault("top_k", artifacts.get("top_k", 5))
            decision["tool_args"] = tool_args

        if decision_data.get("rationale"):
            decision["rationale"] = decision_data["rationale"]

        return decision

    except Exception as e:
        logger.error(f"解析 Decision JSON 失败: {e}", exc_info=True)
        logger.debug(f"原始响应: {response_text}")

        # 降级：返回默认 RAG 决策
        return {
            "action": "CALL_TOOL",
            "tool_name": "rag",
            "tool_args": {
                "query": user_message,
                "session_id": artifacts.get("session_id", "1"),
                "top_k": artifacts.get("top_k", 5)
            },
            "rationale": "JSON 解析失败，降级到默认 RAG 检索"
        }
