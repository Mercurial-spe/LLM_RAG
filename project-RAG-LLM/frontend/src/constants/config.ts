/**
 * 应用配置常量
 */

// API 基础 URL
// 优先使用环境变量，如果没有则根据当前域名自动判断
// 开发环境：http://localhost:5000/api
// 生产环境（Nginx）：/api（相对路径，由 Nginx 反向代理）
const getApiBaseUrl = (): string => {
  // 如果设置了环境变量，直接使用
  if (import.meta.env.VITE_API_BASE_URL) {
    console.log('[Config] Using VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
    return import.meta.env.VITE_API_BASE_URL;
  }
  
  // 开发环境：使用 localhost:5000（直接访问后端，需要 CORS）
  if (import.meta.env.DEV) {
    console.log('[Config] Development mode: using localhost:5000');
    return 'http://localhost:5000/api';
  }
  
  // 生产环境：使用相对路径（通过 Nginx 反向代理，无跨域问题）
  console.log('[Config] Production mode: using relative path /api');
  return '/api';
};

export const API_BASE_URL: string = getApiBaseUrl();

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