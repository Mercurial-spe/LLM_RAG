
# RAG-LLM 智能问答系统

本项目基于 RAG（Retrieval-Augmented Generation）思想，采用前后端分离架构：后端为 Python Flask API 服务，前端为 React + TypeScript 单页应用。系统已完成文档加载/切分、嵌入（向量化）、向量库存储、RAG 查询流程、对话管理、文档上传等核心功能，支持流式输出和对话历史持久化。

## 📁 项目结构

```plaintext
project-RAG-LLM/
├── backend/                         # 后端（Python Flask）
│   ├── Dockerfile                   # Docker 镜像构建文件
│   ├── requirements.txt             # 后端依赖
│   ├── run.py                       # Flask 应用启动入口
│   └── app/
│       ├── __init__.py              # Flask 应用工厂
│       ├── config.py                # 配置：嵌入模型、向量库、切分参数等
│       ├── models.py                # 数据模型定义
│       ├── api/                     # API 路由层
│       │   ├── __init__.py
│       │   ├── chat.py              # 聊天 API（流式输出、对话管理）
│       │   └── document.py          # 文档管理 API（上传、列表、删除）
│       ├── core/                    # 核心逻辑层
│       │   ├── llm_handler.py       # LLM 调用封装（DashScope/Ollama，兼容 OpenAI SDK）
│       │   ├── rag_pipeline.py      # RAG 流程编排（LCEL 链）
│       │   ├── rag_agent.py         # RAG Agent（LangGraph，支持流式、记忆管理）
│       │   └── conversation_manager.py  # 对话历史管理（SQLite）
│       ├── services/                # 服务层
│       │   ├── document_ingest_service.py  # 文档加载/切分
│       │   ├── embedding_service.py        # 嵌入服务（DashScope text-embedding-v4）
│       │   ├── sync_service.py             # 单向差异同步（增量入库）
│       │   └── vector_store_repository.py  # 向量库仓库（ChromaDB 数据访问层）
│       ├── tests/                   # 测试文件
│       │   ├── test_api.py
│       │   ├── test_all.py
│       │   ├── test_langchain.py
│       │   └── test_summary.py
│       └── utils/
│           ├── file_utils.py        # 通用文件工具（哈希/时间/文件信息）
│           └── logger.py            # 日志配置
├── frontend/                        # 前端（React + TypeScript）
│   ├── Dockerfile                   # Docker 镜像构建文件
│   ├── package.json                 # 前端依赖
│   ├── vite.config.ts               # Vite 配置
│   └── src/
│       ├── api/                     # API 客户端
│       │   ├── chat.ts             # 聊天 API 客户端
│       │   ├── conversation.ts      # 对话管理 API 客户端
│       │   └── document.ts         # 文档管理 API 客户端
│       ├── components/             # React 组件
│       │   ├── ConversationSidebar/ # 对话侧边栏
│       │   └── layout/             # 布局组件
│       ├── pages/                  # 页面组件
│       │   ├── Chat/               # 聊天页面
│       │   ├── Documents/          # 文档管理页面
│       │   └── Home/               # 首页
│       ├── stores/                 # 状态管理（Zustand）
│       │   └── conversationStore.ts
│       ├── router/                 # 路由配置
│       └── types/                  # TypeScript 类型定义
├── data/
│   ├── raw_documents/              # 原始文档（txt/md/pdf/docx 等）
│   ├── upload_documents/           # 用户上传的文档
│   ├── vector_store/               # 向量库持久化目录（ChromaDB）
│   └── chat_memory/                # 对话历史数据库（SQLite）
├── scripts/
│   ├── ingest_data.py              # 批量入库脚本（目录级增量处理）
│   └── clear_chat_history.py      # 清理对话历史脚本
├── nginx.conf                      # Nginx 反向代理配置（生产环境）
└── docker-compose.yaml             # Docker Compose 编排文件
```

## ⚙️ 核心功能

### 后端功能

- **文档摄取**（`services/document_ingest_service.py`）
  - 支持 TXT/MD（UTF-8）、PDF、DOCX/DOC（DOC 需系统安装 LibreOffice）
  - 采用 LangChain Loader + `RecursiveCharacterTextSplitter` 切分
  - 统一输出：`{"id", "content", "metadata"}`，元数据包含来源路径、mtime/size、chunk_hash、session_id 等

- **文本向量化**（`services/embedding_service.py`）
  - 阿里云百炼 `text-embedding-v4`（OpenAI SDK 兼容模式）
  - 单例模式；支持批量处理（自动按 batch=10 分批）
  - 默认 1024 维，可通过配置调整

- **向量库存储**（`services/vector_store_repository.py`）
  - 使用 ChromaDB（原生客户端）
  - 原子操作：`upsert_batch`、`delete_by_source`、`delete_by_ids`、`get_indexed_file_state`、`query_similar`
  - 便捷桥接：提供 `as_langchain_retriever()` 以适配 LangChain RAG 查询
  - 支持按 `session_id` 过滤检索（区分系统文档和用户上传文档）

- **RAG 流程**（`core/rag_pipeline.py`、`core/rag_agent.py`）
  - **RAG Pipeline**：基于 LangChain LCEL 的检索-增强-生成流程
  - **RAG Agent**：基于 LangGraph 的智能 Agent，支持工具调用、流式输出
  - 支持动态参数配置（temperature、top_k、messages_to_keep、max_tokens）
  - 自动记忆管理：当 token 数超过阈值时触发 Summarization 压缩历史

- **对话管理**（`core/conversation_manager.py`）
  - SQLite 持久化对话历史（存储在 `data/chat_memory/chat_memory.db`）
  - 支持对话列表查询、消息历史查询、对话删除、标题更新
  - 基于 LangGraph Checkpointer 实现多会话隔离

- **API 服务**（`api/chat.py`、`api/document.py`）
  - **聊天 API**：
    - `POST /api/chat/stream` - SSE 流式聊天（支持动态参数）
    - `GET /api/conversations` - 获取对话列表
    - `GET /api/conversations/<thread_id>/messages` - 获取对话消息
    - `POST /api/conversations` - 创建新对话
    - `DELETE /api/conversations/<thread_id>` - 删除对话
    - `PATCH /api/conversations/<thread_id>` - 更新对话标题
  - **文档 API**：
    - `POST /api/documents/upload` - 文档上传（自动向量化入库）
    - `GET /api/documents` - 获取文档列表
    - `GET /api/documents/session/<session_id>` - 获取会话文档列表
    - `DELETE /api/documents/<document_id>` - 删除文档

- **单向差异同步**（`services/sync_service.py`）
  - 扫描本地文件状态 ↔ 读取向量库状态 → 计算增量差异
  - 删除已变更/已删除文件的旧 chunk；对新增/更新文件重新摄取+向量化+Upsert
  - 输出同步统计：新增/更新/删除文件数，新增/删除 chunk 数

- **入库脚本**（`scripts/ingest_data.py`）
  - 自动加载配置并初始化各服务
  - 基于 `RAW_DOCUMENTS_PATH` 的目录级增量入库
  - 详细日志与总结输出

### 前端功能

- **React + TypeScript + Vite** 现代化前端架构
- **聊天界面**：支持流式消息显示、Markdown 渲染、代码高亮
- **对话管理**：侧边栏显示对话列表，支持创建、切换、删除对话
- **文档管理**：文档上传、列表展示、删除功能
- **状态管理**：使用 Zustand 管理对话状态
- **响应式设计**：适配不同屏幕尺寸

## 🔧 配置与环境

### 环境变量配置

在项目根目录或 `backend/` 目录创建 `.env` 文件（参考 `backend/.env_example`）：

```bash
# LLM 提供商：dashscope（阿里云百炼）或 ollama（本地模型）
LLM_PROVIDER=dashscope

# DashScope API Key（必需）
DASHSCOPE_API_KEY=your_dashscope_api_key

# Ollama 配置（LLM_PROVIDER=ollama 时使用）
OLLAMA_API_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=llama3.2:1b

# LLM 模型配置
LLM_MODEL_NAME=qwen3-max
LLM_MAX_TOKENS=8192
LLM_ENABLE_THINKING=False

# Flask 配置
DEBUG=True
FLASK_HOST=localhost
FLASK_PORT=5000

# CORS 配置（开发环境启用，生产环境禁用）
ENABLE_CORS=True
CORS_ORIGINS=*

# 路径配置（可选，默认基于项目根自动计算）
# VECTOR_STORE_PATH=/abs/path/to/vector_store
# RAW_DOCUMENTS_PATH=/abs/path/to/documents
# CHAT_MEMORY_DB_PATH=/abs/path/to/chat_memory.db
```

### 关键配置项说明

- **嵌入模型**：`EMBEDDING_MODEL_NAME=text-embedding-v4`、`EMBEDDING_DIMENSION=1024`、`EMBEDDING_BATCH_SIZE=10`
- **向量库**：`VECTOR_STORE_PATH`（默认项目绝对路径）、`VECTOR_COLLECTION_NAME=course_documents`
- **文档目录**：`RAW_DOCUMENTS_PATH`（默认项目绝对路径）
- **文档切分**：`CHUNK_SIZE=500`、`CHUNK_OVERLAP=50`
- **RAG 参数**：`RAG_TOP_K=3`、`RAG_TEMPERATURE=0.2`
- **记忆管理**：`MEMORY_MAX_TOKENS_BEFORE_SUMMARY=30000`、`MEMORY_MESSAGES_TO_KEEP=20`

## ▶️ 快速开始

### 环境准备

1. **Python 环境**（推荐 Python 3.11+）
   ```powershell
   # 创建 Conda 环境
   conda create -n rag_llm_env python=3.11
   conda activate rag_llm_env

   # 安装后端依赖
   cd project-RAG-LLM/backend
   pip install -r requirements.txt
   ```

2. **Node.js 环境**（推荐 Node.js 18+）
   ```powershell
   # 安装前端依赖
   cd project-RAG-LLM/frontend
   npm install
   ```

3. **配置环境变量**
   - 在项目根目录或 `backend/` 目录创建 `.env` 文件
   - 配置 `DASHSCOPE_API_KEY` 等必需参数（见上方配置说明）

### 启动服务

#### 方式一：本地开发（推荐）

**启动后端**：
```powershell
cd project-RAG-LLM/backend
python run.py
```
后端将在 `http://localhost:5000` 启动

**启动前端**：
```powershell
cd project-RAG-LLM/frontend
npm run dev
```
前端将在 `http://localhost:5173` 启动

#### 方式二：Docker Compose（生产环境）

```powershell
# 在项目根目录执行
docker-compose up -d
```

后端：`http://localhost:5000`  
前端：`http://localhost:5173`

### 数据入库

**批量入库脚本**（目录级增量处理）：
```powershell
# 激活环境
conda activate rag_llm_env

# 执行入库（读取 backend/app/config.py 的 RAW_DOCUMENTS_PATH）
python project-RAG-LLM/scripts/ingest_data.py
```

**通过前端上传**：
- 访问 `http://localhost:5173/documents`
- 点击上传按钮，选择文档文件
- 系统会自动向量化并入库

### 其他工具脚本

- **清理对话历史**：
  ```powershell
  python project-RAG-LLM/scripts/clear_chat_history.py
  ```

- **向量化服务自检**：
  ```powershell
  python project-RAG-LLM/backend/app/services/embedding_service.py
  ```

- **LLM 调用演示**：
  ```powershell
  python project-RAG-LLM/backend/app/core/llm_handler.py
  ```

### 注意事项

- 若在 Windows 上遇到 OpenAI SDK 平台信息采集导致的偶发阻塞，可尝试升级/降级 `openai` 版本或增加重试与超时
- `.doc` 解析依赖 LibreOffice（`soffice`），未安装时请先转为 `.docx` 再处理
- 生产环境建议使用 Nginx 反向代理，禁用 CORS，统一域名访问

## 🧩 技术架构

### 后端架构

- **API 层**：Flask Blueprint 路由，处理 HTTP 请求/响应
- **核心逻辑层**：
  - `rag_pipeline.py` - RAG 流程编排（LCEL 链）
  - `rag_agent.py` - RAG Agent（LangGraph，支持工具调用、流式输出、记忆管理）
  - `llm_handler.py` - LLM 调用封装（DashScope/Ollama，兼容 OpenAI SDK）
  - `conversation_manager.py` - 对话历史管理（SQLite）
- **服务层**：
  - `document_ingest_service.py` - 文档处理（加载、切分）
  - `embedding_service.py` - 文本向量化（单例、批处理）
  - `sync_service.py` - 差异同步（增量入库）
  - `vector_store_repository.py` - 向量库数据访问（ChromaDB）
- **数据层**：
  - ChromaDB - 向量存储
  - SQLite - 对话历史存储

### 前端架构

- **框架**：React 19 + TypeScript + Vite
- **状态管理**：Zustand
- **路由**：React Router
- **UI 组件**：自定义组件（Chat、Documents、ConversationSidebar）
- **API 客户端**：Axios + SSE（Server-Sent Events）流式处理

### 关键技术栈

- **后端**：Python 3.11+、Flask、LangChain、LangGraph、ChromaDB、SQLite
- **前端**：React、TypeScript、Vite、Zustand、React Router、Axios
- **部署**：Docker、Docker Compose、Nginx（可选）

## 📌 开发者提示

- 由于目录名含有连字符（`project-RAG-LLM`），不建议使用 `-m` 方式作为包运行，直接以文件路径运行脚本更稳妥
- 开发环境建议启用 CORS（`ENABLE_CORS=True`），生产环境禁用 CORS，由 Nginx 反向代理统一处理
- 对话历史存储在 SQLite 数据库中，可通过 `scripts/clear_chat_history.py` 清理
- 文档上传后会自动向量化并入库，支持按 `session_id` 区分不同会话的文档
- RAG Agent 支持动态参数配置（temperature、top_k、messages_to_keep、max_tokens），可通过前端传递

## 🚀 部署说明

### Docker 部署

项目已提供 `docker-compose.yaml`，支持一键部署前后端服务：

```powershell
docker-compose up -d
```

### Nginx 反向代理（生产环境）

生产环境建议使用 Nginx 反向代理，统一域名访问，禁用 CORS。参考 `nginx.conf` 配置示例。

### 环境变量

- 开发环境：在 `.env` 文件中配置
- Docker 环境：通过 `docker-compose.yaml` 的 `environment` 部分配置
- 生产环境：通过系统环境变量或容器环境变量配置
