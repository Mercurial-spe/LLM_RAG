/**
 * 对话状态管理 Store
 * 使用 Zustand 管理对话列表、当前对话和消息
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Conversation, Message, SessionDocument } from '../types';
import conversationAPI from '../api/conversation';
import documentAPI from '../api/document';

interface ConversationStore {
  // 状态
  currentThreadId: string | null;
  conversations: Conversation[];
  currentMessages: Message[];
  isLoading: boolean;
  sessionDocuments: Record<string, SessionDocument[]>;
  
  // Actions
  setCurrentThreadId: (threadId: string | null) => void;
  setConversations: (conversations: Conversation[]) => void;
  setCurrentMessages: (messages: Message[]) => void;
  setIsLoading: (loading: boolean) => void;
  
  // 异步 Actions
  loadConversations: () => Promise<void>;
  createNewConversation: (title?: string) => Promise<string | null>;
  loadMessages: (threadId: string) => Promise<void>;
  addMessage: (message: Message) => void;
  updateMessage: (messageId: number, content: string) => void;
  appendToMessage: (messageId: number, chunk: string) => void;
  deleteConversation: (threadId: string) => Promise<boolean>;
  updateConversationTitle: (threadId: string, title: string) => Promise<boolean>;
  
  // 辅助方法
  clearCurrentMessages: () => void;
  loadSessionDocuments: (threadId: string) => Promise<void>;
  addSessionDocument: (threadId: string, doc: SessionDocument) => void;
}

export const useConversationStore = create<ConversationStore>()(
  persist(
    (set) => ({
      // 初始状态
      currentThreadId: null,
      conversations: [],
      currentMessages: [],
      isLoading: false,
      sessionDocuments: {},
      
      // 同步 Actions
      setCurrentThreadId: (threadId) => {
        console.log('📝 设置当前对话 ID:', threadId);
        set({ currentThreadId: threadId });
      },
      
      setConversations: (conversations) => {
        set({ conversations });
      },
      
      setCurrentMessages: (messages) => {
        set({ currentMessages: messages });
      },
      
      setIsLoading: (loading) => {
        set({ isLoading: loading });
      },
      
      // 异步 Actions
      loadConversations: async () => {
        try {
          console.log('📥 加载对话列表...');
          const conversations = await conversationAPI.getConversations();
          set({ conversations });
          console.log(`✅ 成功加载 ${conversations.length} 个对话`);
        } catch (error) {
          console.error('❌ 加载对话列表失败:', error);
        }
      },
      
      createNewConversation: async (title = '新对话') => {
        try {
          console.log('🆕 创建新对话:', title);
          const result = await conversationAPI.createConversation(title);
          
          if (result) {
            // 注意：此时后端还没有任何 checkpoint 记录，
            // 会话不会出现在 /conversations 列表中。
            // 这里只设置当前 threadId，真正持久化要等首次发送消息。
            set({ 
              currentThreadId: result.thread_id,
              currentMessages: []  // 清空消息列表
            });
            
            console.log('✅ 新对话创建成功:', result.thread_id);
            return result.thread_id;
          }
          
          console.error('❌ 创建对话失败');
          return null;
        } catch (error) {
          console.error('❌ 创建对话失败:', error);
          return null;
        }
      },
      
      loadMessages: async (threadId: string) => {
        try {
          console.log('📥 加载对话消息:', threadId);
          set({ isLoading: true });
          
          const messages = await conversationAPI.getConversationMessages(threadId);
          
          set({ 
            currentMessages: messages,
            currentThreadId: threadId,
            isLoading: false
          });
          
          console.log(`✅ 成功加载 ${messages.length} 条消息`);
        } catch (error) {
          console.error('❌ 加载消息失败:', error);
          set({ isLoading: false });
        }
      },
      
      addMessage: (message) => {
        set((state) => ({
          currentMessages: [...state.currentMessages, message]
        }));
      },
      
      updateMessage: (messageId, content) => {
        set((state) => ({
          currentMessages: state.currentMessages.map(msg =>
            msg.id === messageId ? { ...msg, content } : msg
          )
        }));
      },
      
      appendToMessage: (messageId, chunk) => {
        set((state) => ({
          currentMessages: state.currentMessages.map(msg =>
            msg.id === messageId ? { ...msg, content: msg.content + chunk } : msg
          )
        }));
      },
      
      deleteConversation: async (threadId) => {
        try {
          console.log('🗑️ 删除对话:', threadId);
          const success = await conversationAPI.deleteConversation(threadId);
          
          if (success) {
            // 从列表中移除
            set((state) => {
              const { [threadId]: _, ...restDocs } = state.sessionDocuments;
              return {
                conversations: state.conversations.filter(c => c.thread_id !== threadId),
                // 如果删除的是当前对话，清空当前状态
                currentThreadId: state.currentThreadId === threadId ? null : state.currentThreadId,
                currentMessages: state.currentThreadId === threadId ? [] : state.currentMessages,
                sessionDocuments: restDocs,
              };
            });
            
            console.log('✅ 对话删除成功');
            return true;
          }
          
          console.error('❌ 删除对话失败');
          return false;
        } catch (error) {
          console.error('❌ 删除对话失败:', error);
          return false;
        }
      },
      
      updateConversationTitle: async (threadId, title) => {
        try {
          console.log('✏️ 更新对话标题:', threadId, title);
          const success = await conversationAPI.updateConversationTitle(threadId, title);
          
          if (success) {
            // 更新本地列表
            set((state) => ({
              conversations: state.conversations.map(c =>
                c.thread_id === threadId ? { ...c, title } : c
              )
            }));
            
            console.log('✅ 标题更新成功');
            return true;
          }
          
          console.error('❌ 更新标题失败');
          return false;
        } catch (error) {
          console.error('❌ 更新标题失败:', error);
          return false;
        }
      },
      
      clearCurrentMessages: () => {
        set({ currentMessages: [] });
      },

      // 加载指定对话下的文件列表
      loadSessionDocuments: async (threadId: string) => {
        try {
          console.log('📥 加载会话文档列表:', threadId);
          const res = await documentAPI.getDocumentsBySession(threadId);
          set((state) => ({
            sessionDocuments: {
              ...state.sessionDocuments,
              [threadId]: res.documents || [],
            },
          }));
          console.log(`✅ 成功加载会话 ${threadId} 的 ${res.documents?.length ?? 0} 个文档`);
        } catch (error) {
          console.error('❌ 加载会话文档失败:', error);
        }
      },

      // 本地追加一个文档（用于上传成功后的乐观更新）
      addSessionDocument: (threadId: string, doc: SessionDocument) => {
        set((state) => {
          const prevDocs = state.sessionDocuments[threadId] || [];
          return {
            sessionDocuments: {
              ...state.sessionDocuments,
              [threadId]: [...prevDocs, doc],
            },
          };
        });
      },
    }),
    {
      name: 'conversation-storage',
      // 只持久化 currentThreadId，其他从后端加载
      partialize: (state) => ({ 
        currentThreadId: state.currentThreadId 
      })
    }
  )
);

