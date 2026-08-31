#!/usr/bin/env bash
# setup-project-ai.sh —— macOS 版本地 AI 运行时配置（对应 Windows 的 setup-project-ai.ps1）
# 功能：确保 Ollama 可用、启动服务，并从 models/imports 导入可选 GGUF 模型。
# macOS 与 Linux 均支持；Apple Silicon 使用 Metal，Intel 和普通 Linux 主机按 Ollama 可用能力推理。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_NAME="${1:-student-qwen:latest}"
MODEL_PATH="$PROJECT_ROOT/models/ollama"
MODEL_IMPORT_DIR="$PROJECT_ROOT/models/imports"
MODEL_FILE="$MODEL_IMPORT_DIR/Qwen2.5-7B-Instruct-Q5_K_M.gguf"
MODEL_FILE_DEFINITION="$MODEL_IMPORT_DIR/Modelfile"

mkdir -p "$MODEL_PATH" "$MODEL_IMPORT_DIR" "$PROJECT_ROOT/tmp"

# 1. 确保 ollama 命令可用。仅 macOS 在检测到 Homebrew 时提供安装协助。
if ! command -v ollama >/dev/null 2>&1; then
  if [ "$(uname -s)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    echo "未找到 ollama，正在通过 brew 安装…"
    brew install ollama
  else
    echo "未找到 ollama。请先安装 Ollama（https://ollama.com/download/）后重试。" >&2
    exit 1
  fi
fi
OLLAMA_BIN="$(command -v ollama)"

# 2. 启动项目内 Ollama 服务（幂等，已在运行则跳过）。
export OLLAMA_MODELS="$MODEL_PATH"
"$SCRIPT_DIR/start-project-ai.sh" --quiet

# 3. 导入 GGUF 模型（仅当 models/imports 中已放置模型文件）
if [ -f "$MODEL_FILE" ]; then
  if [ ! -f "$MODEL_FILE_DEFINITION" ]; then
    echo "未找到模型定义文件：$MODEL_FILE_DEFINITION" >&2
    exit 1
  fi
  (cd "$MODEL_IMPORT_DIR" && "$OLLAMA_BIN" create "$MODEL_NAME" -f "$MODEL_FILE_DEFINITION")
  rm -f "$MODEL_FILE"
fi

# 4. 校验基础模型已加载
if ! curl -sf --max-time 15 http://127.0.0.1:11434/api/tags | grep -q "\"$MODEL_NAME\""; then
  echo "模型 $MODEL_NAME 未就绪。请将 GGUF 文件放入 $MODEL_IMPORT_DIR 后重试。" >&2
  exit 1
fi

echo "项目内本地 AI 已就绪。模型：$MODEL_NAME"
