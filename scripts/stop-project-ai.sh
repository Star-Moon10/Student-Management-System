#!/usr/bin/env bash
# stop-project-ai.sh —— macOS 版停止本地 Ollama 服务（对应 Windows 的 stop-project-ai.ps1）
# 功能：停止由 start-project-ai.sh 托管的 ollama serve 并清理 PID 文件。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_PATH="$PROJECT_ROOT/run/ollama.pid"

[ -f "$PID_PATH" ] || exit 0

PID="$(cat "$PID_PATH" 2>/dev/null || true)"
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  # 优雅停止，等待退出后兜底强杀
  kill -TERM "$PID" 2>/dev/null || true
  for _ in $(seq 1 10); do
    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
  fi
fi
rm -f "$PID_PATH"
