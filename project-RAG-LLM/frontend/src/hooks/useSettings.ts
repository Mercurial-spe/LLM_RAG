/**
 * 设置管理 Hook
 * 提供全局的应用设置状态管理
 */
import { useState, useEffect } from 'react';
import type { AppSettings, RagConfig } from '../types';

const DEFAULT_SETTINGS: AppSettings = {
  apiUrl: 'http://localhost:8000/api',
  temperature: 0.2,
  maxTokens: 2000,
  topK: 5,
  messagesToKeep: 20,
  voiceInputEnabled: true,
  voiceAutoSend: true,
  voiceReplyEnabled: true,
};

const useSettings = () => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);

  // 从 localStorage 加载设置
  useEffect(() => {
    const savedSettings = localStorage.getItem('app_settings');
    if (savedSettings) {
      try {
        const parsed = JSON.parse(savedSettings);
        setSettings({ ...DEFAULT_SETTINGS, ...parsed });
      } catch (error) {
        console.warn('加载设置失败，使用默认设置:', error);
      }
    }
    setIsLoaded(true);
  }, []);

  // 更新设置
  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings(prev => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem('app_settings', JSON.stringify(updated));
      console.log('✅ 设置已更新:', updated);
      return updated;
    });
  };

  // 重置设置
  const resetSettings = () => {
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem('app_settings');
    console.log('✅ 设置已重置');
  };

  // 获取 RAG 配置对象 - 用于API请求
  const getRagConfig = (): RagConfig => {
    console.log('🔍 调用 getRagConfig()');
    console.log('   - settings 对象:', settings);
    console.log('   - settings.temperature:', settings.temperature);
    console.log('   - settings.topK:', settings.topK);
    console.log('   - settings.messagesToKeep:', settings.messagesToKeep);
    
    const config: RagConfig = {
      temperature: settings.temperature,
      top_k: settings.topK,
      messages_to_keep: settings.messagesToKeep,
    };
    console.log('🔍 构建的 RAG 配置:', config);
    return config;
  };

  return {
    settings,
    updateSettings,
    resetSettings,
    getRagConfig,
    isLoaded,
  };
};

export default useSettings;
