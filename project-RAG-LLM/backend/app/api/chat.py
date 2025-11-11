from flask import Blueprint, jsonify, request, Response, stream_with_context

from ..core.llm_handler import call_model_stream
from ..core.rag_agent import stream_messages, invoke
from ..config import ENABLE_CORS, CORS_ORIGINS


chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/chat")
def chat_message():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id")

    if not user_message:
        return jsonify({"error": "message 不能为空"}), 400

    # 将流式结果聚合为完整回复（前期便于前后端联调；后续可切换为SSE流）
    reply_parts: list[str] = []
    for chunk in call_model_stream(user_message):
        delta = getattr(chunk.choices[0], "delta", None)
        if delta and getattr(delta, "content", None):
            reply_parts.append(delta.content)

    reply_text = "".join(reply_parts) if reply_parts else ""

    return jsonify({
        "message": reply_text,
        "session_id": session_id,
    })


@chat_bp.get("/chat/history/<string:session_id>")
def chat_history(session_id: str):
    # 先返回占位，后续可接数据库/存储
    return jsonify({
        "session_id": session_id,
        "history": [],
    })



@chat_bp.route("/chat/stream", methods=["POST", "OPTIONS"])
def chat_message_stream():
    # 处理 OPTIONS 预检请求（仅在启用 CORS 时需要）
    if request.method == "OPTIONS" and ENABLE_CORS:
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = CORS_ORIGINS
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    import json
    
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id")
    
    # 使用 session_id 作为 thread_id（如果有），否则默认 "1"
    thread_id = session_id if session_id else "1"

    if not user_message:
        return jsonify({"error": "message 不能为空"}), 400

    @stream_with_context
    def generate_sse():
        try:
            # 使用基于 LangChain Agent 的 RAG 流，只推送"模型文本"
            # 传递 thread_id 以支持短期记忆
            for text in stream_messages(user_message, thread_id=thread_id):
                # 使用 JSON 编码保留换行符，避免与 SSE 的 \n\n 冲突
                yield f"data: {json.dumps(text, ensure_ascii=False)}\n\n"
            yield "event: done\n"
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps(str(e), ensure_ascii=False)}\n\n"

    # 注意：SSE 必须保持文本流类型，并设置正确的响应头
    response = Response(generate_sse(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 禁用 Nginx 缓冲
    
    # 手动添加 CORS 响应头（仅在启用 CORS 时，针对手动创建的 Response 对象）
    # 生产环境中 ENABLE_CORS=False，由 Nginx 反向代理统一处理
    if ENABLE_CORS:
        response.headers['Access-Control-Allow-Origin'] = CORS_ORIGINS
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type'
    
    return response

