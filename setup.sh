#!/usr/bin/env bash
# setup.sh —— macOS 版首次安装脚本（对应 Windows 的 setup.bat）
# 功能：定位 Python 3.12、创建虚拟环境、安装依赖、生成 .env、初始化数据库、可选配置本地 AI。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 定位并校验一个版本 >= 3.12 的系统级 Python 解释器
# 优先级：系统 python3.12 -> 系统 python3（校验版本）-> 通过 uv 安装后定位
find_project_python() {
  local candidate=""
  # 优先级 1：系统 python3.12
  if command -v python3.12 >/dev/null 2>&1; then
    candidate="$(command -v python3.12)"
  fi
  # 优先级 2：系统 python3（需通过版本校验）
  if [ -z "$candidate" ] && command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
      candidate="$(command -v python3)"
    fi
  fi
  # 优先级 3：通过 uv 安装并定位系统级 Python 3.12
  if [ -z "$candidate" ] && command -v uv >/dev/null 2>&1; then
    echo "未找到 Python 3.12，正在通过 uv 安装…"
    uv python install 3.12 >/dev/null
    candidate="$(uv python find 3.12 --system 2>/dev/null || true)"
  fi
  if [ -z "$candidate" ]; then
    echo "未找到 Python。请先安装 Python 3.12（https://www.python.org/downloads/）后重新运行本脚本。"
    exit 1
  fi
  if ! "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    echo "需要 Python 3.12 或更高版本，当前为 $("$candidate" --version 2>&1)。"
    exit 1
  fi
  echo "$candidate"
}

BOOTSTRAP_PYTHON="$(find_project_python)"
echo "使用 Python：$BOOTSTRAP_PYTHON"

# 创建虚拟环境（已存在则跳过）
if [ ! -f .venv/bin/python ]; then
  echo "正在创建项目虚拟环境…"
  "$BOOTSTRAP_PYTHON" -m venv .venv
fi

PROJECT_PYTHON="$SCRIPT_DIR/.venv/bin/python"
# 兜底：确保 venv 内含 pip（例如由 uv 创建的 venv 默认不安装 pip）
if ! "$PROJECT_PYTHON" -m pip --version >/dev/null 2>&1; then
  echo "正在为虚拟环境安装 pip…"
  "$PROJECT_PYTHON" -m ensurepip --upgrade >/dev/null
fi
echo "正在安装项目依赖…"
"$PROJECT_PYTHON" -m pip install --upgrade pip
"$PROJECT_PYTHON" -m pip install -e .

# 首次运行生成 .env（已存在则保留现有配置，迁移时不得覆盖）
if [ ! -f .env ]; then
  echo "正在生成本地配置文件 .env…"
  JWT_SECRET_VALUE="$("$PROJECT_PYTHON" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > .env <<EOF
APP_NAME=Student Management System
ENVIRONMENT=development
DATABASE_URL=sqlite:///./data/student_management.db
JWT_SECRET=${JWT_SECRET_VALUE}
COOKIE_SECURE=false
STORAGE_PATH=storage
EXPORT_PATH=exports
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=student-qwen-cuda:latest
AI_ENABLED=true
EOF
else
  echo "保留现有 .env 配置。"
fi

# 创建运行所需目录
mkdir -p data storage exports run

# 初始化数据库
echo "正在初始化数据库…"
"$PROJECT_PYTHON" -c "from app.db import init_db; init_db()"

# 可选：项目内本地 AI 运行时配置（仅当模型文件已就位时）
AI_READY=0
if [ -f "models/ollama/manifests/registry.ollama.ai/library/student-qwen/latest" ]; then
  AI_READY=1
fi
if [ -f "models/imports/Qwen2.5-7B-Instruct-Q5_K_M.gguf" ]; then
  AI_READY=1
fi

if [ "$AI_READY" -eq 1 ]; then
  if [ -x scripts/setup-project-ai.sh ]; then
    echo "正在配置项目内本地 AI 运行时…"
    if ! ./scripts/setup-project-ai.sh; then
      echo "AI 配置未完成。系统仍可在无 AI 状态下运行。"
    fi
  else
    echo "未找到 scripts/setup-project-ai.sh，跳过 AI 配置。"
  fi
else
  echo "未检测到 AI 模型文件，系统将以 AI 降级模式启动。"
  echo "将模型放入 models/ollama 或 GGUF 放入 models/imports 后，可运行 scripts/setup-project-ai.sh。"
fi

echo ""
echo "安装完成。日常使用请运行 ./start-system.sh（除非需要修复或迁移安装，请勿重复运行本脚本）。"
