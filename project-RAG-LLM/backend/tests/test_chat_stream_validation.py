import io
import sys
import types
from pathlib import Path

import pytest
from flask import Blueprint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 该测试仅验证 /chat/stream 的参数校验，不依赖 document 模块中的历史 EmbeddingService 导入
if "app.api.document" not in sys.modules:
    stub_document = types.ModuleType("app.api.document")
    stub_document.document_bp = Blueprint("document", __name__)
    sys.modules["app.api.document"] = stub_document

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_chat_stream_missing_session_id_returns_unified_error(client):
    response = client.post("/api/chat/stream", json={"message": "hello"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {"success": False, "error": "session_id 不能为空"}


def test_chat_stream_missing_message_returns_unified_error(client):
    response = client.post("/api/chat/stream", json={"session_id": "s1"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {"success": False, "error": "message 不能为空"}


@pytest.mark.parametrize(
    "config_payload,error_message",
    [
        ({"temperature": -0.1}, "temperature 必须在 0 到 2 之间"),
        ({"temperature": 2.1}, "temperature 必须在 0 到 2 之间"),
        ({"temperature": "high"}, "temperature 必须是数字"),
        ({"top_k": 0}, "top_k 必须是大于 0 的整数"),
        ({"top_k": 1.5}, "top_k 必须是大于 0 的整数"),
        ({"messages_to_keep": 0}, "messages_to_keep 必须是大于 0 的整数"),
        ({"max_tokens": 0}, "max_tokens 必须是大于 0 的整数"),
    ],
)
def test_chat_stream_invalid_dynamic_config_returns_unified_error(client, config_payload, error_message):
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "s1",
            "message": "hello",
            "config": config_payload,
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {"success": False, "error": error_message}


def test_chat_voice_invalid_config_json_returns_unified_error(client):
    response = client.post(
        "/api/chat/voice",
        data={
            "audio": (io.BytesIO(b"dummy audio"), "test.wav"),
            "config": "{invalid json}",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {"success": False, "error": "config 必须是合法 JSON"}


@pytest.mark.parametrize(
    "config_payload,error_message",
    [
        ('{"temperature": "high"}', "temperature 必须是数字"),
        ('{"top_k": 0}', "top_k 必须是大于 0 的整数"),
    ],
)
def test_chat_voice_invalid_dynamic_config_returns_unified_error(client, config_payload, error_message):
    response = client.post(
        "/api/chat/voice",
        data={
            "audio": (io.BytesIO(b"dummy audio"), "test.wav"),
            "config": config_payload,
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload == {"success": False, "error": error_message}
