#!/usr/bin/env bash
# start-system.sh —— macOS 版启动脚本（对应 Windows 的 start-system.bat）
# 功能：端口/进程去重、中断更新恢复、可选启动本地 AI、后台启动 uvicorn、健康等待并打开浏览器。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PROJECT_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# 判断端口 8100 是否已被监听，不依赖 lsof。
is_server_listening() {
  "$PROJECT_PYTHON" -c '
import socket
socket.setdefaulttimeout(0.5)
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    raise SystemExit(0 if client.connect_ex(("127.0.0.1", 8100)) == 0 else 1)
finally:
    client.close()
' >/dev/null 2>&1
}

open_browser() {
  case "$(uname -s)" in
    Darwin) open "http://127.0.0.1:8100" ;;
    Linux) command -v xdg-open >/dev/null 2>&1 && xdg-open "http://127.0.0.1:8100" >/dev/null 2>&1 || true ;;
  esac
}

# 判断给定 PID 是否为本项目的 uvicorn 服务进程
is_server_process() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o command= | grep -q 'uvicorn app.main:app'
}

# 1. 通过 PID 文件去重（陈旧 PID 会被清理后继续）
if [ -f run/server.pid ]; then
  PID="$(cat run/server.pid 2>/dev/null || true)"
  if [ -n "$PID" ] && is_server_process "$PID"; then
    echo "学生管理系统已在运行。"
    [ "${SMS_NO_BROWSER:-0}" = "1" ] || open_browser
    exit 0
  fi
  rm -f run/server.pid
fi

# 2. 端口占用检查（防止与其他应用冲突）
if is_server_listening; then
  echo "端口 8100 已被其他程序占用。"
  exit 1
fi

# 3. 项目虚拟环境校验
if [ ! -x "$PROJECT_PYTHON" ]; then
  echo "未找到项目虚拟环境，请先运行 ./setup.sh。"
  exit 1
fi

# 4. 中断更新恢复（更新进程被强制结束后自动回滚到更新前版本）
if [ "${SMS_UPDATE_RESTART:-0}" != "1" ]; then
  mkdir -p run
  if [ ! -f run/update-recovery.py ] && [ -f scripts/recover-interrupted-update.py ]; then
    cp scripts/recover-interrupted-update.py run/update-recovery.py
  fi
  if [ -f run/update-recovery.py ]; then
    if ! "$PROJECT_PYTHON" run/update-recovery.py --project-root "$PWD"; then
      echo "检测到未完成的更新，但无法自动恢复。"
      echo "请保持项目文件不变，并从系统设置中的最近备份恢复。"
      exit 1
    fi
  fi
fi

# 5. 依赖完整性检查
if ! "$PROJECT_PYTHON" -c "import fastapi, uvicorn, sqlalchemy, openpyxl, docx" >/dev/null 2>&1; then
  echo "项目依赖缺失，请先运行 ./setup.sh。"
  exit 1
fi

# 6. 可选：启动本地 AI 运行时（macOS 使用系统级 Ollama；未安装或已在运行则由脚本静默处理）
if [ -x scripts/start-project-ai.sh ]; then
  ./scripts/start-project-ai.sh --quiet || true
fi

# 7. 后台启动服务并记录 PID
mkdir -p run
nohup "$PROJECT_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8100 \
  --log-config app/uvicorn_logging.json > run/server.log 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > run/server.pid

# 8. 等待服务就绪（最多约 10 秒）
for _ in $(seq 1 20); do
  if is_server_listening; then
    break
  fi
  sleep 0.5
done
if ! is_server_listening; then
  echo "服务启动失败，请查看 run/server.log 中的错误信息。"
  exit 1
fi

# 9. 打开浏览器（更新重启场景下由更新器控制跳过）
if [ "${SMS_NO_BROWSER:-0}" != "1" ]; then
  open_browser
fi
echo "服务已启动：http://127.0.0.1:8100"
