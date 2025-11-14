/**
 * 设置页面
 */
import './Settings.css';
import useSettings from '../../hooks/useSettings';
import type { AppSettings } from '../../types';
import { useEffect } from 'react';

const Settings = () => {
  const { settings, updateSettings, resetSettings, isLoaded } = useSettings();

  // 调试日志：监听settings变化
  useEffect(() => {
    if (isLoaded) {
      console.log('⚙️ 当前设置状态:', settings);
    }
  }, [settings, isLoaded]);

  const handleChange = (key: keyof AppSettings, value: string | number) => {
    console.log(`🔄 设置变更: ${key} = ${value}`);
    updateSettings({ [key]: value });
  };

  const handleSave = () => {
    // 设置已经自动保存到 localStorage（在 useSettings 中处理）
    console.log('✅ 设置已手动保存:', settings);
    alert('设置已保存！');
  };

  const handleReset = () => {
    if (!confirm('确定要重置所有设置吗？')) return;
    resetSettings();
    alert('设置已重置！');
  };

  if (!isLoaded) {
    return <div className="settings-container"><p>⏳ 加载中...</p></div>;
  }

  return (
    <div className="settings-container">
      <div className="settings-header">
        <h2>系统设置</h2>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <h3>🌐 API 配置</h3>
          <div className="setting-item">
            <label>API 地址</label>
            <input
              type="text"
              value={settings.apiUrl}
              onChange={(e) => handleChange('apiUrl', e.target.value)}
              placeholder="http://localhost:8000/api"
            />
            <p className="setting-description">后端 API 服务器地址</p>
          </div>
        </div>

        <div className="settings-section">
          <h3>🤖 模型参数</h3>
          
          <div className="setting-item">
            <label>Temperature (温度)</label>
            <div className="slider-container">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
              />
              <span className="slider-value">{settings.temperature}</span>
            </div>
            <p className="setting-description">
              控制回答的随机性。较低的值使输出更确定，较高的值使输出更随机
            </p>
          </div>

          <div className="setting-item">
            <label>最大 Token 数</label>
            <input
              type="number"
              value={settings.maxTokens}
              onChange={(e) => handleChange('maxTokens', parseInt(e.target.value))}
              min="100"
              max="4000"
              step="100"
            />
            <p className="setting-description">生成回答的最大长度</p>
          </div>

          <div className="setting-item">
            <label>Top K</label>
            <input
              type="number"
              value={settings.topK}
              onChange={(e) => handleChange('topK', parseInt(e.target.value))}
              min="1"
              max="20"
            />
            <p className="setting-description">
              检索相关文档的数量。增加此值可能提高答案质量，但会增加响应时间
            </p>
          </div>

          <div className="setting-item">
            <label>保留消息数</label>
            <input
              type="number"
              value={settings.messagesToKeep}
              onChange={(e) => handleChange('messagesToKeep', parseInt(e.target.value))}
              min="10"
              max="100"
              step="5"
            />
            <p className="setting-description">
              记忆压缩时保留的历史消息数量。较高的值保留更多上下文，但消耗更多内存
            </p>
          </div>
        </div>

        <div className="settings-actions">
          <button className="save-button" onClick={handleSave}>
            💾 保存设置
          </button>
          <button className="reset-button" onClick={handleReset}>
            🔄 重置默认
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;

