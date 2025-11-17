from flask import Blueprint, jsonify, request, Response, stream_with_context

from ..core.llm_handler import call_model_stream
from ..core.rag_agent import stream_messages, invoke
from ..core.conversation_manager import (
    get_all_conversations,
    get_conversation_messages,
    delete_conversation,
    update_conversation_title
)
from ..config import ENABLE_CORS, CORS_ORIGINS
from .. import config as app_config_module
from ..services.speech_service import (
    transcribe_audio,
    synthesize_audio,
    SpeechServiceError,
)
import logging
import uuid
import json

logger = logging.getLogger(__name__)


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
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
        
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id")
    
    # 【新增】从前端获取动态配置，并设置默认值
    config_data = data.get("config", {})
    
    # 从 config.py 导入默认值作为 fallback
    from .. import config as app_config
    
    dynamic_params = {
        "temperature": config_data.get("temperature", getattr(app_config, 'RAG_TEMPERATURE', 0.2)),
        "top_k": config_data.get("top_k", app_config.RAG_TOP_K),
        "messages_to_keep": config_data.get("messages_to_keep", app_config.MEMORY_MESSAGES_TO_KEEP)
    }
    
    # 【调试日志】记录接收到的前端配置
    logger.info(f"📥 /chat/stream 接收到前端数据:")
    logger.info(f"   - 前端传递的 config: {config_data}")
    logger.info(f"   - 最终使用的 dynamic_params: {dynamic_params}")
    
    # 要求前端必须显式传入 session_id，避免不同会话写入同一默认线程
    if not session_id:
        logger.warning("/chat/stream 调用缺少 session_id，拒绝请求以避免写入默认线程")
        return jsonify({"error": "session_id 不能为空"}), 400

    # 使用 session_id 作为 thread_id（与 LangGraph 的 configurable.thread_id 对齐）
    thread_id = session_id

    if not user_message:
        return jsonify({"error": "message 不能为空"}), 400


    @stream_with_context
    def generate_sse():
        try:
            # 使用基于 LangChain Agent 的 RAG 流，只推送"模型文本"
            # 传递 thread_id 以支持短期记忆，传递动态参数
            for text in stream_messages(
                user_message,
                thread_id=thread_id,
                **dynamic_params  # 将所有动态参数解包传入
            ):
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
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type'
    
    return response


# ====================
# 语音聊天相关接口
# ====================
@chat_bp.post("/chat/voice")
def chat_voice():
    """
    接收前端上传的音频文件，调用 Qwen ASR + RAG 返回文本回答。
    """
    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"success": False, "error": "audio 文件不能为空"}), 400

    config_raw = request.form.get("config")
    transcribe_only_flag = (request.form.get("transcribe_only", "false") or "false").lower()
    transcribe_only = transcribe_only_flag in {"true", "1", "yes"}
    session_id = request.form.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("语音接口未提供 session_id，自动创建: %s", session_id)

    config_data = {}
    if config_raw:
        try:
            config_data = json.loads(config_raw)
        except json.JSONDecodeError:
            logger.warning("语音接口 config 字段解析失败，原始值: %s", config_raw)

    from .. import config as app_config
    dynamic_params = {
        "temperature": config_data.get("temperature", getattr(app_config, 'RAG_TEMPERATURE', 0.2)),
        "top_k": config_data.get("top_k", app_config.RAG_TOP_K),
        "messages_to_keep": config_data.get("messages_to_keep", app_config.MEMORY_MESSAGES_TO_KEEP)
    }

    try:
        transcript = transcribe_audio(audio_file)
        logger.info("语音识别结果: %s", transcript)
    except SpeechServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        logger.error("语音识别出现未预期错误: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": "语音识别失败"}), 500

    reply_text = ""
    if not transcribe_only:
        try:
            reply_text = invoke(
                transcript,
                thread_id=session_id,
                temperature=dynamic_params["temperature"],
                top_k=dynamic_params["top_k"],
                messages_to_keep=dynamic_params["messages_to_keep"],
            )
        except Exception as exc:  # pragma: no cover
            logger.error("语音问答失败: %s", exc, exc_info=True)
            return jsonify({"success": False, "error": "生成回复失败"}), 500

    return jsonify({
        "success": True,
        "session_id": session_id,
        "transcript": transcript,
        "reply": reply_text,
    })


@chat_bp.post("/chat/voice/reply")
def chat_voice_reply():
    """
    将文本回答转换为语音音频返回前端。
    """
    data = request.get_json(silent=True) or {}
    reply_text = (data.get("text") or "").strip()

    if not reply_text:
        return jsonify({"success": False, "error": "text 字段不能为空"}), 400

    try:
        audio_bytes = synthesize_audio(reply_text)
    except SpeechServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        logger.error("语音合成失败: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": "语音合成失败"}), 500

    response = Response(audio_bytes, mimetype=f"audio/{app_config_module.QWEN_SPEECH_FORMAT}")
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Disposition'] = f"inline; filename=reply.{app_config_module.QWEN_SPEECH_FORMAT}"
    if ENABLE_CORS:
        response.headers['Access-Control-Allow-Origin'] = CORS_ORIGINS
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
    return response


# ==================== 对话管理 API ====================

@chat_bp.get("/conversations")
def get_conversations():
    """
    获取所有对话列表
    
    Returns:
        对话列表，包含 thread_id、title、last_message_time、message_count
    """
    try:
        conversations = get_all_conversations()
        return jsonify({
            "success": True,
            "conversations": conversations
        })
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@chat_bp.get("/conversations/<string:thread_id>/messages")
def get_conversation_messages_api(thread_id: str):
    """
    获取指定对话的完整消息历史
    
    Args:
        thread_id: 对话 ID
        
    Returns:
        包含 thread_id 和 messages 列表的字典
    """
    try:
        result = get_conversation_messages(thread_id)
        return jsonify({
            "success": True,
            **result
        })
    except Exception as e:
        logger.error(f"获取对话消息失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "thread_id": thread_id,
            "messages": []
        }), 500


@chat_bp.post("/conversations")
def create_conversation():
    """
    创建新对话
    
    Returns:
        新对话的 thread_id、title、created_at
    """
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "新对话")
        
        # 生成新的 UUID 作为 thread_id
        new_thread_id = str(uuid.uuid4())
        
        from datetime import datetime
        created_at = datetime.now().isoformat()
        
        logger.info(f"创建新对话: {new_thread_id}")
        
        return jsonify({
            "success": True,
            "thread_id": new_thread_id,
            "title": title,
            "created_at": created_at
        }), 201
        
    except Exception as e:
        logger.error(f"创建对话失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@chat_bp.delete("/conversations/<string:thread_id>")
def delete_conversation_api(thread_id: str):
    """
    删除指定对话
    
    Args:
        thread_id: 对话 ID
        
    Returns:
        删除结果
    """
    try:
        success = delete_conversation(thread_id)
        
        if success:
            logger.info(f"删除对话成功: {thread_id}")
            return jsonify({
                "success": True,
                "message": "对话删除成功"
            })
        else:
            return jsonify({
                "success": False,
                "error": "对话不存在或删除失败"
            }), 404
            
    except Exception as e:
        logger.error(f"删除对话失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@chat_bp.patch("/conversations/<string:thread_id>")
def update_conversation_api(thread_id: str):
    """
    更新对话信息（如标题）
    
    Args:
        thread_id: 对话 ID
        
    Request Body:
        {
            "title": "新标题"
        }
        
    Returns:
        更新结果
    """
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        
        if not title:
            return jsonify({
                "success": False,
                "error": "标题不能为空"
            }), 400
        
        success = update_conversation_title(thread_id, title)
        
        if success:
            logger.info(f"更新对话标题成功: {thread_id} -> {title}")
            return jsonify({
                "success": True,
                "message": "标题更新成功",
                "thread_id": thread_id,
                "title": title
            })
        else:
            return jsonify({
                "success": False,
                "error": "对话不存在或更新失败"
            }), 404
            
    except Exception as e:
        logger.error(f"更新对话标题失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
