# backend/tests/test_ingestion_flow.py

import os
import sys
import shutil
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

# 导入项目中的核心服务
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.vector_store_repository import VectorStoreRepository
from backend.app.services.document_service import DocumentService

# --- 测试常量定义 ---
TEST_DB_PATH = PROJECT_ROOT / "data" / "test_vector_store"
TARGET_FILE_NAME = "深入理解计算机网络_第3章_数据链路层.pdf"
TARGET_FILE_PATH = PROJECT_ROOT / "data" / "raw_documents" / "pdf" / TARGET_FILE_NAME

def run_ingestion_test():
    """执行完整的单文件入库流程测试，结束后提示手动清理。"""
    
    logger.info("=" * 60)
    logger.info("🚀 开始执行 [入库测试]，结束后请手动清理")
    logger.info("=" * 60)
    
    repo = None

    try:
        # --- 1. 准备阶段 ---
        logger.info(f"[准备] 清理旧的测试数据库 (如果存在): {TEST_DB_PATH}")
        if TEST_DB_PATH.exists():
            shutil.rmtree(TEST_DB_PATH)
        
        logger.info(f"[准备] 检查目标文件: {TARGET_FILE_PATH}")
        if not TARGET_FILE_PATH.exists():
            logger.error("✗ 测试失败：目标文件不存在。")
            return

        logger.info("[准备] 初始化服务...")
        repo = VectorStoreRepository(persist_path=str(TEST_DB_PATH))
        doc_service = DocumentService() 
        ingestion_service = IngestionService(repository=repo)
        logger.info("✓ 服务初始化成功")

        # --- 2. 核心测试：处理单个文件并入库 ---
        logger.info("\n" + "-" * 20 + " 处理单个目标文件 " + "-" * 20)
        vectorized_chunks = doc_service.process_document(str(TARGET_FILE_PATH))
        num_chunks_ingested = ingestion_service.ingest_chunks(vectorized_chunks)
        logger.info(f"✓ 数据入库完成，写入 {num_chunks_ingested} 条记录。")

        # --- 3. 结果验证 ---
        logger.info("\n" + "-" * 20 + " 数据库验证 " + "-" * 20)
        stats = repo.get_collection_stats()
        assert stats["total_documents"] == num_chunks_ingested, "数据库总块数应与入库数一致"
        logger.info("✅ 验证成功：目标文件已正确向量化并存入数据库！")

    except Exception as e:
        logger.error(f"✗ 测试失败：测试过程中发生错误: {e}", exc_info=True)
    finally:
        # --- 4. 结束提示 ---
        logger.info("\n" + "=" * 60)
        logger.info("🎉 入库测试流程执行完毕")
        if repo:
            # 提示：这里不再调用shutdown()，因为reset()会清空数据库，
            # 而我们希望保留数据以供下一个脚本查询。
            pass
        
        logger.info("✅ 测试数据库已成功生成并保留。")
        logger.info("👉 后续若需清理，请手动删除以下目录：")
        logger.info(f"   {TEST_DB_PATH}")
        logger.info("=" * 60)


if __name__ == "__main__":
    run_ingestion_test()