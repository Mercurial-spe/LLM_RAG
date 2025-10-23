"""向量仓库 (Repository / DAL)

职责（仅数据访问层，原子操作）：
- 封装与 ChromaDB 的底层交互
- 提供原子性的“存/取/删/查”接口（一次只做一件事）
- 只处理向量、文档、元数据；不负责生成向量、不负责编排业务流程

设计原则：
- 单一职责：仅数据库读写
- 低耦合：不依赖任何业务服务（如 Embedding/LLM 等）
- 高内聚：所有 ChromaDB 操作聚合在此
- 原子性：每个方法完成单一明确的数据库操作
"""

import logging
import os
from .. import config
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection


logger = logging.getLogger(__name__)


class VectorStoreRepository:
	"""ChromaDB 向量库的纯仓库（Repository）

	这是一个“仓库管理员”，只执行原子性的数据库操作。
	"""

	def __init__(
		self, 
		persist_path: Optional[str] = None,
		collection_name: Optional[str] = None
	):
		"""初始化向量仓库
		
		Args:
			persist_path: 持久化路径，默认使用配置文件中的路径
			collection_name: 集合名称，默认使用配置文件中的名称
		"""
		self.persist_path = persist_path or config.VECTOR_STORE_PATH
		self.collection_name = collection_name or config.VECTOR_COLLECTION_NAME
		
		os.makedirs(self.persist_path, exist_ok=True)

		# 初始化 ChromaDB 客户端和集合
		self._client = chromadb.PersistentClient(path=self.persist_path)
		self._collection: Collection = self._client.get_or_create_collection(
			name=self.collection_name
		)

		logger.info(
			"向量仓库初始化成功 - path: %s, collection: %s",
			self.persist_path,
			self.collection_name,
		)

	@property
	def collection(self) -> Collection:
		"""获取当前集合对象"""
		return self._collection

	def upsert_batch(self, chunks: List[Dict[str, Any]]) -> int:
		"""原子操作：写入/更新一批文档块（一次调用一次 Upsert）

		注意：分批策略（batching）的循环不在仓库层实现，应由业务服务控制。
        
		Args:
			chunks: 单个批次的文档块列表（每个包含 content、embedding、metadata）
		Returns:
			本批次写入/更新的数量
		Raises:
			ValueError: 入参缺失必要字段
		"""
		ids: List[str] = []
		embeddings: List[List[float]] = []
		documents: List[str] = []
		metadatas: List[Dict[str, Any]] = []

		for chunk in chunks:
			content = chunk.get("content")
			embedding = chunk.get("embedding")
			metadata = chunk.get("metadata", {})
			file_md5 = metadata.get("file_md5")
			chunk_id = metadata.get("chunk_id")

			# 验证必需字段
			if content is None or embedding is None:
				raise ValueError("chunk 中缺少 content 或 embedding 字段")
			if file_md5 is None or chunk_id is None:
				raise ValueError("chunk metadata 必须包含 file_md5 与 chunk_id")

			# 构建唯一ID
			ids.append(f"{file_md5}_{chunk_id}")
			embeddings.append(embedding)
			documents.append(content)
			metadatas.append(metadata)

		# 批量写入
		self.collection.upsert(
			ids=ids,
			embeddings=embeddings,
			documents=documents,
			metadatas=metadatas,
		)

		return len(ids)

	def query_similar(
		self, 
		query_vector: List[float], 
		top_k: int = 5,
		where_filter: Optional[Dict[str, Any]] = None,
		min_distance: Optional[float] = None
	) -> List[Dict[str, Any]]:
		"""基于向量的相似度检索
		
		这是一个纯粹的数据库查询方法，只接收向量，不负责生成向量。
		
		Args:
			query_vector: 查询向量(必须是已计算好的浮点数列表)
			top_k: 返回的最相似块数量
			where_filter: 元数据过滤条件(可选)
				例如: {'source': 'doc.pdf'} 只在特定文件中搜索
			min_distance: 最大距离阈值(可选,用于过滤低质量结果)
				ChromaDB 使用欧几里得距离,距离越小越相似
				如果提供此参数,将过滤掉 distance > min_distance 的结果
			
		Returns:
			相似文档块列表,每个元素包含:
			{
				'content': str,
				'metadata': {
					...原有元数据...,
					'distance': float,  # 距离分数(越小越相似)
					'similarity': float  # 相似度分数(0-1,越大越相似)
				}
			}
			
		Raises:
			ValueError: query_vector为空或top_k无效
		"""
		if not query_vector:
			raise ValueError("query_vector 不能为空")
		if top_k <= 0:
			raise ValueError("top_k 必须为正整数")

		# 执行向量检索
		query_params = {
			"query_embeddings": [query_vector],
			"n_results": top_k
		}
		
		# 添加元数据过滤(如果提供)
		if where_filter:
			query_params["where"] = where_filter
		
		results = self.collection.query(**query_params)

		# 解析结果
		documents = results.get("documents", [[]])[0]
		metadatas = results.get("metadatas", [[]])[0]
		distances = results.get("distances", [[]])[0]

		if not documents:
			logger.info("未检索到相关文档块")
			return []

		# 格式化并增强结果
		import math
		cleaned_results: List[Dict[str, Any]] = []
		
		for doc, metadata, distance in zip(documents, metadatas, distances):
			# 如果设置了最大距离阈值,进行过滤
			if min_distance is not None and distance > min_distance:
				continue
			
			# 将距离转换为相似度分数(0-1范围,越大越相似)
			# 使用简单的指数衰减: similarity = exp(-distance)
			similarity = math.exp(-distance)
			
			enriched_meta = {
				**metadata, 
				"distance": round(distance, 6),
				"similarity": round(similarity, 4)
			}
			cleaned_results.append({
				"content": doc, 
				"metadata": enriched_meta
			})

		logger.info(
			f"检索完成 - 返回 {len(cleaned_results)}/{top_k} 个结果"
		)
		if cleaned_results:
			logger.debug(f"相似度范围: {[r['metadata']['similarity'] for r in cleaned_results]}")
		
		return cleaned_results

	def get_all_source_md5_mappings(self) -> Dict[str, str]:
		"""查询所有文档的 source -> file_md5 映射（原子读操作）

		Returns:
			形如 {"path/to/file": "md5hash", ...} 的字典
		"""
		data = self.collection.get()
		metadatas = data.get("metadatas", []) or []
		mapping: Dict[str, str] = {}
		for meta in metadatas:
			src = meta.get("source")
			md5 = meta.get("file_md5")
			if src and md5:
				mapping[src] = md5
		return mapping

	def get_stored_md5(self, file_path: str) -> Optional[str]:
		"""获取已存储文件的MD5值
		
		用于增量更新时判断文件是否已变化
		
		Args:
			file_path: 文件路径
			
		Returns:
			文件的MD5值,如果文件未入库则返回None
		"""
		try:
			stored = self.collection.get(where={"source": file_path}, limit=1)
			metadatas = stored.get("metadatas", [])
			if metadatas:
				md5 = metadatas[0].get("file_md5")
				logger.debug(f"文件 {file_path} 在向量库中的 md5 为 {md5}")
				return md5
			logger.debug(f"向量库中未找到文件 {file_path}")
			return None
		except Exception as e:
			logger.error(f"查询文件MD5失败 {file_path}: {e}")
			return None

	def delete_documents_by_source(self, file_path: str) -> int:
		"""删除指定源文件的所有文档块
		
		Args:
			file_path: 文件路径
			
		Returns:
			删除的文档块数量
		"""
		try:
			# 先查询要删除的记录数
			existing = self.collection.get(where={"source": file_path})
			ids = existing.get("ids", [])
			
			if not ids:
				logger.info(f"未在向量库中找到源文件 {file_path} 的记录")
				return 0

			# 执行删除
			self.collection.delete(where={"source": file_path})
			logger.info(f"已删除源文件 {file_path} 的 {len(ids)} 条记录")
			return len(ids)
			
		except Exception as e:
			logger.error(f"删除文档失败 {file_path}: {e}")
			raise

	def delete_documents_by_ids(self, ids: List[str]) -> int:
		"""根据ID列表删除文档块
		
		Args:
			ids: 文档块ID列表
			
		Returns:
			删除的文档块数量
		"""
		if not ids:
			logger.warning("delete_documents_by_ids 调用时未提供任何 ID")
			return 0
		
		try:
			self.collection.delete(ids=ids)
			logger.info(f"已删除 {len(ids)} 个文档块")
			return len(ids)
		except Exception as e:
			logger.error(f"删除文档块失败: {e}")
			raise

	def get_collection_stats(self) -> Dict[str, Any]:
		"""获取集合的统计信息
		
		Returns:
			包含统计信息的字典:
			{
				'total_documents': int,  # 总文档块数
				'unique_sources': int,   # 唯一文件数
				'collection_name': str,  # 集合名称
				'persist_path': str      # 持久化路径
			}
		"""
		try:
			# 获取所有文档的元数据
			all_data = self.collection.get()
			total_docs = len(all_data.get("ids", []))
			
			# 统计唯一文件数
			metadatas = all_data.get("metadatas", [])
			unique_sources = len(set(
				meta.get("source", "") for meta in metadatas
			))
			
			stats = {
				"total_documents": total_docs,
				"unique_sources": unique_sources,
				"collection_name": config.VECTOR_COLLECTION_NAME,
				"persist_path": self.persist_path
			}
			
			logger.info(f"集合统计 - 文档块: {total_docs}, 唯一文件: {unique_sources}")
			return stats
			
		except Exception as e:
			logger.error(f"获取集合统计失败: {e}")
			raise



				