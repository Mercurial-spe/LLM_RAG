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

# --- LLM配置 ---
# 使用 os.getenv() 来安全地获取变量，如果变量不存在，它会返回 None
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY")

# --- 嵌入模型配置 (阿里云百炼 API) ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
EMBEDDING_API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL_NAME = "text-embedding-v4"

# 向量维度配置 (text-embedding-v4支持多种维度)
# 可选值: 64, 128, 256, 512, 768, 1024(默认), 1536, 2048
EMBEDDING_DIMENSION = 1024  # 默认使用1024维，性能和存储的平衡

# 嵌入批处理配置
EMBEDDING_BATCH_SIZE = 10  # text-embedding-v4的批次大小上限为10
EMBEDDING_MAX_TOKENS = 8192  # 单次最大处理Token数

# --- 向量数据库配置 ---
VECTOR_STORE_TYPE = "chroma"  # 使用ChromaDB
# 支持环境变量 VECTOR_STORE_PATH；默认定位到项目 data/vector_store（绝对路径）
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", str(PROJECT_ROOT / "data" / "vector_store"))
VECTOR_COLLECTION_NAME = "course_documents"  # 集合名称

# --- 文档来源目录（新增，可通过环境变量 RAW_DOCUMENTS_PATH 覆盖） ---
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

