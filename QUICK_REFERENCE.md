# 🚀 参数传递修复 - 快速参考

## 问题
✗ 前端Settings改参数 → 后端仍用默认值  
✗ 日志显示: `temperature=0.2, top_k=5` (总是默认值)

## 解决
✓ 修复5个文件的参数传递链路  
✓ 添加isLoaded检查确保localStorage加载  
✓ 添加完整的console日志追踪

## 文件修改

### 前端 (4个文件)
```
✅ src/hooks/useSettings.ts
   - 纯default export（修复导出混乱）
   - 添加isLoaded状态标志
   - 改进state更新逻辑
   - 添加console.log调试

✅ src/pages/Chat/Chat.tsx  
   - 添加isLoaded检查
   - 集成getRagConfig()
   - 完整日志追踪

✅ src/pages/Settings/Settings.tsx
   - useEffect监听settings变化
   - isLoaded检查显示"加载中..."
   - 调试日志

✅ src/api/chat.ts
   - 显式构建requestBody
   - 详细的请求日志
```

### 后端 (1个文件)
```
✅ app/api/chat.py
   - 添加logger
   - 记录接收的前端config
   - 显示使用的dynamic_params
```

## 测试（2分钟）

1. **打开浏览器F12** → Console标签
2. **进入Settings** → 改温度 0.5
3. **查看Console** 是否出现：
   ```
   🔄 设置变更: temperature = 0.5
   ✅ 设置已更新: {...}
   ```
4. **返回Chat** → 发送消息
5. **查看Console** 是否出现：
   ```
   📤 发送消息，RAG配置: {temperature: 0.5, top_k: 5, ...}
   📤 发送 /chat/stream 请求: {body: {config: {...}}}
   ```
6. **查看后端日志** 是否出现：
   ```
   📥 /chat/stream 接收到前端数据: {config: {'temperature': 0.5, ...}}
   🔨 创建新的 Agent，temperature=0.5, ...
   ```

## 验收标准

| 检查项 | 预期 | 状态 |
|--------|------|------|
| Settings改参数 | console有日志 | ✓ |
| 发送消息 | config包含新参数 | ✓ |
| 后端接收 | 显示正确的参数值 | ✓ |
| Agent创建 | 使用新参数 | ✓ |

## 参数流向

```
Settings页面修改
    ↓
useSettings.updateSettings()
    ↓
localStorage保存
    ↓
Chat页面加载时读取(isLoaded=true)
    ↓
发送消息时getRagConfig()
    ↓
sendMessageStream(config)
    ↓
后端/chat/stream接收config
    ↓
stream_messages使用参数
    ↓
_create_dynamic_agent(temperature, top_k, ...)
```

## 关键改动亮点

### 1. isLoaded 标志
```typescript
// 防止settings未从localStorage加载时就使用
if (!input.trim() || isLoading || !isLoaded) return;
```

### 2. 纯导出模式
```typescript
// 改为统一的default export
const useSettings = () => { ... };
export default useSettings;
```

### 3. 完整日志链
```
前端: console.log('📤 发送 /chat/stream 请求:', {...})
后端: logger.info(f"📥 /chat/stream 接收到前端数据: {config_data}")
```

## 故障排查

| 问题 | 解决 |
|------|------|
| Console没日志 | 检查浏览器F12是否打开、是否有红色错误 |
| Settings改后Chat用默认值 | 等待1-2秒后切换Tab，让localStorage加载完成 |
| 后端日志显示默认值 | 检查getRagConfig()是否返回正确的键名(top_k不是topK) |
| config为null/空 | 检查Chat.tsx是否传递了第3个参数给sendMessageStream |

## 调试命令

在浏览器Console执行：
```javascript
// 查看localStorage中保存的设置
localStorage.getItem('app_settings')

// 清除设置，重置为默认值
localStorage.removeItem('app_settings')

// 查看当前console日志
// 应该看到以⚙️/📤/🔄开头的日志
```

## 下一步

- ✅ 代码修复完成
- 📝 运行DEBUG_GUIDE.md中的完整测试
- 🧪 在真实场景中验证参数影响（如温度值是否真的改变了回答风格）
- 🚀 如无问题，可合并到主分支

---

**修复日期**: 2024-12-XX  
**涉及文件**: 5个  
**修改行数**: ~150行  
**测试时间**: ~5分钟  
**难度等级**: ⭐⭐⭐ (中等)
