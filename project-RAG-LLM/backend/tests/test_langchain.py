"""
RAG Agent 测试（带 session_id 过滤）
====================================
本测试验证：
  1. RAG Agent 是否能正确检索并回答问题
  2. session_id 过滤是否生效（系统文档 + 用户文档）
  3. 检索的文档来源和 session_id 是否正确
"""

import logging
import sys
from pathlib import Path

# --- 将项目根目录添加到 Python 路径中 ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

# --- 导入项目内模块 ---
try:
    from backend.app.core.rag_agent import invoke, stream_messages
    from backend.app.services.vector_store_repository import VectorStoreRepository
except ImportError as e:
    print(f"导入模块失败，请检查 PYTHONPATH 是否正确设置: {e}")
    print(f"PROJECT_ROOT (已添加到 sys.path): {PROJECT_ROOT}")
    sys.exit(1)


# --- 日志配置（抑制第三方噪声，聚焦结果展示） ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("backend.app.core.rag_agent").setLevel(logging.INFO)  # 显示 agent 日志


# --- 测试场景配置 ---
TEST_SCENARIOS = [
    {
        "name": "测试系统文档（session_id=system）",
        "thread_id": "1",
        "questions": [
            "说明计算机网络的学习内容。",
            "TCP 和 UDP 有什么主要区别？",
        ],
        "expected_session_ids": ["system"],  # 期望检索到的 session_id
    },
    {
        "name": "测试用户会话1（session_id=1）",
        "thread_id": "1",
        "questions": [
            "请详细解释一下 TCP 的三次握手过程。",
        ],
        "expected_session_ids": ["system", "1"],  # 系统文档 + 用户上传文档
    },
]


def check_retrieved_documents(thread_id: str, question: str):
    """
    手动检索文档，验证 session_id 过滤是否生效
    """
    from backend.app.services.embedding_service import EmbeddingService
    
    logger.info(f"\n[验证检索] 手动检查 thread_id={thread_id} 的文档检索...")
    
    embedding_service = EmbeddingService.get_instance()
    vector_repo = VectorStoreRepository()
    
    # 生成查询向量
    query_vector = embedding_service.embed_text(question)
    
    # 使用过滤条件检索
    search_filter = {
        "$or": [
            {"session_id": "system"},
            {"session_id": thread_id}
        ]
    }
    
    results = vector_repo.collection.query(
        query_embeddings=[query_vector],
        n_results=5,
        where=search_filter,
        include=["metadatas", "documents", "distances"]
    )
    
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    
    if documents:
        logger.info(f"✓ 检索到 {len(documents)} 个文档块")
        for idx, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            session_id = meta.get("session_id", "unknown")
            source = meta.get("source", "unknown")
            logger.info(f"  [{idx}] session_id={session_id}, source={source}, distance={dist:.4f}")
            logger.info(f"      内容预览: {doc[:100]}...")
    else:
        logger.warning("✗ 未检索到任何文档！")
    
    return len(documents) > 0


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 开始 RAG Agent 测试（带 session_id 过滤验证）")
    logger.info("=" * 60)

    try:
        # 检查向量数据库中是否有数据
        logger.info("\n[0] 检查向量数据库状态...")
        vector_repo = VectorStoreRepository()
        collection_count = vector_repo.collection.count()
        logger.info(f"✓ 向量数据库中共有 {collection_count} 个文档块")
        
        if collection_count == 0:
            logger.warning("⚠️  向量数据库为空！请先运行 scripts/ingest_data.py 导入文档")
            sys.exit(0)
        
        # 查看有哪些 session_id
        all_metadata = vector_repo.collection.get(include=["metadatas"])
        session_ids = set()
        for meta in all_metadata.get("metadatas", []):
            if "session_id" in meta:
                session_ids.add(meta["session_id"])
        logger.info(f"✓ 数据库中存在的 session_id: {sorted(session_ids)}")
        
        # 执行测试场景
        total_questions = sum(len(scenario["questions"]) for scenario in TEST_SCENARIOS)
        question_counter = 0
        
        for scenario_idx, scenario in enumerate(TEST_SCENARIOS, 1):
            logger.info("\n" + "=" * 60)
            logger.info(f"场景 {scenario_idx}: {scenario['name']}")
            logger.info(f"  thread_id: {scenario['thread_id']}")
            logger.info(f"  期望 session_id: {scenario['expected_session_ids']}")
            logger.info("=" * 60)
            
            for question in scenario["questions"]:
                question_counter += 1
                
                logger.info("\n" + "-" * 25 + f" [ 问题 {question_counter}/{total_questions} ] " + "-" * 25)
                logger.info(f"  [问题]: {question}")
                
                # 先验证检索功能
                has_docs = check_retrieved_documents(scenario["thread_id"], question)
                
                if not has_docs:
                    logger.warning("  ⚠️  未检索到文档，跳过 Agent 调用")
                    continue
                
                # 使用 RAG Agent（流式输出）
                logger.info(f"\n  [调用 RAG Agent] thread_id={scenario['thread_id']}")
                print("\n" + "-" * 20 + " RAG Agent 流式回答 " + "-" * 20)
                
                final_text = []
                try:
                    for text_chunk in stream_messages(question, thread_id=scenario["thread_id"]):
                        final_text.append(text_chunk)
                        print(text_chunk, end="", flush=True)
                    
                    print("\n" + "-" * 20 + " 回答完成 " + "-" * 20)
                    
                    if not final_text:
                        logger.warning("  ⚠️  Agent 未返回任何内容")
                    else:
                        logger.info(f"  ✓ Agent 回答长度: {len(''.join(final_text))} 字符")
                
                except Exception as e:
                    logger.error(f"  ✗ Agent 调用失败: {e}", exc_info=True)
                
                print()  # 换行
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 RAG Agent 测试执行完毕")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ 测试失败: {e}", exc_info=True)

