"""
LangChain 读取测试
=================
本测试仅通过 LangChain 的 Retriever 接口从本地 Chroma 集合读取，
不进行任何写入或重新索引。核心区别：不调用我们自定义的相似度检索，
而是使用 `VectorStoreRepository.as_langchain_retriever(...)` 返回的
LangChain Retriever 完成检索。
"""

import logging
import sys
from pathlib import Path
from typing import List

# --- 将项目根目录添加到 Python 路径中 ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

# --- 导入项目内模块 ---
try:
    from backend.app.services.embedding_service import EmbeddingService
    from backend.app.services.vector_store_repository import VectorStoreRepository
except ImportError as e:
    print(f"导入模块失败，请检查 PYTHONPATH 是否正确设置: {e}")
    print(f"PROJECT_ROOT (已添加到 sys.path): {PROJECT_ROOT}")
    sys.exit(1)

# --- LangChain 接口 ---
from langchain_core.embeddings import Embeddings
from langchain.tools import tool
from langchain.agents import create_agent


# --- 日志配置（抑制第三方噪声，聚焦结果展示） ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


class LCEmbeddingAdapter(Embeddings):
    """将项目内的 EmbeddingService 适配为 LangChain Embeddings 接口。

    仅实现查询与文档嵌入所需的最小方法：
      - embed_documents
      - embed_query
    """

    def __init__(self, service: EmbeddingService):
        self._service = service

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._service.embed_texts(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._service.embed_text(text)


TEST_QUESTIONS = [
    "说明计算机网络的学习内容。",
    "TCP 和 UDP 有什么主要区别？",
    "请详细解释一下 TCP 的三次握手过程。",
]


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 开始 LangChain Retriever 本地读取测试（仅读，不写）")
    logger.info("=" * 60)

    try:
        # 1) 初始化服务
        logger.info("[1] 初始化 EmbeddingService 与 VectorStoreRepository ...")
        embedding_service = EmbeddingService.get_instance()
        vector_repo = VectorStoreRepository()

        # 2) 构建 LangChain Embeddings 适配器与 Retriever
        logger.info("[2] 构建 LangChain Embeddings 适配器与 Retriever ...")
        lc_embeddings = LCEmbeddingAdapter(embedding_service)

        retriever = vector_repo.as_langchain_retriever(
            embedding_instance=lc_embeddings,
            search_type="similarity",
            search_kwargs={"k": 5},
        )
        logger.info("✓ Retriever 构建成功（附着到现有 Chroma 集合，仅执行读取）")

        # 3) 基于 Agent 的实现：将检索注册为工具，由 Agent 自主调用
        logger.info("[3] 构建 Agent（检索作为工具） ...")
        from backend.app.core.llm_handler import LLMHandler
        llm = LLMHandler.get_instance().get_model()

        @tool("retrieve_context", response_format="content_and_artifact")
        def retrieve_context(query: str):
            """检索与问题相关的上下文内容。返回拼接文本以及原始文档列表。"""
            retrieved_docs = retriever.invoke(query)
            serialized = "\n\n".join(
                (f"Source: {doc.metadata.get('source', '<unknown>')}\nContent: {doc.page_content}")
                for doc in retrieved_docs
            )
            return serialized, retrieved_docs

        tools = [retrieve_context]
        system_prompt = (
            "你有一个用于检索上下文的工具 retrieve_context。"
            "请在需要外部知识时调用该工具，并基于返回的内容回答用户问题。"
            "无法从上下文确定答案时请明确说明。"
        )

        agent = create_agent(llm, tools, system_prompt=system_prompt)

        # 4) 执行查询（仅流式 LLM 文本输出）：不显示工具步骤
        logger.info(f"[4] 准备执行 {len(TEST_QUESTIONS)} 个查询 ...")
        for i, question in enumerate(TEST_QUESTIONS, start=1):
            logger.info("\n" + "=" * 24 + f" [ 测试 {i}/{len(TEST_QUESTIONS)} ] " + "=" * 24)
            logger.info(f"  [问题]: {question}")

            print("\n" + "-" * 20 + " Agent Streaming (LLM messages) " + "-" * 20)
            final_text = []
            for token, metadata in agent.stream(
                {"messages": [{"role": "user", "content": question}]},
                stream_mode="messages",
            ):
                # 只关注模型节点产生的文本块（忽略工具与非文本块）
                node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None
                content_blocks = getattr(token, "content_blocks", None)
                if node == "model" and content_blocks:
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                final_text.append(text)
                                print(text, end="", flush=True)

            print("\n" + "-" * 20 + " Agent 最终回答（合并） " + "-" * 20)
            print("".join(final_text) or "<无输出>")

        logger.info("\n" + "=" * 60)
        logger.info("🎉 LangChain 读取测试执行完毕")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ LangChain 读取测试失败: {e}", exc_info=True)

