/**
 * 文档管理相关的 API 调用
 */
import axios from 'axios';
import { API_BASE_URL } from '../constants/config';
import type { DocumentResponse, UploadResponse } from '../types';

const documentAPI = {
  /**
   * 上传文档
   * @param file - 文档文件
   * @returns 上传结果
   */
  uploadDocument: async (file: File): Promise<UploadResponse> => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API_BASE_URL}/documents/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('上传文档失败:', error);
      throw error;
    }
  },

  /**
   * 获取文档列表
   * @returns 文档列表
   */
  getDocuments: async (): Promise<DocumentResponse> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/documents`);
      return response.data;
    } catch (error) {
      console.error('获取文档列表失败:', error);
      throw error;
    }
  },

  /**
   * 删除文档
   * @param documentId - 文档ID
   * @returns 删除结果
   */
  deleteDocument: async (documentId: string): Promise<any> => {
    try {
      const response = await axios.delete(`${API_BASE_URL}/documents/${documentId}`);
      return response.data;
    } catch (error) {
      console.error('删除文档失败:', error);
      throw error;
    }
  },
};

export default documentAPI;