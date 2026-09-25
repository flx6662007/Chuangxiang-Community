FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# 浏览器始终访问当前网站的 /api，构建产物不包含服务器密钥。
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

FROM caddy:2.11.4-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/frontend

