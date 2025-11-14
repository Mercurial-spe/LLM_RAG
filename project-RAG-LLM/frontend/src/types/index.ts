// 聊天相关类型
export interface Message {
    id: number;
    type: 'user' | 'assistant' | 'error';
    content: string;
    timestamp: Date;
  }
  
  export interface ChatResponse {
    answer?: string;
    message?: string;
    session_id?: string;
  }
  
  // 文档相关类型
  export interface Document {
    id: string;
    name: string;
    size: number;
    created_at: string;
    status?: 'processed' | 'processing';
  }
  
  export interface DocumentResponse {
    documents: Document[];
  }
  
  export interface UploadResponse {
    message: string;
    document_id: string;
  }
  
  // API 响应基础类型
  export interface ApiResponse<T = any> {
    success: boolean;
    data?: T;
    message?: string;
    error?: string;
  }
  
  // 导航项类型
  export interface NavItem {
    path: string;
    label: string;
    icon: string;
  }
  
  // 上传进度类型
  export interface UploadProgress {
    name: string;
    progress: number;
  }
  
  // RAG 配置类型
  export interface RagConfig {
    temperature?: number;    // LLM 温度参数 (0-2)
    top_k?: number;          // RAG 检索的文档数量 (1-20)
    messages_to_keep?: number; // 记忆压缩后保留的消息数 (10-100)
  }
  
  // 应用设置类型
  export interface AppSettings {
    apiUrl: string;
    temperature: number;
    maxTokens: number;
    topK: number;
    messagesToKeep: number;
  }