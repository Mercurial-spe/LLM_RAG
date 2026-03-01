from flask import Flask
from flask_cors import CORS
import logging
import os

from .config import DEBUG, ENABLE_CORS, CORS_ORIGINS, LANGSMITH_API_KEY, LANGSMITH_PROJECT
from .utils.logger import setup_logging

# 【关键】在创建 Flask app 之前配置日志
setup_logging()

logger = logging.getLogger(__name__)

# 配置 LangSmith (可观测性)
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    logger.info(f"🔍 LangSmith 追踪已启用 - 项目: {LANGSMITH_PROJECT}")
else:
    logger.info("ℹ️ LangSmith 未配置 (需要 LANGSMITH_API_KEY 环境变量)")


def create_app() -> Flask:
    app = Flask(__name__)

    # CORS 配置（根据环境变量决定是否启用）
    # 开发环境：启用 CORS，允许前端跨域访问
    # 生产环境：禁用 CORS，由 Nginx 反向代理统一处理
    if ENABLE_CORS:
        logger.info(f"🔓 CORS 已启用 - 允许来源: {CORS_ORIGINS}")
        CORS(app, resources={
            r"/api/*": {
                "origins": CORS_ORIGINS,  # 从环境变量读取
                # 需要显式包含 PATCH，避免浏览器预检请求报错
                "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "Accept"],
                "expose_headers": ["Content-Type"],
                "supports_credentials": False,
                "max_age": 3600
            }
        })
    else:
        logger.info("🔒 CORS 已禁用 - 由 Nginx 反向代理处理跨域")

    # 注册蓝图
    from .api.chat import chat_bp
    from .api.document import document_bp
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(document_bp, url_prefix="/api")

    # 运行时配置（如需）
    app.config["DEBUG"] = DEBUG

    return app


