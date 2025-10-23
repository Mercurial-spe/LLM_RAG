# backend/tests/test_load_only.py

"""
仅测试文档加载和切分 - 不进行向量化
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.document_service import DocumentService


def main():
    print("=" * 70)
    print("文档加载和切分测试 (不进行向量化)")
    print("=" * 70)
    
    # 初始化服务
    print("\n[1] 初始化文档服务...")
    service = DocumentService()
    print("✓ 初始化成功")
    print(f"  支持的格式: {list(service.SUPPORTED_FORMATS.keys())}")
    print(f"  文本切分配置: chunk_size={service.text_splitter._chunk_size}, overlap={service.text_splitter._chunk_overlap}")
    
    # 测试文件列表
    data_dir = project_root / "data" / "raw_documents"
    
    test_files = [
        ("TXT", data_dir / "txt" / "计网大纲.txt"),
        ("MD", data_dir / "md" / "小测选择题.md"),
        ("PDF", data_dir / "pdf" / "第四章主观作业.pdf"),
        ("DOC", data_dir / "docx" / "第2章（物理层）_主观题_答案版.doc"),
        ("DOCX", data_dir / "docx" / "第5章（网络层之主观题）_答案.docx"),
    ]
    
    results = []
    
    for file_type, file_path in test_files:
        if not file_path.exists():
            print(f"\n⚠️  文件不存在: {file_path.name}")
            continue
        
        print(f"\n{'=' * 70}")
        print(f"[{file_type}] {file_path.name}")
        print(f"  文件大小: {file_path.stat().st_size / 1024:.2f} KB")
        print('-' * 70)
        
        try:
            # 步骤1: 加载文档
            print("  步骤1: 加载文档...")
            documents = service.load_document(str(file_path))
            print(f"    ✓ 加载成功 - 原始段落数: {len(documents)}")
            
            # 步骤2: 切分文档
            print("  步骤2: 切分文档...")
            chunks = service.split_documents(documents)
            print(f"    ✓ 切分成功 - 文本块数: {len(chunks)}")
            
            # 显示第一块信息
            if chunks:
                first_chunk = chunks[0]
                print(f"\n  第一块信息:")
                print(f"    字符数: {len(first_chunk['content'])}")
                print(f"    Chunk ID: {first_chunk['metadata']['chunk_id']}")
                
                # 内容预览
                preview = first_chunk['content'][:150].replace('\n', ' ').strip()
                print(f"    内容预览: {preview}...")
                
                # 显示所有元数据
                print(f"\n    元数据:")
                for key, value in first_chunk['metadata'].items():
                    if isinstance(value, str) and len(str(value)) > 50:
                        print(f"      {key}: {str(value)[:50]}...")
                    else:
                        print(f"      {key}: {value}")
            
            results.append({
                'type': file_type,
                'file': file_path.name,
                'success': True,
                'documents': len(documents),
                'chunks': len(chunks),
                'avg_chunk_size': sum(len(c['content']) for c in chunks) // len(chunks) if chunks else 0
            })
            
        except Exception as e:
            print(f"    ✗ 处理失败: {e}")
            results.append({
                'type': file_type,
                'file': file_path.name,
                'success': False,
                'error': str(e)
            })
    
    # 总结
    print(f"\n{'=' * 70}")
    print("测试总结")
    print('=' * 70)
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\n总测试数: {total_count}")
    print(f"成功: {success_count} ✓")
    print(f"失败: {total_count - success_count} ✗")
    print(f"成功率: {success_count/total_count*100:.1f}%" if total_count > 0 else "N/A")
    
    if success_count > 0:
        total_chunks = sum(r.get('chunks', 0) for r in results if r['success'])
        avg_chunk_size = sum(r.get('avg_chunk_size', 0) for r in results if r['success']) // success_count
        print(f"\n生成的文本块总数: {total_chunks}")
        print(f"平均块大小: {avg_chunk_size} 字符")
    
    print(f"\n详细结果:")
    print(f"{'类型':<8} {'文件名':<40} {'状态':<6} {'块数':<8} {'平均大小'}")
    print('-' * 70)
    
    for r in results:
        if r['success']:
            print(f"{r['type']:<8} {r['file']:<40} {'✓':<6} {r['chunks']:<8} {r['avg_chunk_size']}")
        else:
            error = r.get('error', 'Unknown')[:30]
            print(f"{r['type']:<8} {r['file']:<40} {'✗':<6} {error}")
    
    print("\n" + "=" * 70)
    
    if success_count == total_count:
        print("🎉 所有文件加载和切分测试通过!")
        print("提示: 现在可以运行完整测试(包含向量化)")
    else:
        print(f"⚠️  有 {total_count - success_count} 个文件处理失败")
    
    print("=" * 70)
    
    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
