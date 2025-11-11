/**
 * 应用配置常量
 */

// API 基础 URL
// 优先使用环境变量，如果没有则根据当前域名自动判断
// 开发环境：http://localhost:5000/api
// 生产环境：使用当前页面的协议和主机名，端口 5000
const getApiBaseUrl = (): string => {
  // 如果设置了环境变量，直接使用
  if (import.meta.env.VITE_API_BASE_URL) {
    console.log('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL);
    const url = import.meta.env.VITE_API_BASE_URL;
    // 如果是相对路径（以 / 开头），需要转换为完整 URL（包含端口）
    if (url.startsWith('/')) {
      // 相对路径会自动使用当前页面的协议和主机，但不会包含端口
      // 我们需要手动添加端口 5000（后端端口）
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;
      return `${protocol}//${hostname}:5000${url}`;
    }
    // 如果是完整 URL，直接返回
    return url;
  }
  
  // 开发环境：使用 localhost
  if (import.meta.env.DEV) {
    console.log('DEV', import.meta.env.DEV);
    return 'http://localhost:5000/api';
  }
  
  // 生产环境：使用当前页面的协议和主机名
  // 如果前端和后端在同一台服务器，使用相对路径更安全
  // 如果前端和后端在不同服务器，需要设置 VITE_API_BASE_URL
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  
  // 如果是 localhost 或 127.0.0.1，说明是本地开发
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:5000/api';
  }
  
  // 生产环境：使用当前域名 + 端口 5000
  // 如果后端在同一个域名下，可以使用相对路径
  return `${protocol}//${hostname}:5000/api`;
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