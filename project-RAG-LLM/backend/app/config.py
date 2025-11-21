# backend/app/config.py
#
# Only API keys are read from the environment; all other settings live here.

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# 优先加载项目内 .env，如未找到再加载上一层（当前仓库根目录外的 .env）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / ".env")

# --- Paths ---
# 已在上方定义

# --- API keys (env-only) ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY")

# --- Provider & model selection ---
LLM_PROVIDER = "dashscope"  # switch provider here (dashscope / ollama)
LLM_API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL_NAME = "qwen3-max"
_LLM_ADDITIONAL_MODELS = ["qwen-flash"]
LLM_SUPPORTED_MODELS: List[str] = []
for candidate in [LLM_MODEL_NAME, *_LLM_ADDITIONAL_MODELS]:
    if candidate and candidate not in LLM_SUPPORTED_MODELS:
        LLM_SUPPORTED_MODELS.append(candidate)


def resolve_llm_model(requested_model: Optional[str]) -> str:
    """Return a supported LLM model or fall back to the default."""
    if requested_model and requested_model in LLM_SUPPORTED_MODELS:
        return requested_model
    return LLM_MODEL_NAME


LLM_ENABLE_THINKING = False
LLM_MAX_TOKENS = 8192
RAG_TEMPERATURE = 0.2

# Ollama (local) configuration
OLLAMA_API_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL_NAME = "llama3.2:1b"

# --- Embeddings ---
DASHSCOPE_API_BASE_URL = LLM_API_BASE_URL
EMBEDDING_API_BASE_URL = DASHSCOPE_API_BASE_URL
EMBEDDING_MODEL_NAME = "text-embedding-v4"
EMBEDDING_DIMENSION = 1024
EMBEDDING_BATCH_SIZE = 10
EMBEDDING_MAX_TOKENS = 8192

# --- RAG / retrieval ---
RAG_TOP_K = 3

# --- Vector store ---
VECTOR_STORE_TYPE = "chroma"
VECTOR_STORE_PATH = str(PROJECT_ROOT / "data" / "vector_store")
VECTOR_COLLECTION_NAME = "course_documents"

# --- Conversation memory ---
CHAT_MEMORY_DB_PATH = str(PROJECT_ROOT / "data" / "chat_memory" / "chat_memory.db")
MEMORY_MAX_TOKENS_BEFORE_SUMMARY = 30000
MEMORY_MESSAGES_TO_KEEP = 20

# --- Speech (Qwen ASR/TTS) ---
QWEN_ASR_MODEL = "qwen3-asr-flash"
QWEN_TTS_MODEL = "qwen-tts"
QWEN_SPEECH_VOICE = "Cherry"
QWEN_SPEECH_SPEED = 1.0
QWEN_SPEECH_FORMAT = "wav"
QWEN_SPEECH_SAMPLE_RATE = 24000
QWEN_TTS_TOKEN_LIMIT = 512
QWEN_MAX_AUDIO_SECONDS = 30
QWEN_MAX_AUDIO_SIZE = 2 * 1024 * 1024
TIKTOKEN_CACHE_DIR = str(PROJECT_ROOT / "data")
# 语音朗读前是否用 LLM 重写为纯文本
TTS_REWRITE_WITH_LLM = True

# --- Document ingest ---
RAW_DOCUMENTS_PATH = str(PROJECT_ROOT / "data" / "raw_documents")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# --- Flask runtime ---
DEBUG = True
HOST = "localhost"
PORT = 5000

# --- CORS ---
ENABLE_CORS = True
CORS_ORIGINS = "*"

# --- Web search (Tavily) ---
WEB_SEARCH_ENABLED = True
WEB_SEARCH_RESULT_LIMIT = 4
TAVILY_API_BASE_URL = "https://api.tavily.com/search"
TAVILY_MAX_RESULTS = 4
TAVILY_SEARCH_DEPTH = "basic"
TAVILY_TIMEOUT = 8.0
