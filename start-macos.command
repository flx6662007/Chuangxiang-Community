#!/bin/bash

# Finder 双击启动；所有项目路径都从本文件位置计算。
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
SITE_URL="http://localhost:5173/"
BACKEND_URL="http://127.0.0.1:8000/api/v1/health/"
FRONTEND_PID=""
BACKEND_PID=""

# Finder 启动时的 PATH 往往比交互终端短；兼容常见的 Mac 安装位置。
export PATH="$HOME/.local/opt/node/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONIOENCODING=utf-8

cleanup() {
  trap - EXIT INT TERM
  printf '\n正在停止本次启动的服务...\n'
  if [ -n "$FRONTEND_PID" ]; then
    pkill -P "$FRONTEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ]; then
    pkill -P "$BACKEND_PID" 2>/dev/null || true
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  [ -n "$FRONTEND_PID" ] && wait "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && wait "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

fail() {
  printf '\n启动失败：%s\n' "$1" >&2
  if [ -t 0 ]; then
    printf '按回车关闭此窗口...'
    read -r _
  fi
  exit 1
}

backend_ready() {
  case "$(curl -fsS --max-time 2 "$BACKEND_URL" 2>/dev/null)" in
    *'"service":"chuangxiang-backend"'*) return 0 ;;
    *) return 1 ;;
  esac
}

wait_for_backend() {
  local attempt
  for attempt in $(seq 1 30); do
    backend_ready && return 0
    [ -n "$BACKEND_PID" ] && ! kill -0 "$BACKEND_PID" 2>/dev/null && return 1
    sleep 1
  done
  return 1
}

wait_for_frontend() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 2 "$SITE_URL" >/dev/null 2>&1 && \
       curl -fsS --max-time 2 "${SITE_URL}api/v1/health/" | grep -q 'chuangxiang-backend'; then
      return 0
    fi
    ! kill -0 "$FRONTEND_PID" 2>/dev/null && return 1
    sleep 1
  done
  return 1
}

printf '创享平台 macOS 开发启动器\n项目目录：%s\n' "$ROOT_DIR"
[ -f "$BACKEND_DIR/manage.py" ] || fail '找不到 backend/manage.py，请把启动文件放在项目根目录。'
[ -f "$FRONTEND_DIR/package.json" ] || fail '找不到 frontend/package.json，请把启动文件放在项目根目录。'
command -v curl >/dev/null 2>&1 || fail '找不到 macOS 自带的 curl。'
command -v npm >/dev/null 2>&1 || fail '找不到 npm；请先安装满足 frontend/package.json 要求的 Node.js。'
command -v node >/dev/null 2>&1 || fail '找不到 Node.js；请先安装 Node.js。'
[ -x "$BACKEND_PYTHON" ] || fail '找不到 backend/.venv/bin/python；请按 docs/backend-development.md 安装 Python 3.13 和后端依赖。'
[ -f "$BACKEND_DIR/.env" ] || fail '找不到 backend/.env；请按 docs/backend-development.md 配置本机数据库和 Django 密钥。'

printf '\n正在检查后端配置与 PostgreSQL...\n'
if ! (cd "$BACKEND_DIR" && "$BACKEND_PYTHON" manage.py check); then
  fail 'Django 配置检查未通过，请查看上方错误和 docs/backend-development.md。'
fi

if backend_check_output=$(cd "$BACKEND_DIR" && "$BACKEND_PYTHON" scripts/check_environment.py 2>&1); then
  printf '%s\n' "$backend_check_output"
else
  postgres_app=''
  [ -d '/Applications/Postgres.app' ] && postgres_app='/Applications/Postgres.app'
  [ -d "$HOME/Applications/Postgres.app" ] && postgres_app="$HOME/Applications/Postgres.app"
  [ -n "$postgres_app" ] || fail 'PostgreSQL 连接失败；请启动你本机的 PostgreSQL 17 服务并检查 backend/.env。'
  postgres_data="$HOME/Library/Application Support/Postgres/var-17"
  postgres_ctl="$postgres_app/Contents/Versions/17/bin/pg_ctl"
  if [ -x "$postgres_ctl" ] && [ -f "$postgres_data/PG_VERSION" ]; then
    printf 'PostgreSQL 尚未就绪，正在启动本机 Postgres.app 数据库...\n'
    "$postgres_ctl" -D "$postgres_data" -l "$postgres_data/startup.log" start || fail 'PostgreSQL 17 无法启动；请检查 Postgres.app。'
  else
    printf 'PostgreSQL 尚未初始化，正在打开 Postgres.app...\n'
    open -a "$postgres_app" || fail '无法打开 Postgres.app。'
  fi
  connected=0
  for attempt in $(seq 1 30); do
    if backend_check_output=$(cd "$BACKEND_DIR" && "$BACKEND_PYTHON" scripts/check_environment.py 2>&1); then
      connected=1
      printf '%s\n' "$backend_check_output"
      break
    fi
    sleep 1
  done
  if [ "$connected" -ne 1 ]; then
    printf '%s\n' "$backend_check_output" >&2
    fail 'PostgreSQL 仍无法连接；请检查服务、用户和 backend/.env。'
  fi
fi

if ! (cd "$BACKEND_DIR" && "$BACKEND_PYTHON" manage.py migrate --check); then
  fail '数据库迁移尚未应用；请按 docs/backend-development.md 完成 migrate 和目录初始化。'
fi

if ! backend_ready; then
  printf '\n正在启动后端：Django http://127.0.0.1:8000/\n'
  (cd "$BACKEND_DIR" && exec "$BACKEND_PYTHON" manage.py runserver 127.0.0.1:8000) &
  BACKEND_PID=$!
  wait_for_backend || fail '后端未能在 30 秒内就绪；请检查上方 Django 输出或 8000 端口。'
else
  printf '\n后端已在运行，继续使用现有服务。\n'
fi

if [ ! -f "$FRONTEND_DIR/node_modules/vite/bin/vite.js" ]; then
  printf '\n前端依赖未安装，正在按 package-lock.json 执行 npm ci...\n'
  (cd "$FRONTEND_DIR" && npm ci) || fail 'npm ci 失败；请检查网络和 frontend/package-lock.json。'
fi

printf '\n正在启动前端：Vite %s\n' "$SITE_URL"
(cd "$FRONTEND_DIR" && exec npm run dev -- --host localhost --strictPort) &
FRONTEND_PID=$!
wait_for_frontend || fail '前端或 API 代理未能在 30 秒内就绪；请检查上方 Vite 输出或 5173 端口。'

printf '\n启动成功！本地访问地址：%s\n' "$SITE_URL"
printf '浏览器即将打开。保持此终端窗口运行；按 Ctrl+C 停止本次启动的前后端服务。\n\n'
open "$SITE_URL" || fail '服务已启动，但无法打开默认浏览器。'

while kill -0 "$FRONTEND_PID" 2>/dev/null; do
  if [ -n "$BACKEND_PID" ] && ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    fail '后端运行过程中退出；请检查上方 Django 输出。'
  fi
  sleep 1
done
fail '前端运行过程中退出；请检查上方 Vite 输出。'
