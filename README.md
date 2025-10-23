

# RAG-LLM 智能问答系统

本项目基于 RAG（Retrieval-Augmented Generation）思想，采用前后端分离架构：后端为 Python 代码库（Flask 预留，当前以服务类和脚本为主），前端预留 Vue 目录。当前阶段已完成文档加载/切分、嵌入（向量化）、向量库仓库与入库编排等基础能力。

## 📁 实际项目结构（已对齐当前代码）

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
│       ├── services/                # 服务层（已实现）
│       │   ├── document_service.py      # 文档加载/切分与向量化编排
│       │   ├── embedding_service.py     # 嵌入服务（DashScope text-embedding-v4）
│       │   ├── ingestion_service.py     # 入库编排（增量对比、分批写入）
│       │   └── vector_store_repository.py # 向量库仓库（ChromaDB 数据访问层）
│       ├── tests/                   # 后端测试脚本（可直接运行）
│       │   ├── test_document_service.py
│       │   ├── test_load_only.py
│       │   ├── test_simple.py
│       │   └── test_ingestion_flow.py   # 占位
│       └── utils/
│           └── file_utils.py        # 通用文件工具（MD5 等）
├── data/
│   ├── raw_documents/               # 原始文档（txt/md/pdf/docx 等）
│   └── vector_store/                # 向量库持久化目录（ChromaDB）
├── scripts/
│   └── ingest_data.py               # 入库脚本（已实现，支持命令行与配置文件）
└── frontend/                        # 前端占位（便于 Git 识别目录）
```

提示：当前 API 与 RAG 主链路尚未落地，可先使用 tests 与 services 验证加载、切分与向量化流程；向量库已具备仓库与入库编排能力。

## ⚙️ 当前已实现的核心能力

- **完整入库系统**（从零构建）
  - 文档处理（`services/document_service.py`）：支持 TXT/MD（UTF-8）、PDF、DOCX/DOC、PPTX（可选）
  - 嵌入服务（`services/embedding_service.py`）：阿里云百炼 `text-embedding-v4`，单例模式，支持批量处理
  - 向量库仓库（`services/vector_store_repository.py`）：ChromaDB 数据访问层，原子操作设计
  - 入库编排（`services/ingestion_service.py`）：增量更新、MD5去重、分批入库
  - 入库脚本（`scripts/ingest_data.py`）：命令行工具，支持配置化目录扫描

- **核心特性**
  - 统一块结构：`{"content": str, "metadata": {source, chunk_id, file_md5, ...}, "embedding": [...]}`
  - 增量更新：基于文件MD5比对，只处理新增/变更文件
  - 批量优化：文本切分（`RecursiveCharacterTextSplitter`）、嵌入批处理（batch=10）、向量库分批写入
  - 完整测试：端到端入库测试（`test_ingestion_flow.py`）、相似度检索测试（`test_similarity_search.py`）

## 🧭 规划中的能力（占位/未完成功能）

- **RAG 查询流程**（`core/rag__pipeline.py`）：Query→向量检索→上下文组装→LLM生成→答案+引用
- **API 服务层**（`app/api/chat.py`、`app/api/document.py`）：HTTP接口，对接前端交互
- **LLM 集成优化**（`core/llm_handler.py`）：流式输出、错误处理、多模型支持

## � 配置与环境

- 在 `backend/.env` 配置：
  - `MODELSCOPE_API_KEY=...`
  - `DASHSCOPE_API_KEY=...`
- 关键配置项（见 `backend/app/config.py`）：
  - 嵌入：`EMBEDDING_API_BASE_URL`、`EMBEDDING_MODEL_NAME=text-embedding-v4`、`EMBEDDING_DIMENSION=1024`、`EMBEDDING_BATCH_SIZE=10`
  - 向量库：`VECTOR_STORE_PATH`（默认项目绝对路径，支持环境变量覆盖）、`VECTOR_COLLECTION_NAME=course_documents`
  - 文档目录：`RAW_DOCUMENTS_PATH`（默认项目绝对路径，支持环境变量覆盖）
  - 切分：`CHUNK_SIZE=500`、`CHUNK_OVERLAP=50`

### 路径配置增强

- **稳定路径**：`VECTOR_STORE_PATH` 和 `RAW_DOCUMENTS_PATH` 现在使用基于项目根的绝对路径，无论从哪里启动进程都保持一致
- **环境变量覆盖**：可通过 `.env` 文件或系统环境变量自定义路径：

  ```bash
  # .env 文件示例
  VECTOR_STORE_PATH=/path/to/custom/vector_store
  RAW_DOCUMENTS_PATH=/path/to/custom/documents
  ```

## ▶️ 快速验证（本地，PowerShell）

以下脚本均可直接运行验证入库系统：

- **完整入库流程测试**（单文件处理）
  - 运行：`python project-RAG-LLM/backend/tests/test_ingestion_flow.py`
  - 功能：加载→切分→向量化→入库→验证

- **相似度检索测试**（依赖上述入库结果）
  - 运行：`python project-RAG-LLM/backend/tests/test_similarity_search.py`  
  - 功能：问题向量化→相似检索→结果展示

- **生产入库脚本**（目录批量处理）
  - 运行：`python project-RAG-LLM/scripts/ingest_data.py`
  - 功能：扫描默认目录→增量入库→健康检查

- **其他验证脚本**
  - 仅文档解析：`python project-RAG-LLM/backend/tests/test_load_only.py`
  - LLM调用演示：`python project-RAG-LLM/backend/run.py`

注意：若在 Windows 上遇到 OpenAI SDK 平台信息采集导致的偶发阻塞，可尝试升级/降级 `openai` 版本或增加重试与超时；`.doc` 解析依赖 LibreOffice（`soffice`），未安装时请先转为 `.docx` 再处理。

## 🧩 架构设计（已实现部分）

- **数据访问层**：`vector_store_repository.py` - ChromaDB原子操作，单一职责设计
- **服务业务层**：`document_service.py`（文档处理）、`embedding_service.py`（向量化）、`ingestion_service.py`（入库编排）
- **工具脚本层**：`ingest_data.py` - 生产入库工具，支持配置化与命令行覆盖  
- **测试验证层**：端到端测试流程，覆盖入库→检索全链路
- **配置管理**：统一的路径配置，支持环境变量覆盖

## 📌 开发者提示

- 项目内部模块多使用相对导入；如需以模块方式运行，请在仓库根目录下执行（示例）：
  - `python -m backend.app.services.embedding_service`（建议在该文件中补充 `if __name__ == "__main__":` 测试入口）
- 依赖安装：
  - 建议使用 Conda 创建环境：`conda create -n rag_env python=3.11`；进入 `project-RAG-LLM/backend` 后 `pip install -r requirements.txt`

后续将逐步补全 RAG 管道与 API 层，并提供统一的启动方式（Flask + CORS）。
