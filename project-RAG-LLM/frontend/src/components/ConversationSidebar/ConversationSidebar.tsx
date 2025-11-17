/**
 * 对话侧边栏组件
 * 显示对话列表，支持新建、切换、删除和重命名
 */
import { useState } from 'react';
import { useConversationStore } from '../../stores/conversationStore';
import './ConversationSidebar.css';

const ConversationSidebar = () => {
  const {
    currentThreadId,
    conversations,
    createNewConversation,
    loadMessages,
    deleteConversation,
    updateConversationTitle
  } = useConversationStore();
  
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  
  const handleNewConversation = async () => {
    await createNewConversation('新对话');
  };
  
  const handleSelectConversation = async (threadId: string) => {
    if (threadId !== currentThreadId) {
      await loadMessages(threadId);
    }
  };
  
  const handleDeleteConversation = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();  // 防止触发选择事件
    
    if (window.confirm('确定要删除这个对话吗？')) {
      await deleteConversation(threadId);
    }
  };
  
  // const handleStartEdit = (e: React.MouseEvent, threadId: string, currentTitle: string) => {
  //   e.stopPropagation();
  //   setEditingThreadId(threadId);
  //   setEditingTitle(currentTitle);
  // };
  
  const handleSaveEdit = async (threadId: string) => {
    if (editingTitle.trim()) {
      const success = await updateConversationTitle(threadId, editingTitle.trim());
      if (!success) {
        // 后端未能更新标题（例如该 thread 尚无任何 checkpoint 或已被删除）
        // 不修改本地标题，只给出提示，保持前后端数据一致
        window.alert('标题更新失败：该对话可能还没有任何消息或已被删除。');
      }
    }
    setEditingThreadId(null);
  };
  
  const handleCancelEdit = () => {
    setEditingThreadId(null);
    setEditingTitle('');
  };
  
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 7) return `${diffDays} 天前`;
    
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };
  
  return (
    <div className="conversation-sidebar">
      <div className="sidebar-header">
        <button 
          className="new-conversation-btn"
          onClick={handleNewConversation}
          title="新建对话"
        >
          <span className="icon">➕</span>
          <span>新对话</span>
        </button>
      </div>
      
      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="empty-conversations">
            <p>暂无对话</p>
            <p className="hint">点击上方按钮创建新对话</p>
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.thread_id}
              className={`conversation-item ${
                conv.thread_id === currentThreadId ? 'active' : ''
              }`}
              onClick={() => handleSelectConversation(conv.thread_id)}
            >
              <div className="conversation-content">
                {editingThreadId === conv.thread_id ? (
                  <input
                    type="text"
                    className="title-edit-input"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onBlur={() => handleSaveEdit(conv.thread_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleSaveEdit(conv.thread_id);
                      } else if (e.key === 'Escape') {
                        handleCancelEdit();
                      }
                    }}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div className="conversation-title" title={conv.title}>
                    {conv.title}
                  </div>
                )}
                
                <div className="conversation-meta">
                  <span className="message-count">{conv.message_count} 条消息</span>
                  <span className="separator">·</span>
                  <span className="time">{formatDate(conv.last_message_time)}</span>
                </div>
              </div>
              
              <div className="conversation-actions">
                {/* <button
                  className="action-btn edit-btn"
                  onClick={(e) => handleStartEdit(e, conv.thread_id, conv.title)}
                  title="重命名"
                >
                  ✏️
                </button> */}
                <button
                  className="action-btn delete-btn"
                  onClick={(e) => handleDeleteConversation(e, conv.thread_id)}
                  title="删除对话"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ConversationSidebar;

