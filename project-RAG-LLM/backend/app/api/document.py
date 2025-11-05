# backend/app/api/document.py

import os
from pathlib import Path
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from datetime import datetime

from ..config import PROJECT_ROOT, MAX_UPLOAD_SIZE


document_bp = Blueprint("document", __name__)

# 定义上传文件保存路径
UPLOAD_FOLDER = PROJECT_ROOT / "data" / "upload_documents"

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx', '.doc', '.md'}


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@document_bp.post("/documents/upload")
def upload_document():
    """
    处理文档上传请求
    接收文件并保存到 data/upload_documents 目录
    """
    # 检查是否有文件在请求中
    if 'file' not in request.files:
        return jsonify({"error": "请求中没有文件"}), 400
    
    file = request.files['file']
    
    # 检查用户是否选择了文件
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400
    
    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({
            "error": f"不支持的文件类型。支持的格式：{', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # 确保上传目录存在
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # 使用安全的文件名
        filename = secure_filename(file.filename)
        
        # 生成唯一文件名（添加时间戳避免重名）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) == 2:
            unique_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
        else:
            unique_filename = f"{filename}_{timestamp}"
        
        # 完整的文件保存路径
        file_path = UPLOAD_FOLDER / unique_filename
        
        # 保存文件
        file.save(str(file_path))
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 检查文件大小
        if file_size > MAX_UPLOAD_SIZE:
            # 删除超大文件
            os.remove(file_path)
            return jsonify({
                "error": f"文件大小超过限制 ({MAX_UPLOAD_SIZE / 1024 / 1024:.1f}MB)"
            }), 400
        
        return jsonify({
            "message": "文件上传成功",
            "filename": unique_filename,
            "original_filename": file.filename,
            "size": file_size,
            "path": str(file_path.relative_to(PROJECT_ROOT)),
            "uploaded_at": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": f"文件上传失败: {str(e)}"
        }), 500


@document_bp.get("/documents")
def get_documents():
    """
    获取已上传的文档列表
    """
    try:
        # 确保目录存在
        if not UPLOAD_FOLDER.exists():
            return jsonify({"documents": []}), 200
        
        documents = []
        for file_path in UPLOAD_FOLDER.iterdir():
            if file_path.is_file() and allowed_file(file_path.name):
                stat = file_path.stat()
                documents.append({
                    "id": file_path.stem,  # 使用文件名（不含扩展名）作为ID
                    "name": file_path.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "status": "uploaded"  # 可以扩展为 uploaded/processing/processed
                })
        
        # 按创建时间倒序排序
        documents.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({"documents": documents}), 200
        
    except Exception as e:
        return jsonify({
            "error": f"获取文档列表失败: {str(e)}"
        }), 500


@document_bp.delete("/documents/<string:document_id>")
def delete_document(document_id: str):
    """
    删除指定文档
    """
    try:
        # 查找匹配的文件（document_id 是文件名不含扩展名的部分）
        deleted = False
        for file_path in UPLOAD_FOLDER.iterdir():
            if file_path.is_file() and file_path.stem == document_id:
                os.remove(file_path)
                deleted = True
                break
        
        if deleted:
            return jsonify({"message": "文档删除成功"}), 200
        else:
            return jsonify({"error": "文档不存在"}), 404
            
    except Exception as e:
        return jsonify({
            "error": f"删除文档失败: {str(e)}"
        }), 500

