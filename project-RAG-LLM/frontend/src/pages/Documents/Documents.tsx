/**
 * 文档管理页面（只读按会话查看）
 */
import { useState, useEffect } from 'react';
import { useConversationStore } from '../../stores/conversationStore';
import documentAPI from '../../api/document';
import { formatFileSize, formatDateTime } from '../../utils/helpers';
import type { SessionDocument } from '../../types';
import './Documents.css';

const Documents = () => {
  const {
    conversations,
    currentThreadId,
    loadConversations,
  } = useConversationStore();

  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<SessionDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // 初始化加载会话列表
  useEffect(() => {
    const init = async () => {
      if (conversations.length === 0) {
        await loadConversations();
      }
    };
    init();
  }, [conversations.length, loadConversations]);

  // 根据当前会话和会话列表决定默认选中会话
  useEffect(() => {
    if (selectedThreadId) return;
    if (currentThreadId && conversations.some(c => c.thread_id === currentThreadId)) {
      setSelectedThreadId(currentThreadId);
    } else if (conversations.length > 0) {
      setSelectedThreadId(conversations[0].thread_id);
    }
  }, [currentThreadId, conversations, selectedThreadId]);

  // 当选中会话变化时，加载该会话的文档列表
  useEffect(() => {
    const loadDocs = async () => {
      if (!selectedThreadId) return;
      setIsLoading(true);
      try {
        const res = await documentAPI.getDocumentsBySession(selectedThreadId);
        setDocuments(res.documents || []);
      } catch (error) {
        console.error('加载会话文档失败:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadDocs();
  }, [selectedThreadId]);

  const currentConversation = conversations.find(c => c.thread_id === selectedThreadId) || null;

  return (
    <div className="documents-container">
      <div className="documents-header">
        <h2>文档管理 / 对话文档总览</h2>
      </div>

      <div className="documents-content">
        {conversations.length === 0 ? (
          <div className="empty-state">
            <p>📂 目前还没有任何对话</p>
            <p>请先在聊天页面创建并发送消息，然后在这里查看各对话上传的文档。</p>
          </div>
        ) : (
          <div className="documents-layout">
            {/* 左侧：会话列表 */}
            <div className="documents-conversation-list">
              {conversations.map((conv) => (
                <div
                  key={conv.thread_id}
                  className={
                    'documents-conversation-item' +
                    (conv.thread_id === selectedThreadId ? ' active' : '')
                  }
                  onClick={() => setSelectedThreadId(conv.thread_id)}
                >
                  <div className="documents-conversation-title">{conv.title}</div>
                  <div className="documents-conversation-meta">
                    <span>{new Date(conv.last_message_time).toLocaleString('zh-CN', {
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}</span>
                    <span> · </span>
                    <span>{conv.message_count} 条消息</span>
                  </div>
                </div>
              ))}
            </div>

            {/* 右侧：选中会话的文档列表 */}
            <div className="documents-session-content">
              <div className="documents-session-header">
                {currentConversation ? (
                  <>
                    <h3>
                      当前对话：{currentConversation.title}{' '}
                      <span className="documents-session-thread-id">
                        ({currentConversation.thread_id.slice(0, 8)}…)
                      </span>
                    </h3>
                  </>
                ) : (
                  <h3>请选择左侧的一个对话</h3>
                )}
              </div>

              {isLoading ? (
                <div className="loading">加载中...</div>
              ) : !selectedThreadId || documents.length === 0 ? (
                <div className="empty-state">
                  <p>📁 该对话还没有上传任何文档</p>
                  <p>可以在聊天页面中点击“上传文档”按钮进行上传。</p>
                </div>
              ) : (
                <div className="documents-grid">
                  {documents.map((doc) => (
                    <div key={doc.id} className="document-card">
                      <div className="document-icon">📄</div>
                      <div className="document-info">
                        <h3 title={doc.file_name}>{doc.file_name}</h3>
                        <p className="document-meta">
                          <span>{formatFileSize(doc.size)}</span>
                          <span>•</span>
                          <span>
                            {doc.uploaded_at ? formatDateTime(doc.uploaded_at) : '-'}
                          </span>
                        </p>
                        {doc.status && (
                          <span className={`status-badge ${doc.status}`}>
                            {doc.status === 'processed' ? '已处理' : '处理中'}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Documents;

