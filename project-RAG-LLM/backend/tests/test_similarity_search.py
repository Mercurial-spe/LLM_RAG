# backend/tests/test_similarity_search.py

import os
import sys
import logging
from pathlib import Path

# --- 路径设置 ---
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
except NameError:
    PROJECT_ROOT = Path('.').resolve().parent
    
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入所需的服务
from backend.app.services.vector_store_repository import VectorStoreRepository
from backend.app.services.embedding_service import EmbeddingService

# --- 配置 ---
# 【重要】这里的路径必须和 test_ingestion_flow.py 中的 TEST_DB_PATH 完全一致
DB_PATH = PROJECT_ROOT / "data" / "test_vector_store"

# 【自定义】在这里定义您想查询的语句
QUERY_TEXT = "数据链路层的差错检测机制有哪些？"

# 【自定义】希望返回的最相似结果数量
TOP_K = 5

def run_similarity_test():
    """执行相似度查询测试"""
    logger.info("=" * 60)
    logger.info("🚀 开始执行 [相似度查询测试]")
    logger.info("=" * 60)

    # 1. 检查数据库是否存在
    if not DB_PATH.exists():
        logger.error(f"✗ 查询失败：测试数据库不存在！")
        logger.error(f"请先运行 'test_ingestion_flow.py' 来生成数据库。")
        logger.error(f"预期路径: {DB_PATH}")
        return

    try:
        # 2. 初始化服务
        logger.info("[步骤1] 初始化服务...")
        embedding_service = EmbeddingService.get_instance()
        repo = VectorStoreRepository(persist_path=str(DB_PATH))
        logger.info("✓ 服务初始化成功。")

        # 3. 将查询语句向量化
        logger.info(f"\n[步骤2] 正在将查询语句向量化: '{QUERY_TEXT}'")
        query_vector = embedding_service.embed_text(QUERY_TEXT)
        logger.info("✓ 查询语句向量化成功。")

        # 4. 执行相似度检索
        logger.info(f"\n[步骤3] 正在数据库中检索最相似的 {TOP_K} 个结果...")
        results = repo.query_similar(query_vector=query_vector, top_k=TOP_K)
        
        # 5. 打印结果
        logger.info("\n" + "=" * 25 + " 检索结果 " + "=" * 25)
        if not results:
            logger.warning("未找到相关的文档块。")
        else:
            for i, result in enumerate(results, 1):
                similarity = result.get("metadata", {}).get("similarity", 0)
                source_file = result.get("metadata", {}).get("source", "未知来源")
                content = result.get("content", "")

                print(f"--- [ 结果 {i} ] ---\n")
                print(f"相似度: {similarity:.2%}")
                print(f"距离: {result.get('metadata', {}).get('distance', 'N/A')}")
                print(f"来源: {os.path.basename(source_file)}")
                print("\n原文片段:")
                print(f"  {content.strip()}\n")
        
        logger.info("=" * 60)
        logger.info("🎉 相似度查询测试执行完毕")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ 测试过程中发生严重错误: {e}", exc_info=True)


if __name__ == "__main__":
    run_similarity_test()