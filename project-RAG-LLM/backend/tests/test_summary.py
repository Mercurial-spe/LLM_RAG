"""
测试 Chat Memory 数据库内容和 Summarization 功能
========================================================
用途：
1. 查看 chat_memory.db 的实际存储内容（使用 SQLChatMessageHistory）
2. 验证 checkpointer 是否正确保存对话历史
3. 测试 Summarization 是否能正确触发
4. 观察消息数量和 token 统计
"""

import sys
import os
import sqlite3
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config
from app.core.rag_agent import invoke, stream_messages

# 导入 LangGraph 的 SqliteSaver 来正确读取 checkpoints
from langgraph.checkpoint.sqlite import SqliteSaver


def inspect_database_with_sql_history(thread_id="1"):
    """使用 LangGraph SqliteSaver 检查数据库的消息历史"""
    print("=" * 80)
    print("📊 检查 Chat Memory 数据库 (使用 LangGraph SqliteSaver)")
    print("=" * 80)
    
    db_path = config.CHAT_MEMORY_DB_PATH
    print(f"数据库路径: {db_path}")
    print(f"目标 Thread ID: {thread_id}\n")
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在！请先运行对话生成数据。")
        return
    
    try:
        # 使用 LangGraph 的 SqliteSaver 来读取 checkpoints
        conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # 1. 先检查表结构
        cursor = conn.cursor()
        print("📋 数据库中的表:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        print()
        
        table_names = [t[0] for t in tables]
        
        if 'checkpoints' not in table_names:
            print("❌ 未找到 checkpoints 表！")
            conn.close()
            return
        
        # 2. 使用 SqliteSaver 的 API
        print("✅ 使用 LangGraph SqliteSaver 读取 checkpoints...\n")
        saver = SqliteSaver(conn)
        
        # 3. 查看所有 thread_ids
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints;")
        thread_ids = [t[0] for t in cursor.fetchall()]
        print(f"🧵 所有 Thread IDs: {thread_ids}\n")
        
        # 4. 获取目标 thread 的最新 checkpoint
        print(f"📬 Thread '{thread_id}' 的消息历史:")
        print("-" * 80)
        
        # 使用 get_tuple 方法获取最新的 checkpoint
        # 参数: config = {"configurable": {"thread_id": thread_id}}
        from langgraph.checkpoint.base import CheckpointTuple
        
        checkpoint_config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = saver.get_tuple(checkpoint_config)
        
        if checkpoint_tuple is None:
            print(f"⚠️  Thread '{thread_id}' 没有 checkpoint 记录")
        else:
            print(f"✅ 找到 Checkpoint!")
            print(f"  Checkpoint ID: {checkpoint_tuple.config['configurable'].get('checkpoint_id', 'N/A')}")
            
            # 从 checkpoint 中提取消息
            checkpoint = checkpoint_tuple.checkpoint
            
            # LangGraph checkpoint 结构: {'v': 1, 'channel_values': {...}, ...}
            if 'channel_values' in checkpoint:
                channel_values = checkpoint.get('channel_values', {})
                messages = channel_values.get('messages', [])
                
                print(f"  消息总数: {len(messages)}\n")
                
                if messages:
                    print("  所有消息:")
                    print("-" * 80)
                    for i, msg in enumerate(messages, 1):
                        # 获取消息类型
                        if hasattr(msg, 'type'):
                            role = msg.type
                        elif hasattr(msg, '__class__'):
                            role = msg.__class__.__name__
                        else:
                            role = str(type(msg).__name__)
                        
                        # 获取消息内容
                        if hasattr(msg, 'content'):
                            content = msg.content
                        else:
                            content = str(msg)
                        
                        # 截断过长的内容
                        content_preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"\n  [{i}] {role}:")
                        print(f"    {content_preview}")
                else:
                    print("  ⚠️  Checkpoint 中没有消息")
            else:
                print("  ⚠️  Checkpoint 结构异常，未找到 channel_values")
                print(f"  Checkpoint keys: {list(checkpoint.keys())}")
        
        # 5. 统计信息
        cursor.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?;", (thread_id,))
        checkpoint_count = cursor.fetchone()[0]
        print(f"\n📊 Thread '{thread_id}' 的统计:")
        print(f"  Checkpoint 记录数: {checkpoint_count}")
        print(f"  (注意：每次对话可能产生多个 checkpoint)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 检查失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


def inspect_database():
    """原始的数据库检查函数（保留以备用）"""
    print("=" * 80)
    print("📊 检查 Chat Memory 数据库（原始方法）")
    print("=" * 80)
    
    db_path = config.CHAT_MEMORY_DB_PATH
    print(f"数据库路径: {db_path}\n")
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在！请先运行对话生成数据。")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 查看所有表
    print("📋 数据库中的表:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
    print()
    
    # 2. 查看 checkpoints 表结构（如果存在）
    table_names = [t[0] for t in tables]
    
    if 'checkpoints' in table_names:
        print(f"📐 表 'checkpoints' 的结构:")
        cursor.execute(f"PRAGMA table_info(checkpoints);")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        print()
        
        # 3. 统计记录数
        cursor.execute(f"SELECT COUNT(*) FROM checkpoints;")
        count = cursor.fetchone()[0]
        print(f"📈 总记录数: {count}\n")
        
        # 4. 查看所有 thread_id
        cursor.execute(f"SELECT DISTINCT thread_id FROM checkpoints;")
        thread_ids = cursor.fetchall()
        print(f"🧵 所有 Thread IDs: {[t[0] for t in thread_ids]}\n")
        
        # 5. 按 thread_id 统计
        for thread_id_tuple in thread_ids:
            thread_id = thread_id_tuple[0]
            cursor.execute(f"SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?;", (thread_id,))
            thread_count = cursor.fetchone()[0]
            print(f"  Thread '{thread_id}': {thread_count} 条记录")
    
    conn.close()
    print("\n" + "=" * 80)


def test_conversation_memory():
    """测试对话记忆功能"""
    print("\n" + "=" * 80)
    print("🧪 测试对话记忆功能")
    print("=" * 80)
    
    thread_id = "test_thread_1"
    
    questions = [
        "什么是快速排序？",
        "它的时间复杂度是多少？",
        "能给我写个Python实现吗？"
    ]
    
    print(f"使用 Thread ID: {thread_id}\n")
    
    for i, question in enumerate(questions, 1):
        print(f"\n--- 第 {i} 轮对话 ---")
        print(f"问题: {question}")
        print("回答: ", end="", flush=True)
        
        # 流式输出回答
        answer_parts = []
        for chunk in stream_messages(question, thread_id=thread_id):
            print(chunk, end="", flush=True)
            answer_parts.append(chunk)
        
        answer = "".join(answer_parts)
        print(f"\n(总计 {len(answer)} 字符)")
    
    print("\n✅ 对话完成！现在检查数据库...")


def test_summarization_trigger():
    """测试 Summarization 触发（通过大量对话）"""
    print("\n" + "=" * 80)
    print("🔥 测试 Summarization 触发")
    print("=" * 80)
    
    thread_id = "test_summary_thread"
    
    print(f"使用 Thread ID: {thread_id}")
    print(f"当前配置:")
    print(f"  - Max Tokens Before Summary: {config.MEMORY_MAX_TOKENS_BEFORE_SUMMARY}")
    print(f"  - Messages To Keep: {config.MEMORY_MESSAGES_TO_KEEP}\n")
    
    # 生成多轮对话以触发 summarization
    questions = [
        "介绍一下冒泡排序算法",
        "冒泡排序的时间复杂度是多少",
        "给我写一个Python版本的冒泡排序",
        "如何优化冒泡排序",
        "介绍一下选择排序算法",
        "选择排序和冒泡排序有什么区别",
        "给我写一个C++版本的选择排序",
        "介绍一下插入排序算法",
        "插入排序适用于什么场景",
        "给我写一个Java版本的插入排序",
        "介绍一下归并排序算法",
        "归并排序的空间复杂度是多少",
        "给我写一个Python版本的归并排序",
        "介绍一下堆排序算法",
        "堆排序如何实现原地排序",
    ]
    
    print(f"将进行 {len(questions)} 轮对话，尝试触发 Summarization...\n")
    
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question[:30]}...")
        
        # 使用 invoke 而不是 stream，加快测试速度
        answer = invoke(question, thread_id=thread_id)
        print(f"    ✓ 回答长度: {len(answer)} 字符\n")
    
    print("✅ 对话完成！检查数据库是否触发了 Summarization...")


def clear_database():
    """清空数据库（用于重新测试）"""
    print("\n" + "=" * 80)
    print("🗑️  清空数据库")
    print("=" * 80)
    
    db_path = config.CHAT_MEMORY_DB_PATH
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，无需清空。")
        return
    
    response = input(f"确认要删除数据库文件 '{db_path}' 吗？(yes/no): ")
    if response.lower() == 'yes':
        os.remove(db_path)
        print("✅ 数据库已删除！")
    else:
        print("❌ 取消操作。")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Chat Memory 数据库测试工具")
    parser.add_argument(
        "action",
        choices=["inspect", "test", "summary", "clear", "history"],
        help="操作类型: inspect(查看数据库), test(测试对话), summary(测试总结), clear(清空数据库), history(查看消息历史)"
    )
    parser.add_argument(
        "--thread",
        type=str,
        default="1",
        help="指定要查看的 thread_id (默认: 1)"
    )
    
    args = parser.parse_args()
    
    if args.action == "inspect":
        inspect_database()
    elif args.action == "history":
        inspect_database_with_sql_history(thread_id=args.thread)
    elif args.action == "test":
        test_conversation_memory()
        inspect_database_with_sql_history(thread_id="test_thread_1")
    elif args.action == "summary":
        test_summarization_trigger()
        inspect_database_with_sql_history(thread_id="test_summary_thread")
    elif args.action == "clear":
        clear_database()

