# project-RAG-LLM/scripts/ingest_data.py

import os
import sys
import logging
import argparse
from pathlib import Path

# --- 路径设置 ---
# 将项目根目录添加到 Python 路径中，以便脚本可以导入 backend 模块
try:
    # __file__ 是当前脚本的路径, Path(__file__).resolve() 获取绝对路径
    # .parent 定位到 scripts/ 目录
    # .parent.parent 定位到 project-RAG-LLM/ 根目录
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
except NameError:
    PROJECT_ROOT = Path('.').resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 导入核心服务
# 这一步依赖于上面的路径设置
from backend.app.services.ingestion_service import IngestionService
from backend.app import config

def main():
    """主函数：解析命令行参数并执行数据入库流程。"""
    
    # --- 1. 设置命令行参数解析 ---
    parser = argparse.ArgumentParser(
        description="RAG-LLM 项目数据入库脚本。扫描指定目录，进行增量更新到向量数据库。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # 定义要扫描的目录参数，默认来自 config.RAW_DOCUMENTS_PATH（可被命令行覆盖）
    default_docs_path = Path(config.RAW_DOCUMENTS_PATH)
    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        default=str(default_docs_path),
        help=f"要扫描的文档来源目录。\n(默认: {default_docs_path})"
    )
    args = parser.parse_args()

    # --- 2. 执行入库流程 ---
    docs_path = Path(args.directory).resolve()
    
    if not docs_path.exists() or not docs_path.is_dir():
        logger.error(f"错误：指定的目录不存在或不是一个有效的目录 -> {docs_path}")
        return

    logger.info("=" * 60)
    logger.info(f"🚀 开始执行数据入库流程")
    logger.info(f"扫描目录: {docs_path}")
    logger.info("=" * 60)

    try:
        # 初始化 IngestionService
        # 它会自动使用 config.py 中定义的生产环境向量数据库路径
        service = IngestionService()
        
        # 调用核心方法，执行完整的增量入库
        # recursive=True 表示会递归扫描所有子目录
        result = service.run_ingestion_from_directory(str(docs_path), recursive=True)
        
        logger.info("\n" + "-" * 20 + " 入库流程完成 " + "-" * 20)
        logger.info(f"✓ 新增/更新文件数: {result.get('upsert_files', 0)}")
        logger.info(f"✓ 新增/更新文本块: {result.get('upsert_chunks', 0)}")
        logger.info(f"✓ 已删除文件数:     {result.get('deleted_files', 0)}")
        logger.info(f"✓ 已删除文本块:     {result.get('deleted_chunks', 0)}")
        
        # 检查知识库健康状况
        health_check = service.check_knowledge_base_health()
        logger.info("\n" + "-" * 20 + " 知识库状态检查 " + "-" * 20)
        logger.info(f"  - 知识库状态: {'健康' if health_check.get('healthy') else '异常'}")
        logger.info(f"  - 文档块总数: {health_check.get('total_documents', 'N/A')}")
        logger.info(f"  - 唯一文件数: {health_check.get('unique_sources', 'N/A')}")
        logger.info(f"  - 数据库路径: {health_check.get('persist_path', 'N/A')}")

    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        logger.error("请确保您在项目的根目录 'project-RAG-LLM' 下运行此脚本，或者已正确安装所有依赖。")
    except Exception as e:
        logger.error(f"入库过程中发生未知错误: {e}", exc_info=True)
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 脚本执行完毕")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()