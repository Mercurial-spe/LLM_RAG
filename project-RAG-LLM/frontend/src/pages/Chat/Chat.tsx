/**
 * 聊天对话页面
 */
import { useState, useRef, useEffect } from 'react';
import chatAPI from '../../api/chat';
import useSettings from '../../hooks/useSettings';
import { useConversationStore } from '../../stores/conversationStore';
import ConversationSidebar from '../../components/ConversationSidebar/ConversationSidebar';
import type { Message } from '../../types';
import './Chat.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import documentAPI from '../../api/document';
import { SUPPORTED_FILE_TYPES, MAX_FILE_SIZE } from '../../constants/config';
import { formatFileSize, formatDateTime, validateFileType } from '../../utils/helpers';
import userAvatar from '../../assets/user-avatar.png';
import aiAvatar from '../../assets/ai-avatar.png';
import ragFlowImg from '../../assets/RAGFLOW_LangChain.png';

// 快速设置组件
const ChatSettings = () => {
  const [showSettings, setShowSettings] = useState(false);
  const { settings, updateSettings } = useSettings();

  const handleQuickUpdate = (key: keyof typeof settings, value: any) => {
    console.log(`⚡ 快速设置变更: ${key} = ${value}`);
    updateSettings({ [key]: value });
  };

  return (
    <div className="chat-settings">
      <button 
        className="settings-toggle"
        onClick={() => setShowSettings(!showSettings)}
        title="快速设置"
      >
        ⚙️
      </button>
      
      {showSettings && (
        <div className="quick-settings">
          <div className="setting-group">
            <label>温度: {settings.temperature.toFixed(1)}</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.temperature}
              onChange={(e) => handleQuickUpdate('temperature', parseFloat(e.target.value))}
            />
          </div>
          
          <div className="setting-group">
            <label>Top K: {settings.topK}</label>
            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={settings.topK}
              onChange={(e) => handleQuickUpdate('topK', parseInt(e.target.value))}
            />
          </div>
          
          <div className="setting-group">
            <label>保留消息: {settings.messagesToKeep}</label>
            <input
              type="range"
              min="10"
              max="100"
              step="5"
              value={settings.messagesToKeep}
              onChange={(e) => handleQuickUpdate('messagesToKeep', parseInt(e.target.value))}
            />
          </div>
        </div>
      )}
    </div>
  );
};

const Chat = () => {
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadFileName, setUploadFileName] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const { getRagConfig, isLoaded } = useSettings();
  
  // 使用 Zustand store 管理对话状态
  const {
    currentThreadId,
    currentMessages,
    conversations,
    loadConversations,
    createNewConversation,
    loadMessages,
    addMessage,
    appendToMessage,
    sessionDocuments,
    loadSessionDocuments,
    addSessionDocument,
  } = useConversationStore();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages]);
  
  // 初始化：加载对话列表
  useEffect(() => {
    const initializeConversations = async () => {
      console.log('🔄 初始化对话系统...');
      await loadConversations();

      // 使用最新的 store 状态做决策，避免闭包中的旧值
      const { currentThreadId: latestThreadId, conversations: latestConvs } = useConversationStore.getState();

      if (latestThreadId && latestConvs.some(c => c.thread_id === latestThreadId)) {
        console.log('📥 恢复上次对话:', latestThreadId);
        await loadMessages(latestThreadId);
      } else if (latestConvs.length > 0) {
        console.log('📥 加载最新对话');
        await loadMessages(latestConvs[0].thread_id);
      } else {
        console.log('ℹ️ 当前没有任何历史对话，等待用户创建新对话');
      }
    };

    initializeConversations();
  }, [loadConversations, loadMessages]); // 只在依赖稳定时执行一次

  // 当当前对话变化时，加载该对话的文件列表
  useEffect(() => {
    const loadDocsForCurrent = async () => {
      if (!currentThreadId) return;
      await loadSessionDocuments(currentThreadId);
    };
    loadDocsForCurrent();
  }, [currentThreadId, loadSessionDocuments]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // 确保有当前会话 ID，没有则先创建
    let targetThreadId = currentThreadId;
    if (!targetThreadId) {
      console.warn('⚠️ 没有当前对话，上传前先创建新对话...');
      const newId = await createNewConversation('新对话');
      if (!newId) {
        alert('创建新对话失败，无法上传文档。');
        return;
      }
      targetThreadId = newId;
    }

    for (const file of Array.from(files)) {
      // 验证文件类型
      if (!validateFileType(file, SUPPORTED_FILE_TYPES)) {
        alert(`不支持的文件类型：${file.name}。支持的格式：${SUPPORTED_FILE_TYPES.join(', ')}`);
        continue;
      }

      // 验证文件大小
      if (file.size > MAX_FILE_SIZE) {
        alert(`文件大小超过限制：${file.name}。最大支持 ${formatFileSize(MAX_FILE_SIZE)}`);
        continue;
      }

      try {
        setIsUploading(true);
        setUploadFileName(file.name);
        const res = await documentAPI.uploadDocument(file, targetThreadId);

        // 乐观更新当前会话的文档列表
        addSessionDocument(targetThreadId, {
          id: res.path || res.filename,
          session_id: res.session_id,
          file_name: res.original_filename || file.name,
          stored_path: res.path,
          size: res.size,
          uploaded_at: res.uploaded_at,
          status: 'processed',
        });
      } catch (error) {
        console.error('❌ 上传文档失败:', error);
        alert(`上传文档失败：${file.name}`);
      } finally {
        setIsUploading(false);
        setUploadFileName('');
      }
    }

    // 清空 input 值，以便可以上传同名文件
    event.target.value = '';
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading || !isLoaded) {
      return;
    }

    // 确保一定有一个可用的 threadId；如果没有则先创建
    let targetThreadId = currentThreadId;
    if (!targetThreadId) {
      console.warn('⚠️ 没有当前对话，尝试创建新对话...');
      const newId = await createNewConversation('新对话');
      if (!newId) {
        console.error('❌ 创建新对话失败，无法发送消息');
        return;
      }
      targetThreadId = newId;
    }

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    // 添加到 store
    addMessage(userMessage);
    setInput('');
    setIsLoading(true);

    try {
      // 先插入一个空的助手消息，占位并逐步填充
      const assistantId = Date.now() + 1;
      const assistantMessage: Message = {
        id: assistantId,
        type: 'assistant',
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      addMessage(assistantMessage);

      // 获取当前 RAG 配置并使用流式接口逐块更新内容
      const ragConfig = getRagConfig();
      console.log('📤 发送消息到对话:', targetThreadId);
      console.log('📤 RAG配置:', ragConfig);
      
      // 使用当前 threadId 发送消息
      for await (const chunk of chatAPI.sendMessageStream(
        userMessage.content, 
        targetThreadId,  // 使用当前对话 ID
        ragConfig
      )) {
        // 追加消息内容（使用 appendToMessage 避免状态不同步问题）
        appendToMessage(assistantId, chunk);
      }
      
      // 重新加载对话列表以更新时间和消息数
      await loadConversations();
      
    } catch (error) {
      console.error('❌ 发送消息错误:', error);
      const errorMessage: Message = {
        id: Date.now() + 2,
        type: 'error',
        content: '抱歉，发送消息时出现错误，请稍后再试。',
        timestamp: new Date(),
      };
      addMessage(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page-layout">
      {/* 左侧边栏 - 对话列表 */}
      <ConversationSidebar />
      
      {/* 主聊天区域 */}
      <div className="chat-container">
        <div className="chat-header">
          <h2> SCUT 计算机网络助手</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {/* 当前对话文件上传 */}
            <label className="upload-button" style={{ marginRight: '0.5rem', cursor: 'pointer' }}>
              <input
                type="file"
                multiple
                onChange={handleFileUpload}
                accept={SUPPORTED_FILE_TYPES.join(',')}
                style={{ display: 'none' }}
              />
              📤 上传文档
            </label>
            <ChatSettings />
          </div>
        </div>

        {/* 当前对话文件列表 */}
        {currentThreadId && (
          <div className="session-documents">
            <div className="session-documents-header">
              <span>
                📂 当前对话文件
                {(() => {
                  const conv = conversations.find(c => c.thread_id === currentThreadId);
                  return conv ? `（${conv.title}）` : '';
                })()}
              </span>
              {isUploading && uploadFileName && (
                <span className="session-documents-uploading">
                  正在上传：{uploadFileName}
                </span>
              )}
            </div>
            <div className="session-documents-list">
              {sessionDocuments[currentThreadId]?.length ? (
                sessionDocuments[currentThreadId].map((doc) => (
                  <div key={doc.id} className="session-document-item">
                    <span className="session-document-icon">📄</span>
                    <span className="session-document-name" title={doc.file_name}>
                      {doc.file_name}
                    </span>
                    <span className="session-document-size">
                      {formatFileSize(doc.size)}
                    </span>
                    <span className="session-document-time">
                      {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : '-'}
                    </span>
                  </div>
                ))
              ) : (
                <div className="session-documents-empty">
                  该对话还没有上传任何文档，可以点击上方“上传文档”按钮。
                </div>
              )}
            </div>
          </div>
        )}

        <div className="messages-container">
          {currentMessages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-content">
                <img src={ragFlowImg} alt="RAG流程" className="empty-state-image" />
                <h3>👋 你好！我是你的 AI 助手</h3>
                <p>我可以帮你解答关于计算机网络的问题</p>
                <p className="empty-hint">💡 提示：你可以先上传文档，然后基于文档内容提问</p>
              </div>
            </div>
          ) : (
            currentMessages
              .filter((message) => message.content && message.content.trim().length > 0)  // 过滤空内容消息
              .map((message) => (
                <div key={message.id} className={`message ${message.type}`}>
                  <div className="message-avatar">
                    <img 
                      src={message.type === 'user' ? userAvatar : aiAvatar} 
                      alt={message.type === 'user' ? '用户头像' : 'AI助手头像'}
                      className="avatar-image"
                    />
                  </div>
                  <div className="message-content">
                    {message.type === 'assistant' ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeHighlight]}
                      >
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      <p style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{message.content}</p>
                    )}
                    <span className="message-time">
                      {typeof message.timestamp === 'string' 
                        ? new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                        : message.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                      }
                    </span>
                  </div>
                </div>
              ))
          )}
          {isLoading && (
            <div className="message assistant">
              <div className="message-avatar">
                <img 
                  src={aiAvatar} 
                  alt="AI助手头像"
                  className="avatar-image"
                />
              </div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
            rows={3}
            disabled={isLoading}
          />
          <button onClick={handleSend} disabled={!input.trim() || isLoading}>
            {isLoading ? '发送中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chat;

