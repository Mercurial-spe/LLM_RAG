from __future__ import annotations

import base64
import io
import logging
from typing import Optional, Any

import httpx
from dashscope.audio.qwen_tts import SpeechSynthesizer
from werkzeug.datastructures import FileStorage

from .. import config

logger = logging.getLogger(__name__)

ASR_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DOWNLOAD_TIMEOUT = 60


class SpeechServiceError(RuntimeError):
    """Raised when audio transcription or synthesis fails."""


def _validate_audio_file(file_storage: FileStorage) -> bytes:
    """Ensure file meets duration/size requirements and return raw bytes."""
    if not file_storage or not getattr(file_storage, "stream", None):
        raise SpeechServiceError("未检测到上传的音频文件")

    file_storage.stream.seek(0, io.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size == 0:
        raise SpeechServiceError("音频文件为空")
    if size > config.QWEN_MAX_AUDIO_SIZE:
        raise SpeechServiceError("音频文件超过大小限制")

    data = file_storage.read()
    if not data:
        raise SpeechServiceError("无法读取音频文件")
    return data


def _detect_audio_format(file_storage: FileStorage) -> str:
    """Infer audio format from mimetype or filename."""
    mime = (file_storage.mimetype or "").lower()
    filename = (file_storage.filename or "").lower()
    if "wav" in mime or filename.endswith(".wav"):
        return "wav"
    if "mp3" in mime or filename.endswith(".mp3"):
        return "mp3"
    if "webm" in mime or filename.endswith(".webm"):
        return "webm"
    if "ogg" in mime or filename.endswith(".ogg"):
        return "ogg"
    return "wav"


def _extract_transcript_from_data(data: dict[str, Any]) -> Optional[str]:
    """Try multiple known response patterns to get transcript text."""
    if not isinstance(data, dict):
        return None

    output_text = data.get("output_text")
    if isinstance(output_text, list):
        for item in output_text:
            if isinstance(item, str) and item.strip():
                return item.strip()

    output = data.get("output")
    if isinstance(output, dict):
        direct_text = output.get("text")
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        choices = output.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                message = choice.get("message") if isinstance(choice, dict) else None
                if not isinstance(message, dict):
                    continue
                contents = message.get("content")
                if isinstance(contents, list):
                    for block in contents:
                        if isinstance(block, dict):
                            text = block.get("text")
                            if isinstance(text, str) and text.strip():
                                return text.strip()

        contents = output.get("content")
        if isinstance(contents, list):
            for block in contents:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()

    if isinstance(output, list):
        for item in output:
            contents = item.get("content") if isinstance(item, dict) else None
            if not isinstance(contents, list):
                continue
            for block in contents:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()

    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                continue
            contents = message.get("content")
            if isinstance(contents, list):
                for block in contents:
                    if isinstance(block, dict):
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            return text.strip()
    return None


def transcribe_audio(file_storage: FileStorage) -> str:
    """Send audio to DashScope ASR and return transcript text."""
    audio_bytes = _validate_audio_file(file_storage)
    audio_format = _detect_audio_format(file_storage)

    if not config.DASHSCOPE_API_KEY:
        raise SpeechServiceError("DASHSCOPE_API_KEY 未配置，无法使用语音识别")

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    data_url = f"data:audio/{audio_format};base64,{audio_b64}"
    payload = {
        "model": config.QWEN_ASR_MODEL,
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {"text": "请精准地将音频转写为文本，只返回识别结果。"}
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {"audio": data_url}
                    ]
                }
            ]
        },
        "result_format": "text",
    }

    headers = {
        "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            ASR_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=DOWNLOAD_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.error("调用 DashScope ASR 网络异常: %s", exc, exc_info=True)
        raise SpeechServiceError("语音识别请求失败，请检查网络连接")

    if response.status_code >= 400:
        logger.error(
            "调用 DashScope ASR 失败 status=%s body=%s",
            response.status_code,
            response.text,
        )
        raise SpeechServiceError("语音识别失败，请检查 DashScope 配置或配额")

    data = response.json()
    transcript = _extract_transcript_from_data(data)
    if not transcript:
        logger.error("DashScope ASR 返回无有效文本: %s", data)
        raise SpeechServiceError("语音识别未返回文本，请稍后重试")
    return transcript.strip()


def synthesize_audio(text: str) -> bytes:
    """Convert reply text into speech audio bytes."""
    if not text.strip():
        raise SpeechServiceError("合成内容不能为空")
    if not config.DASHSCOPE_API_KEY:
        raise SpeechServiceError("DASHSCOPE_API_KEY 未配置，无法使用语音合成")

    try:
        response = SpeechSynthesizer.call(
            model=config.QWEN_TTS_MODEL,
            api_key=config.DASHSCOPE_API_KEY,
            text=text,
            voice=config.QWEN_SPEECH_VOICE,
            format=config.QWEN_SPEECH_FORMAT,
            sample_rate=config.QWEN_SPEECH_SAMPLE_RATE,
            speed=config.QWEN_SPEECH_SPEED,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("调用 Qwen TTS 失败: %s", exc, exc_info=True)
        raise SpeechServiceError("语音合成失败，请稍后再试")

    audio_bytes = _extract_tts_audio_bytes(response)
    if audio_bytes is None:
        raise SpeechServiceError("语音合成接口未返回音频数据")
    return audio_bytes


def _extract_tts_audio_bytes(response) -> Optional[bytes]:
    """Extract audio bytes from DashScope TTS response, downloading if needed."""
    audio_data = _safe_getattr(response, "audio_data")
    if isinstance(audio_data, str) and audio_data.strip():
        try:
            return base64.b64decode(audio_data)
        except Exception as exc:
            logger.warning("base64 解码 TTS 音频失败: %s", exc)

    data_dict = _response_to_dict(response)
    if not isinstance(data_dict, dict):
        return None

    output = data_dict.get("output", {})
    audio_info = output.get("audio", {}) if isinstance(output, dict) else {}

    audio_data = audio_info.get("data")
    if isinstance(audio_data, str) and audio_data.strip():
        try:
            return base64.b64decode(audio_data)
        except Exception as exc:
            logger.warning("base64 解码 TTS 音频失败: %s", exc)

    audio_url = audio_info.get("url")
    if not audio_url and isinstance(output, dict):
        audio_url = output.get("audio_url")

    if audio_url:
        try:
            resp = httpx.get(audio_url, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            logger.error("下载 TTS 音频失败: %s", exc, exc_info=True)
            return None
    return None


def _safe_getattr(obj, attr, default=None):
    try:
        return getattr(obj, attr)
    except AttributeError:
        return default
    except KeyError:
        return default


def _response_to_dict(response) -> Optional[dict]:
    """Best-effort conversion of DashScope SDK response to dict."""
    if isinstance(response, dict):
        return response
    to_dict = getattr(response, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except Exception:
            pass
    output = getattr(response, "output", None)
    if isinstance(output, dict):
        return {"output": output}
    return None
