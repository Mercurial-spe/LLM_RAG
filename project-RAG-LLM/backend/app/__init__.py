from flask import Flask
from flask_cors import CORS

from .config import DEBUG


def create_app() -> Flask:
    app = Flask(__name__)

    # CORS 在应用层统一开启（可按需细化）
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    from .api.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix="/api")

    # 运行时配置（如需）
    app.config["DEBUG"] = DEBUG

    return app


