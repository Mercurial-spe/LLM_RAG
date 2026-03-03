# 📝 项目维护日志

> **文档状态**: 🟢 活跃维护中
> **最后更新**: 2026-03-04
> **用途**: 记录项目开发过程中的变更日志、技术决策和问题追踪

---

## 📊 项目概况

### 当前技术栈

**技术栈**:

- **后端**: Flask 3.1.2 + LangChain 1.0.2 + LangGraph 1.0.1
- **LLM**: 阿里云 DashScope (Qwen3-max / Qwen-flash)
- **向量库**: ChromaDB 1.2.1
- **Embedding**: text-embedding-v4 (1024维)
- **前端**: React (待详细分析)
- **其他**: Tavily Web Search, Qwen ASR/TTS

**当前架构**:

```
backend/app/
├── agents/                        # LangGraph StateGraph 架构
│   ├── graph.py                   # StateGraph 构建与编译
│   ├── runtime.py                 # Agent Runtime (invoke/stream + SSE)
│   ├── state.py                   # AgentState/Decision/ToolResult 契约
│   └── nodes/                     # Graph 节点实现
│       ├── orchestrator.py        # LLM 决策路由
│       ├── tool_exec.py           # 工具执行节点
│       └── respond.py             # LLM 生成回复
├── tools/                         # 工具接口层
│   ├── rag_tool.py                # RAG 检索工具
│   └── web_search_tool.py         # 网络搜索工具
├── services/                      # 服务层
│   ├── retriever_service.py       # Retriever 构建
│   ├── vector_store_repository.py # ChromaDB 封装
│   ├── embedding_service.py       # 向量化服务
│   ├── web_search_service.py      # Tavily 搜索
│   └── speech_service.py          # 语音识别/合成
├── core/                          # 核心层
│   ├── llm_handler.py             # LLM 调用适配器
│   ├── checkpointer.py            # Checkpointer 工厂
│   └── conversation_manager.py    # 对话历史管理
├── prompts/                       # Prompt 管理
│   ├── orchestrator_decision.md   # 决策提示词
│   ├── rag_system.md              # RAG 系统提示词
│   └── loader.py                  # Prompt 加载器
└── api/                           # API 路由层
    ├── chat.py                    # 聊天接口
    └── document.py                # 文档管理接口
```

---

## 📝 变更日志

### 2026-02-27

- ✅ 创建初始升级改造计划
- ✅ 完成项目现状分析
- ✅ 定义 5 个阶段的详细任务

### 2026-02-27 15:30

- ✅ **Phase 1 完成** - 代码清理与工程化基础
- ✅ 删除 `rag_pipeline.py` (210 行冗余代码)
- ✅ 删除 `llm_handler.py` 中未使用的 `call_model_stream` 函数
- ✅ 清理所有 `__pycache__` 目录 (24 个 .pyc 文件)
- ✅ 验证核心接口已有完整类型标注
- ✅ 验证日志系统已完善配置
- ✅ 验证 API 路由已有完善错误处理
- 📝 **Phase 1 总结**: 采用务实方案,跳过过度工程化的配置 (mypy/structlog/自定义异常),聚焦高价值清理工作

### 2026-02-27 16:00

- 📝 **Phase 2 计划确定** - LangChain 技术栈升级
- ✅ 完成技术验证和完整性审查

### 2026-03-03

- ✅ **LLM 集成完成** - 接入 LLM 到 orchestrator 和 respond 节点
- ✅ 创建 `orchestrator_decision.md` 提示词文件,定义决策规则
- ✅ 修改 `orchestrator.py` 使用 LLM 进行智能决策
  - 支持 CALL_TOOL/RESPOND/END 等决策动作
  - 支持 RAG 和 WebSearch 工具选择
  - 包含降级机制(LLM 失败时使用简单规则)
- ✅ 修改 `respond.py` 使用 LLM 生成智能回复
  - 基于工具结果生成引用式回答
  - 支持对话历史上下文
  - 包含降级机制(LLM 失败时使用模板)
- ✅ 实现真正的流式输出
  - 修改 `runtime.py` 的 `stream_messages` 方法
  - 实现 `_stream_respond` 方法进行 token-by-token 流式生成
  - 添加 `_build_prompt_with_tools_internal` 辅助方法
- ✅ 完善错误处理
  - 修复 `tool_exec.py` 中的类型不一致问题
  - 统一使用字典字面量而非 TypedDict 构造函数

### 2026-02-27 17:00

- ✅ **LangChain 技术栈升级完成**
- ✅ **Step 0**: 修复 `chat.py` 断链导入 Bug
  - 删除 `from ..core.llm_handler import call_model_stream` (已废弃)
  - 删除旧的 `/chat` 端点 (已被 `/chat/stream` 取代)
  - 删除旧的 `/chat/history` 端点 (已有 conversation_manager)
- ✅ **Step 1**: `embedding_service.py` 瘦身 (→ OpenAIEmbeddings)
  - 删除 `EmbeddingService` 类 (200+ 行手搓代码)
  - 删除 `LCEmbeddingAdapter` (10 行适配器)
  - 使用 `langchain_openai.OpenAIEmbeddings` 替代
  - 保留 `get_embeddings()` 单例工厂函数
  - 文件从 236 行缩减至 38 行 (减少 83%)
- ✅ **Step 2**: 创建 `tools/` 包,拆分工具定义
  - 创建 `app/tools/rag_tool.py` - RAG 检索工具
  - 创建 `app/tools/web_search_tool.py` - Web 搜索工具
  - 创建 `app/tools/__init__.py` - 包导出
  - 工具可独立测试,职责清晰
- ✅ **Step 3**: 抽取 `checkpointer.py` + `prompts/`
  - 创建 `app/core/checkpointer.py` - Checkpointer 工厂 (58 行)
  - 创建 `app/prompts/` 包 - Prompt 管理系统
  - 从 `rag_agent.py` 中移除 35 行 checkpointer 代码
  - 从 `rag_agent.py` 中移除 20 行 system_prompt 代码

### 2026-03-03 22:15

- ✅ 补齐测试运行环境并执行本轮最小回归测试
  - 安装 `pytest`、`flask`、`flask-cors`
  - 运行 `tests/test_chat_stream_validation.py` 与 `tests/test_runtime_streaming_path.py`，结果 3 passed
- ✅ 修复测试过程中暴露的历史回归问题
  - `app/api/document.py` 仍引用已删除的 `EmbeddingService`
  - 已改为 `get_embeddings().embed_documents(...)` 调用路径，消除 ImportError
- ✅ 更新测试文件以便在当前独立环境执行
  - 为测试增加项目路径注入与可选依赖 stub（仅测试隔离用途）

### 2026-03-03 23:05

- ✅ 完成 `/chat/stream` 动态参数校验增强与日志收敛
  - 新增 `temperature/top_k/messages_to_keep/max_tokens` 类型与边界校验
  - 日志改为仅记录 `config_keys` 与白名单参数，避免打印原始配置对象
- ✅ 补齐 `/chat/voice` 参数校验一致性
  - `config` 非法 JSON 时返回统一 400 结构：`{"success": false, "error": "config 必须是合法 JSON"}`
  - 复用动态参数校验，阻断无效温度/检索参数进入运行时
- ✅ 收敛 SSE 异常输出
  - `/chat/stream` 发生内部异常时返回通用错误文案，详细异常仅写日志
- ✅ 扩展最小回归测试
  - 新增语音接口配置非法场景测试
  - 运行 `tests/test_chat_stream_validation.py` 与 `tests/test_runtime_streaming_path.py`，结果 13 passed

### 2026-03-03 23:40

- ✅ 修复 legacy 模块与新 Prompt 管理之间的断链
  - `app/prompts/README.md` 从 `RAG_SYSTEM_PROMPT` 常量改为 `get_rag_system_prompt()` 按需加载示例
- ✅ 对齐文档与代码现状
  - 更新 `docs/ARCHITECTURE.md`（原 `目录树.md`）中的目录结构，移除已删除文件的陈旧记录

### 2026-03-03 23:55

- ✅ 物理删除确认废弃的 legacy/冗余模块
  - 删除 `app/core/rag_agent.py`（已被 agents/runtime 替代）
  - 删除 `app/services/sync_service.py`（未使用）
  - 删除旧 `app/tools/` 下的嵌入式工具实现（已下沉到独立工具层）

### 2026-03-04

- ✅ **架构边界收敛完成**
- ✅ 工具函数下沉到 `app/tools/` 独立层
  - 创建 `app/tools/rag_tool.py` - RAG 检索工具（从 tool_exec.py 下沉）
  - 创建 `app/tools/web_search_tool.py` - 网络搜索工具（从 tool_exec.py 下沉）
  - 修改 `app/agents/nodes/tool_exec.py` - 调用工具层而非嵌入式实现
  - 删除 `tool_exec.py` 中的 `_execute_rag_tool` 和 `_execute_web_search_tool` 函数
- ✅ 架构文档完善
  - 将 `docs/目录树.md` 改造为 `docs/ARCHITECTURE.md`
  - 新增"架构契约"章节（AgentState/Decision/ToolResult 字段规范）
  - 新增"架构设计"章节（总体架构图与设计原则）
  - 删除旧的 `docs/目录树.md` 文件
- ✅ 维护日志清理
  - 重写 `docs/UPGRADE_PLAN.md`，清理过时内容
  - 移除已删除模块的陈旧记录（`rag_agent.py`、`sync_service.py`、旧 `tools/`）
  - 对齐当前架构状态

---

## 🔄 维护说明

**本文档由 AI Assistant 维护,遵循以下规则**:

1. **实时更新**: 每次代码修改后,立即更新对应的任务状态
2. **讨论记录**: 重要的技术决策讨论后,更新到对应章节
3. **问题追踪**: 遇到问题时,记录到对应的章节中
4. **完成标准**: 每个阶段完成后,更新完成标准的检查项

**更新频率**:

- 代码修改后: 立即更新
- 技术讨论后: 当天更新
- 阶段完成后: 立即更新变更日志

---

## ✅ 当前状态

**架构状态**: ✅ 稳定

- LangGraph StateGraph 架构已落地
- 显式 Decision 路由已实现
- Tools/Services 边界已明确
- 流式输出单路径执行已验证
- 架构契约文档已完善

**待优化项** (非阻塞):

- [ ] 多轮工具调用增强（P2，含循环终止与调用上限）
- [ ] CLARIFY 动作的显式路由处理
- [ ] LangSmith 集成（可观测性）
- [ ] chunk 参数调优（中文文档优化）

---

**文档版本**: v2.0.0
**最后更新**: 2026-03-04
**下次审查**: 架构优化阶段开始前
