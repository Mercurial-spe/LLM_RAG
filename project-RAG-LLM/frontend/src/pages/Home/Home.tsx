/**
 * 首页
 */
import { Link } from 'react-router-dom';
import './Home.css';
// 导入图片资源
import reactLogo from '../../assets/react.svg';
import flaskLogo from '../../assets/flask.png';
import langchainLogo from '../../assets/LangChain.png';
import qwenLogo from '../../assets/qwen3.png';
import ragFlowImg from '../../assets/RAG_LangChain.png';
import RAGFlowImg from '../../assets/RAGFLOW_LangChain.png';
import summaryFlowImg from '../../assets/summary_LangChain.png';
import middlewareFlowImg from '../../assets/middleware_LangChain.png';
const Home = () => {
  return (
    <div className="home-container">
      <div className="home-content">
        <h1 className="home-title">以太寻光</h1>
        <p className="home-description">
          基于检索增强生成（RAG）技术的 SCUT 计算机网络学习助手，上传知识库文档，开始智能对话
        </p>
        
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">💬</div>
            <h3>SCUT 计算机网络助手</h3>
            <p>基于本地全局知识库以及用户上传知识库进行问答</p>
            <Link to="/chat" className="feature-link">开始对话 →</Link>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">📄</div>
            <h3>文档管理</h3>
            <p>上传和管理知识库文档</p>
            <Link to="/documents" className="feature-link">管理文档 →</Link>
          </div>
        </div>

        <div className="quick-start">
          <h2>快速开始</h2>
          <ol>
            <li>在"文档管理"页面上传知识库文档（支持 PDF、DOCX、TXT、MD 格式）</li>
            <li>等待文档处理完成， 可以在文档管理处看到每个chat上传的文件</li>
            <li>在"对话"页面开始提问</li>
          </ol>
        </div>
        {/* RAG 流程说明 */}
        <div className="system-architecture">
          <div className="architecture-grid">
            <div className="architecture-card">

              <img src={ragFlowImg} alt="RAG流程图" className="flow-image" />
              <p></p>
            </div>
            <div className="architecture-card">

              <img src={RAGFlowImg} alt="RAGFlow流程图" className="flow-image" />
              <p></p>
            </div>
            <div className="architecture-card">

              <img src={summaryFlowImg} alt="summary_LangChain流程图" className="flow-image" />
              <p></p>
            </div>
            <div className="architecture-card">
              <img src={middlewareFlowImg} alt="middleware_LangChain流程图" className="flow-image" />
            </div>
          </div>
        </div>
        {/* 技术栈展示 */}
        <div className="tech-stack">
          <div className="tech-logos">
            <div className="tech-item">
              <img src={reactLogo} alt="React" />
              <span>React</span>
            </div>
            <div className="tech-item">
              <img src={flaskLogo} alt="Flask" />
              <span>Flask</span>
            </div>
            <div className="tech-item">
              <img src={langchainLogo} alt="LangChain" />
              <span>LangChain</span>
            </div>
            <div className="tech-item">
              <img src={qwenLogo} alt="Qwen3" />
              <span>Qwen3</span>
            </div>
          </div>
        </div>





      </div>
    </div>
  );
};

export default Home;

