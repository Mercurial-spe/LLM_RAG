# backend/app/services/document_service.py

"""
文档处理服务
负责加载、解析和切分各种格式的文档(TXT, MD, PDF, DOCX, PPTX)
"""

import hashlib
import os
import logging
from typing import List, Dict, Any
from pathlib import Path

# 配置日志(必须在最前面)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LangChain文档加载器
from langchain_community.document_loaders import (
    TextLoader,           # TXT和MD文件
    PyPDFLoader,          # PDF文件
    UnstructuredWordDocumentLoader,       # DOCX/Doc文件
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 导入PPTX加载器(可选)
try:
    from langchain_community.document_loaders import UnstructuredPowerPointLoader
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False
    logger.warning("UnstructuredPowerPointLoader未安装,PPTX支持将被禁用")

from .. import config
from .embedding_service import EmbeddingService
from ..utils.file_utils import calculate_file_md5


class DocumentService:
    """
    文档处理服务
    提供文档加载、切分和向量化功能
    """
    
    # 支持的文件格式及对应的加载器
    SUPPORTED_FORMATS = {
        '.txt': TextLoader,
        '.md': TextLoader,
        '.pdf': PyPDFLoader,
        '.docx': UnstructuredWordDocumentLoader,
        '.doc': UnstructuredWordDocumentLoader,
    }
    
    # 如果PPTX支持可用,添加到支持列表
    if PPTX_AVAILABLE:
        SUPPORTED_FORMATS['.pptx'] = UnstructuredPowerPointLoader
    
    def __init__(self):
        """初始化文档服务"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
        )
        self.embedding_service = EmbeddingService.get_instance()
        logger.info(f"文档服务初始化成功 - chunk_size: {config.CHUNK_SIZE}, overlap: {config.CHUNK_OVERLAP}")
    
    
    def is_supported_format(self, file_path: str) -> bool:
        """
        检查文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持该格式
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_FORMATS
    
    #
    def load_document(self, file_path: str) -> List[Dict[str, Any]]:
        """
        加载单个文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            LangChain Document对象列表
            
        Raises:
            ValueError: 文件不存在或格式不支持
            Exception: 文档加载失败
        """
        # 验证文件存在
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")
        
        # 验证文件格式
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的文件格式: {ext}")
        
        try:
            # 获取对应的加载器
            loader_class = self.SUPPORTED_FORMATS[ext]
            
            # 根据文件类型设置不同的加载参数
            if ext == '.pptx':
                # PPTX需要特殊模式
                loader = loader_class(file_path, mode="elements")
            elif ext in ['.txt', '.md']:
                # TXT和MD需要指定UTF-8编码
                loader = loader_class(file_path, encoding='utf-8')
            else:
                # PDF和DOCX/DOC需要使用默认参数
                loader = loader_class(file_path)
            
            # 加载文档
            documents = loader.load()
            logger.info(f"文档加载成功: {file_path} - 页数/分段: {len(documents)}")
            
            return documents
            
        except Exception as e:
            logger.error(f"文档加载失败: {file_path} - {e}")
            raise
    
    def split_documents(self, documents: List[Any]) -> List[Dict[str, Any]]:
        """
        切分文档为文本块
        
        Args:
            documents: LangChain Document对象列表
            
        Returns:
            切分后的文档块列表,每个块包含:
            {
                'content': '文本内容',
                'metadata': {
                    'source': '文件名',
                    'chunk_id': 块序号,
                    ... 其他元数据
                }
            }
        """
        try:
            # 使用RecursiveCharacterTextSplitter切分
            split_docs = self.text_splitter.split_documents(documents)
            
            # 转换为标准格式并添加chunk_id
            chunks = []
            for idx, doc in enumerate(split_docs):
                chunk = {
                    'content': doc.page_content,
                    'metadata': {
                        **doc.metadata,
                        'chunk_id': idx,
                        'chunk_size': len(doc.page_content)
                    }
                }
                chunks.append(chunk)
            
            logger.info(f"文档切分成功 - 原始段落: {len(documents)}, 切分后块数: {len(chunks)}")
            return chunks
            
        except Exception as e:
            logger.error(f"文档切分失败: {e}")
            raise
    
    def vectorize_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        为文档块生成向量
        
        Args:
            chunks: 文档块列表
            
        Returns:
            添加了embedding字段的文档块列表
            {
                'content': '...',
                'metadata': {...},
                'embedding': [0.1, 0.2, ...]  # 新增
            }
        """
        try:
            # 提取所有文本内容
            texts = [chunk['content'] for chunk in chunks]
            
            # 批量向量化
            logger.info(f"开始批量向量化 - 文本块数: {len(texts)}")
            embeddings = self.embedding_service.embed_texts(texts)
            
            # 将向量添加到每个块中
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding
            
            logger.info(f"向量化完成 - 向量维度: {len(embeddings[0])}")
            return chunks
            
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            raise
    
    def process_document(self, file_path: str) -> List[Dict[str, Any]]:
        """
        一站式处理文档: 加载 -> 切分 -> 向量化
        
        这是对外暴露的主函数
        
        Args:
            file_path: 文件路径
            
        Returns:
            完整处理后的文档块列表(包含向量和file_md5)
            
        Raises:
            Exception: 处理过程中的任何错误
        """
        logger.info(f"=" * 60)
        logger.info(f"开始处理文档: {file_path}")
        
        try:
            # 0. 计算文件MD5
            file_md5 = calculate_file_md5(file_path)
            logger.info(f"文件MD5: {file_md5}")
            
            # 1. 加载文档
            documents = self.load_document(file_path)
            
            # 2. 切分文档
            chunks = self.split_documents(documents)
            
            # 3. 为每个chunk添加file_md5
            for chunk in chunks:
                chunk['metadata']['file_md5'] = file_md5
            
            # 4. 向量化
            vectorized_chunks = self.vectorize_chunks(chunks)
            
            logger.info(f"文档处理完成 - 最终块数: {len(vectorized_chunks)}")
            logger.info(f"=" * 60)
            
            return vectorized_chunks
            
        except Exception as e:
            logger.error(f"文档处理失败: {file_path} - {e}")
            raise
    
    def process_directory(self, directory_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        批量处理目录下的所有文档
        
        Args:
            directory_path: 目录路径
            recursive: 是否递归处理子目录
            
        Returns:
            所有文档的向量化块列表
        """
        all_chunks = []
        
        if not os.path.exists(directory_path):
            raise ValueError(f"目录不存在: {directory_path}")
        
        # 获取所有支持的文件
        pattern = "**/*" if recursive else "*"
        files = []
        
        for ext in self.SUPPORTED_FORMATS.keys():
            files.extend(Path(directory_path).glob(f"{pattern}{ext}"))
        
        logger.info(f"找到 {len(files)} 个文档文件")
        
        # 逐个处理
        for idx, file_path in enumerate(files, 1):
            logger.info(f"处理进度: {idx}/{len(files)}")
            try:
                chunks = self.process_document(str(file_path))
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(f"跳过文件 {file_path}: {e}")
                continue
        
        logger.info(f"批量处理完成 - 总文档数: {len(files)}, 总块数: {len(all_chunks)}")
        return all_chunks
    
    def get_document_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取文档处理统计信息
        
        Args:
            chunks: 文档块列表
            
        Returns:
            统计信息字典
        """
        if not chunks:
            return {
                'total_chunks': 0,
                'total_chars': 0,
                'avg_chunk_size': 0,
                'sources': []
            }
        
        total_chars = sum(len(chunk['content']) for chunk in chunks)
        sources = list(set(chunk['metadata'].get('source', 'unknown') for chunk in chunks))
        
        return {
            'total_chunks': len(chunks),
            'total_chars': total_chars,
            'avg_chunk_size': total_chars // len(chunks),
            'sources': sources,
            'embedding_dimension': len(chunks[0].get('embedding', []))
        }


