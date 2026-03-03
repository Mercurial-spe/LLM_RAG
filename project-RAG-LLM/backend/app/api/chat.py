from flask import Blueprint, jsonify, request, Response, stream_with_context

from ..agents.runtime import get_runtime
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
from ..services.web_search_service import WebSearchService
import logging
import uuid
import json

logger = logging.getLogger(__name__)


chat_bp = Blueprint("chat", __name__)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_dynamic_config(config_data: dict):
    """校验前端动态参数，返回错误信息（无错误时返回 None）"""
    if "temperature" in config_data:
        temperature = config_data.get("temperature")
        if not _is_number(temperature):
            return "temperature 必须是数字"
        if temperature < 0 or temperature > 2:
            return "temperature 必须在 0 到 2 之间"

    for field in ["top_k", "messages_to_keep", "max_tokens"]:
        if field in config_data:
            value = config_data.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return f"{field} 必须是大于 0 的整数"

    return None


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
    if not isinstance(config_data, dict):
        return jsonify({"success": False, "error": "config 必须是对象"}), 400

    config_validation_error = _validate_dynamic_config(config_data)
    if config_validation_error:
        return jsonify({"success": False, "error": config_validation_error}), 400

    # 从 config.py 导入默认值作为 fallback
    from .. import config as app_config
    
    requested_llm_model = config_data.get("llm_model")
    resolved_llm_model = app_config.resolve_llm_model(requested_llm_model)
    if requested_llm_model and resolved_llm_model != requested_llm_model:
        logger.warning("前端请求的 llm_model=%s 未受支持，已回退至 %s", requested_llm_model, resolved_llm_model)

    dynamic_params = {
        "temperature": config_data.get("temperature", getattr(app_config, 'RAG_TEMPERATURE', 0.2)),
        "top_k": config_data.get("top_k", app_config.RAG_TOP_K),
        "messages_to_keep": config_data.get("messages_to_keep", app_config.MEMORY_MESSAGES_TO_KEEP),
        "max_tokens": config_data.get("max_tokens", app_config.LLM_MAX_TOKENS),
        "llm_model": resolved_llm_model,
    }
    use_web_search = bool(config_data.get("web_search_enabled"))
    web_search_service = WebSearchService.get_instance()
    if use_web_search and not web_search_service.is_available():
        logger.warning("前端请求启用联网搜索，但后端未启用该功能或缺少 Tavily API Key")
    
    # 【调试日志】记录接收到的前端配置
    logger.info("/chat/stream 接收到前端数据: config_keys=%s", sorted(config_data.keys()))
    logger.info(
        "/chat/stream 最终使用 dynamic_params: temperature=%s, top_k=%s, messages_to_keep=%s, max_tokens=%s, llm_model=%s, web_search_enabled=%s",
        dynamic_params["temperature"],
        dynamic_params["top_k"],
        dynamic_params["messages_to_keep"],
        dynamic_params["max_tokens"],
        dynamic_params["llm_model"],
        use_web_search,
    )
    
    # 要求前端必须显式传入 session_id，避免不同会话写入同一默认线程
    if not session_id:
        logger.warning("/chat/stream 调用缺少 session_id，拒绝请求以避免写入默认线程")
        return jsonify({"success": False, "error": "session_id 不能为空"}), 400

    # 使用 session_id 作为 thread_id（与 LangGraph 的 configurable.thread_id 对齐）
    thread_id = session_id

    if not user_message:
        return jsonify({"success": False, "error": "message 不能为空"}), 400


    @stream_with_context
    def generate_sse():
        try:
            # 创建 AgentRuntime 实例（传递动态参数）
            runtime = get_runtime(
                session_id=thread_id,
                temperature=dynamic_params["temperature"],
                top_k=dynamic_params["top_k"],
                messages_to_keep=dynamic_params["messages_to_keep"],
                max_tokens=dynamic_params["max_tokens"],
                use_web_search=use_web_search,
                llm_model=dynamic_params["llm_model"],
            )

            # 使用新的 AgentRuntime 流式输出
            for chunk in runtime.stream_messages(
                user_message,
                thread_id=thread_id,
            ):
                # 使用 JSON 编码保留换行符，避免与 SSE 的 \n\n 冲突
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "event: done\n"
        except Exception as e:
            logger.error("/chat/stream SSE 处理失败: %s", e, exc_info=True)
            yield "event: error\n"
            yield f"data: {json.dumps('服务内部错误', ensure_ascii=False)}\n\n"

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
            logger.warning("语音接口 config 字段解析失败")
            return jsonify({"success": False, "error": "config 必须是合法 JSON"}), 400

    if not isinstance(config_data, dict):
        return jsonify({"success": False, "error": "config 必须是对象"}), 400

    config_validation_error = _validate_dynamic_config(config_data)
    if config_validation_error:
        return jsonify({"success": False, "error": config_validation_error}), 400

    from .. import config as app_config
    requested_llm_model = config_data.get("llm_model")
    resolved_llm_model = app_config.resolve_llm_model(requested_llm_model)
    if requested_llm_model and resolved_llm_model != requested_llm_model:
        logger.warning("语音接口请求的 llm_model=%s 未受支持，已回退至 %s", requested_llm_model, resolved_llm_model)

    dynamic_params = {
        "temperature": config_data.get("temperature", getattr(app_config, 'RAG_TEMPERATURE', 0.2)),
        "top_k": config_data.get("top_k", app_config.RAG_TOP_K),
        "messages_to_keep": config_data.get("messages_to_keep", app_config.MEMORY_MESSAGES_TO_KEEP),
        "max_tokens": config_data.get("max_tokens", app_config.LLM_MAX_TOKENS),
        "llm_model": resolved_llm_model,
    }
    voice_web_search = bool(config_data.get("web_search_enabled"))
    if voice_web_search and not WebSearchService.get_instance().is_available():
        logger.warning("语音接口请求启用联网搜索，但后端未启用该功能或缺少 Tavily API Key")

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
            # 创建 AgentRuntime 实例（传递动态参数）
            runtime = get_runtime(
                session_id=session_id,
                temperature=dynamic_params["temperature"],
                top_k=dynamic_params["top_k"],
                messages_to_keep=dynamic_params["messages_to_keep"],
                max_tokens=dynamic_params["max_tokens"],
                use_web_search=voice_web_search,
                llm_model=dynamic_params["llm_model"],
            )

            # 使用新的 AgentRuntime 调用
            reply_text = runtime.invoke(
                transcript,
                thread_id=session_id,
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
    
