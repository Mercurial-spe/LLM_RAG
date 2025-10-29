/**
 * 首页
 */
import { Link } from 'react-router-dom';
import './Home.css';

const Home = () => {
  return (
    <div className="home-container">
      <div className="home-content">
        <h1 className="home-title">欢迎使用 RAG-LLM 问答系统</h1>
        <p className="home-description">
          基于检索增强生成（RAG）技术的智能问答系统，上传您的文档，开始智能对话
        </p>
        
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">💬</div>
            <h3>智能对话</h3>
            <p>基于您的文档内容进行智能问答</p>
            <Link to="/chat" className="feature-link">开始对话 →</Link>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">📄</div>
            <h3>文档管理</h3>
            <p>上传和管理您的知识库文档</p>
            <Link to="/documents" className="feature-link">管理文档 →</Link>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">⚙️</div>
            <h3>系统设置</h3>
            <p>配置模型参数和系统选项</p>
            <Link to="/settings" className="feature-link">进入设置 →</Link>
          </div>
        </div>

        <div className="quick-start">
          <h2>快速开始</h2>
          <ol>
            <li>在"文档管理"页面上传您的文档（支持 PDF、DOCX、TXT、MD 格式）</li>
            <li>等待文档处理完成</li>
            <li>在"对话"页面开始提问</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

export default Home;

