/**
 * 聊天对话页面
 */
import { useState, useRef, useEffect } from 'react';
import chatAPI from '../../api/chat';
import type { Message } from '../../types';
import './Chat.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

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

      // 使用流式接口逐块更新内容
      for await (const chunk of chatAPI.sendMessageStream(userMessage.content)) {
        setMessages((prev) => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + chunk } : m
        ));
      }
    } catch (error) {
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

