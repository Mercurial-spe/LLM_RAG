"""
对话管理模块
====================
职责：
- 从 SQLite checkpoints 数据库读取对话历史
- 提供对话列表、消息查询、删除等功能
- 管理对话元数据（标题、时间等）
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from .. import config

logger = logging.getLogger(__name__)


def _get_db_connection():
    """获取数据库连接"""
    try:
        conn = sqlite3.connect(config.CHAT_MEMORY_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
        return conn
    except Exception as e:
        logger.error(f"无法连接到数据库: {e}")
        raise


def get_all_conversations() -> List[Dict[str, Any]]:
    """
    获取所有对话列表
    
    Returns:
        对话列表，包含 thread_id、title、last_message_time、message_count
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints';")
        if not cursor.fetchone():
            logger.warning("checkpoints 表不存在，返回空列表")
            conn.close()
            return []
        
        # 获取每个 thread_id 的最新 checkpoint
        query = """
        SELECT 
            thread_id,
            MAX(checkpoint_ns) as last_checkpoint_ns,
            COUNT(*) as checkpoint_count
        FROM checkpoints
        GROUP BY thread_id
        ORDER BY last_checkpoint_ns DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        conversations = []
        for row in rows:
            thread_id = row['thread_id']
            
            # 获取该 thread 的最新 checkpoint 详情
            cursor.execute("""
                SELECT checkpoint, metadata
                FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
            """, (thread_id, row['last_checkpoint_ns']))
            
            checkpoint_row = cursor.fetchone()
            if not checkpoint_row:
                continue
            
            # 解析 checkpoint（blob 格式）
            checkpoint_blob = checkpoint_row['checkpoint']
            metadata_blob = checkpoint_row['metadata']
            
            # 默认值
            title = None
            message_count = 0
            
            try:
                # LangGraph 的 checkpoint 是序列化的，需要解析
                checkpoint_data = _parse_checkpoint(checkpoint_blob)
                metadata = _parse_metadata(metadata_blob)
                
                # 为了保证与前端实际看到的消息数量一致，这里直接复用
                # get_conversation_messages 的逻辑，按其返回的 messages 长度计数
                try:
                    from .conversation_manager import get_conversation_messages as _get_msgs  # type: ignore
                except ImportError:
                    _get_msgs = get_conversation_messages  # 同模块内回退
                
                try:
                    conv_detail = _get_msgs(thread_id)
                    message_count = len(conv_detail.get('messages', []))
                except Exception as e:
                    logger.warning(f"统计 thread {thread_id} 消息数失败: {e}")
                    # 如果失败则退回到 checkpoint 中的粗略统计
                    messages = checkpoint_data.get('channel_values', {}).get('messages', [])
                    if isinstance(messages, list):
                        message_count = len(messages)
                
                # 生成标题（优先 metadata.title，其次首条用户消息，再次默认）
                title = metadata.get('title', None)
                if not title:
                    messages = checkpoint_data.get('channel_values', {}).get('messages', [])
                    if isinstance(messages, list) and messages:
                        for msg in messages:
                            if isinstance(msg, dict) and msg.get('type') in ['human', 'user']:
                                content = msg.get('content', '')
                                title = content[:30] + '...' if len(content) > 30 else content
                                break
                
            except Exception as e:
                logger.warning(f"解析 thread {thread_id} 的 checkpoint 失败: {e}")
            
            if not title:
                title = f"对话 {thread_id[:8]}"
            
            # 时间戳转换（checkpoint_ns 可能是字符串，需要转换）
            checkpoint_ns = row['last_checkpoint_ns']
            try:
                if isinstance(checkpoint_ns, str):
                    if not checkpoint_ns or checkpoint_ns.strip() == '':
                        # 空字符串，使用当前时间
                        last_message_time = datetime.now().isoformat()
                    else:
                        checkpoint_ns = float(checkpoint_ns)
                        last_message_time = datetime.fromtimestamp(checkpoint_ns / 1e9).isoformat()
                else:
                    last_message_time = datetime.fromtimestamp(checkpoint_ns / 1e9).isoformat()
            except (ValueError, TypeError, OSError) as e:
                logger.warning(f"时间戳转换失败: {e}，使用当前时间")
                last_message_time = datetime.now().isoformat()
            
            conversations.append({
                'thread_id': thread_id,
                'title': title,
                'last_message_time': last_message_time,
                'message_count': message_count,
                'checkpoint_count': row['checkpoint_count']
            })
        
        conn.close()
        logger.info(f"获取到 {len(conversations)} 个对话")
        return conversations
        
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        return []


def get_conversation_messages(thread_id: str) -> Dict[str, Any]:
    """
    获取指定对话的完整消息历史
    
    Args:
        thread_id: 对话 ID
        
    Returns:
        包含 thread_id 和 messages 列表的字典
    """
    try:
        # 尝试使用 LangGraph 的 SqliteSaver 来正确读取 checkpoint
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3
            
            conn = sqlite3.connect(config.CHAT_MEMORY_DB_PATH, check_same_thread=False)
            saver = SqliteSaver(conn)
            
            # 使用 get_tuple 方法获取 checkpoint
            checkpoint_config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = saver.get_tuple(checkpoint_config)
            
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                # 从 checkpoint 中提取消息
                checkpoint_data = checkpoint_tuple.checkpoint
                messages = checkpoint_data.get('channel_values', {}).get('messages', [])
                
                # 转换消息格式，过滤掉工具调用消息（ToolMessage）
                formatted_messages = []
                filtered_count = 0
                for msg in messages:
                    # 获取消息类型
                    msg_type = None
                    content = ''
                    
                    if isinstance(msg, dict):
                        msg_type = msg.get('type', '')
                        content = msg.get('content', '')
                    elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                        # LangChain Message 对象
                        msg_type = msg.type
                        content = msg.content
                    elif hasattr(msg, '__class__'):
                        # 通过类名判断消息类型
                        class_name = msg.__class__.__name__
                        if 'HumanMessage' in class_name:
                            msg_type = 'human'
                        elif 'AIMessage' in class_name:
                            msg_type = 'ai'
                        elif 'ToolMessage' in class_name:
                            msg_type = 'tool'
                        elif 'SystemMessage' in class_name:
                            msg_type = 'system'
                        
                        if hasattr(msg, 'content'):
                            content = msg.content
                    
                    # 过滤掉工具调用消息和系统消息，只保留用户消息和助手回复
                    if msg_type in ['tool', 'system']:
                        filtered_count += 1
                        logger.debug(f"过滤掉 {msg_type} 类型消息（工具调用或系统消息）")
                        continue
                    
                    # 只处理用户消息和助手消息
                    if msg_type in ['human', 'user']:
                        role = 'user'
                    elif msg_type in ['ai', 'assistant']:
                        role = 'assistant'
                    else:
                        # 未知类型，跳过
                        continue
                    
                    # 获取时间戳
                    if isinstance(msg, dict):
                        timestamp = msg.get('timestamp') or datetime.now().isoformat()
                    else:
                        timestamp = datetime.now().isoformat()
                    
                    formatted_messages.append({
                        'role': role,
                        'content': content,
                        'timestamp': timestamp
                    })
                
                conn.close()
                logger.info(
                    f"获取 thread {thread_id} 的消息: "
                    f"原始消息 {len(messages)} 条, "
                    f"过滤掉 {filtered_count} 条工具/系统消息, "
                    f"返回 {len(formatted_messages)} 条用户可见消息"
                )
                return {
                    'thread_id': thread_id,
                    'messages': formatted_messages
                }
            
            # 未找到任何 checkpoint，返回空消息列表（避免返回 None 导致前端解构失败）
            conn.close()
            logger.info(f"thread {thread_id} 未找到任何 checkpoint，返回空消息列表")
        
        except ImportError:
            logger.warning("无法导入 SqliteSaver，使用原始方法")
        except Exception as e:
            logger.warning(f"使用 SqliteSaver 读取失败: {e}，使用原始方法")
        
    except Exception as e:
        logger.error(f"获取对话消息失败: {e}", exc_info=True)
    
    # 兜底：任何异常或无记录时，都返回空列表而不是 None
    return {
        'thread_id': thread_id,
        'messages': []
    }


def delete_conversation(thread_id: str) -> bool:
    """
    删除指定对话的所有 checkpoint
    
    Args:
        thread_id: 对话 ID
        
    Returns:
        是否删除成功
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"删除 thread {thread_id}，共 {deleted_count} 条记录")
        return deleted_count > 0
        
    except Exception as e:
        logger.error(f"删除对话失败: {e}", exc_info=True)
        return False


def update_conversation_title(thread_id: str, title: str) -> bool:
    """
    更新对话标题（存储在最新 checkpoint 的 metadata 中）
    
    Args:
        thread_id: 对话 ID
        title: 新标题
        
    Returns:
        是否更新成功
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        # 获取最新的 checkpoint
        cursor.execute("""
            SELECT checkpoint_ns, metadata
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_ns DESC
            LIMIT 1
        """, (thread_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            logger.warning(f"未找到 thread_id={thread_id} 的对话")
            return False
        
        # 解析并更新 metadata
        metadata = _parse_metadata(row['metadata'])
        metadata['title'] = title
        
        # 序列化回去
        updated_metadata = _serialize_metadata(metadata)
        
        # 更新数据库
        cursor.execute("""
            UPDATE checkpoints
            SET metadata = ?
            WHERE thread_id = ? AND checkpoint_ns = ?
        """, (updated_metadata, thread_id, row['checkpoint_ns']))
        
        conn.commit()
        conn.close()
        
        logger.info(f"更新 thread {thread_id} 的标题为: {title}")
        return True
        
    except Exception as e:
        logger.error(f"更新对话标题失败: {e}", exc_info=True)
        return False


# ========== 辅助函数 ==========

def _parse_checkpoint(checkpoint_blob: bytes) -> Dict[str, Any]:
    """
    解析 checkpoint blob
    LangGraph 使用 pickle 序列化
    """
    if not checkpoint_blob:
        return {}
    
    try:
        import pickle
        checkpoint = pickle.loads(checkpoint_blob)
        return checkpoint if isinstance(checkpoint, dict) else {}
    except Exception as e:
        # Pickle 解析失败，可能是数据损坏或格式不兼容
        # 不要尝试其他解析方式，直接返回空字典
        logger.debug(f"checkpoint 解析失败（可能是 pickle 格式不兼容）: {e}")
        return {}


def _parse_metadata(metadata_blob: Optional[bytes]) -> Dict[str, Any]:
    """解析 metadata blob"""
    if not metadata_blob:
        return {}
    
    try:
        import pickle
        metadata = pickle.loads(metadata_blob)
        return metadata if isinstance(metadata, dict) else {}
    except Exception as e:
        # Metadata 解析失败，直接返回空字典
        logger.debug(f"metadata 解析失败: {e}")
        return {}


def _serialize_metadata(metadata: Dict[str, Any]) -> bytes:
    """序列化 metadata"""
    try:
        import pickle
        return pickle.dumps(metadata)
    except Exception as e:
        logger.error(f"metadata 序列化失败: {e}")
        return b''

