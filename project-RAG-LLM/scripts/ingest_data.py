# scripts/ingest_data.py

import logging
import sys
from pathlib import Path

# --- 将项目根目录添加到 Python 路径中，确保能正确导入 app 内的模块 ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))
# -------------------------------------------------------------------

# 现在可以安全地从 app 导入了
from backend.app import config
from backend.app.services.document_ingest_service import DocumentIngestService
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.sync_service import SyncService
from backend.app.services.vector_store_repository import VectorStoreRepository

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 主程序 ---
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 开始执行数据同步流程")
    # [关键]：从 config 模块读取要扫描的目录的【绝对路径】
    logger.info(f"扫描目录: {config.RAW_DOCUMENTS_PATH}")
    logger.info("=" * 60)
    
    try:
        # 1. 初始化所有依赖的服务（所有参数都从 config 读取）
        ingest_service = DocumentIngestService(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            embedding_model=config.EMBEDDING_MODEL_NAME
        )
        
        embedding_service = EmbeddingService.get_instance()
        
        vector_repo = VectorStoreRepository(
            persist_path=config.VECTOR_STORE_PATH,
            collection_name=config.VECTOR_COLLECTION_NAME
        )

        # 2. 初始化同步服务
        sync_service = SyncService(
            ingest_service=ingest_service,
            embedding_service=embedding_service,
            vector_repo=vector_repo,
            project_root=str(config.PROJECT_ROOT)
        )
        
        # 3. [关键]：将 config 中定义的【绝对路径】作为基准路径传递给 run 方法
        # 传入 session_id="system" 标记为系统全局文档
        summary = sync_service.run(target_path=config.RAW_DOCUMENTS_PATH, session_id="system")
        
        logger.info("\n" + "-" * 20 + " 同步流程完成 " + "-" * 20)
        logger.info(f"✓ 新增文件数: {summary.get('files_added', 0)}")
        logger.info(f"✓ 更新文件数: {summary.get('files_updated', 0)}")
        logger.info(f"✓ 删除文件数: {summary.get('files_deleted', 0)}")
        logger.info(f"✓ 新增文本块: {summary.get('chunks_added', 0)}")
        logger.info(f"✓ 删除文本块: {summary.get('chunks_deleted', 0)}")
        
    except Exception as e:
        logger.error(f"同步过程中发生严重错误: {e}", exc_info=True)
        
    finally:
        logger.info("\n" + "=" * 60)
        logger.info("🎉 脚本执行完毕")
        logger.info("=" * 60)