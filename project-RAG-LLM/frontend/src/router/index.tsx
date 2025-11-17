/**
 * 路由配置
 */
import { createBrowserRouter } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import Home from '../pages/Home/Home';
import Chat from '../pages/Chat/Chat';
import Documents from '../pages/Documents/Documents';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <Home />,
      },
      {
        path: 'chat',
        element: <Chat />,
      },
      {
        path: 'documents',
        element: <Documents />,
      },
    ],
  },
]);

export default router;

