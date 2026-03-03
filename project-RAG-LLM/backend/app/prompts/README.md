# Prompts 目录说明

## 概述
本目录采用 **Markdown 文件管理 Prompt** 的方式，便于版本控制、协作编辑和复用。

## 文件结构

```
prompts/
├── __init__.py           # 导出接口
├── loader.py             # Prompt 加载器
├── README.md             # 本文件
├── rag_system.md         # RAG 系统提示词
├── summarization.md      # 对话摘要提示词
└── query_rewrite.md      # 查询改写提示词
```

## 使用方法

### 1. 加载 Prompt

```python
from app.prompts import load_prompt

# 加载 RAG 系统提示词
system_prompt = load_prompt("rag_system")

# 加载摘要提示词
summary_prompt = load_prompt("summarization")
```

### 2. 兼容调用（推荐）

```python
from app.prompts import get_rag_system_prompt

# 通过按需加载函数获取系统提示词
prompt = get_rag_system_prompt()
print(prompt)
```

### 3. 重新加载 Prompt

```python
from app.prompts import reload_prompt

# 强制重新加载（忽略缓存）
updated_prompt = reload_prompt("rag_system")
```

### 4. 列出所有 Prompt

```python
from app.prompts import list_available_prompts

# 获取所有可用的 Prompt 名称
prompts = list_available_prompts()
print(prompts)  # ['query_rewrite', 'rag_system', 'summarization']
```

## Prompt 编写规范

### 1. 文件命名
- 使用小写字母和下划线
- 文件名应清晰描述用途
- 示例: `rag_system.md`, `query_rewrite.md`

### 2. 内容结构
推荐使用以下结构：

```markdown
# Prompt 标题

## 角色定位
[描述 AI 的角色]

## 任务说明
[描述具体任务]

## 规则/原则
[列出关键规则]

## 示例
[提供具体示例]

## 注意事项
[特殊注意事项]
```

### 3. 格式要求
- 使用 Markdown 标准语法
- 使用标题层级组织内容
- 使用列表、代码块等增强可读性
- 保持简洁，避免冗余

### 4. 变量占位符
如需动态替换内容，使用 `{variable_name}` 格式：

```markdown
你是 {role_name}，负责 {task_description}。
```

## 最佳实践

### 1. 版本控制
- 所有 Prompt 文件纳入 Git 版本控制
- 重大修改前先备份
- 使用有意义的 commit message

### 2. 协作编辑
- 使用 Pull Request 审查 Prompt 修改
- 在 README 中记录修改历史
- 团队成员共同维护

### 3. 测试验证
- 修改 Prompt 后进行充分测试
- 记录测试结果和效果对比
- 保留旧版本以便回滚

### 4. 性能优化
- Prompt 加载器自动缓存内容
- 避免频繁重新加载
- 生产环境使用缓存模式

## 参考资源

### Prompt Engineering 最佳实践
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Prompt Engineering](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [LangChain Prompt Templates](https://python.langchain.com/docs/modules/model_io/prompts/)

### 主流 Prompt 模式
- **Chain-of-Thought (CoT)**: 引导模型逐步推理
- **Few-Shot Learning**: 提供示例引导输出格式
- **Role-Playing**: 定义明确的角色和任务
- **Structured Output**: 使用 Markdown/JSON 格式化输出

## 修改历史

### 2026-03-02
- 初始化 Prompt 管理系统
- 创建 `rag_system.md`, `summarization.md`, `query_rewrite.md`
- 实现 `loader.py` 加载器
- 添加缓存机制
