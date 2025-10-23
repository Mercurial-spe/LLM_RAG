# backend/tests/test_document_service.py

"""
文档处理服务测试
测试各种格式文档的加载、切分和向量化功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.document_service import DocumentService


def print_separator(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print('=' * 70)
    else:
        print('-' * 70)


def test_single_file(service: DocumentService, file_path: str, file_type: str):
    """
    测试单个文件的处理
    
    Args:
        service: 文档服务实例
        file_path: 文件路径
        file_type: 文件类型描述
    """
    print_separator(f"测试 {file_type} 文件")
    
    try:
        print(f"文件路径: {file_path}")
        print(f"文件大小: {os.path.getsize(file_path) / 1024:.2f} KB")
        
        # 处理文档
        print("\n开始处理...")
        chunks = service.process_document(file_path)
        
        # 显示结果
        print(f"\n✓ 处理成功!")
        print(f"  切分块数: {len(chunks)}")
        
        if chunks:
            print(f"  向量维度: {len(chunks[0]['embedding'])}")
            print(f"  第一块字符数: {len(chunks[0]['content'])}")
            print(f"\n  第一块内容预览:")
            preview = chunks[0]['content'][:150].replace('\n', ' ')
            print(f"  {preview}...")
            
            # 显示元数据
            print(f"\n  元数据:")
            for key, value in chunks[0]['metadata'].items():
                print(f"    {key}: {value}")
        
        return True, len(chunks)
        
    except Exception as e:
        print(f"\n✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


def test_directory(service: DocumentService, dir_path: str, dir_name: str):
    """
    测试目录批量处理
    
    Args:
        service: 文档服务实例
        dir_path: 目录路径
        dir_name: 目录名称描述
    """
    print_separator(f"测试 {dir_name} 目录批量处理")
    
    try:
        print(f"目录路径: {dir_path}")
        
        # 统计文件
        files = list(Path(dir_path).glob("*"))
        files = [f for f in files if f.is_file()]
        print(f"文件数量: {len(files)}")
        for f in files:
            print(f"  - {f.name} ({os.path.getsize(f) / 1024:.2f} KB)")
        
        # 批量处理
        print("\n开始批量处理...")
        chunks = service.process_directory(dir_path, recursive=False)
        
        # 显示结果
        print(f"\n✓ 批量处理成功!")
        print(f"  总块数: {len(chunks)}")
        
        # 获取统计信息
        stats = service.get_document_stats(chunks)
        print(f"\n  统计信息:")
        print(f"    总块数: {stats['total_chunks']}")
        print(f"    总字符数: {stats['total_chars']}")
        print(f"    平均块大小: {stats['avg_chunk_size']}")
        print(f"    向量维度: {stats['embedding_dimension']}")
        print(f"    文档来源数: {len(stats['sources'])}")
        
        return True, len(chunks)
        
    except Exception as e:
        print(f"\n✗ 批量处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


def main():
    """主测试函数"""
    print_separator("文档处理服务完整测试")
    print(f"测试时间: {__import__('datetime').datetime.now()}")
    
    # 定义文档目录
    data_dir = project_root / "data" / "raw_documents"
    
    # 测试结果统计
    results = {
        'total_tests': 0,
        'passed_tests': 0,
        'failed_tests': 0,
        'total_chunks': 0
    }
    
    try:
        # 初始化服务
        print_separator("1. 初始化文档服务")
        service = DocumentService()
        print("✓ 文档服务初始化成功")
        print(f"  支持的格式: {list(service.SUPPORTED_FORMATS.keys())}")
        
        # ==================== 测试TXT文件 ====================
        results['total_tests'] += 1
        txt_files = list((data_dir / "txt").glob("*.txt"))
        if txt_files:
            success, chunk_count = test_single_file(
                service, 
                str(txt_files[0]), 
                "TXT"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        else:
            print_separator("测试 TXT 文件")
            print("⚠️  未找到TXT文件")
        
        # ==================== 测试MD文件 ====================
        results['total_tests'] += 1
        md_files = list((data_dir / "md").glob("*.md"))
        if md_files:
            success, chunk_count = test_single_file(
                service, 
                str(md_files[0]), 
                "Markdown"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        else:
            print_separator("测试 Markdown 文件")
            print("⚠️  未找到MD文件")
        
        # ==================== 测试PDF文件 ====================
        results['total_tests'] += 1
        pdf_files = list((data_dir / "pdf").glob("*.pdf"))
        if pdf_files:
            success, chunk_count = test_single_file(
                service, 
                str(pdf_files[0]), 
                "PDF"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        else:
            print_separator("测试 PDF 文件")
            print("⚠️  未找到PDF文件")
        
        # ==================== 测试DOCX文件 ====================
        results['total_tests'] += 1
        docx_files = list((data_dir / "docx").glob("*.docx"))
        if docx_files:
            success, chunk_count = test_single_file(
                service, 
                str(docx_files[0]), 
                "DOCX"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        else:
            print_separator("测试 DOCX 文件")
            print("⚠️  未找到DOCX文件")
        
        # ==================== 测试DOC文件 ====================
        results['total_tests'] += 1
        doc_files = list((data_dir / "docx").glob("*.doc"))
        if doc_files:
            success, chunk_count = test_single_file(
                service, 
                str(doc_files[0]), 
                "DOC"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        else:
            print_separator("测试 DOC 文件")
            print("⚠️  未找到DOC文件")
        
        # ==================== 测试PDF目录批量处理 ====================
        results['total_tests'] += 1
        pdf_dir = data_dir / "pdf"
        if pdf_dir.exists() and list(pdf_dir.glob("*.pdf")):
            success, chunk_count = test_directory(
                service, 
                str(pdf_dir), 
                "PDF"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        
        # ==================== 测试DOCX目录批量处理 ====================
        results['total_tests'] += 1
        docx_dir = data_dir / "docx"
        if docx_dir.exists() and (list(docx_dir.glob("*.docx")) or list(docx_dir.glob("*.doc"))):
            success, chunk_count = test_directory(
                service, 
                str(docx_dir), 
                "DOCX/DOC"
            )
            if success:
                results['passed_tests'] += 1
                results['total_chunks'] += chunk_count
            else:
                results['failed_tests'] += 1
        
        # ==================== 测试全目录批量处理 ====================
        print_separator("测试全目录递归批量处理")
        print(f"目录路径: {data_dir}")
        print("\n开始递归处理所有文档...")
        
        all_chunks = service.process_directory(str(data_dir), recursive=True)
        
        print(f"\n✓ 全目录处理完成!")
        print(f"  总块数: {len(all_chunks)}")
        
        # 完整统计信息
        full_stats = service.get_document_stats(all_chunks)
        print(f"\n  完整统计信息:")
        print(f"    总块数: {full_stats['total_chunks']}")
        print(f"    总字符数: {full_stats['total_chars']:,}")
        print(f"    平均块大小: {full_stats['avg_chunk_size']}")
        print(f"    向量维度: {full_stats['embedding_dimension']}")
        print(f"    文档数量: {len(full_stats['sources'])}")
        print(f"\n  处理的文档列表:")
        for source in full_stats['sources']:
            print(f"    - {Path(source).name}")
        
        # ==================== 最终总结 ====================
        print_separator("测试总结")
        print(f"总测试数: {results['total_tests']}")
        print(f"通过测试: {results['passed_tests']} ✓")
        print(f"失败测试: {results['failed_tests']} ✗")
        print(f"成功率: {results['passed_tests']/results['total_tests']*100:.1f}%")
        print(f"\n生成的文本块总数: {results['total_chunks']}")
        print(f"全目录处理块数: {len(all_chunks)}")
        
        if results['failed_tests'] == 0:
            print("\n🎉 所有测试通过!")
        else:
            print(f"\n⚠️  有 {results['failed_tests']} 个测试失败")
        
        print_separator()
        
    except Exception as e:
        print(f"\n✗ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0 if results['failed_tests'] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
