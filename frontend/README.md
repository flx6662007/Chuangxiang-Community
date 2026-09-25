# 创享平台前端

本目录是电脑端 Vue 3 前端工程。当前阶段仅包含工程入口、路由、请求封装、Element Plus 和基础布局，尚无赛事或账号等业务页面。

## 环境与启动

- Node.js 20.19+ 或 22.12+
- npm（随标准 Node.js 安装提供）

在 `frontend/` 目录执行：

```powershell
npm install
npm run dev
```

浏览器打开终端显示的本地地址（默认 `http://localhost:5173/`）。生产构建可执行 `npm run build`，本地预览构建结果可执行 `npm run preview`。

## 目录

```text
src/
├── api/        # Axios 实例和按功能划分的请求函数
├── layouts/    # 页面共用布局
├── router/     # 路由定义
├── styles/     # 全局基础样式
├── views/      # 路由对应的视图
├── App.vue     # 应用根组件
└── main.js     # 应用入口与插件注册
```

开发环境中，以 `/api` 开头的请求由 Vite 转发到 `http://127.0.0.1:8000`。如需修改后端地址，可复制 `.env.example` 为 `.env.local`，设置 `DEV_PROXY_TARGET`；Axios 的基础路径由 `VITE_API_BASE_URL` 控制，默认 `/api/v1`。本机配置不要提交。当前 `src/api/health.js` 只封装已有的健康检查接口，后端业务接口尚未实现，新增业务请求前须与后端确认接口契约。
