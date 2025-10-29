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
    { path: '/chat', label: '对话', icon: '💬' },
    { path: '/documents', label: '文档管理', icon: '📄' },
    { path: '/settings', label: '设置', icon: '⚙️' },
  ];

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1>RAG-LLM</h1>
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
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;