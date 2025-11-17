/**
 * 主布局组件
 */
import { Outlet, Link, useLocation } from 'react-router-dom';
import './Layout.css';
import type { NavItem } from '../../types/index.ts';

const Layout = ():  React.JSX.Element => {
  const location = useLocation();

  const navItems: NavItem[] = [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/chat', label: 'SCUT 计算机网络助手', icon: '💬' },
    { path: '/documents', label: '文档管理', icon: '📄' },
  ];

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1>以太寻光</h1>
        </div>
        <ul className="nav-list">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={location.pathname === item.path ? 'active' : ''}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <main className="main-content">
        <div className="main-content-wrapper">
          <Outlet />
        </div>
        <footer className="site-footer">
          <p className="icp-info">
            <a 
              href="https://beian.miit.gov.cn/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="icp-link"
            >
              黔ICP备2025060353号
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
};

export default Layout;