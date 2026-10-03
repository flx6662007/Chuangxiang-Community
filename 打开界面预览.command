#!/bin/bash
# 双击打开当前源码的 UI 预览，无需数据库；业务数据为前端预览占位。
set -u
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PREVIEW_URL='http://127.0.0.1:5174/?ui_preview=1'
PREVIEW_ORIGIN='http://127.0.0.1:5174'
PREVIEW_PID=''
export PATH="$HOME/.local/opt/node/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
fail() {
  printf '\n启动失败：%s\n' "$1" >&2
  if [ -t 0 ]; then read -r -p '按回车关闭窗口…' _; fi
  exit 1
}
cleanup() {
  if [ -n "$PREVIEW_PID" ]; then
    kill "$PREVIEW_PID" 2>/dev/null || true
    wait "$PREVIEW_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
printf '创享 · 当前源码界面预览\n目录：%s\n' "$PROJECT_DIR"
cd "$PROJECT_DIR/frontend" || fail '找不到 frontend 文件夹。'
NODE_BIN="$(command -v node || true)"
if [ -z "$NODE_BIN" ]; then
  NODE_BIN="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
fi
[ -x "$NODE_BIN" ] || fail '未找到 Node.js，请安装 Node.js 22.12 或更新版本。'
[ -f node_modules/vite/bin/vite.js ] || fail '前端依赖未安装，请先在 frontend 中执行 npm ci。'
if lsof -nP -iTCP:5174 -sTCP:LISTEN >/dev/null 2>&1; then
  # Only reuse a Vite process whose working directory is this checkout.
  MATCHED=0
  for pid in $(lsof -t -iTCP:5174 -sTCP:LISTEN); do
    if lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep -Fxq "n$(pwd -P)"; then MATCHED=1; fi
  done
  [ "$MATCHED" = 1 ] || fail '5174 端口被其他项目占用，请先关闭该服务。'
  curl -fsS --max-time 3 "$PREVIEW_ORIGIN/@vite/client" >/dev/null || fail '已有服务未响应，请关闭原预览窗口后重试。'
  open "$PREVIEW_URL" || fail '无法打开浏览器。'
  printf '\n已打开正在运行的本项目预览。\n'
  exit 0
fi
"$NODE_BIN" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort &
PREVIEW_PID=$!
READY=0
for ((attempt=0; attempt<40; attempt++)); do
  kill -0 "$PREVIEW_PID" 2>/dev/null || fail '预览服务启动失败，请查看上方输出。'
  if curl -fsS --max-time 1 "$PREVIEW_ORIGIN/@vite/client" >/dev/null 2>&1; then READY=1; break; fi
  sleep .25
done
[ "$READY" = 1 ] || fail '预览服务未能及时启动。'
open "$PREVIEW_URL" || fail '浏览器未能打开。'
printf '\n已打开：%s\n这是当前源码的界面预览；完整业务功能请使用 start-macos.command。\n请保持此终端窗口开启，关闭窗口或按 Ctrl+C 会停止预览。\n' "$PREVIEW_URL"
wait "$PREVIEW_PID"
