# backend/app/config.py

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 这会寻找项目中的 .env 文件并将其内容加载到系统环境变量中
load_dotenv()

# --- 路径根定位（确保无论从哪里启动进程，路径都稳定） ---
_THIS_FILE = Path(__file__).resolve()
# 目录层级：.../project-RAG-LLM/backend/app/config.py
# parents[0]=app, [1]=backend, [2]=project-RAG-LLM
PROJECT_ROOT = _THIS_FILE.parents[2]

# --- 本地的ollama模型 ---

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "dashscope").lower()
OLLAMA_API_BASE_URL = os.getenv("OLLAMA_API_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "llama3.2:1b")

# --- 嵌入模型配置 (阿里云百炼 API) ---
# 当前 嵌入和 LLM 聊天共用一个 API Key 和 Base URL
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
DASHSCOPE_API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

EMBEDDING_API_BASE_URL = DASHSCOPE_API_BASE_URL
EMBEDDING_MODEL_NAME = "text-embedding-v4"

# 向量维度配置 (text-embedding-v4支持多种维度)
# 可选值: 64, 128, 256, 512, 768, 1024(默认), 1536, 2048
EMBEDDING_DIMENSION = 1024  # 默认使用1024维，性能和存储的平衡

# 嵌入批处理配置
EMBEDDING_BATCH_SIZE = 10  # text-embedding-v4的批次大小上限为10
EMBEDDING_MAX_TOKENS = 8192  # 单次最大处理Token数


# --- LLM配置 ---
# [更新] LLM 默认使用和嵌入相同的 Base URL
LLM_API_BASE_URL = os.getenv("LLM_API_BASE_URL", DASHSCOPE_API_BASE_URL)

# [更新] LLM 的模型名称，更新为 qwen-plus
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen3-max")

# [新增] Qwen3 特定参数
# Qwen3模型通过enable_thinking参数控制思考过程
# 开源版默认True，商业版默认False。非流式输出时可能需要设置为False。
LLM_ENABLE_THINKING = os.getenv("LLM_ENABLE_THINKING", "False").lower() == "true"
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))     # 默认8192


# --- RAG 查询配置 ---
RAG_TOP_K = 3 # 检索时返回的最相关文档块数量
RAG_TEMPERATURE = 0.2 # LLM 生成答案时的温度系数，越低越稳定

# --- 向量数据库配置 ---
VECTOR_STORE_TYPE = "chroma"  # 使用ChromaDB
# 支持环境变量 VECTOR_STORE_PATH；默认定位到项目 data/vector_store（绝对路径）
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", str(PROJECT_ROOT / "data" / "vector_store"))
VECTOR_COLLECTION_NAME = "course_documents"  # 集合名称

# --- 对话记忆配置 ---
# 短期记忆数据库路径（SQLite）
CHAT_MEMORY_DB_PATH = os.getenv("CHAT_MEMORY_DB_PATH", str(PROJECT_ROOT / "data" / "chat_memory" / "chat_memory.db"))
# Summarization 触发阈值（token数）
MEMORY_MAX_TOKENS_BEFORE_SUMMARY = int(os.getenv("MEMORY_MAX_TOKENS_BEFORE_SUMMARY", "30000"))
# Summarization 后保留的消息数
MEMORY_MESSAGES_TO_KEEP = int(os.getenv("MEMORY_MESSAGES_TO_KEEP", "20"))

# --- 文档来源目录 ---
# 默认定位到项目 data/raw_documents（绝对路径）
RAW_DOCUMENTS_PATH = os.getenv("RAW_DOCUMENTS_PATH", str(PROJECT_ROOT / "data" / "raw_documents"))

# --- 文档处理配置 ---
CHUNK_SIZE = 500  # 文本块大小(字符数)
CHUNK_OVERLAP = 50  # 文本块重叠大小
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 最大上传文件大小: 10MB

# --- Flask配置 ---
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 监听地址配置
# 开发环境：0.0.0.0 允许局域网访问
# 生产环境：建议使用 localhost（仅本机访问，通过 Nginx 反向代理对外）
HOST = os.getenv("FLASK_HOST", "localhost")
PORT = int(os.getenv("FLASK_PORT", "5000"))

# --- CORS 配置 ---
# 开发环境：启用 CORS（前端 localhost:5173 访问后端 localhost:5000）
# 生产环境：禁用 CORS（前后端通过 Nginx 统一域名，无跨域问题）
ENABLE_CORS = os.getenv("ENABLE_CORS", "True").lower() == "true"

# CORS 允许的来源
# 开发环境：* 或指定 localhost
# 生产环境：如果启用 CORS，应指定具体域名
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# --- 废弃的 Key (保留以防万一) ---
# 此 Key 在当前 DashScope 流程中未使用
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY")

