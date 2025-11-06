# sync_service.py
# -*- coding: utf-8 -*-
"""
单向差异同步服务模块
=====================
功能：
  1. 扫描本地文件系统，获取文件状态（路径, mtime, size）。
  2. 从向量数据库获取已索引文件的状态。
  3. 对比两种状态，计算出需要“新增”、“修改”、“删除”的文件列表。
  4. 编排其他服务执行同步操作：
     - 删除：调用 VectorStoreRepository.delete_by_source()
     - 新增/修改：调用 DocumentIngestService 处理文件，
                调用 EmbeddingService 生成向量，
                最后调用 VectorStoreRepository.upsert_batch() 批量入库。

设计：
  - 这是一个高层编排服务，是同步逻辑的“大脑”。
  - 它通过依赖注入的方式使用其他原子服务。
"""

import os
import logging
from typing import List, Dict, Any


from .vector_store_repository import VectorStoreRepository
from .document_ingest_service import DocumentIngestService
from .embedding_service import EmbeddingService  

logger = logging.getLogger(__name__)

class SyncService:
    """编排文件同步到向量数据库的服务"""

    def __init__(
        self,
        ingest_service: DocumentIngestService,
        embedding_service: EmbeddingService,
        vector_repo: VectorStoreRepository,
        project_root: str,
        allowed_extensions: List[str] = None
    ):
        """
        通过依赖注入初始化服务
        
        Args:
            ingest_service: 文档摄取服务的实例
            embedding_service: 文本向量化服务的实例
            vector_repo: 向量仓库的实例
            allowed_extensions: (可选) 允许同步的文件扩展名列表, e.g., [".pdf", ".txt"]
        """
        self.ingest_service = ingest_service
        self.embedding_service = embedding_service
        self.vector_repo = vector_repo
        self.project_root = project_root
        self.allowed_extensions = allowed_extensions or [".pdf", ".docx", ".doc", ".txt", ".md"]
        logger.info("同步服务 (SyncService) 初始化完成。")
        logger.info(f"项目根目录设置为: {self.project_root}")

    def run(self, target_path: str, session_id: str = "system") -> Dict[str, int]:
        """
        执行一次完整的单向同步。
        
        Args:
            target_path: 要扫描和同步的本地文件夹路径。
            session_id: 会话ID，默认 "system" 表示系统全局文档
            
        Returns:
            一个包含同步结果统计的字典。
        """
        logger.info(f"开始对 '{target_path}' 目录进行单向差异同步...")

        # 1. 获取本地和数据库的文件状态
        local_state = self._get_local_file_state(target_path)
        db_state = self.vector_repo.get_indexed_file_state()

        # 2. 计算差异
        diff = self._calculate_diff(local_state, db_state)
        files_to_add = diff["added"]
        files_to_update = diff["updated"]
        files_to_delete = diff["deleted"]
        
        logger.info(
            f"差异计算完成 - 待新增: {len(files_to_add)}, "
            f"更新: {len(files_to_update)}, 删除: {len(files_to_delete)}"
        )

        # 3. 执行同步操作
        # 3.1 处理删除
        deleted_chunks_count = self._delete_files(files_to_delete)
        
        # 3.2 处理新增和更新 (逻辑相同：删除旧的 -> 批量添加新的)
        updated_chunks_count = self._delete_files(files_to_update) # 更新=先删除
        files_to_process = files_to_add + files_to_update
        added_chunks_count = self._process_and_upsert_files(files_to_process, session_id=session_id)

        summary = {
            "files_added": len(files_to_add),
            "files_updated": len(files_to_update),
            "files_deleted": len(files_to_delete),
            "chunks_added": added_chunks_count,
            "chunks_deleted": deleted_chunks_count + updated_chunks_count,
        }
        
        logger.info(f"同步完成: {summary}")
        return summary

    def _get_local_file_state(self, path: str) -> Dict[str, Dict[str, Any]]:
        """递归扫描本地路径，获取【相对于项目根目录】的文件状态Map"""
        local_state = {}
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                # 根据扩展名过滤
                if not any(file.lower().endswith(ext) for ext in self.allowed_extensions):
                    continue
                
                try:
                    # 使用项目根为基准计算相对路径
                    relative_path = os.path.relpath(file_path, self.project_root)
                    stat = os.stat(file_path)
                    local_state[relative_path] = {
                        "mtime": stat.st_mtime,
                        "size": stat.st_size
                    }
                except OSError as e:
                    logger.warning(f"无法访问文件 '{file_path}': {e}")
        return local_state

    def _calculate_diff(self, local_state: dict, db_state: dict) -> Dict[str, List[str]]:
        """比较本地与数据库状态，返回差异"""
        local_files = set(local_state.keys())
        db_files = set(db_state.keys())

        added = list(local_files - db_files)
        deleted = list(db_files - local_files)
        
        potential_updates = local_files.intersection(db_files) #取交集
        updated = []
        for file in potential_updates:
            # 比较 mtime 和 size
            if (local_state[file]["mtime"] != db_state[file]["mtime"] or
                local_state[file]["size"] != db_state[file]["size"]):
                updated.append(file)
                
        return {"added": added, "updated": updated, "deleted": deleted}

    def _delete_files(self, file_paths: List[str]) -> int:
        """调用 repository 删除指定源文件对应的所有 chunks"""
        total_deleted_chunks = 0
        if not file_paths:
            return 0
            
        logger.info(f"正在删除 {len(file_paths)} 个源文件的文档块...")
        for path in file_paths:
            try:
                count = self.vector_repo.delete_by_source(path)
                total_deleted_chunks += count
            except Exception as e:
                logger.error(f"删除源文件 '{path}' 失败: {e}")
        return total_deleted_chunks

    def _process_and_upsert_files(self, file_paths: List[str], session_id: str = "system") -> int:
        """
        处理文件(摄取、向量化)并批量入库
        
        Args:
            file_paths: 文件路径列表
            session_id: 会话ID，默认 "system" 表示系统全局文档
        """
        if not file_paths:
            return 0

        logger.info(f"正在处理 {len(file_paths)} 个新增/更新的文件 (session_id={session_id})...")
        
        all_chunks_to_upsert = []
        for path in file_paths:
            try:
                # 1. 文档摄取，生成 chunks 和 metadata（传入 session_id）
                full_path = os.path.join(self.project_root, path)
                processed_chunks = self.ingest_service.process_document(full_path, path, session_id=session_id)
                if processed_chunks:
                    all_chunks_to_upsert.extend(processed_chunks)
            except Exception as e:
                logger.error(f"处理文件 '{path}' 失败: {e}")
                continue # 跳过此文件，继续处理下一个

        if not all_chunks_to_upsert:
            logger.info("没有有效的文档块需要入库。")
            return 0

        # 2. 批量生成向量
        logger.info(f"正在为 {len(all_chunks_to_upsert)} 个文档块生成向量...")
        contents = [chunk['content'] for chunk in all_chunks_to_upsert]
        embeddings = self.embedding_service.embed_texts(contents)

        # 3. 准备数据并批量入库
        ids = [chunk['id'] for chunk in all_chunks_to_upsert]
        metadatas = [chunk['metadata'] for chunk in all_chunks_to_upsert]
        
        try:
            self.vector_repo.upsert_batch(
                ids=ids,
                documents=contents, # upsert 也需要原始文本
                embeddings=embeddings,
                metadatas=metadatas
            )
            return len(ids)
        except Exception as e:
            logger.error(f"批量入库失败: {e}")
            return 0