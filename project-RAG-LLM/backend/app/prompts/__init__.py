# backend/app/prompts/__init__.py

"""
Prompts 包
基于 Markdown 文件的 Prompt 管理系统
"""

from .loader import load_prompt, reload_prompt, clear_cache, list_available_prompts

# 导出常用 Prompt 获取函数（真正的按需加载）
def get_rag_system_prompt() -> str:
    """获取 RAG 系统提示词（按需加载）"""
    return load_prompt("rag_system")

def get_summarization_prompt() -> str:
    """获取对话摘要提示词（按需加载）"""
    return load_prompt("summarization")

def get_query_rewrite_prompt() -> str:
    """获取查询改写提示词（按需加载）"""
    return load_prompt("query_rewrite")

__all__ = [
    "load_prompt",
    "reload_prompt",
    "clear_cache",
    "list_available_prompts",
    "get_rag_system_prompt",
    "get_summarization_prompt",
    "get_query_rewrite_prompt",
]
