/**
 * 主应用组件
 */
import { RouterProvider } from 'react-router-dom';
import router from './router';
import './App.css';

function App():  React.JSX.Element {
  return <RouterProvider router={router} />;
}

export default App;