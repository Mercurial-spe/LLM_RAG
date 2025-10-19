

# RAG-LLM 智能问答系统

本项目是一个基于检索增强生成（Retrieval-Augmented Generation, RAG）架构的智能问答系统。旨在以特定课程资料为知识库，为用户提供精准、基于事实的回答。项目采用前后端分离架构，前端使用 Vue 构建用户交互界面，后端使用 Python (Flask) 提供 API 服务，并通过 API-KEY 的方式调用大语言模型（LLM）。

## 📁 文件目录结构

```plaintext
Project-RAG-LLM/
├── backend/                  # 后端服务 (Python, Flask)
│   ├── app/                  # Flask 应用核心代码
│   │   ├── __init__.py       # 应用工厂
│   │   ├── api/              # API 路由/视图
│   │   │   ├── chat.py       # 处理聊天问答 API
│   │   │   └── document.py   # 处理文件上传 API
│   │   ├── core/             # 核心业务逻辑
│   │   │   ├── rag_pipeline.py # RAG 核心管道
│   │   │   └── llm_handler.py  # LLM API 封装
│   │   ├── services/         # 服务层 (原子化功能)
│   │   │   ├── document_service.py # 文档处理服务
│   │   │   └── vector_store_service.py # 向量数据库服务
│   │   ├── config.py         # 配置文件
│   │   └── models.py         # Pydantic 数据模型
│   ├── tests/                # 测试用例
│   ├── run.py                # 启动 Flask 应用的入口
│   └── requirements.txt      # Python 依赖
├── frontend/                 # 前端服务 (Vue)
│   └── ...
├── data/                     # 数据与知识库
│   ├── raw_documents/        # 原始课程资料 (PDF等)
├── scripts/                  # 辅助脚本
│   └── ingest_data.py        # 离线数据预处理和入库脚本
├── .gitignore                # Git 忽略配置
└── README.md                 # 项目说明文档
```

## ⚙️ 核心业务逻辑

项目主要包含三种核心的业务流程：

### 1\. 离线知识库构建

此流程用于在项目启动前，将所有静态的课程资料构建成可供检索的向量数据库。

1.  **触发**：开发者在服务器上运行命令 `python scripts/ingest_data.py`。
2.  **`ingest_data.py`** 脚本开始执行，它会遍历 `data/raw_documents/` 目录下的所有文件。
3.  对于每个文件，脚本会调用 **`services/document_service.py`** 中的函数。该服务负责将文件（如PDF）加载、解析并切分成小的文本块（Chunks）。
4.  脚本收集所有文本块，调用嵌入模型（Embedding Model）将它们批量转换为向量。
5.  最后，脚本调用 **`services/vector_store_service.py`** 中的函数，将所有文本块和它们对应的向量存入 `data/vector_store/` 中的数据库。
6.  流程结束，一个可供查询的知识库构建完成。

### 2\. 用户实时问答 (Chat)

当用户在前端界面提出问题时，系统执行此流程。

1.  **触发**：前端向后端的 `/api/chat` 接口发送一个包含用户问题的 POST 请求。
2.  **`api/chat.py`** 接收到请求，验证数据格式后，调用核心处理管道 **`core/rag_pipeline.py`**。
3.  **`rag_pipeline.py`** 开始执行 RAG 流程：
    a. 将用户问题转换为查询向量。
    b. 调用 **`services/vector_store_service.py`**，在向量数据库中检索最相关的上下文文本块。
    c. 构建一个包含“上下文”和“用户问题”的 Prompt。
    d. 调用 **`core/llm_handler.py`**，将构建好的 Prompt 发送给大语言模型（LLM）。
4.  **`llm_handler.py`** 接收到 LLM 返回的纯文本答案。
5.  结果逐层返回到 **`api/chat.py`**，它会将最终答案和引用来源打包成 JSON 格式，通过 HTTP 响应回传给前端。

### 3\. 用户上传新文件

此流程允许用户动态地向知识库中添加新的文档。

1.  **触发**：用户在前端界面上传一个新文件（如PDF），前端将文件发送到 `/api/document` 接口。
2.  **`api/document.py`** 接收到文件。
3.  它调用 **`services/document_service.py`**，将这个新文件解析并切分成文本块。
4.  接着，它调用嵌入模型将这些新的文本块转换为向量。
5.  最后，它调用 **`services/vector_store_service.py`**，将这些新的文本块和向量**添加**到现有的向量数据库中。
6.  流程结束，知识库被实时更新。

-----

## 📄 重点文件深度解析

以下文件是项目架构的核心，理解它们的职责是理解整个项目的关键。

### `core/llm_handler.py` (LLM 处理器)

这个文件是项目与外部大语言模型（LLM）API之间的**唯一**接口，扮演着“采购员”或“翻译官”的角色。

  * **这个文件只关注**：如何根据配置（API-Key, Endpoint）调用一个具体的大模型 API，并处理其特定的请求格式和响应格式。
  * **输入**：一个已经由 `rag_pipeline` 精心构建好的、可以直接发给模型的 Prompt 字符串。
  * **输出**：一个从 LLM 返回的、纯净的答案字符串。

### `core/rag_pipeline.py` (RAG 核心管道)

这个文件是项目业务逻辑的**总指挥**，负责编排整个 RAG 流程。它就像一个“总工程师”。

  * **这个文件只关注**：接收用户问题后，如何一步步地执行“检索 -\> 增强 -\> 生成”的完整流程。它决定了应该先做什么、后做什么。
  * **输入**：用户的原始问题字符串 (e.g., "什么是RAG?")。
  * **输出**：一个包含最终答案和引用来源的结构化数据（通常是 Python 字典），供 API 层返回给前端。

### `services/` 目录 (原子服务层)

这个目录下的文件提供具体的、可复用的“专业职能”服务。

  * **`document_service.py`**

      * **这个文件只关注**：如何将一个**单个**原始文件（如 PDF, TXT）转换成标准化的文本块列表（List of Chunks）。它负责加载、解析、清洗和切分。
      * **输入**：一个文件的路径或文件对象。
      * **输出**：一个由多个字符串组成的文本块列表。

  * **`vector_store_service.py`**

      * **这个文件只关注**：如何与底层的向量数据库进行交互（增、查）。它屏蔽了具体数据库（如 Chroma, FAISS）的实现细节。
      * **输入**：在**存入**时，输入是文本块和对应的向量；在**查询**时，输入是查询向量。
      * **输出**：在**查询**时，输出是相关的文本块列表。

### `api/chat.py` 和 `api/document.py` (API 接口层)

这两个文件是后端与前端通信的**网关**，是项目的“前台接待”。

  * **这两个文件只关注**：处理 HTTP 请求和发送 HTTP 响应。它们负责解析前端传来的 JSON 数据或文件，调用相应的业务逻辑（`core` 或 `services`），然后将处理结果打包成 JSON 格式返回给前端。
  * **输入**：来自前端的 HTTP 请求。
  * **输出**：发送给前端的、符合接口约定的 JSON 格式的 HTTP 响应。

### `scripts/ingest_data.py` (离线处理脚本)

这个文件是用于执行批量化、耗时较长的数据处理任务的**独立脚本**。它就像项目的“施工队长”。

  * **这个文件只关注**：编排整个离线知识库的构建流程。它不处理实时网络请求。
  * **输入**：无直接输入，它会主动读取 `data/raw_documents/` 目录下的文件。
  * **输出**：一个构建完成并保存在 `data/vector_store/` 的向量数据库，以及在命令行中打印的日志信息。
  
## 项目运行：
### 初始环境构建
- conda create -n rag_env python=3.11
- conda activate rag_env
- cd project-RAG-LLM\backend
- pip install -r requirements.txt

### python后端说明
- 项目只有在出口处使用绝对导入，这里指的是run.py
- 项目内部均使用相对导入 .xxx.xxx.xxx 所以要运行单个模块的话(以llm_handler.py为例，根目录为project-RAG-LLM) ： python -m backend.app.core.llm_handler (要写 if __name__ == "__main__")
- 运行整个项目 python run.py
- 在LLM_RAG\project-RAG-LLM\backend使用pip freeze > requirements.txt 一键添加包信息，方便其他人使用

### 貌似没有文件的文件夹GitHub不会识别，所以我在前端里塞了几个没用的文件