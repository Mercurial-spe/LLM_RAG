# backend/app/utils/logger.py

"""
统一日志配置模块
================
在应用启动时调用 setup_logging() 来统一配置所有日志
"""

import logging
import sys


def setup_logging(level=logging.INFO):
    """
    配置应用日志系统
    
    Args:
        level: 日志级别，默认 INFO
    """
    # 使用 force=True 确保即使之前调用过 basicConfig 也能重新配置
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Python 3.8+ 支持，强制重新配置
    )
    
    # 抑制第三方库的噪音日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)  # Flask 默认日志保持 INFO

