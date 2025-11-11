# RAG-LLM Frontend

React + Vite 前端应用

## 环境变量配置

### 开发环境

在项目根目录创建 `.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:5000/api
```

### 生产环境部署

#### 方式 1：前后端在同一台服务器（推荐）

在服务器上创建 `.env.production` 文件：

```env
# 使用相对路径，代码会自动转换为：http://当前域名:5000/api
VITE_API_BASE_URL=/api
```

或者不设置环境变量，代码会自动使用当前页面的域名 + 端口 5000。

**注意**：即使使用相对路径 `/api`，代码也会自动添加端口 5000，所以最终会请求 `http://112.74.163.199:5000/api`。

#### 方式 2：前后端在不同服务器

在服务器上创建 `.env.production` 文件：

```env
# 使用完整的服务器地址
VITE_API_BASE_URL=http://your-server-ip:5000/api
# 或使用域名
VITE_API_BASE_URL=https://api.yourdomain.com/api
```

### 重要说明

⚠️ **为什么不能使用 localhost？**

- 前端代码运行在**用户的浏览器**中
- 浏览器中的 `localhost` 指向**用户的本地机器**，不是服务器
- 如果前端代码硬编码 `localhost:5000`，用户访问时会尝试连接自己本地的 5000 端口
- 解决方案：使用环境变量或自动检测当前域名

### 构建和运行

```bash
# 安装依赖
npm install

# 开发环境
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview
```

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
