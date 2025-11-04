/**
 * 聊天相关的 API 调用
 */
import axios from 'axios';
import { API_BASE_URL } from '../constants/config';
import type { ChatResponse } from '../types';

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
   */
  sendMessageStream: (
    message: string,
    sessionId: string | null = null,
  ): AsyncIterable<string> => {
    async function* iterator() {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({ message, session_id: sessionId }),
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
                  // 后端使用 JSON 编码传输，需要解码以还原换行符
                  try {
                    yield JSON.parse(data);
                  } catch {
                    // 降级：如果解析失败，直接返回原始字符串
                    yield data;
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
                // 后端使用 JSON 编码传输，需要解码以还原换行符
                try {
                  yield JSON.parse(data);
                } catch {
                  // 降级：如果解析失败，直接返回原始字符串
                  yield data;
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
};

export default chatAPI;