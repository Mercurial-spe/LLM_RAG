// 联网搜索结果
export interface SearchSource {
  title: string;
  url?: string;
  snippet?: string;
  score?: number;
  source?: string;
}

// 聊天相关类型
export interface Message {
  id: number;
  type: 'user' | 'assistant' | 'error';
  role?: 'user' | 'assistant';  // 新增：兼容后端格式
  content: string;
  timestamp: Date | string;  // 支持字符串格式的时间戳
  webSearchSources?: SearchSource[];
  webSearchUsed?: boolean;
  webSearchRequested?: boolean;
}
  
  // 对话相关类型
  export interface Conversation {
    thread_id: string;
    title: string;
    last_message_time: string;
    message_count: number;
    checkpoint_count?: number;  // 可选：checkpoint 数量
  }
  
export interface ChatResponse {
    answer?: string;
    message?: string;
    session_id?: string;
  }

export type ChatStreamChunk =
  | { type: 'text'; content: string }
  | { type: 'sources'; sources: SearchSource[]; web_search_used?: boolean };
  
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
  
  // 单次上传返回（与后端 /documents/upload 对齐）
  export interface UploadResponse {
    message: string;
    session_id: string;
    filename: string;           // 存储名（带时间戳）
    original_filename: string;  // 原始文件名（用户看到的名字）
    size: number;
    chunks_processed: number;
    path: string;
    uploaded_at: string;
  }
  
  // 会话级文档（按 thread_id/session_id 聚合后的文件级信息）
  export interface SessionDocument {
    id: string;
    session_id: string;
    file_name: string;       // 原始文件名，UI 主展示字段
    stored_path: string;     // 后端返回的路径（source）
    size: number;
    uploaded_at: string;
    status?: 'processed' | 'processing';
  }
  
  export interface SessionDocumentResponse {
    documents: SessionDocument[];
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
    max_tokens?: number;
    web_search_enabled?: boolean;
    llm_model?: string;      // 运行期可切换的 LLM 模型
  }
  
  // 应用设置类型
export interface AppSettings {
    apiUrl: string;
    temperature: number;
    maxTokens: number;
    topK: number;
    messagesToKeep: number;
    voiceInputEnabled: boolean;
    voiceAutoSend: boolean;
    voiceReplyEnabled: boolean;
    webSearchEnabled: boolean;
    llmModel: string;
  }

export interface VoiceChatResponse {
    success: boolean;
    session_id: string;
    transcript: string;
    reply?: string;
}
