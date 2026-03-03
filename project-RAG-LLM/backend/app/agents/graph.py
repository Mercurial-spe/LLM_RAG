"""
StateGraph 构建模块
==================
职责：构建和编译 LangGraph StateGraph

Graph 设计：
- orchestrator: 分析输入，产出 Decision
- tool_exec: 根据 Decision 执行工具
- respond: 生成最终回复

路由逻辑：
- orchestrator -> tool_exec (当 action=CALL_TOOL)
- orchestrator -> respond (当 action=RESPOND)
- orchestrator -> END (当 action=END)
- tool_exec -> respond (当前版本固定单轮工具调用)
- respond -> END
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import orchestrator_node, tool_exec_node, respond_node

logger = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    """
    构建 StateGraph

    Args:
        checkpointer: 可选的 Checkpointer 实例（用于持久化对话历史）

    Returns:
        编译后的 Graph 实例
    """
    logger.info("开始构建 StateGraph")

    # 创建 StateGraph
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("tool_exec", tool_exec_node)
    graph.add_node("respond", respond_node)

    # 添加边
    # START -> orchestrator
    graph.add_edge(START, "orchestrator")

    # orchestrator -> tool_exec/respond (条件路由)
    graph.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        {
            "tool_exec": "tool_exec",
            "respond": "respond",
            "end": END
        }
    )

    # tool_exec -> respond（当前版本固定单轮工具调用）
    graph.add_edge("tool_exec", "respond")

    # respond -> END
    graph.add_edge("respond", END)

    # 编译 Graph（传入 Checkpointer）
    compiled_graph = graph.compile(checkpointer=checkpointer)

    logger.info(f"StateGraph 构建完成 (checkpointer={'enabled' if checkpointer else 'disabled'})")

    return compiled_graph


def _route_after_orchestrator(state: AgentState) -> Literal["tool_exec", "respond", "end"]:
    """
    orchestrator 节点后的路由逻辑

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    decision = state.get("decision")

    if not decision:
        logger.warning("route: decision 为空，默认路由到 end")
        return "end"

    action = decision.get("action")

    if action == "CALL_TOOL":
        logger.info("route: action=CALL_TOOL，路由到 tool_exec")
        return "tool_exec"
    elif action == "RESPOND":
        logger.info("route: action=RESPOND，路由到 respond")
        return "respond"
    elif action == "END":
        logger.info("route: action=END，路由到 end")
        return "end"
    else:
        logger.warning(f"route: 未知的 action={action}，默认路由到 respond")
        return "respond"
