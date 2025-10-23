# backend/tests/test_simple.py

"""
简单测试 - 测试单个文件
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.document_service import DocumentService


def main():
    print("=" * 70)
    print("简单测试 - 测试文档处理")
    print("=" * 70)
    
    # 初始化服务
    print("\n[1] 初始化文档服务...")
    service = DocumentService()
    print("✓ 初始化成功")
    print(f"  支持的格式: {list(service.SUPPORTED_FORMATS.keys())}")
    
    # 测试文件列表
    data_dir = project_root / "data" / "raw_documents"
    
    test_files = [
        data_dir / "txt" / "计网大纲.txt",
        data_dir / "md" / "小测选择题.md",
        data_dir / "pdf" / "第四章主观作业.pdf",
        data_dir / "docx" / "第2章（物理层）_主观题_答案版.doc",
        data_dir / "docx" / "第5章（网络层之主观题）_答案.docx",
    ]
    
    results = []
    
    for file_path in test_files:
        if not file_path.exists():
            print(f"\n⚠️  文件不存在: {file_path.name}")
            continue
        
        print(f"\n{'=' * 70}")
        print(f"测试文件: {file_path.name}")
        print(f"文件类型: {file_path.suffix}")
        print(f"文件大小: {file_path.stat().st_size / 1024:.2f} KB")
        print('-' * 70)
        
        try:
            # 处理文档
            chunks = service.process_document(str(file_path))
            
            # 显示结果
            print(f"\n✓ 处理成功!")
            print(f"  切分块数: {len(chunks)}")
            print(f"  向量维度: {len(chunks[0]['embedding'])}")
            print(f"  第一块字符数: {len(chunks[0]['content'])}")
            
            # 内容预览
            preview = chunks[0]['content'][:100].replace('\n', ' ')
            print(f"\n  内容预览: {preview}...")
            
            results.append({
                'file': file_path.name,
                'success': True,
                'chunks': len(chunks)
            })
            
        except Exception as e:
            print(f"\n✗ 处理失败: {e}")
            results.append({
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
    
    if success_count > 0:
        total_chunks = sum(r.get('chunks', 0) for r in results if r['success'])
        print(f"\n生成的文本块总数: {total_chunks}")
    
    print(f"\n详细结果:")
    for r in results:
        status = "✓" if r['success'] else "✗"
        if r['success']:
            print(f"  {status} {r['file']}: {r['chunks']} 块")
        else:
            print(f"  {status} {r['file']}: {r.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    
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
