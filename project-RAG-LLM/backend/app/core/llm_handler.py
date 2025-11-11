# backend/app/core/llm_handler.py

"""
LLM 调用服务 (适配器)
=====================
功能：
  1. 封装对 LLM API 的调用 (基于 LangChain 的 ChatOpenAI 包装器)。
  2. 采用与 EmbeddingService 相同的单例模式和 OpenAI 兼容 SDK 模式。
  3.  从 config.py 读取 DashScope 配置 (DASHSCOPE_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME)。
  4.  支持 Qwen3 模型的 'extra_body' (enable_thinking) 参数。
  5. 为上层 (RagPipeline) 提供一个稳定、统一的 LLM 实例。
"""

import logging
from .. import config
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

from openai import OpenAI
from .. import config  # <-- 保留相对导入，完全没问题！

def call_model_stream(user_prompt: str):
    """封装了调用LLM并流式返回的核心功能"""
    client = OpenAI(
        base_url='https://api-inference.modelscope.cn/v1',
        # 使用最简洁的方式直接赋值
        api_key=config.MODELSCOPE_API_KEY, 
    )

    response = client.chat.completions.create(
        model='Qwen/Qwen3-8B',
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': user_prompt}
        ],
        stream=True
    )
    yield from response
    
class LLMHandler:
    """
    LLM 调用服务 (单例模式)
    负责初始化和提供 Chat Model 实例
    """

    _instance = None
    _client: BaseChatModel = None # 类型注解为 LangChain 的基础聊天模型

    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化 LLM 客户端
        使用 LangChain 的 ChatOpenAI 包装器，
        以适配 DashScope 的 OpenAI 兼容 API。
        """
        if self._client is None:
            try:
                #  关键：从 config.py 读取 LLM 的特定配置
                #  使用 DASHSCOPE_API_KEY
                api_key = config.DASHSCOPE_API_KEY
                base_url = config.LLM_API_BASE_URL
                model_name = config.LLM_MODEL_NAME
                temperature = config.RAG_TEMPERATURE

                if not api_key:
                    raise ValueError("DASHSCOPE_API_KEY 未在 .env 或环境变量中设置")
                if not base_url:
                    raise ValueError("LLM_API_BASE_URL 未在 config.py 中设置")
                if not model_name:
                    raise ValueError("LLM_MODEL_NAME 未在 config.py 中设置")

                #  构造 LangChain model_kwargs 以传递 extra_body
                model_kwargs = {}
                
                # 为 Qwen3 模型添加 enable_thinking 参数
                # 从 config.py 中读取这个配置
                # 注意：LangChain 的 ChatOpenAI 会自动将 model_kwargs 里的
                # 'extra_body' 传递给底层的 OpenAI 客户端。
                model_kwargs["extra_body"] = {
                    "enable_thinking": config.LLM_ENABLE_THINKING
                }
                
                logger.info(f"为模型 {model_name} 设置 model_kwargs: {model_kwargs}")

                self._client = ChatOpenAI(
                    model_name=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    streaming=True, # 默认启用流式，API层可以按需调用
                    model_kwargs=model_kwargs #  传递额外参数
                )
                
                logger.info(f"LLM 处理器初始化成功 - 模型: {model_name}, 温度: {temperature}")
                logger.info(f"LLM API Base URL: {base_url}")

            except Exception as e:
                logger.error(f"LLM 处理器初始化失败: {e}")
                raise

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_model(self) -> BaseChatModel:
        """
        获取已初始化的 LangChain Chat Model 实例
        
        Returns:
            BaseChatModel: ChatOpenAI 实例
        """
        if self._client is None:
            self.get_instance() # 确保已初始化
        return self._client

