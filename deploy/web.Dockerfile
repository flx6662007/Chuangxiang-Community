FROM node:24-bookworm-slim AS build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# 前台与内部信息库共用人工整理的公开内容，不复制数据库或配置文件。
COPY backend/information_library/data/ /app/backend/information_library/data/
# 浏览器始终访问当前网站的 /api，构建产物不包含服务器密钥。
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

FROM caddy:2.11.4-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/frontend/dist /srv/frontend

