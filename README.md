

# RAG-LLM 智能问答系统

本项目基于 RAG（Retrieval-Augmented Generation）思想，采用前后端分离架构：后端为 Python 代码库（Flask 预留，当前以服务类和脚本为主），前端预留 Vue 目录。当前阶段已完成文档加载/切分、嵌入（向量化）、向量库仓库与“单向差异同步”入库编排等基础能力。

## 📁 项目结构（已对齐当前代码）

```plaintext
project-RAG-LLM/
├── backend/                         # 后端（Python）
│   ├── .env_example                 # 环境变量示例（MODELSCOPE_API_KEY, DASHSCOPE_API_KEY）
│   ├── requirements.txt             # 后端依赖
│   ├── run.py                       # 临时入口（演示调用 LLM 流式输出）
│   └── app/
│       ├── __init__.py              # 占位（后续用于 Flask 应用工厂）
│       ├── config.py                # 配置：嵌入模型、向量库、切分参数等
│       ├── models.py                # 占位（后续用于请求/响应模型）
│       ├── api/                     # API 层（当前占位）
│       │   ├── __init__.py
│       │   ├── chat.py              # 预留 /api/chat（暂空）
│       │   └── document.py          # 预留 /api/document（暂空）
│       ├── core/                    # 核心逻辑
│       │   ├── llm_handler.py       # LLM 调用封装（基于 ModelScope 兼容 OpenAI SDK）
│       │   └── rag__pipeline.py     # RAG 主流程（占位，尚未实现）
│       ├── services/                # 服务层（已实现，已重构命名）
│       │   ├── document_ingest_service.py  # 文档加载/切分（不含向量化与存储）
│       │   ├── embedding_service.py        # 嵌入服务（DashScope text-embedding-v4，单例+批处理）
│       │   ├── sync_service.py             # 单向差异同步（增量对比→删除→重建入库）
│       │   └── vector_store_repository.py  # 向量库仓库（ChromaDB 数据访问层，原子操作）
│       ├── tests/
│       │   └── test_api.py           # 预留（当前为空）
│       └── utils/
│           └── file_utils.py        # 通用文件工具（哈希/时间/文件信息）
├── data/
│   ├── raw_documents/               # 原始文档（txt/md/pdf/docx 等）
│   └── vector_store/                # 向量库持久化目录（ChromaDB）
├── scripts/
│   └── ingest_data.py               # 入库脚本（已实现，整合配置与同步服务）
└── frontend/                        # 前端占位（便于 Git 识别目录）
```

提示：API 与 RAG 主链路尚未落地，可先使用脚本和服务层验证“加载→切分→向量化→入库→检索”的链路；向量库已具备仓库与入库编排能力。

## ⚙️ 当前已实现的核心能力

- 文档摄取（`services/document_ingest_service.py`）
  - 支持 TXT/MD（UTF-8）、PDF、DOCX/DOC（DOC 需系统安装 LibreOffice）、可按需支持更多
  - 采用 LangChain Loader + `RecursiveCharacterTextSplitter` 切分
  - 统一输出：`{"id", "content", "metadata"}`，元数据包含来源路径、mtime/size、chunk_hash 等

- 文本向量化（`services/embedding_service.py`）
  - 阿里云百炼 `text-embedding-v4`（OpenAI SDK 兼容模式）
  - 单例模式；支持批量处理（自动按 batch=10 分批）
  - 默认 1024 维，可通过配置调整

- 向量库存储（`services/vector_store_repository.py`）
  - 使用 ChromaDB（原生客户端）
  - 原子操作：`upsert_batch`、`delete_by_source`、`delete_by_ids`、`get_indexed_file_state`、`query_similar`
  - 便捷桥接：提供 `as_langchain_retriever()` 以适配 LangChain RAG 查询

- 单向差异同步（`services/sync_service.py`）
  - 扫描本地文件状态 ↔ 读取向量库状态 → 计算增量差异
  - 删除已变更/已删除文件的旧 chunk；对新增/更新文件重新摄取+向量化+Upsert
  - 输出同步统计：新增/更新/删除文件数，新增/删除 chunk 数

- 入库脚本（`scripts/ingest_data.py`）
  - 自动加载配置并初始化各服务
  - 基于 `RAW_DOCUMENTS_PATH` 的目录级增量入库
  - 详细日志与总结输出

## 🧭 规划中的能力（占位/未完成功能）

- RAG 查询流程（`core/rag__pipeline.py`）：Query→向量检索→上下文组装→LLM 生成→答案+引用
- API 服务层（`app/api/chat.py`、`app/api/document.py`）：HTTP 接口，对接前端交互
- LLM 集成优化（`core/llm_handler.py`）：流式输出、错误处理、多模型支持

## 🔧 配置与环境

- 在 `backend/.env` 配置：
  - `MODELSCOPE_API_KEY=...`
  - `DASHSCOPE_API_KEY=...`
- 关键配置项（见 `backend/app/config.py`）：
  - 嵌入：`EMBEDDING_API_BASE_URL`、`EMBEDDING_MODEL_NAME=text-embedding-v4`、`EMBEDDING_DIMENSION=1024`、`EMBEDDING_BATCH_SIZE=10`
  - 向量库：`VECTOR_STORE_PATH`（默认项目绝对路径，支持环境变量覆盖）、`VECTOR_COLLECTION_NAME=course_documents`
  - 文档目录：`RAW_DOCUMENTS_PATH`（默认项目绝对路径，支持环境变量覆盖）
  - 切分：`CHUNK_SIZE=500`、`CHUNK_OVERLAP=50`

### 路径配置说明

- 稳定路径：`VECTOR_STORE_PATH` 与 `RAW_DOCUMENTS_PATH` 均基于项目根自动计算为绝对路径，无论工作目录如何变化都稳定
- 环境变量覆盖：可通过 `.env` 或系统环境变量自定义路径：

  ```bash
  # .env 文件示例
  VECTOR_STORE_PATH=/abs/path/to/vector_store
  RAW_DOCUMENTS_PATH=/abs/path/to/documents
  ```

## ▶️ 快速验证（Windows PowerShell）

- 生产入库脚本（目录批量增量处理）

  ```powershell
  # 激活环境（示例）
  conda activate rag_llm_env

  # 执行入库（读取 backend/app/config.py 的 RAW_DOCUMENTS_PATH）
  python project-RAG-LLM/scripts/ingest_data.py
  ```

- 向量化服务自检（带演示）

  ```powershell
  python project-RAG-LLM/backend/app/services/embedding_service.py
  ```

- LLM 调用演示（ModelScope 兼容 OpenAI SDK）

  ```powershell
  python project-RAG-LLM/backend/app/core/llm_handler.py
  ```

注意：若在 Windows 上遇到 OpenAI SDK 平台信息采集导致的偶发阻塞，可尝试升级/降级 `openai` 版本或增加重试与超时；`.doc` 解析依赖 LibreOffice（`soffice`），未安装时请先转为 `.docx` 再处理。

## 🧩 分层架构（已实现部分）

- 数据访问层：`vector_store_repository.py` - ChromaDB 原子操作，单一职责设计
- 服务业务层：`document_ingest_service.py`（文档处理）、`embedding_service.py`（向量化）、`sync_service.py`（差异同步）
- 工具脚本层：`ingest_data.py` - 生产入库工具
- 配置管理：统一路径配置，支持环境变量覆盖

## 📌 开发者提示

- 由于目录名含有连字符（`project-RAG-LLM`），不建议使用 `-m` 方式作为包运行，直接以文件路径运行脚本更稳妥
- 依赖安装：
  - 建议使用 Conda 创建环境：`conda create -n rag_llm_env python=3.11`；进入 `project-RAG-LLM/backend` 后：`pip install -r requirements.txt`

后续将逐步补全 RAG 管道与 API 层，并提供统一的启动方式（Flask + CORS）。
