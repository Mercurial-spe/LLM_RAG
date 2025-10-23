# backend/app/services/embedding_service.py

"""
文本嵌入服务
使用阿里云百炼 text-embedding-v4 API 将文本转换为向量
"""

import logging
from typing import List, Union
from openai import OpenAI
from .. import config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    文本嵌入服务(单例模式)
    负责将文本转换为向量表示
    """
    
    _instance = None
    _client = None
    
    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化嵌入服务客户端"""
        if self._client is None:
            try:
                self._client = OpenAI(
                    api_key=config.DASHSCOPE_API_KEY,
                    base_url=config.EMBEDDING_API_BASE_URL
                )
                logger.info(f"嵌入服务初始化成功 - 模型: {config.EMBEDDING_MODEL_NAME}, 维度: {config.EMBEDDING_DIMENSION}")
            except Exception as e:
                logger.error(f"嵌入服务初始化失败: {e}")
                raise
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def embed_text(self, text: str, dimensions: int = None) -> List[float]:
        """
        将单条文本转换为向量
        
        Args:
            text: 输入文本
            dimensions: 向量维度(可选)，如不指定则使用配置文件中的默认值
            
        Returns:
            向量列表(长度为指定的dimensions)
            
        Raises:
            ValueError: 当文本为空时
            Exception: API调用失败时
        """
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")
        
        # 清理文本(去除多余的空白字符)
        cleaned_text = " ".join(text.split())
        
        try:
            # 使用配置的维度或默认维度
            embed_dim = dimensions or config.EMBEDDING_DIMENSION
            
            # 调用API
            response = self._client.embeddings.create(
                model=config.EMBEDDING_MODEL_NAME,
                input=cleaned_text,
                dimensions=embed_dim
            )
            
            # 提取向量
            embedding = response.data[0].embedding
            logger.debug(f"文本向量化成功 - 文本长度: {len(text)}, 向量维度: {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"文本向量化失败: {e}")
            raise
    
    def embed_texts(self, texts: List[str], dimensions: int = None) -> List[List[float]]:
        """
        批量将文本转换为向量(更高效)
        
        Args:
            texts: 文本列表(最多10条，这是API限制)
            dimensions: 向量维度(可选)
            
        Returns:
            向量列表的列表
            
        Raises:
            ValueError: 当文本列表为空或超过批次限制时
            Exception: API调用失败时
        """
        if not texts:
            raise ValueError("文本列表不能为空")
        
        if len(texts) > config.EMBEDDING_BATCH_SIZE:
            logger.warning(f"文本数量({len(texts)})超过批次限制({config.EMBEDDING_BATCH_SIZE})，将分批处理")
            return self._embed_texts_in_batches(texts, dimensions)
        
        # 清理所有文本
        cleaned_texts = [" ".join(text.split()) for text in texts if text and text.strip()]
        
        if not cleaned_texts:
            raise ValueError("没有有效的文本内容")
        
        try:
            embed_dim = dimensions or config.EMBEDDING_DIMENSION
            
            # 批量调用API
            response = self._client.embeddings.create(
                model=config.EMBEDDING_MODEL_NAME,
                input=cleaned_texts,
                dimensions=embed_dim
            )
            
            # 提取所有向量
            embeddings = [item.embedding for item in response.data]
            logger.info(f"批量向量化成功 - 文本数量: {len(texts)}, 向量维度: {len(embeddings[0])}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"批量文本向量化失败: {e}")
            raise
    
    def _embed_texts_in_batches(self, texts: List[str], dimensions: int = None) -> List[List[float]]:
        """
        分批处理大量文本
        
        Args:
            texts: 文本列表
            dimensions: 向量维度
            
        Returns:
            所有文本的向量列表
        """
        all_embeddings = []
        batch_size = config.EMBEDDING_BATCH_SIZE
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            batch_embeddings = self.embed_texts(batch, dimensions)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    def get_embedding_dimension(self) -> int:
        """返回当前配置的向量维度"""
        return config.EMBEDDING_DIMENSION
    
    def get_model_info(self) -> dict:
        """返回模型信息"""
        return {
            "model_name": config.EMBEDDING_MODEL_NAME,
            "dimension": config.EMBEDDING_DIMENSION,
            "batch_size": config.EMBEDDING_BATCH_SIZE,
            "max_tokens": config.EMBEDDING_MAX_TOKENS,
            "api_base": config.EMBEDDING_API_BASE_URL
        }


# --- 测试代码 ---
if __name__ == "__main__":
    print("=" * 60)
    print("测试阿里云百炼嵌入服务 (text-embedding-v4)")
    print("=" * 60)
    
    try:
        # 1. 获取服务实例
        print("\n[1] 初始化嵌入服务...")
        service = EmbeddingService.get_instance()
        print(f"✓ 服务初始化成功")
        print(f"  模型信息: {service.get_model_info()}")
        
        # 2. 测试单条文本向量化
        print("\n[2] 测试单条文本向量化...")
        test_text = "RAG是检索增强生成技术，结合了信息检索和文本生成"
        embedding = service.embed_text(test_text)
        print(f"✓ 单条文本向量化成功")
        print(f"  原文本: {test_text}")
        print(f"  向量维度: {len(embedding)}")
        print(f"  向量前10个值: {embedding[:10]}")
        
        # 3. 测试批量文本向量化
        print("\n[3] 测试批量文本向量化...")
        test_texts = [
            "什么是人工智能?",
            "机器学习是AI的一个分支",
            "深度学习使用神经网络",
            "自然语言处理处理文本数据",
            "计算机视觉处理图像数据"
        ]
        embeddings = service.embed_texts(test_texts)
        print(f"✓ 批量文本向量化成功")
        print(f"  文本数量: {len(test_texts)}")
        print(f"  向量数量: {len(embeddings)}")
        print(f"  每个向量维度: {len(embeddings[0])}")
        
        # 4. 测试中文文本
        print("\n[4] 测试中文文本...")
        chinese_text = "这是一个测试中文文本向量化功能的例子"
        chinese_embedding = service.embed_text(chinese_text)
        print(f"✓ 中文文本向量化成功")
        print(f"  文本: {chinese_text}")
        print(f"  向量维度: {len(chinese_embedding)}")
        
        # 5. 验证单例模式
        print("\n[5] 验证单例模式...")
        service2 = EmbeddingService.get_instance()
        print(f"✓ 单例验证: service 和 service2 是同一个实例 = {service is service2}")
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
