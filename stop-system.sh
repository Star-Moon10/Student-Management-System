#!/usr/bin/env bash
# stop-system.sh —— macOS 版停止脚本（对应 Windows 的 stop-system.bat）
# 功能：优雅停止托管中的 uvicorn 服务、清理 PID 文件、可选停止本地 AI。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 判断给定 PID 是否为本项目的 uvicorn 服务进程
is_server_process() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o command= | grep -q 'uvicorn app.main:app'
}

if [ ! -f run/server.pid ]; then
  echo "没有托管中的服务进程。"
  exit 0
fi

PID="$(cat run/server.pid 2>/dev/null || true)"
if [ -z "$PID" ] || ! is_server_process "$PID"; then
  echo "记录的进程已不再是学生管理服务器。"
  rm -f run/server.pid
  exit 0
fi

# 优雅停止，等待退出后兜底强杀
kill -TERM "$PID" 2>/dev/null || true
for _ in $(seq 1 10); do
  if ! kill -0 "$PID" 2>/dev/null; then
    break
  fi
  sleep 0.5
done
if kill -0 "$PID" 2>/dev/null; then
  echo "服务未在限时内退出，强制停止…"
  kill -9 "$PID" 2>/dev/null || true
fi

rm -f run/server.pid

# 可选：停止项目内本地 AI
if [ -f run/ollama.pid ] && [ -x scripts/stop-project-ai.sh ]; then
  ./scripts/stop-project-ai.sh || true
fi
echo "学生管理系统服务已停止。"
