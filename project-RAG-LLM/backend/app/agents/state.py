"""
Agent State Contract
====================
定义 AgentState、Decision、ToolResult 数据结构

这些是本次重构的"工程骨架"，确保：
1. 节点之间的数据契约清晰
2. 路由决策显式化（不依赖 tool_calls）
3. 工具输出统一化（便于 respond 节点消费）
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict
from typing_extensions import NotRequired


class Decision(TypedDict):
    """
    显式路由决策结构

    由 orchestrator 节点产出，用于控制 Graph 的路由逻辑。
    禁止使用 tool_calls[0]["name"] 作为路由依据（脆弱且难扩展）。
    """
    action: Literal["CALL_TOOL", "RESPOND", "END", "CLARIFY"]
    tool_name: NotRequired[str]  # 当 action=CALL_TOOL 时必填
    tool_args: NotRequired[Dict[str, Any]]  # 工具参数
    rationale: NotRequired[str]  # 决策理由（可选，用于调试）
    confidence: NotRequired[float]  # 置信度（可选，用于排序/阈值）


class ToolResult(TypedDict):
    """
    统一工具输出结构

    所有 Tool（RAG/WebSearch/...）必须返回此结构。
    确保 respond 节点可以"无差别消费工具输出"。
    """
    ok: bool  # 是否成功
    name: str  # 工具名称
    data: Any  # 结构化数据
    sources: NotRequired[List[Dict[str, Any]]]  # 引用来源（RAG 文档/网页链接等）
    error: NotRequired[str]  # 错误信息
    latency_ms: NotRequired[int]  # 延迟（可选，用于监控）


class AgentState(TypedDict):
    """
    Agent 状态契约

    字段写入规则（强制）：
    - orchestrator: 只写 decision（可写 trace）
    - tool_exec: 只追加 tool_results（可写 trace/last_error）
    - respond: 只追加 messages（assistant）与可写 trace

    规范：
    - messages: 始终追加，不随意覆盖
    - decision: 由 orchestrator 写入，用于路由
    - tool_results: 由 tool_exec 追加，用于 respond 生成引用式回答
    """
    messages: List[Dict[str, Any]]  # 对话消息列表
    decision: NotRequired[Decision]  # 路由决策
    tool_results: NotRequired[List[ToolResult]]  # 工具调用结果列表
    artifacts: NotRequired[Dict[str, Any]]  # 结构化产出（可选）
    last_error: NotRequired[str]  # 最后一次错误（可选）
    trace: NotRequired[Dict[str, Any]]  # 追踪信息（可选：节点耗时、路由路径等）
