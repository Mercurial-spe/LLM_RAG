 # syntax=docker/dockerfile:1

 FROM node:20-alpine

 ENV NODE_ENV=development

 WORKDIR /app

 # 仅复制依赖清单以利用缓存
 COPY project-RAG-LLM/frontend/package*.json ./

 RUN npm ci

 # 复制其余前端代码
 COPY project-RAG-LLM/frontend ./

 EXPOSE 5173

 # 启动 Vite 开发服务器（vite.config.ts 已配置 host/port）
 CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


