/**
 * 聊天对话页面
 */
import { useState, useRef, useEffect } from 'react';
import chatAPI from '../../api/chat';
import useSettings from '../../hooks/useSettings';
import type { Message } from '../../types';
import './Chat.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

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
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const { getRagConfig, isLoaded } = useSettings();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading || !isLoaded) return;

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // 先插入一个空的助手消息，占位并逐步填充
      const assistantId = Date.now() + 1;
      const assistantMessage: Message = {
        id: assistantId,
        type: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // 获取当前 RAG 配置并使用流式接口逐块更新内容
      const ragConfig = getRagConfig();
      console.log('📤 发送消息，RAG配置:', ragConfig);
      console.log('📋 完整请求信息:', {
        message: userMessage.content,
        sessionId: null,
        config: ragConfig,
      });
      
      // 添加强制检查
      if (!ragConfig || Object.keys(ragConfig).length === 0) {
        console.error('❌ 警告：RAG配置为空!', { ragConfig });
      } else {
        console.log('✅ RAG配置包含数据，共', Object.keys(ragConfig).length, '个键');
      }
      
      for await (const chunk of chatAPI.sendMessageStream(
        userMessage.content, 
        null, // sessionId，暂时使用 null 让后端使用默认值
        ragConfig // 传递 RAG 配置
      )) {
        setMessages((prev) => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + chunk } : m
        ));
      }
    } catch (error) {
      console.error('❌ 发送消息错误:', error);
      const errorMessage: Message = {
        id: Date.now() + 1,
        type: 'error',
        content: '抱歉，发送消息时出现错误，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
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
    <div className="chat-container">
      <div className="chat-header">
        <h2>智能对话</h2>
        <ChatSettings />
      </div>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            <p>👋 你好！我是你的 AI 助手，有什么可以帮助你的吗？</p>
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className={`message ${message.type}`}>
              <div className="message-avatar">
                {message.type === 'user' ? '👤' : '🤖'}
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
                  {message.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="message assistant">
            <div className="message-avatar">🤖</div>
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
  );
};

export default Chat;

