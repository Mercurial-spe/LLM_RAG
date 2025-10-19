# backend/app/config.py

import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 这会寻找项目中的 .env 文件并将其内容加载到系统环境变量中
load_dotenv()

# --- 从环境中读取配置 ---
# 使用 os.getenv() 来安全地获取变量，如果变量不存在，它会返回 None
MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY")
