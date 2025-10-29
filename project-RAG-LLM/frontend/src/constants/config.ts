/**
 * 应用配置常量
 */

// API 基础 URL
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api';

// 应用名称
export const APP_NAME: string = 'RAG-LLM 问答系统';

// 路由路径
export const ROUTES = {
  HOME: '/',
  CHAT: '/chat',
  DOCUMENTS: '/documents',
  SETTINGS: '/settings',
} as const;

// 支持的文档类型
export const SUPPORTED_FILE_TYPES: readonly string[] = [
  '.pdf',
  '.docx',
  '.txt',
  '.md',
] as const;

// 最大文件大小（字节）
export const MAX_FILE_SIZE: number = 10 * 1024 * 1024; // 10MB