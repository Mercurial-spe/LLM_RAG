import threading
from typing import Optional
from langchain_openai import OpenAIEmbeddings
from .. import config

# 1. 定义私有全局变量（类型标注使用 Optional）
_embeddings: Optional[OpenAIEmbeddings] = None

# 2. 预先创建一个全局互斥锁对象
# 它是模块级别的单例，用于保护初始化过程
_lock = threading.Lock()

def get_embeddings() -> OpenAIEmbeddings:
    """获取全局共享的 Embeddings 实例（线程安全的懒加载单例）。"""
    global _embeddings
    
    # --- 第一次检查：若已初始化，直接跳过锁，提升读性能 ---
    if _embeddings is None:
        # --- 加锁：确保只有一个线程能进入初始化逻辑 ---
        with _lock:
            # --- 第二次检查：防止在等待锁期间，其他线程已经完成了初始化 ---
            if _embeddings is None:
                _embeddings = OpenAIEmbeddings(
                    model=config.EMBEDDING_MODEL_NAME,
                    openai_api_key=config.DASHSCOPE_API_KEY,
                    openai_api_base=config.EMBEDDING_API_BASE_URL,
                    dimensions=config.EMBEDDING_DIMENSION,
                    chunk_size=config.EMBEDDING_BATCH_SIZE,
                )
    
    return _embeddings