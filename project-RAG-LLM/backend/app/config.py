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
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen-plus")

# [新增] Qwen3 特定参数
# Qwen3模型通过enable_thinking参数控制思考过程
# 开源版默认True，商业版默认False。非流式输出时可能需要设置为False。
LLM_ENABLE_THINKING = os.getenv("LLM_ENABLE_THINKING", "False").lower() == "true"


# --- RAG 查询配置 ---
RAG_TOP_K = 3 # 检索时返回的最相关文档块数量
RAG_TEMPERATURE = 0.2 # LLM 生成答案时的温度系数，越低越稳定

# --- 向量数据库配置 ---
VECTOR_STORE_TYPE = "chroma"  # 使用ChromaDB
# 支持环境变量 VECTOR_STORE_PATH；默认定位到项目 data/vector_store（绝对路径）
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", str(PROJECT_ROOT / "data" / "vector_store"))
VECTOR_COLLECTION_NAME = "course_documents"  # 集合名称

# --- 文档来源目录 ---
# 默认定位到项目 data/raw_documents（绝对路径）
RAW_DOCUMENTS_PATH = os.getenv("RAW_DOCUMENTS_PATH", str(PROJECT_ROOT / "data" / "raw_documents"))

# --- 文档处理配置 ---
CHUNK_SIZE = 500  # 文本块大小(字符数)
CHUNK_OVERLAP = 50  # 文本块重叠大小
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 最大上传文件大小: 10MB

# --- Flask配置 ---
DEBUG = True
HOST = "0.0.0.0"
PORT = 5000

# --- 废弃的 Key (保留以防万一) ---
# 此 Key 在当前 DashScope 流程中未使用
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY")

