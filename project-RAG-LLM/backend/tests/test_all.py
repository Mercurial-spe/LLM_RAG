# backend/tests/test_rag_pipeline.py

"""
RAG Pipeline 计网知识集成测试
================================
目的：
  - 验证 RagPipeline 能否针对“计算机网络”知识库进行端到端的问答。
  - 评估 RAG 从检索、组装上下文到生成答案的整体效果。
  - [已更新] 抑制第三方库的 INFO 日志。
  - [已更新] 打印检索来源及其相似度分数。

运行此测试的前提：
  1. `.env` 文件已正确配置 `DASHSCOPE_API_KEY`。
  2. 向量数据库 (`data/vector_store`) 中已存入计网文档。
  3. DashScope 账户 (Embedding 和 LLM) 额度充足。
"""

import logging
import sys
from pathlib import Path

# --- 将项目根目录添加到 Python 路径中 ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))
# -------------------------------------------------------------------

# --- 现在可以使用绝对路径导入 app 内的模块 ---
try:
    from backend.app.services.embedding_service import EmbeddingService
    from backend.app.services.vector_store_repository import VectorStoreRepository
    from backend.app.core.llm_handler import LLMHandler
    from backend.app.core.rag_pipeline import RagPipeline
except ImportError as e:
    print(f"导入模块失败，请检查 PYTHONPATH 是否正确设置: {e}")
    print(f"PROJECT_ROOT (已添加到 sys.path): {PROJECT_ROOT}")
    sys.exit(1)

# --- [已更新] 配置日志 ---
# 1. 将所有库的默认日志级别设为 WARNING
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# 2. 仅将我们自己的脚本 (logger) 的日志级别设为 INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 3. 特别指定其他嘈杂库的日志级别（如果需要）
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


# --- 精心设计的计网测试问题 ---
COMPUTER_NETWORK_QUESTIONS = [
    "说明计算机网络的学习内容。",
    "TCP 和 UDP 有什么主要区别？",
    "请详细解释一下 TCP 的三次握手过程。",
    # "数据链路层的主要功能有哪些？",
    # "路由器和交换机在功能上有什么不同？",
    # "ARP 协议的作用是什么？",
    # "谁是阿里巴巴的现任 CEO？" # 边界测试
]


# --- 主测试程序 ---
if __name__ == "__main__":
    
    logger.info("=" * 60)
    logger.info("🚀 开始 RAG Pipeline 计网知识集成测试 (日志已简化)")
    logger.info("=" * 60)
    
    try:
        # 1. 初始化所有服务
        logger.info("\n[1] 初始化所有依赖服务...")
        embedding_service = EmbeddingService.get_instance()
        vector_repo = VectorStoreRepository()
        llm_handler = LLMHandler.get_instance()
        
        # 2. 初始化 RAG 管道
        rag_pipeline = RagPipeline(
            embedding_service=embedding_service,
            vector_repo=vector_repo,
            llm_handler=llm_handler
        )
        logger.info("✓ 所有服务和 RAG Pipeline 初始化成功。")
        
        # 3. 循环执行所有计网问题
        logger.info(f"\n[2] 准备执行 {len(COMPUTER_NETWORK_QUESTIONS)} 个计网 RAG 查询...")
        
        for i, question in enumerate(COMPUTER_NETWORK_QUESTIONS):
            
            logger.info(f"\n" + "=" * 25 + f" [ 测试 {i+1}/{len(COMPUTER_NETWORK_QUESTIONS)} ] " + "=" * 25)
            logger.info(f"  [问题]: {question}")
            
            # 执行 RAG 查询
            result = rag_pipeline.query(question)
            
            # [已更新] 打印格式化的结果 (包含相似度)
            print("\n" + "-" * 20 + " RAG 结果 " + "-" * 20)
            print(f"  [回答]: {result['answer']}")
            
            sources_list = result.get('retrieved_chunks', [])
            if sources_list:
                print("  [来源 (按相似度排序)]: ")
                for item in sources_list:
                    print(f"    - : {item['source']} \n   {item['content']}  \n (相似度: {item['similarity']:.4f})  \n")
            else:
                print("  [来源]: 未检索到来源")
            
            if "error" in result:
                print(f"  [错误]: {result['error']}")
            
            print("-" * 52)
        
    except Exception as e:
        logger.error(f"\n✗ RAG Pipeline 测试失败: {e}", exc_info=True)
        
    finally:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 计网测试脚本执行完毕")
        logger.info("=" * 60)

