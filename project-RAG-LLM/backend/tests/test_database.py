"""
查看向量数据库和记忆数据库的表结构
========================================================
用途：
1. 查看 ChromaDB 向量数据库的集合结构和数据
2. 查看 SQLite 记忆数据库的表结构和数据
"""

import sys
import os
import sqlite3
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config
import chromadb


def inspect_vector_database():
    """查看 ChromaDB 向量数据库的结构和数据"""
    print("=" * 80)
    print("📊 检查 ChromaDB 向量数据库")
    print("=" * 80)
    
    vector_store_path = config.VECTOR_STORE_PATH
    collection_name = config.VECTOR_COLLECTION_NAME
    
    print(f"向量库路径: {vector_store_path}")
    print(f"集合名称: {collection_name}\n")
    
    if not os.path.exists(vector_store_path):
        print("❌ 向量库目录不存在！")
        return
    
    try:
        # 连接 ChromaDB
        client = chromadb.PersistentClient(path=vector_store_path)
        
        # 获取所有集合
        print("📋 所有集合:")
        collections = client.list_collections()
        for col in collections:
            print(f"  - {col.name} (id: {col.id})")
        print()
        
        # 获取目标集合
        try:
            collection = client.get_collection(name=collection_name)
        except Exception as e:
            print(f"❌ 集合 '{collection_name}' 不存在: {e}")
            return
        
        # 查看集合信息
        count = collection.count()
        print(f"✅ 集合 '{collection_name}' 信息:")
        print(f"  文档总数: {count}")
        print()
        
        # 查看集合的元数据字段结构（通过获取少量样本）
        if count > 0:
            print("📄 样本数据（前3条）:")
            print("-" * 80)
            sample = collection.get(limit=3, include=["documents", "metadatas", "embeddings"])
            
            for i in range(min(3, len(sample['ids']))):
                print(f"\n文档 {i+1}:")
                print(f"  ID: {sample['ids'][i]}")
                print(f"  内容预览: {sample['documents'][i][:100]}...")
                print(f"  元数据: {sample['metadatas'][i]}")
                if sample.get('embeddings'):
                    print(f"  向量维度: {len(sample['embeddings'][i])}")
            print()
            
            # 查看所有唯一的 metadata 键
            print("🔑 元数据字段结构:")
            print("-" * 80)
            all_metadata = collection.get(include=["metadatas"])
            if all_metadata.get('metadatas'):
                # 收集所有唯一的键
                all_keys = set()
                for meta in all_metadata['metadatas']:
                    if meta:
                        all_keys.update(meta.keys())
                
                print(f"  元数据字段: {sorted(all_keys)}")
                
                # 统计每个字段的示例值
                print("\n  字段示例值:")
                for key in sorted(all_keys):
                    values = []
                    for meta in all_metadata['metadatas']:
                        if meta and key in meta:
                            val = meta[key]
                            if val not in values:
                                values.append(val)
                            if len(values) >= 3:  # 只显示前3个示例
                                break
                    print(f"    {key}: {values}")
            print()
        
        # ChromaDB 底层使用 SQLite，查看底层表结构
        print("🗄️  ChromaDB 底层 SQLite 表结构:")
        print("-" * 80)
        chroma_db_path = os.path.join(vector_store_path, "chroma.sqlite3")
        if os.path.exists(chroma_db_path):
            conn = sqlite3.connect(chroma_db_path)
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print("  表列表:")
            for table in tables:
                print(f"    - {table[0]}")
            
            # 查看主要表的结构
            if tables:
                print("\n  主要表结构:")
                for table in tables[:5]:  # 只显示前5个表
                    table_name = table[0]
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    print(f"\n    表: {table_name}")
                    for col in columns:
                        print(f"      {col[1]} ({col[2]})")
            
            conn.close()
        else:
            print("  ⚠️  未找到 chroma.sqlite3 文件")
        
    except Exception as e:
        print(f"❌ 检查向量数据库失败: {e}")
        import traceback
        traceback.print_exc()


def inspect_memory_database():
    """查看 SQLite 记忆数据库的表结构和数据"""
    print("\n" + "=" * 80)
    print("📊 检查 SQLite 记忆数据库")
    print("=" * 80)
    
    db_path = config.CHAT_MEMORY_DB_PATH
    print(f"数据库路径: {db_path}\n")
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在！")
        return
    
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
        cursor = conn.cursor()
        
        # 1. 查看所有表
        print("📋 数据库中的表:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        print()
        
        if not tables:
            print("⚠️  数据库中没有表")
            conn.close()
            return
        
        # 2. 查看每个表的结构
        print("🗄️  表结构详情:")
        print("-" * 80)
        for table in tables:
            table_name = table[0]
            print(f"\n表: {table_name}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("  字段:")
            for col in columns:
                col_info = f"    {col[1]} ({col[2]}"
                if col[3]:  # NOT NULL
                    col_info += " NOT NULL"
                if col[4]:  # DEFAULT
                    col_info += f" DEFAULT {col[4]}"
                if col[5]:  # PRIMARY KEY
                    col_info += " PRIMARY KEY"
                col_info += ")"
                print(col_info)
            
            # 获取记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"  记录数: {count}")
            
            # 如果是 checkpoints 表，显示一些统计信息
            if table_name == "checkpoints":
                print("\n  📊 checkpoints 表统计:")
                
                # 统计每个 thread_id 的 checkpoint 数量
                cursor.execute("""
                    SELECT thread_id, COUNT(*) as count 
                    FROM checkpoints 
                    GROUP BY thread_id 
                    ORDER BY count DESC
                    LIMIT 10
                """)
                thread_stats = cursor.fetchall()
                if thread_stats:
                    print("    各 thread_id 的 checkpoint 数量（前10）:")
                    for row in thread_stats:
                        print(f"      {row[0]}: {row[1]} 个")
                
                # 查看最新的几条记录（不包含 blob 内容）
                cursor.execute("""
                    SELECT thread_id, checkpoint_ns, 
                           LENGTH(checkpoint) as checkpoint_size,
                           LENGTH(metadata) as metadata_size
                    FROM checkpoints 
                    ORDER BY checkpoint_ns DESC 
                    LIMIT 5
                """)
                recent = cursor.fetchall()
                if recent:
                    print("\n    最新记录（前5条）:")
                    for row in recent:
                        print(f"      thread_id: {row[0]}")
                        print(f"      checkpoint_ns: {row[1]}")
                        print(f"      checkpoint 大小: {row[2]} bytes")
                        print(f"      metadata 大小: {row[3]} bytes")
                        print()
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 检查记忆数据库失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🔍 数据库结构检查工具")
    print("=" * 80 + "\n")
    
    # 检查向量数据库
    inspect_vector_database()
    
    # 检查记忆数据库
    inspect_memory_database()
    
    print("\n" + "=" * 80)
    print("✅ 检查完成")
    print("=" * 80 + "\n")

