"""
Tools Package
=============
工具接口层：统一的工具签名与 ToolResult 输出

职责：
- 参数校验与默认值注入
- 调用 Service 层执行真正的业务逻辑
- 返回统一的 ToolResult 结构

禁止：
- 直接访问数据库/向量库/HTTP（必须通过 Service）
- 在 Tool 内写复杂策略与路由逻辑
"""

from .rag_tool import execute_rag_tool
from .web_search_tool import execute_web_search_tool

__all__ = ["execute_rag_tool", "execute_web_search_tool"]
