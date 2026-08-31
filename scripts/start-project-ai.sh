#!/usr/bin/env bash
# start-project-ai.sh —— macOS 版启动本地 Ollama 服务（对应 Windows 的 start-project-ai.ps1）
# 功能：检查 Ollama 可用性、端口去重、以项目模型目录启动 ollama serve 并记录 PID。
# 说明：Intel Mac 无 NVIDIA GPU，故不设置 CUDA_VISIBLE_DEVICES，Ollama 使用 CPU 推理。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_PATH="$PROJECT_ROOT/models/ollama"
PID_PATH="$PROJECT_ROOT/run/ollama.pid"
QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

# Ollama 未安装时安静退出（由 start-system.sh 在 --quiet 模式下调用）
if ! command -v ollama >/dev/null 2>&1; then
  if [ "$QUIET" = "1" ]; then
    exit 0
  fi
  echo "尚未安装 Ollama。请先运行 scripts/setup-project-ai.sh。" >&2
  exit 1
fi
OLLAMA_BIN="$(command -v ollama)"

mkdir -p "$MODEL_PATH" "$PROJECT_ROOT/run"

# 端口去重：已有 Ollama 服务在 11434 运行则直接复用
if curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  exit 0
fi

# 以项目模型目录启动服务并记录 PID
export OLLAMA_MODELS="$MODEL_PATH"
export OLLAMA_CONTEXT_LENGTH=4096
# Intel Mac 上启用 flash attention 与量化 KV cache，降低内存占用并提升 CPU 推理速度
if [ "$(uname -m)" = "x86_64" ]; then
  export OLLAMA_FLASH_ATTENTION=1
  export OLLAMA_KV_CACHE_TYPE=q8_0
fi
nohup "$OLLAMA_BIN" serve > "$PROJECT_ROOT/run/ollama.log" 2>&1 &
echo $! > "$PID_PATH"

# 等待服务就绪（最多约 10 秒）
for _ in $(seq 1 20); do
  if curl -sf --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    [ "$QUIET" = "1" ] || echo "项目内 Ollama 服务已就绪：http://127.0.0.1:11434"
    exit 0
  fi
  sleep 0.5
done

rm -f "$PID_PATH"
echo "Ollama 启动失败，请查看 run/ollama.log。" >&2
exit 1
