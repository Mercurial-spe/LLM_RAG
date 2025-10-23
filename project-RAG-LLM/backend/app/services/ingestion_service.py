"""数据入库编排服务 (IngestionService)

职责：
- 负责编排复杂的入库流程（分批、增量、对比等）
- 调用 Repository 执行原子数据库操作
- 调用 DocumentService/EmbeddingService 进行处理

注意：这里是业务服务层（Service），不直接操作底层数据库 API。
"""

import logging
from typing import Any, Dict, List, Optional

from .document_service import DocumentService
from .embedding_service import EmbeddingService
from .vector_store_repository import VectorStoreRepository


logger = logging.getLogger(__name__)


class IngestionService:
    """入库编排服务"""

    #--- 初始化 ---
    def __init__(
        self,
        document_service: Optional[DocumentService] = None,
        repository: Optional[VectorStoreRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        batch_size: int = 100,
    ) -> None:
        self.docs = document_service or DocumentService()
        self.repo = repository or VectorStoreRepository()
        self.embed = embedding_service or EmbeddingService.get_instance()
        self.batch_size = batch_size

        logger.info("IngestionService 初始化完成 - batch_size=%s", batch_size)

    # --- 分批入库 ---
    def ingest_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """将已向量化的文档块分批写入向量库（编排逻辑）

        注意：底层一次写入调用 repo.upsert_batch（原子操作）。
        """
        if not chunks:
            return 0

        total = 0
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            total += self.repo.upsert_batch(batch)
            logger.debug("ingest batch done: %s-%s", i, i + len(batch))
        logger.info("ingest_chunks 完成，入库 %s 条", total)
        return total

    def run_ingestion_from_directory(self, directory_path: str, recursive: bool = True) -> Dict[str, Any]:
        """从目录执行完整的增量入库流程（编排）

        步骤：
        1) 读取仓库中已有的 source->md5 映射
        2) 遍历目录、计算每个文件 md5，与仓库对比
        3) 对于新增/变更的文件：解析->切分->向量化->入库
        4) 对于删除的文件：从仓库删除
        """
        import os
        from ..utils.file_utils import calculate_file_md5

        logger.info("开始目录入库: %s", directory_path)

        # 1) 读取仓库状态
        db_map = self.repo.get_all_source_md5_mappings()

        # 2) 构建文件系统状态
        fs_map: Dict[str, str] = {}
        for root, _, files in os.walk(directory_path):
            for name in files:
                path = os.path.join(root, name)
                fs_map[path] = calculate_file_md5(path)
            if not recursive:
                break

        to_upsert: List[str] = []
        to_delete: List[str] = []

        # 新增或变更
        for path, md5 in fs_map.items():
            if db_map.get(path) != md5:
                to_upsert.append(path)

        # 已删除
        for path in db_map.keys():
            if path not in fs_map:
                to_delete.append(path)

        logger.info("变更统计：新增/更新=%s, 删除=%s", len(to_upsert), len(to_delete))

        # 3) 处理需要 upsert 的文件
        total_chunks = 0
        for idx, path in enumerate(to_upsert, 1):
            try:
                chunks = self.docs.process_document(path)  # 含 embedding
                # DocumentService 已为 chunks 添加 file_md5/source/chunk_id 等元数据
                total_chunks += self.ingest_chunks(chunks)
            except Exception as e:
                logger.warning("入库失败，跳过文件 %s: %s", path, e)

        # 4) 删除已经不存在的文件的数据
        total_deleted = 0
        for path in to_delete:
            try:
                total_deleted += self.repo.delete_documents_by_source(path)
            except Exception as e:
                logger.warning("删除失败 %s: %s", path, e)

        return {
            "upsert_files": len(to_upsert),
            "deleted_files": len(to_delete),
            "upsert_chunks": total_chunks,
            "deleted_chunks": total_deleted,
        }

    def check_knowledge_base_health(self) -> Dict[str, Any]:
        """知识库健康检查（编排层定义“健康”标准）"""
        stats = self.repo.get_collection_stats()
        healthy = stats.get("total_documents", 0) >= 0  # 这里只示例：能读到统计即认为健康
        return {"healthy": healthy, **stats}
