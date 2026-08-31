#!/usr/bin/env bash
# setup-project-ai.sh —— macOS 版本地 AI 运行时配置（对应 Windows 的 setup-project-ai.ps1）
# 功能：确保 Ollama 可用（优先 brew 安装）、启动服务、从 models/imports 导入 GGUF 模型、
#       创建项目内模型（student-qwen 及可选的 student-qwen-cuda 兼容配置）。
# 说明：Intel Mac 无 NVIDIA GPU，Ollama 使用 CPU 推理，CUDA 相关配置被移除。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_NAME="${1:-student-qwen:latest}"
MODEL_PATH="$PROJECT_ROOT/models/ollama"
MODEL_IMPORT_DIR="$PROJECT_ROOT/models/imports"
MODEL_FILE="$MODEL_IMPORT_DIR/Qwen2.5-7B-Instruct-Q5_K_M.gguf"
MODEL_FILE_DEFINITION="$MODEL_IMPORT_DIR/Modelfile"
CUDA_MODEL="student-qwen-cuda:latest"
CUDA_MODEL_DEFINITION="$PROJECT_ROOT/models/cuda.Modelfile"

mkdir -p "$MODEL_PATH" "$MODEL_IMPORT_DIR" "$PROJECT_ROOT/tmp"

# 1. 确保 ollama 命令可用（优先通过 brew 安装，Intel Mac 为 CPU 推理）
if ! command -v ollama >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "未找到 ollama，正在通过 brew 安装…"
    brew install ollama
  else
    echo "未找到 ollama。请先安装 Ollama（https://ollama.com/download/mac）后重试。" >&2
    exit 1
  fi
fi
OLLAMA_BIN="$(command -v ollama)"

# 2. 先启动项目内 Ollama 服务（幂等，已在运行则跳过）
"$SCRIPT_DIR/start-project-ai.sh" --quiet

# 3. 导入 GGUF 模型（仅当 models/imports 中已放置模型文件）
export OLLAMA_MODELS="$MODEL_PATH"
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

# 5. 创建与 Windows 兼容命名的模型（Intel Mac 上无 CUDA，仅为保持配置一致；定义文件缺失则跳过）
if [ -f "$CUDA_MODEL_DEFINITION" ]; then
  "$OLLAMA_BIN" create "$CUDA_MODEL" -f "$CUDA_MODEL_DEFINITION"
else
  echo "未找到 $CUDA_MODEL_DEFINITION，跳过兼容模型创建。"
fi

echo "项目内本地 AI 已就绪。模型：$CUDA_MODEL"
