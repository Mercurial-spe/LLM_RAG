"""
LangGraph Agent Runtime 模块
============================
职责：
- 提供基于 LangGraph StateGraph 的 Agent 运行时
- 支持 RAG 和 WebSearch 作为 Tool（能力）
- 实现显式 Decision 路由（不依赖 tool_calls）
- 支持流式输出（SSE）和记忆管理

架构：
- runtime.py: Agent 运行时（invoke/astream + SSE 适配 + 记忆钩子）
- graph.py: StateGraph 构建与编译
- state.py: AgentState/Decision/ToolResult 数据结构
- nodes/: 节点实现（orchestrator/tool_exec/respond）
"""

from .runtime import AgentRuntime
from .state import AgentState, Decision, ToolResult

__all__ = ["AgentRuntime", "AgentState", "Decision", "ToolResult"]
