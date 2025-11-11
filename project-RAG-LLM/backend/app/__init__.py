from flask import Flask
from flask_cors import CORS

from .config import DEBUG
from .utils.logger import setup_logging

# 【关键】在创建 Flask app 之前配置日志
setup_logging()


def create_app() -> Flask:
    app = Flask(__name__)

    # CORS 在应用层统一开启（支持流式响应和跨域）
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",  # 允许所有来源（生产环境建议指定具体域名）
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 允许的 HTTP 方法
            "allow_headers": ["Content-Type", "Authorization", "Accept"],  # 允许的请求头
            "expose_headers": ["Content-Type"],  # 暴露给前端的响应头
            "supports_credentials": False,  # 不需要凭证（如果改为 True，origins 不能为 *）
            "max_age": 3600  # preflight 缓存时间（秒）
        }
    })

    # 注册蓝图
    from .api.chat import chat_bp
    from .api.document import document_bp
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(document_bp, url_prefix="/api")

    # 运行时配置（如需）
    app.config["DEBUG"] = DEBUG

    return app


