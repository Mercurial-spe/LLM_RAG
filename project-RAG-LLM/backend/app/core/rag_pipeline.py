# backend/app/core/rag_pipeline.py

"""
RAG 核心编排层
=================
功能：
  1. 整合 EmbeddingService, VectorStoreRepository, LLMHandler。
  2. 采用 LangChain 表达式语言 (LCEL) 构建 RAG 链。
  3. 负责“检索-增强-生成”的完整流程编排。
  4. [已更新] 提供结构化的问答结果，包含答案、来源文件、相似度和原始文本块。
"""

import logging
from typing import List, Dict, Any, Tuple

# 导入您项目已有的服务
from ..services.embedding_service import EmbeddingService
from ..services.vector_store_repository import VectorStoreRepository
from .llm_handler import LLMHandler
from .. import config

# 导入 LangChain 核心组件
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

# --- RAG 核心提示词模板 ---
RAG_PROMPT_TEMPLATE = """
**任务**: 你是一个专业的问答助手。请根据下面提供的“上下文信息”来回答“用户的问题”。

**规则**:
1.  你必须**只使用**“上下文信息”来回答问题，可以适当使用你的知识来润色语言。
2.  **严禁**使用任何“上下文信息”之外的外部知识或个人见解。
3.  如果“上下文信息”中没有足够的内容来回答问题，请**直接**回复："根据我所掌握的资料，无法回答问题。"
4.  你的回答应保持简洁、专业，并直接针对“用户的问题”。
5.  在回答的最后，你**必须**以 "来源: [文件名]" 的格式，列出你参考的所有上下文来源的文件名。

---
[上下文信息]:
{context}
---

[用户的问题]:
{question}
---

[你的回答]:
"""

class RagPipeline:
    """
    RAG 流程编排器
    整合服务并构建 LCEL 链
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_repo: VectorStoreRepository,
        llm_handler: LLMHandler
    ):
        """
        通过依赖注入初始化 RAG 管道
        
        Args:
            embedding_service: 已初始化的 EmbeddingService 实例
            vector_repo: 已初始化的 VectorStoreRepository 实例
            llm_handler: 已初始化的 LLMHandler 实例
        """
        self.embedding_service = embedding_service
        self.vector_repo = vector_repo
        self.llm_handler = llm_handler
        self.llm = llm_handler.get_model() # 获取 ChatOpenAI 实例
        
        # 1. 定义 Prompt 模板
        self.prompt_template = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
        
        # 2. 定义 RAG 链 (使用 LCEL)
        self.rag_chain = (
            self.prompt_template
            | self.llm
            | StrOutputParser()
        )
        
        logger.info("RAG Pipeline 初始化成功。")

    def _format_context(self, docs: List[Dict[str, Any]]) -> str:
        """
        辅助函数：将从 vector_repo 检索到的文档块列表格式化为单个字符串。
        (此函数用于构建 RAG 提示词的上下文)
        
        Args:
            docs: vector_repo.query_similar() 返回的文档块列表
        
        Returns:
            str: 格式化后的上下文字符串
        """
        if not docs:
            return "没有找到相关上下文。"
            
        context_parts = []
        
        for i, doc in enumerate(docs):
            content = doc.get('content')
            file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
            
            context_parts.append(f"[上下文 {i+1} - 来源: {file_name}]:\n{content}")
            
        # 使用分隔符将所有上下文块连接起来
        context_str = "\n\n---\n\n".join(context_parts)
        return context_str

    def _process_retrieved_docs(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        [已更新] 辅助函数：
        1. 从检索到的文档中提取来源、相似度和原始 chunk 内容。
        2. 按相似度降序排序。
        (此函数用于格式化最终返回给用户的结果)
        
        Args:
            docs: vector_repo.query_similar() 返回的文档块列表
        
        Returns:
            List[Dict[str, Any]]: 排序后的 chunk 列表
        """
        if not docs:
            return []

        processed_chunks = []
        for doc in docs:
            file_name = doc.get('metadata', {}).get('file_name', 'Unknown')
            #  vector_repo 直接返回了 'similarity'
            similarity = doc.get('similarity', 0.0)
            content = doc.get('content', '')
            
            processed_chunks.append({
                "source": file_name,
                "similarity": similarity,
                "content": content
            })
        
        # 按相似度降序排序
        processed_chunks.sort(key=lambda x: x['similarity'], reverse=True)
        return processed_chunks

    def query(self, question: str) -> Dict[str, Any]:
        """
        执行一次完整的 RAG 查询
        
        Args:
            question: 用户的原始问题字符串
            
        Returns:
            一个包含答案和检索到的 chunks（含相似度）的字典
        """
        logger.info(f"收到 RAG 查询: '{question}'")
        
        try:
            # 步骤 1: 查询向量化 (Vectorize)
            logger.debug("步骤 1: 正在向量化查询...")
            query_vector = self.embedding_service.embed_text(question)
            
            # 步骤 2: 检索上下文 (Retrieve)
            logger.debug(f"步骤 2: 正在检索 Top-K={config.RAG_TOP_K} 的文档块...")
            similar_docs = self.vector_repo.query_similar(
                query_vector,
                top_k=config.RAG_TOP_K
            )
            
            # [已更新]
            if not similar_docs:
                logger.warning("未检索到任何相关文档。")
                context_str = "没有找到相关上下文。"
                retrieved_chunks = []
            else:
                logger.info(f"检索到 {len(similar_docs)} 个相关文档块。")
                # 步骤 3 (辅助): 格式化上下文 (用于 LLM)
                context_str = self._format_context(similar_docs)
                # 步骤 3 (辅助): 处理检索结果 (用于用户)
                retrieved_chunks = self._process_retrieved_docs(similar_docs)

            # 步骤 4 & 5: 增强 (Augment) 与 生成 (Generate)
            logger.debug("步骤 3/4: 正在调用 LLM 生成答案...")
            answer = self.rag_chain.invoke({
                "context": context_str,
                "question": question
            })
            
            logger.info("RAG 查询成功完成。")
            
            # 步骤 6: 结果封装
            # [已更新] 返回 retrieved_chunks
            return {
                "question": question,
                "answer": answer.strip(),
                "retrieved_chunks": retrieved_chunks, # 
            }
            
        except Exception as e:
            logger.error(f"RAG 查询失败: {e}", exc_info=True)
            return {
                "question": question,
                "answer": "处理问题时发生内部错误，请稍后再试。",
                "retrieved_chunks": [], # <-- 修正：确保返回此键
                "error": str(e)
            }

