# 项目架构文档

> **文档状态**: 🟢 活跃维护中
> **最后更新**: 2026-03-04
> **用途**: 项目架构说明、目录结构、核心模块与架构契约

---

## 📁 项目目录结构

```
backend/
├── .env_example                          # 环境变量配置示例
├── .gitignore                            # Git 忽略文件配置
├── Dockerfile                            # Docker 容器配置
├── requirements.txt                      # Python 依赖列表
├── run.py                                # Flask 应用启动入口
│
├── app/                                  # 应用主目录
│   ├── __init__.py                       # Flask 应用工厂函数
│   ├── config.py                         # 全局配置(API Key、模型参数、路径等)
│   ├── models.py                         # 数据模型定义(空文件,待扩展)
│   │
│   ├── agents/                           # Agent 系统(LangGraph StateGraph 架构)
│   │   ├── __init__.py
│   │   ├── graph.py                      # StateGraph 构建与编译
│   │   ├── runtime.py                    # Agent Runtime(invoke/stream + SSE + Checkpointer)
│   │   ├── state.py                      # AgentState/Decision/ToolResult 数据结构
│   │   └── nodes/                        # Graph 节点实现
│   │       ├── __init__.py
│   │       ├── orchestrator.py           # Orchestrator 节点(LLM 决策路由)
│   │       ├── respond.py                # Respond 节点(LLM 生成回复)
│   │       └── tool_exec.py              # Tool Execution 节点(调用工具层)
│   │
│   ├── tools/                            # 工具接口层(统一 ToolResult 输出)
│   │   ├── __init__.py
│   │   ├── rag_tool.py                   # RAG 检索工具
│   │   └── web_search_tool.py            # 网络搜索工具
│   │
│   ├── api/                              # API 路由层
│   │   ├── __init__.py
│   │   ├── chat.py                       # 聊天接口(流式/语音/对话管理)
│   │   └── document.py                   # 文档上传/查询/删除接口
│   │
│   ├── core/                             # 核心业务逻辑层
│   │   ├── __init__.py
│   │   ├── checkpointer.py               # LangGraph Checkpointer 工厂(SQLite/Memory)
│   │   ├── conversation_manager.py       # 对话历史管理(读取/删除/更新标题)
│   │   └── llm_handler.py                # LLM 调用适配器(DashScope/Ollama)
│   │
│   ├── prompts/                          # Prompt 模板管理
│   │   ├── __init__.py                   # Prompt 加载器导出
│   │   ├── loader.py                     # Prompt 文件加载工具
│   │   ├── README.md                     # Prompt 管理说明文档
│   │   ├── orchestrator_decision.md      # Orchestrator 决策 Prompt
│   │   ├── query_rewrite.md              # 查询重写 Prompt(未使用)
│   │   ├── rag_system.md                 # RAG 系统 Prompt(Agent 使用)
│   │   └── summarization.md              # 对话摘要 Prompt(未使用)
│   │
│   ├── services/                         # 服务层(业务逻辑封装)
│   │   ├── document_ingest_service.py    # 文档摄取服务(加载、切分、生成 metadata)
│   │   ├── embedding_service.py          # 向量化服务(OpenAI Embeddings 单例)
│   │   ├── retriever_service.py          # Retriever 构建服务(支持 MultiQuery)
│   │   ├── speech_service.py             # 语音服务(Qwen ASR/TTS)
│   │   ├── vector_store_repository.py    # 向量数据库仓储层(Chroma 操作封装)
│   │   └── web_search_service.py         # 联网搜索服务(Tavily API)
│   │
│   └── utils/                            # 工具函数
│       ├── file_utils.py                 # 文件操作工具(哈希、时间戳、文件信息)
│       └── logger.py                     # 日志配置(结构化日志)
│
├── docs/                                 # 项目文档
│   ├── 3.3重构报告.md                    # 3.3 阶段重构报告
│   ├── Agent架构学习.md                  # Agent 架构学习笔记
│   ├── crewAI工程化借鉴.md               # 工程化实践借鉴
│   ├── ARCHITECTURE.md                   # 项目架构文档(本文档)
│   └── UPGRADE_PLAN.md                   # 项目升级改造计划
│
└── tests/                                # 测试目录
    ├── test_api.py                       # API 接口测试
    ├── test_chat_stream_validation.py    # /chat/stream 参数校验与错误结构测试
    ├── test_database.py                  # 数据库测试
    └── test_runtime_streaming_path.py    # Runtime 流式单路径执行测试
```

---

## 🏗️ 架构设计

### 总体架构

```
API Layer (Flask)
    ↓
Agent Runtime (invoke/stream + SSE + Checkpointer)
    ↓
StateGraph (orchestrator → tool_exec → respond)
    ↓
Tools Layer (rag_tool, web_search_tool)
    ↓
Services Layer (retriever, vector_store, web_search, etc.)
```

### 核心设计原则

1. **职责分离**: Runtime/Graph/Nodes/Tools/Services 各司其职
2. **显式路由**: 使用 Decision 结构控制流程，禁止依赖 `tool_calls[0]["name"]`
3. **统一输出**: 所有工具返回统一的 ToolResult 结构
4. **单次执行**: 流式输出采用单次 Graph 执行路径，避免重复推进

---

## 📋 架构契约 (Graph Contract)

### 1. AgentState 字段契约

**字段定义**:
- `messages: List[Dict]` - 对话消息列表
- `decision: Decision | None` - 路由决策
- `tool_results: List[ToolResult]` - 工具调用结果列表
- `artifacts: Dict` - 结构化产出(session_id、temperature、top_k 等)
- `last_error: str | None` - 最后一次错误
- `trace: Dict | None` - 追踪信息(节点耗时、路由路径等)

**字段写入规则（强制）**:
- **orchestrator**: 只写 `decision`（可写 `trace`）
- **tool_exec**: 只追加 `tool_results`（可写 `trace`/`last_error`）
- **respond**: 只追加 `messages`（assistant）与可写 `trace`

**规范**:
- `messages`: 始终追加，不随意覆盖
- `decision`: 由 orchestrator 写入，用于路由
- `tool_results`: 由 tool_exec 追加，用于 respond 生成引用式回答

### 2. Decision 结构契约

**字段定义**:
- `action: Literal["CALL_TOOL", "RESPOND", "END", "CLARIFY"]` - 路由动作
- `tool_name?: str` - 工具名称（当 action=CALL_TOOL 时必填）
- `tool_args?: Dict` - 工具参数
- `rationale?: str` - 决策理由（可选，用于调试）
- `confidence?: float` - 置信度（可选，用于排序/阈值）

**路由规则**:
- `action == CALL_TOOL` → tool_exec
- `action == RESPOND` → respond
- `action == CLARIFY` → respond（输出澄清问题）
- `action == END` → END

**禁止事项**:
- 禁止使用 `tool_calls[0]["name"]` 作为路由依据（脆弱且难扩展）

### 3. ToolResult 结构契约

**字段定义**:
- `ok: bool` - 是否成功
- `name: str` - 工具名称
- `data: Any` - 结构化数据
- `sources?: List[Dict]` - 引用来源（RAG 文档/网页链接等）
- `error?: str` - 错误信息
- `latency_ms?: int` - 延迟（可选，用于监控）

**规范**:
- 每次工具调用都必须返回 ToolResult（不允许直接 throw 到图外）
- `sources` 用于 respond 节点生成引用式回答（可选）

---

## 🔧 核心模块说明

### 1. 配置层 (`config.py`)

- 集中管理所有配置项(API Key、模型参数、路径等)
- 支持多 LLM 模型配置与动态切换
- 环境变量优先,代码配置兜底

### 2. Agent 系统 (`agents/`)

**架构**: LangGraph StateGraph + Explicit Decision Routing

- **runtime.py**: Agent Runtime 运行时
  - 提供 `invoke()` 和 `stream_messages()` 接口
  - 集成 SQLite Checkpointer 管理会话记忆
  - 支持动态参数传递(temperature、top_k、max_tokens 等)
  - 采用单次图执行路径，避免流式链路重复推进

- **graph.py**: StateGraph 构建与编译
  - 定义节点(orchestrator、tool_exec、respond)
  - 定义边和条件路由
  - 集成 Checkpointer

- **state.py**: 数据结构定义
  - `AgentState`: 状态契约(messages、decision、tool_results、artifacts)
  - `Decision`: 显式路由决策(action、tool_name、tool_args、rationale)
  - `ToolResult`: 统一工具输出(ok、name、data、sources、error)

- **nodes/**: Graph 节点实现
  - `orchestrator.py`: 使用 LLM 分析用户输入,产出 Decision
  - `tool_exec.py`: 根据 Decision 调用工具层
  - `respond.py`: 使用 LLM 生成最终回复(支持流式)

### 3. 工具层 (`tools/`)

**职责**: 统一的工具签名与 ToolResult 输出

**允许**:
- 参数校验与默认值注入
- 调用 Service 层执行真正的业务逻辑
- 返回统一的 ToolResult 结构

**禁止**:
- 直接访问数据库/向量库/HTTP（必须通过 Service）
- 在 Tool 内写复杂策略与路由逻辑

### 4. API 层 (`api/`)

- **chat.py**: 聊天接口(流式输出、语音识别/合成、对话管理)
- **document.py**: 文档管理接口(上传、向量化、查询、删除)

### 5. 核心层 (`core/`)

- **llm_handler.py**: LLM 调用适配器,支持 DashScope/Ollama
- **conversation_manager.py**: 对话历史管理,从 SQLite 读取/删除/更新
- **checkpointer.py**: LangGraph Checkpointer 工厂,优先 SQLite,降级 Memory

### 6. 服务层 (`services/`)

- **document_ingest_service.py**: 文档摄取(加载、切分、生成 metadata)
- **embedding_service.py**: 向量化服务(OpenAI Embeddings 单例)
- **retriever_service.py**: Retriever 构建服务(支持 MultiQueryRetriever)
- **vector_store_repository.py**: 向量数据库仓储层(Chroma 操作封装)
- **speech_service.py**: 语音服务(Qwen ASR/TTS)
- **web_search_service.py**: 联网搜索服务(Tavily API)

### 7. Prompt 管理 (`prompts/`)

- 使用 Markdown 文件管理 Prompt 模板
- `loader.py` 提供统一加载接口
- 支持动态加载与热更新

### 8. 工具函数 (`utils/`)

- **file_utils.py**: 文件操作工具(哈希、时间戳、文件信息)
- **logger.py**: 结构化日志配置

---

## 🛠️ 技术栈

- **Web 框架**: Flask
- **LLM 框架**: LangChain + LangGraph
- **向量数据库**: Chroma
- **LLM 提供商**: 阿里云 DashScope (Qwen 系列)
- **Embedding 模型**: text-embedding-v4
- **语音服务**: Qwen ASR/TTS
- **联网搜索**: Tavily API

---

## 💾 数据存储

- **向量数据库**: `data/vector_store/` (Chroma)
- **对话历史**: `data/chat_memory/chat_memory.db` (SQLite)
- **上传文档**: `data/upload_documents/`

---

## ✨ 关键特性

1. **动态 Agent 创建**: 每次请求按需创建 Agent,支持动态参数(temperature、top_k、max_tokens 等)
2. **会话隔离**: 基于 session_id 隔离文档与对话历史
3. **记忆管理**: SQLite 持久化对话历史,自动 Summarization 压缩
4. **联网搜索**: 可选启用 Tavily 联网搜索增强 RAG
5. **语音交互**: 支持语音输入(ASR)与语音输出(TTS)
6. **流式输出**: SSE 流式返回 LLM 生成内容
7. **模型降级**: 支持多模型配置与自动降级

---

## 📝 维护说明

**本文档由 AI Assistant 维护,遵循以下规则**:

1. **架构变更**: 每次架构调整后,立即更新对应章节
2. **契约更新**: State/Decision/ToolResult 结构变更时,同步更新契约章节
3. **模块新增**: 新增核心模块时,补充到核心模块说明章节
4. **目录同步**: 目录结构变更时,同步更新目录树

**更新频率**:
- 架构变更后: 立即更新
- 契约变更后: 立即更新
- 模块新增后: 当天更新

---

**文档版本**: v2.0.0
**最后更新**: 2026-03-04
