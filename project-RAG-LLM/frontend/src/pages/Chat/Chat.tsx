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

          <div className="setting-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={settings.voiceInputEnabled}
                onChange={(e) => handleQuickUpdate('voiceInputEnabled', e.target.checked)}
              />
              启用语音输入
            </label>
          </div>

          <div className="setting-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={settings.voiceAutoSend}
                onChange={(e) => handleQuickUpdate('voiceAutoSend', e.target.checked)}
              />
              语音识别后自动发送
            </label>
          </div>

          <div className="setting-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={settings.voiceReplyEnabled}
                onChange={(e) => handleQuickUpdate('voiceReplyEnabled', e.target.checked)}
              />
              启用语音播报
            </label>
          </div>
        </div>
      )}
    </div>
  );
};

type VoiceProcess = 'idle' | 'recording' | 'transcribing' | 'thinking' | 'speaking';

const Chat = () => {
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadFileName, setUploadFileName] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const { getRagConfig, isLoaded, settings } = useSettings();
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const [supportsRecording, setSupportsRecording] = useState(false);
  const [pendingTranscript, setPendingTranscript] = useState('');
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const [lastVoiceMessageId, setLastVoiceMessageId] = useState<number | null>(null);
  const [voiceProcess, setVoiceProcess] = useState<VoiceProcess>('idle');
  const voiceStreamAbortRef = useRef<AbortController | null>(null);
  const [voiceFlowActive, setVoiceFlowActive] = useState(false);
  const voiceStatusText: Record<VoiceProcess, string> = {
    idle: '语音助手待命',
    recording: '录音中...',
    transcribing: '正在识别语音...',
    thinking: '正在思考...',
    speaking: '正在播报...',
  };
  
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

  const resolveThreadId = async (): Promise<string> => {
    let targetThreadId = useConversationStore.getState().currentThreadId;
    if (!targetThreadId) {
      console.warn('⚠️ 没有当前对话，尝试创建新对话...');
      const newId = await createNewConversation('新对话');
      if (!newId) {
        throw new Error('创建新对话失败，无法发送消息');
      }
      targetThreadId = newId;
    }
    return targetThreadId;
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentMessages]);

  useEffect(() => {
    const available =
      typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      Boolean(navigator.mediaDevices?.getUserMedia) &&
      typeof MediaRecorder !== 'undefined';
    setSupportsRecording(available);
  }, []);
  
  useEffect(() => {
    return () => {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);
  
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

  const handleSend = async (
    overrideText?: string,
    options?: {
      signal?: AbortSignal;
      voiceFlow?: boolean;
    }
  ) => {
    const textToSend = (overrideText ?? input).trim();
    if (!textToSend || isLoading || !isLoaded) {
      return;
    }

    let targetThreadId: string;
    try {
      targetThreadId = await resolveThreadId();
    } catch (error) {
      console.error('❌ 创建对话失败:', error);
      setRecordingError('创建对话失败，请稍后再试');
      return;
    }

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      role: 'user',
      content: textToSend,
      timestamp: new Date(),
    };

    addMessage(userMessage);
    setInput('');
    setPendingTranscript('');
    if (options?.voiceFlow) {
      setVoiceFlowActive(true);
    }
    setIsLoading(true);

    try {
      const assistantId = Date.now() + 1;
      const assistantMessage: Message = {
        id: assistantId,
        type: 'assistant',
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };
      addMessage(assistantMessage);

      const ragConfig = getRagConfig();
      console.log('📤 发送消息到对话:', targetThreadId);
      console.log('📤 RAG配置:', ragConfig);

      let assistantReply = '';
      for await (const chunk of chatAPI.sendMessageStream(
        textToSend,
        targetThreadId,
        ragConfig,
        options?.signal
      )) {
        appendToMessage(assistantId, chunk);
        assistantReply += chunk;
      }

      await loadConversations();

      if (settings.voiceReplyEnabled && assistantReply.trim()) {
        await playVoiceReply(assistantReply.trim(), assistantId);
      }
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') {
        console.warn('语音流已取消');
      } else {
        console.error('❌ 发送消息错误:', error);
        const errorMessage: Message = {
          id: Date.now() + 2,
          type: 'error',
          content: '抱歉，发送消息时出现错误，请稍后再试。',
          timestamp: new Date(),
        };
        addMessage(errorMessage);
      }
      if (options?.voiceFlow) {
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
      }
    } finally {
      setIsLoading(false);
      if (options?.voiceFlow && (!settings.voiceReplyEnabled || !voiceFlowActive)) {
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
      }
    }
  };

  const handleStopPlayback = () => {
    const audioElement = audioPlayerRef.current;
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setIsSpeaking(false);
    if (voiceFlowActive) {
      setVoiceProcess('idle');
      setVoiceFlowActive(false);
    }
  };

  const playVoiceReply = async (text: string, messageId: number) => {
    if (!settings.voiceReplyEnabled || !text.trim()) {
      return;
    }
    setIsGeneratingAudio(true);
    setRecordingError(null);

    try {
      const audioBlob = await chatAPI.requestVoiceReply(text);
      handleStopPlayback();

      const url = URL.createObjectURL(audioBlob);
      audioUrlRef.current = url;

      const audioElement = audioPlayerRef.current;
      if (!audioElement) {
        console.warn('音频元素尚未就绪，无法播放 TTS');
        return;
      }

      audioElement.src = url;
      audioElement.onended = () => {
        setIsSpeaking(false);
        if (voiceFlowActive) {
          setVoiceProcess('idle');
          setVoiceFlowActive(false);
        }
      };
      if (voiceFlowActive) {
        setVoiceProcess('speaking');
      }
      await audioElement.play();
      setIsSpeaking(true);
      setLastVoiceMessageId(messageId);
    } catch (error) {
      console.error('语音播报失败:', error);
      setRecordingError('语音播报失败，请稍后再试');
      if (voiceFlowActive) {
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
      }
    } finally {
      setIsGeneratingAudio(false);
    }
  };

  const handleVoiceUpload = async (audioBlob: Blob) => {
    if (!settings.voiceInputEnabled) {
      setRecordingError('已关闭语音输入，请在设置中开启');
      return;
    }
    if (audioBlob.size === 0) {
      setRecordingError('未检测到有效音频，请重试');
      return;
    }

    setIsTranscribing(true);
    setRecordingError(null);
    setVoiceProcess('transcribing');
    try {
      const ragConfig = getRagConfig();
      const response = await chatAPI.sendVoiceMessage(
        audioBlob,
        useConversationStore.getState().currentThreadId,
        ragConfig,
        true
      );
      const transcript = response?.transcript?.trim();
      if (!transcript) {
        setRecordingError('语音识别失败，请重试');
        setVoiceProcess('idle');
        return;
      }
      setPendingTranscript(transcript);
      setInput(transcript);
      if (settings.voiceAutoSend) {
        await handleVoiceSend(transcript);
        setPendingTranscript('');
      } else {
        setVoiceProcess('idle');
      }
    } catch (error) {
      console.error('语音识别失败:', error);
      setRecordingError('语音识别失败，请检查网络或权限');
      setVoiceProcess('idle');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleVoiceSend = async (transcript: string) => {
    const controller = new AbortController();
    voiceStreamAbortRef.current = controller;
    setVoiceFlowActive(true);
    setVoiceProcess('thinking');
    try {
      await handleSend(transcript, {
        signal: controller.signal,
        voiceFlow: true,
      });
    } catch (error) {
      console.error('❌ 语音发送失败:', error);
      setRecordingError('语音消息发送失败');
      setVoiceProcess('idle');
      setVoiceFlowActive(false);
    } finally {
      voiceStreamAbortRef.current = null;
      if (!settings.voiceReplyEnabled) {
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
      }
    }
  };

  const handleVoiceButtonClick = () => {
    switch (voiceProcess) {
      case 'idle':
        if (!supportsRecording) {
          setRecordingError('当前浏览器不支持语音输入');
          return;
        }
        startRecording();
        break;
      case 'recording':
        stopRecording();
        break;
      case 'transcribing':
        setIsTranscribing(false);
        setVoiceProcess('idle');
        setRecordingError('已取消语音识别');
        break;
      case 'thinking':
        voiceStreamAbortRef.current?.abort();
        voiceStreamAbortRef.current = null;
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
        setRecordingError('已终止生成');
        break;
      case 'speaking':
        handleStopPlayback();
        setVoiceProcess('idle');
        setVoiceFlowActive(false);
        setRecordingError('已停止播报');
        break;
    }
  };

  const startRecording = async () => {
    if (!settings.voiceInputEnabled) {
      setRecordingError('请先启用语音输入');
      return;
    }
    if (!supportsRecording) {
      setRecordingError('当前浏览器不支持语音输入');
      return;
    }
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setRecordingError('当前环境无法访问麦克风');
      return;
    }

    try {
      setRecordingError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      audioChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error('录音发生错误:', event.error);
        setRecordingError(`录音失败：${event.error?.message ?? ''}`);
        setIsRecording(false);
        setVoiceProcess('idle');
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setIsRecording(false);
        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType });
        audioChunksRef.current = [];
        if (audioBlob.size > 0) {
          setVoiceProcess('transcribing');
          await handleVoiceUpload(audioBlob);
        } else {
          setVoiceProcess('idle');
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setVoiceProcess('recording');
      setVoiceFlowActive(false);
    } catch (error) {
      console.error('无法访问麦克风:', error);
      setRecordingError('无法访问麦克风，请检查设备权限');
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
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
          <button
            className={`voice-toggle ${voiceProcess !== 'idle' ? 'active' : ''}`}
            onClick={handleVoiceButtonClick}
            disabled={
              voiceProcess === 'idle'
                ? (!supportsRecording || !settings.voiceInputEnabled)
                : false
            }
            title={!supportsRecording ? '当前浏览器不支持语音输入' : undefined}
          >
            {voiceProcess === 'recording'
              ? '结束录音'
              : voiceProcess === 'idle'
              ? '语音'
              : '停止'}
          </button>
          <button onClick={() => handleSend()} disabled={!input.trim() || isLoading}>
            {isLoading ? '发送中...' : '发送'}
          </button>
        </div>
        {(voiceProcess !== 'idle' || recordingError) && (
          <div className="voice-status-line">
            {voiceProcess !== 'idle' && (
              <span className="voice-status-text">{voiceStatusText[voiceProcess]}</span>
            )}
            {recordingError && <span className="voice-error-inline">{recordingError}</span>}
            {lastVoiceMessageId && isSpeaking && (
              <span className="voice-status-text">播报消息 #{lastVoiceMessageId}</span>
            )}
          </div>
        )}
        <audio ref={audioPlayerRef} style={{ display: 'none' }} />
      </div>
    </div>
  );
};

export default Chat;
