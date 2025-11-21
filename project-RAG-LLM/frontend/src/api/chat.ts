/**
 * 聊天相关的 API 调用
 */
import axios from 'axios';
import { API_BASE_URL } from '../constants/config';
import type { ChatResponse, VoiceChatResponse, ChatStreamChunk, SearchSource } from '../types';

const chatAPI = {
  /**
   * 发送聊天消息
   * @param message - 用户消息
   * @param sessionId - 会话ID
   * @returns 响应数据
   */
  sendMessage: async (message: string, sessionId: string | null = null): Promise<ChatResponse> => {
    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message,
        session_id: sessionId,
      });
      // console.log("成功获取到message")
      return response.data;
    } catch (error) {
      console.error('发送消息失败:', error);
      throw error;
    }
  },

  /**
   * 获取聊天历史
   * @param sessionId - 会话ID
   * @returns 聊天历史
   */
  getChatHistory: async (sessionId: string): Promise<any> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/chat/history/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error('获取聊天历史失败:', error);
      throw error;
    }
  },

  /**
   * 以流式方式发送聊天消息（SSE over fetch）
   * 返回一个异步迭代器，逐块产出字符串内容
   * @param message - 用户消息
   * @param sessionId - 会话ID
   * @param config - 可选的配置对象（支持动态参数：temperature, top_k, messages_to_keep 等）
   */
  sendMessageStream: (
    message: string,
    sessionId: string | null = null,
    config: Record<string, any> | null = null,
    signal?: AbortSignal
  ): AsyncIterable<ChatStreamChunk> => {
    async function* iterator() {
      const requestBody = {
        message,
        session_id: sessionId,
        config: config,  // 传递配置对象
      };
      
      // 【调试日志】记录发送的完整请求
      console.log('📤 发送 /chat/stream 请求:', {
        url: `${API_BASE_URL}/chat/stream`,
        body: requestBody,
      });
      
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(requestBody),
        signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`网络错误: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE 按双换行分隔事件
          let idx;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const rawEvent = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            // 仅解析以 data: 开头的行
            const lines = rawEvent.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data) {
                  let parsed: unknown = data;
                  try {
                    parsed = JSON.parse(data);
                  } catch {
                    parsed = data;
                  }
                  if (typeof parsed === 'string') {
                    yield { type: 'text', content: parsed };
                  } else if (parsed && typeof parsed === 'object') {
                    const chunk = parsed as Record<string, unknown>;
                    if (chunk.type === 'sources') {
                      const sources = Array.isArray(chunk.sources) ? (chunk.sources as SearchSource[]) : [];
                      yield {
                        type: 'sources',
                        sources,
                        web_search_used: Boolean(chunk.web_search_used),
                      };
                    } else {
                      const rawContent = (chunk as Record<string, unknown>).content;
                      const content = typeof rawContent === 'string'
                        ? rawContent
                        : String(rawContent ?? '');
                      yield { type: 'text', content };
                    }
                  }
                }
              }
              // 可选：处理 event: done / error
            }
          }
        }
        // 处理尾部残留
        if (buffer.trim()) {
          const lines = buffer.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data) {
                let parsed: unknown = data;
                try {
                  parsed = JSON.parse(data);
                } catch {
                  parsed = data;
                }
                if (typeof parsed === 'string') {
                  yield { type: 'text', content: parsed };
                } else if (parsed && typeof parsed === 'object') {
                  const chunk = parsed as Record<string, unknown>;
                  if (chunk.type === 'sources') {
                    const sources = Array.isArray(chunk.sources) ? (chunk.sources as SearchSource[]) : [];
                    yield {
                      type: 'sources',
                      sources,
                      web_search_used: Boolean(chunk.web_search_used),
                    };
                  } else {
                    const rawContent = (chunk as Record<string, unknown>).content;
                    const content = typeof rawContent === 'string'
                      ? rawContent
                      : String(rawContent ?? '');
                    yield { type: 'text', content };
                  }
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    }

    return {
      [Symbol.asyncIterator]() {
        return iterator();
      },
    } as AsyncIterable<string>;
  },

  /**
   * 上传语音音频并返回转写结果（可按需返回即时回答）。
   */
  sendVoiceMessage: async (
    audioBlob: Blob,
    sessionId: string | null = null,
    config: Record<string, any> | null = null,
    transcribeOnly = true,
  ): Promise<VoiceChatResponse> => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice-input.webm');
    if (sessionId) {
      formData.append('session_id', sessionId);
    }
    if (config) {
      formData.append('config', JSON.stringify(config));
    }
    formData.append('transcribe_only', transcribeOnly ? 'true' : 'false');

    const response = await fetch(`${API_BASE_URL}/chat/voice`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || '语音接口调用失败');
    }

    return response.json();
  },

  /**
   * 请求语音播报指定文本。
   */
  requestVoiceReply: async (text: string): Promise<Blob> => {
    const response = await fetch(`${API_BASE_URL}/chat/voice/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || '语音回复接口调用失败');
    }

    return response.blob();
  },
};

export default chatAPI;
