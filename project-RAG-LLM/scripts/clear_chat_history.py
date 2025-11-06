"""
清理对话历史数据库
解决 tool_call 不完整的问题
"""
import sqlite3
from pathlib import Path

# 定位数据库文件
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "chat_memory" / "chat_memory.db"

print(f"数据库路径: {DB_PATH}")

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 清理所有对话历史表
    tables = ['checkpoints', 'checkpoint_blobs', 'checkpoint_writes']
    
    for table in tables:
        try:
            cursor.execute(f'DELETE FROM {table}')
            print(f"✓ 已清理表: {table}")
        except sqlite3.OperationalError as e:
            print(f"⚠ 表 {table} 不存在或无法清理: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ 对话历史已成功清理！")
    print("💡 现在可以重新开始对话了")
    
except Exception as e:
    print(f"❌ 清理失败: {e}")
    import traceback
    traceback.print_exc()

