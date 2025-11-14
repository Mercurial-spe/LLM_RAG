# document_service.py
# -*- coding: utf-8 -*-
"""
文档摄取（Ingest）服务模块
===========================
功能：
  1. 加载指定路径的文档（支持 PDF、TXT、DOCX 等）
  2. 切分文档为标准化的文本块（chunks）
  3. 为每个 chunk 自动生成 metadata（包含文件信息、chunk 信息、哈希等）
  4. 输出统一格式的 chunk 列表，用于后续的向量化与入库

注意：
  - 本模块不涉及任何数据库 / 向量存储操作
  - 所有关于 embedding 或 Chroma 的逻辑应在其他模块中实现
"""

import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any

from langchain_community.document_loaders import (
    UnstructuredPDFLoader,
    UnstructuredWordDocumentLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# 统一从工具模块导入通用函数
from ..utils.file_utils import get_file_info, sha1_text, now_iso


class DocumentIngestService:
    """文档摄取服务：负责加载、切分与生成标准化 chunks"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "openai-embedding-vX",
        # PDF 解析相关配置
        use_unstructured_pdf: bool = True,
        unstructured_strategy: str = "fast",  # "fast" 轻依赖，hi_res重依赖需要 unstructured-inference
        ocr_languages: str = "chi_sim+eng",  # 中英混排文档
        infer_table_structure: bool = False,  # 若不需要表格结构重建，保持 False 可减少依赖与耗时
        extract_images_in_pdf: bool = False,  # 避免提取图片以减少处理量
    ):
        """
        初始化
        :param chunk_size: 每个chunk的字符数
        :param chunk_overlap: chunk间重叠字符数
        :param embedding_model: 用于记录在metadata中的embedding模型名称
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        # PDF 解析配置
        self.use_unstructured_pdf = use_unstructured_pdf
        self.unstructured_strategy = unstructured_strategy
        self.ocr_languages = ocr_languages
        self.infer_table_structure = infer_table_structure
        self.extract_images_in_pdf = extract_images_in_pdf
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # ========== 工具函数来自 utils/file_utils.py ==========

    # ========== 核心功能区 ==========

    def load_document(self, file_path: str) -> List[Document]:
        """
        加载文档
        根据文件类型选择合适的Loader
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            # 默认启用 Unstructured 以更好支持图片/扫描件与复杂版面
            if self.use_unstructured_pdf:
                loader = UnstructuredPDFLoader(
                    file_path,
                    # 关键参数：使用 hi_res 策略，提升 OCR 质量
                    strategy=self.unstructured_strategy,
                    # 指定 OCR 语言，避免默认英文导致的告警，并提升中文识别
                    ocr_languages=self.ocr_languages,
                    # 不重建表格结构可显著减少复杂依赖和错误几率
                    infer_table_structure=self.infer_table_structure,
                    # 可选：是否提取图片
                    extract_images_in_pdf=self.extract_images_in_pdf,
                )
            else:
                # 如需极简依赖可切换为其他轻量 loader（此处保留 Unstructured 默认构造）
                loader = UnstructuredPDFLoader(file_path, strategy="fast")
        elif ext in [".doc", ".docx"]:
            loader = UnstructuredWordDocumentLoader(file_path)
        elif ext ==".md":
            loader = UnstructuredMarkdownLoader(file_path)
        else:
            
            loader = TextLoader(file_path, encoding="utf-8")

        return loader.load()

    def split_documents(self, docs: List[Document]) -> List[Document]:
        """
        切分文档为小块（chunks）
        :param docs: LangChain Document 列表
        :return: 切分后的 Document 列表
        """
        return self.splitter.split_documents(docs)

    def process_document(self, full_file_path: str, relative_file_path: str, session_id: str = "system") -> List[Dict[str, Any]]:
        """
        完整处理流程：
        1. 加载文档
        2. 切分为chunks
        3. 生成metadata与id
        4. 返回统一格式列表

        Args:
            full_file_path: 文件的绝对路径（用于读取与状态计算）
            relative_file_path: 相对于项目根目录的路径（用于元数据 source 字段）
            session_id: 会话ID，默认 "system" 表示系统全局文档
        """
        file_info = get_file_info(full_file_path)
        docs = self.load_document(full_file_path)
        chunks = self.split_documents(docs)
        ingested_at = now_iso()

        processed_chunks = []
        for idx, chunk in enumerate(chunks):
            content = chunk.page_content
            chunk_hash = sha1_text(content)
            chunk_size = len(content)

            # 生成确定性id（基于文件 mtime 原始时间戳 + size + chunk_id）
            id_source = f"{file_info['file_mtime']}|{file_info['file_size']}|{idx}"
            chunk_id_hash = hashlib.sha1(id_source.encode("utf-8")).hexdigest()

            # 构造metadata
            metadata = {
                "source": relative_file_path,
                "file_name": file_info["file_name"],
                "source_type": file_info["source_type"],
                "file_mtime": file_info["file_mtime"],
                "file_size": file_info["file_size"],
                "chunk_id": idx,
                "chunk_hash": chunk_hash, # 内容哈希，唯一内容标识
                "chunk_size": chunk_size,
                "embedding_model": self.embedding_model,
                "ingested_at": ingested_at, # 摄取时间
                "session_id": session_id,  # 会话ID，用于区分不同会话的文档
            }

            #构造最终chunk字典
            processed_chunks.append({
                "id": chunk_id_hash,
                "content": content,
                "metadata": metadata,
            })

        return processed_chunks


