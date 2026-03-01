# backend/app/core/checkpointer.py

"""
Checkpointer 工厂模块
负责创建和管理 LangGraph Checkpointer 实例
"""

import logging
import os
import sqlite3
from .. import config

logger = logging.getLogger(__name__)

# 全局单例实例
_checkpointer = None


def get_checkpointer():
    """
    获取全局共享的 Checkpointer 实例(懒加载单例)

    优先使用 SQLite Checkpointer,如果不可用则降级到 MemorySaver

    Returns:
        Checkpointer 实例(SqliteSaver 或 MemorySaver)
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    # 确保目录存在
    db_dir = os.path.dirname(config.CHAT_MEMORY_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # 尝试使用 SQLite Checkpointer(需要 langgraph-checkpoint-sqlite)
    # 如果不可用,降级到 MemorySaver(内存存储)
    try:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            conn = sqlite3.connect(config.CHAT_MEMORY_DB_PATH, check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            _checkpointer.setup()
            logger.info(f"使用 SQLite Checkpointer,数据库路径: {config.CHAT_MEMORY_DB_PATH}")
        except Exception as e:
            logger.error(
                "初始化 SqliteSaver 失败,将降级为 MemorySaver。错误: %s: %s",
                type(e).__name__, str(e), exc_info=True
            )
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
            logger.warning("已切换为 MemorySaver(内存存储,重启后丢失)。")
    except Exception as e:
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
        logger.warning(f"初始化 Checkpointer 失败: {e},使用 MemorySaver(内存存储)")

    return _checkpointer
