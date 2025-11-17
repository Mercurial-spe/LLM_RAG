/**
 * 对话管理相关的 API 调用
 */
import axios from 'axios';
import { API_BASE_URL } from '../constants/config';
import type { Conversation, Message } from '../types';

const conversationAPI = {
  /**
   * 获取所有对话列表
   * @returns 对话列表
   */
  getConversations: async (): Promise<Conversation[]> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/conversations`);
      if (response.data.success) {
        return response.data.conversations || [];
      }
      console.error('获取对话列表失败:', response.data.error);
      return [];
    } catch (error) {
      console.error('获取对话列表失败:', error);
      return [];
    }
  },

  /**
   * 获取指定对话的消息历史
   * @param threadId - 对话 ID
   * @returns 消息列表
   */
  getConversationMessages: async (threadId: string): Promise<Message[]> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/conversations/${threadId}/messages`);
      if (response.data.success) {
        const messages = response.data.messages || [];
        // 转换后端格式为前端格式，并过滤掉内容为空的消息
        return messages
          .filter((msg: any) => msg.content && msg.content.trim().length > 0)  // 过滤空内容
          .map((msg: any, index: number) => ({
            id: Date.now() + index,  // 生成唯一 ID
            type: msg.role === 'user' ? 'user' : 'assistant',
            role: msg.role,
            content: msg.content,
            timestamp: typeof msg.timestamp === 'string' ? new Date(msg.timestamp) : msg.timestamp
          }));
      }
      console.error('获取对话消息失败:', response.data.error);
      return [];
    } catch (error) {
      console.error('获取对话消息失败:', error);
      return [];
    }
  },

  /**
   * 创建新对话
   * @param title - 对话标题（可选）
   * @returns 新对话信息
   */
  createConversation: async (title: string = '新对话'): Promise<{ thread_id: string; title: string } | null> => {
    try {
      const response = await axios.post(`${API_BASE_URL}/conversations`, { title });
      if (response.data.success) {
        return {
          thread_id: response.data.thread_id,
          title: response.data.title
        };
      }
      console.error('创建对话失败:', response.data.error);
      return null;
    } catch (error) {
      console.error('创建对话失败:', error);
      return null;
    }
  },

  /**
   * 删除对话
   * @param threadId - 对话 ID
   * @returns 是否删除成功
   */
  deleteConversation: async (threadId: string): Promise<boolean> => {
    try {
      const response = await axios.delete(`${API_BASE_URL}/conversations/${threadId}`);
      return response.data.success === true;
    } catch (error) {
      console.error('删除对话失败:', error);
      return false;
    }
  },

  /**
   * 更新对话标题
   * @param threadId - 对话 ID
   * @param title - 新标题
   * @returns 是否更新成功
   */
  updateConversationTitle: async (threadId: string, title: string): Promise<boolean> => {
    try {
      const response = await axios.patch(`${API_BASE_URL}/conversations/${threadId}`, { title });
      return response.data.success === true;
    } catch (error) {
      console.error('更新对话标题失败:', error);
      return false;
    }
  }
};

export default conversationAPI;

