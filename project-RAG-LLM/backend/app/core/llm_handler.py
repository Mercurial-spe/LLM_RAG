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
from typing import Dict, Optional, Tuple
from .. import config
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

class LLMHandler:
    """
    LLM 调用服务 (单例模式)
    负责初始化和提供 Chat Model 实例
    """

    _instance = None
    _clients: Dict[Tuple[str, str], BaseChatModel] = {}

    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化默认 LLM 客户端，其余模型将在首次访问时懒加载。
        """
        provider = config.LLM_PROVIDER.lower()
        try:
            self.get_model(provider=provider)
        except Exception as exc:
            logger.error("LLM 处理器初始化失败: %s", exc)
            raise

    def _build_client(self, provider: str, model_name: str) -> BaseChatModel:
        """
        根据 provider + 模型名称构造新的 Chat Model 客户端。
        """
        provider = provider.lower()
        temperature = config.RAG_TEMPERATURE

        if provider == "ollama":
            base_url = config.OLLAMA_API_BASE_URL
            if not base_url:
                raise ValueError("LLM_PROVIDER='ollama' 但 OLLAMA_API_BASE_URL 未设置")
            if not model_name:
                raise ValueError("LLM_PROVIDER='ollama' 但模型名称未设置")
            logger.info("初始化 Ollama 客户端，模型: %s", model_name)
            return ChatOllama(
                model=model_name,
                base_url=base_url,
                temperature=temperature,
            )

        if provider == "dashscope":
            api_key = config.DASHSCOPE_API_KEY
            base_url = config.LLM_API_BASE_URL
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY 未在 .env 或环境变量中设置")
            if not base_url:
                raise ValueError("LLM_API_BASE_URL 未在 config.py 中设置")
            if not model_name:
                raise ValueError("LLM_MODEL_NAME 未在 config.py 中设置")

            model_kwargs = {}
            extra_body = None
            if model_name.lower().startswith("qwen3"):
                extra_body = {
                    "enable_thinking": config.LLM_ENABLE_THINKING
                }

            logger.info("初始化 DashScope 客户端，模型: %s, extra_body: %s", model_name, extra_body)
            return ChatOpenAI(
                model_name=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                streaming=True,
                model_kwargs=model_kwargs,
                extra_body=extra_body,
            )

        raise ValueError(f"未知的 LLM_PROVIDER: '{provider}'，仅支持 dashscope 或 ollama")

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_model(
        self,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> BaseChatModel:
        """
        获取（或懒加载）指定 provider + model 对应的 Chat Model。
        """
        provider_key = (provider or config.LLM_PROVIDER).lower()
        if provider_key == "dashscope":
            target_model = model_name or config.LLM_MODEL_NAME
        elif provider_key == "ollama":
            target_model = model_name or config.OLLAMA_MODEL_NAME
        else:
            raise ValueError(f"未知的 LLM_PROVIDER: '{provider_key}'，仅支持 dashscope 或 ollama")

        cache_key = (provider_key, target_model)
        if cache_key not in self._clients:
            self._clients[cache_key] = self._build_client(provider_key, target_model)
            logger.info("LLM 客户端缓存新增: %s", cache_key)
        return self._clients[cache_key]

