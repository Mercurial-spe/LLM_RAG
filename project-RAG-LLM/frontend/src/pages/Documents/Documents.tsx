/**
 * 文档管理页面
 */
import { useState, useEffect } from 'react';
import documentAPI from '../../api/document';
import { formatFileSize, formatDateTime, validateFileType } from '../../utils/helpers';
import { SUPPORTED_FILE_TYPES, MAX_FILE_SIZE } from '../../constants/config';
import type { Document, UploadProgress } from '../../types';
import './Documents.css';

const Documents = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const data = await documentAPI.getDocuments();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('加载文档失败:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    if (!validateFileType(file, SUPPORTED_FILE_TYPES)) {
      alert(`不支持的文件类型。支持的格式：${SUPPORTED_FILE_TYPES.join(', ')}`);
      return;
    }

    // 验证文件大小
    if (file.size > MAX_FILE_SIZE) {
      alert(`文件大小超过限制。最大支持 ${formatFileSize(MAX_FILE_SIZE)}`);
      return;
    }

    setUploadProgress({ name: file.name, progress: 0 });

    try {
      await documentAPI.uploadDocument(file);
      setUploadProgress({ name: file.name, progress: 100 });
      setTimeout(() => {
        setUploadProgress(null);
        loadDocuments();
      }, 1000);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      alert('上传失败：' + errorMessage);
      setUploadProgress(null);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!confirm('确定要删除这个文档吗？')) return;

    try {
      await documentAPI.deleteDocument(documentId);
      loadDocuments();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      alert('删除失败：' + errorMessage);
    }
  };

  return (
    <div className="documents-container">
      <div className="documents-header">
        <h2>文档管理</h2>
        <label className="upload-button">
          <input
            type="file"
            onChange={handleFileUpload}
            accept={SUPPORTED_FILE_TYPES.join(',')}
            style={{ display: 'none' }}
          />
          📤 上传文档
        </label>
      </div>

      {uploadProgress && (
        <div className="upload-progress">
          <p>正在上传: {uploadProgress.name}</p>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${uploadProgress.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="documents-content">
        {isLoading ? (
          <div className="loading">加载中...</div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <p>📂 还没有上传任何文档</p>
            <p>点击上方"上传文档"按钮开始</p>
          </div>
        ) : (
          <div className="documents-grid">
            {documents.map((doc) => (
              <div key={doc.id} className="document-card">
                <div className="document-icon">📄</div>
                <div className="document-info">
                  <h3>{doc.name}</h3>
                  <p className="document-meta">
                    <span>{formatFileSize(doc.size)}</span>
                    <span>•</span>
                    <span>{formatDateTime(doc.created_at)}</span>
                  </p>
                  {doc.status && (
                    <span className={`status-badge ${doc.status}`}>
                      {doc.status === 'processed' ? '已处理' : '处理中'}
                    </span>
                  )}
                </div>
                <button
                  className="delete-button"
                  onClick={() => handleDelete(doc.id)}
                  title="删除文档"
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Documents;

