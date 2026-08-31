#!/usr/bin/env bash
# update-system.sh —— macOS/Linux 版受控更新执行器（对应 Windows 的 update-system.ps1）
# 功能：获取并校验更新包 → 备份代码与数据库 → 替换程序文件 → 升级依赖与数据库结构
#       → 重启并健康检查；任一步失败自动回滚到更新前版本。
# 事务文件（run/update-transaction.json）的 schema 与 scripts/recover_interrupted_update.py 保持兼容。
set -uo pipefail

# ---------- 参数解析（与 PowerShell 版调用约定一致：-JobPath <job.json>） ----------
JOB_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -JobPath) JOB_PATH="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done
if [ -z "$JOB_PATH" ]; then
  echo "缺少 -JobPath 参数（应指向更新任务的 job.json）"
  exit 1
fi

# ---------- 全局状态 ----------
PROJECT_ROOT=""
PROJECT_PYTHON=""
STATUS_PATH=""
JOB_DIRECTORY=""
JOB_ID=""
SOURCE=""
OFFLINE_PACKAGE=""
OFFLINE_CHECKSUM=""
RELEASE_PACKAGE_URL=""
RELEASE_CHECKSUM_URL=""
RELEASE_PACKAGE_BROWSER_URL=""
RELEASE_CHECKSUM_BROWSER_URL=""
STAGE_DIRECTORY=""
PACKAGE_PATH=""
ROLLBACK_DIRECTORY=""
DATABASE_PATH=""
DATABASE_ROLLBACK_PATH=""
TRANSACTION_PATH=""
RECOVERY_SOURCE=""
RECOVERY_RUNTIME=""
MANIFEST_VERSION=""
TRANSACTION_SET=0

# ---------- 引导阶段：先用系统 Python 定位项目虚拟环境 ----------
# 说明：解析 job.json 需要 Python，而项目 Python 位于 project_root/.venv 下，
#       必须先读取 project_root 才能确定解释器路径，因此这里使用系统 python3 做引导。
SYSTEM_PYTHON="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
if [ -z "$SYSTEM_PYTHON" ]; then
  echo "未找到 python3，无法解析更新任务" >&2
  exit 1
fi
PROJECT_ROOT="$("$SYSTEM_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("project_root",""))' "$JOB_PATH" 2>/dev/null || true)"
if [ -z "$PROJECT_ROOT" ]; then
  echo "job.json 缺少 project_root 字段" >&2
  exit 1
fi
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"

ALLOWED_DIRECTORIES="app scripts docs"
ALLOWED_FILES=".env.example Dockerfile LICENSE README.md README.en.md VERSION docker-compose.yml pyproject.toml requirements.lock"

# ---------- 从 job.json 读取指定字段 ----------
job_value() {
  "$PROJECT_PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2], ""))' "$JOB_PATH" "$1"
}

# ---------- 从 job.json 的 release 嵌套结构读取字段 ----------
release_value() {
  "$PROJECT_PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])).get("release", {}); print(d.get(sys.argv[2], {}).get(sys.argv[3], ""))' "$JOB_PATH" "$1" "$2"
}

# ---------- 读取更新包 manifest.json 字段 ----------
read_manifest() {
  "$PROJECT_PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2], ""))' "$STAGE_DIRECTORY/manifest.json" "$1"
}

# ---------- 输出 manifest.files 的 "相对路径|sha256" 行 ----------
list_manifest_files() {
  "$PROJECT_PYTHON" -c '
import json, sys
manifest = json.load(open(sys.argv[1]))
for rel, digest in manifest.get("files", {}).items():
    print(f"{rel}|{digest}")
' "$STAGE_DIRECTORY/manifest.json"
}

# ---------- 原子写入状态文件 run/update-status.json ----------
write_status() {
  "$PROJECT_PYTHON" -c '
import json, os, sys
from datetime import datetime, timezone
path, state, message, progress, error = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
payload = {
    "state": state,
    "message": message,
    "progress": int(progress),
    "error": error,
    "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
os.replace(tmp, path)
' "$STATUS_PATH" "$1" "$2" "$3" "${4:-}"
}

# ---------- 原子写入事务文件 run/update-transaction.json ----------
write_transaction() {
  "$PROJECT_PYTHON" -c '
import json, os, sys
from datetime import datetime, timezone
path, state = sys.argv[1], sys.argv[2]
payload = {
    "format": 1,
    "job_id": sys.argv[3],
    "state": state,
    "project_root": sys.argv[4],
    "rollback_directory": sys.argv[5],
    "database_path": sys.argv[6],
    "database_rollback_path": sys.argv[7],
    "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
os.replace(tmp, path)
' "$TRANSACTION_PATH" "$1" "$JOB_ID" "$PROJECT_ROOT" "$ROLLBACK_DIRECTORY" "$DATABASE_PATH" "$DATABASE_ROLLBACK_PATH"
}

# ---------- 删除事务文件 ----------
remove_transaction() {
  [ -f "$TRANSACTION_PATH" ] && rm -f "$TRANSACTION_PATH"
  true
}

# ---------- 计算文件 SHA-256 ----------
sha256_file() {
  "$PROJECT_PYTHON" -c '
import hashlib, sys
digest = hashlib.sha256()
with open(sys.argv[1], "rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
' "$1"
}

# ---------- 安全解压更新包（不依赖 unzip，并拒绝 zip-slip 路径） ----------
extract_package() {
  "$PROJECT_PYTHON" -c '
import sys
import zipfile
from pathlib import PurePosixPath
package, destination = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(package) as archive:
    for item in archive.infolist():
        path = PurePosixPath(item.filename)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe archive member: {item.filename}")
    archive.extractall(destination)
' "$PACKAGE_PATH" "$STAGE_DIRECTORY"
}

# ---------- 校验路径位于项目根目录内（防止更新包路径逃逸） ----------
assert_project_child() {
  "$PROJECT_PYTHON" -c '
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
candidate = Path(sys.argv[2]).resolve()
try:
    candidate.relative_to(root)
except ValueError:
    print("更新路径不在项目目录内：" + str(candidate), file=sys.stderr)
    sys.exit(1)
print(candidate)
' "$PROJECT_ROOT" "$1"
}

# ---------- 停止托管中的服务（复用 stop-system.sh） ----------
stop_server() {
  if [ -f "$PROJECT_ROOT/run/server.pid" ]; then
    "$PROJECT_ROOT/stop-system.sh" >/dev/null 2>&1 || true
  fi
}

# ---------- 重启服务（复用 start-system.sh，跳过恢复检查且不打开浏览器） ----------
start_server() {
  SMS_UPDATE_RESTART=1 SMS_NO_BROWSER=1 "$PROJECT_ROOT/start-system.sh"
}

# ---------- 健康检查：等待 /health 返回 {"status":"ok"}（最长 60 秒） ----------
wait_health() {
  local i body
  for i in $(seq 1 60); do
    body="$(curl -s --max-time 3 "http://127.0.0.1:8100/health" 2>/dev/null || true)"
    if echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# ---------- 备份白名单运行时目录与文件到目标目录 ----------
copy_runtime_to() {
  local dest="$1" dir file
  mkdir -p "$dest"
  for dir in $ALLOWED_DIRECTORIES; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
      cp -R "$PROJECT_ROOT/$dir" "$dest/"
    fi
  done
  for file in $ALLOWED_FILES; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
      cp "$PROJECT_ROOT/$file" "$dest/"
    fi
  done
}

# ---------- 用指定源码目录替换白名单运行时（用于应用更新或回滚） ----------
replace_runtime() {
  local source_root="$1" dir file target
  for dir in $ALLOWED_DIRECTORIES; do
    target="$PROJECT_ROOT/$dir"
    rm -rf "$target"
    if [ -d "$source_root/$dir" ]; then
      cp -R "$source_root/$dir" "$target"
    fi
  done
  for file in $ALLOWED_FILES; do
    if [ -f "$source_root/$file" ]; then
      cp "$source_root/$file" "$PROJECT_ROOT/$file"
    fi
  done
}

# ---------- 获取并校验更新包 ----------
acquire_package() {
  write_status "downloading" "正在获取更新包并校验 SHA-256" 10
  mkdir -p "$JOB_DIRECTORY"
  local token="${SMS_UPDATE_GITHUB_TOKEN:-}" expected=""
  if [ "$SOURCE" = "offline" ]; then
    cp "$OFFLINE_PACKAGE" "$PACKAGE_PATH"
    expected="$OFFLINE_CHECKSUM"
  else
    local package_url checksum_url
    if [ -n "$token" ]; then
      package_url="$RELEASE_PACKAGE_URL"
      checksum_url="$RELEASE_CHECKSUM_URL"
    else
      package_url="$RELEASE_PACKAGE_BROWSER_URL"
      checksum_url="$RELEASE_CHECKSUM_BROWSER_URL"
    fi
    if [ -z "$package_url" ] || [ -z "$checksum_url" ]; then
      echo "更新任务缺少下载地址" >&2
      return 1
    fi
    if [ -n "$token" ]; then
      curl -sS -L -H "Authorization: Bearer $token" -H "Accept: application/octet-stream" -o "$PACKAGE_PATH" "$package_url" || return 1
      curl -sS -L -H "Authorization: Bearer $token" -H "Accept: application/octet-stream" -o "$PACKAGE_PATH.sha256" "$checksum_url" || return 1
    else
      curl -sS -L -o "$PACKAGE_PATH" "$package_url" || return 1
      curl -sS -L -o "$PACKAGE_PATH.sha256" "$checksum_url" || return 1
    fi
    expected="$(grep -oE '[a-fA-F0-9]{64}' "$PACKAGE_PATH.sha256" 2>/dev/null | tr 'A-F' 'a-f' | head -1)"
  fi
  if [ -z "$expected" ] || [ "$(sha256_file "$PACKAGE_PATH")" != "$expected" ]; then
    echo "更新包 SHA-256 校验失败，已拒绝安装" >&2
    return 1
  fi
  echo "更新包 SHA-256 校验通过"
}

# ---------- 解压并全面校验更新包 ----------
validate_package() {
  write_status "validating" "正在验证更新包清单" 25
  rm -rf "$STAGE_DIRECTORY"
  mkdir -p "$STAGE_DIRECTORY"
  extract_package || return 1
  local manifest_path="$STAGE_DIRECTORY/manifest.json" format rel_hash rel hash candidate
  if [ ! -f "$manifest_path" ]; then
    echo "更新包缺少 manifest.json" >&2
    return 1
  fi
  MANIFEST_VERSION="$(read_manifest version)"
  format="$(read_manifest format)"
  if [ "$format" != "1" ] || [ -z "$MANIFEST_VERSION" ]; then
    echo "更新包 manifest 格式无效" >&2
    return 1
  fi
  # 逐文件哈希校验（同时阻止 zip-slip 路径逃逸）
  while IFS= read -r rel_hash; do
    rel="${rel_hash%%|*}"
    hash="${rel_hash#*|}"
    candidate="$(assert_project_child "$STAGE_DIRECTORY/$rel")" || return 1
    if [ ! -f "$candidate" ]; then
      echo "更新包文件缺失：$rel" >&2
      return 1
    fi
    if [ "$(sha256_file "$candidate")" != "$hash" ]; then
      echo "更新包文件校验失败：$rel" >&2
      return 1
    fi
  done < <(list_manifest_files)
  # 顶层路径白名单
  local item name
  for item in "$STAGE_DIRECTORY"/*; do
    name="$(basename "$item")"
    case " $ALLOWED_DIRECTORIES $ALLOWED_FILES manifest.json " in
      *" $name "*) ;;
      *)
        echo "更新包包含未允许的路径：$name" >&2
        return 1
        ;;
    esac
  done
  echo "更新包清单校验通过（v${MANIFEST_VERSION}）"
}

# ---------- 主流程 ----------
main() {
  if ! acquire_package; then return 1; fi
  if ! validate_package; then return 1; fi

  # 备份代码与数据库，写入事务
  write_status "backing_up" "正在保存更新前代码和数据库副本" 40
  mkdir -p "$ROLLBACK_DIRECTORY"
  copy_runtime_to "$ROLLBACK_DIRECTORY"
  if [ -f "$RECOVERY_SOURCE" ]; then
    cp "$RECOVERY_SOURCE" "$RECOVERY_RUNTIME"
  fi
  write_transaction "prepared"
  TRANSACTION_SET=1

  # 停服并替换程序文件
  write_status "applying" "正在停止服务并替换程序文件" 55
  write_transaction "applying"
  stop_server
  if [ -f "$DATABASE_PATH" ]; then
    cp "$DATABASE_PATH" "$DATABASE_ROLLBACK_PATH"
  fi
  replace_runtime "$STAGE_DIRECTORY"

  # 升级依赖与数据库结构
  write_status "installing" "正在更新依赖并升级数据库结构" 70
  write_transaction "installing"
  if [ ! -f "$PROJECT_PYTHON" ]; then
    echo "未找到项目虚拟环境，无法安装依赖" >&2
    return 1
  fi
  "$PROJECT_PYTHON" -m pip install --disable-pip-version-check -r "$PROJECT_ROOT/requirements.lock" || { echo "Python 依赖更新失败" >&2; return 1; }
  "$PROJECT_PYTHON" -m pip install --disable-pip-version-check --no-deps -e "$PROJECT_ROOT" || { echo "项目本体安装失败" >&2; return 1; }
  "$PROJECT_PYTHON" -c "from app.db import init_db; init_db()" || { echo "数据库升级失败" >&2; return 1; }

  # 重启并健康检查
  write_status "restarting" "正在重新启动服务并等待健康检查" 88
  write_transaction "restarting"
  start_server
  if ! wait_health; then
    echo "更新后的服务未能在 60 秒内通过健康检查" >&2
    return 1
  fi

  remove_transaction
  TRANSACTION_SET=0
  write_status "completed" "已更新至 v$MANIFEST_VERSION" 100
  echo "系统更新完成：v$MANIFEST_VERSION"
  return 0
}

# ---------- 回滚流程 ----------
rollback() {
  local failure="${1:-更新失败}"
  echo "触发回滚：$failure" >&2
  write_status "rolling_back" "更新失败，正在恢复上一版本" 92 "$failure"
  # 若备份尚未完成（如下载/校验阶段失败），未产生任何代码变更，无需恢复服务
  if [ "$TRANSACTION_SET" != "1" ] || [ ! -d "$ROLLBACK_DIRECTORY" ]; then
    write_status "failed" "更新失败，未产生代码变更" 100 "$failure"
    return 1
  fi
  write_transaction "rolling_back"
  stop_server
  replace_runtime "$ROLLBACK_DIRECTORY"
  if [ -f "$DATABASE_ROLLBACK_PATH" ]; then
    cp "$DATABASE_ROLLBACK_PATH" "$DATABASE_PATH"
  fi
  if [ -f "$PROJECT_PYTHON" ]; then
    "$PROJECT_PYTHON" -m pip install --disable-pip-version-check --no-deps -e "$PROJECT_ROOT" >/dev/null 2>&1 || true
  fi
  start_server || true
  if wait_health; then
    remove_transaction
    TRANSACTION_SET=0
    write_status "rolled_back" "更新失败，已自动恢复上一版本" 100 "$failure"
    echo "已回滚并恢复服务"
    return 0
  fi
  write_status "failed" "更新失败，自动回滚后服务未恢复" 100 "$failure"
  return 1
}

# ---------- 读取 job 关键字段并初始化路径 ----------
STATUS_PATH="$(job_value status_path)"
JOB_DIRECTORY="$(cd "$(dirname "$JOB_PATH")" && pwd)"
JOB_ID="$(job_value job_id)"
SOURCE="$(job_value source)"
OFFLINE_PACKAGE="$(job_value offline_package)"
OFFLINE_CHECKSUM="$(job_value offline_checksum)"

STAGE_DIRECTORY="$JOB_DIRECTORY/stage"
PACKAGE_PATH="$JOB_DIRECTORY/$(job_value package_name)"
ROLLBACK_DIRECTORY="$JOB_DIRECTORY/rollback"
DATABASE_PATH="$PROJECT_ROOT/data/student_management.db"
DATABASE_ROLLBACK_PATH="$ROLLBACK_DIRECTORY/student_management.db"
TRANSACTION_PATH="$PROJECT_ROOT/run/update-transaction.json"
RECOVERY_SOURCE="$PROJECT_ROOT/scripts/recover-interrupted-update.py"
RECOVERY_RUNTIME="$PROJECT_ROOT/run/update-recovery.py"

# 读取 release 资产地址（GitHub 更新源）
if [ "$SOURCE" = "github_release" ]; then
  RELEASE_PACKAGE_URL="$(release_value package url)"
  RELEASE_CHECKSUM_URL="$(release_value checksum url)"
  RELEASE_PACKAGE_BROWSER_URL="$(release_value package browser_url)"
  RELEASE_CHECKSUM_BROWSER_URL="$(release_value checksum browser_url)"
fi

# 前置校验
if [ -z "$PROJECT_ROOT" ] || [ -z "$JOB_PATH" ]; then
  echo "job.json 缺少必要字段（project_root / job_id）" >&2
  exit 1
fi
if [ ! -f "$PROJECT_PYTHON" ]; then
  echo "未找到项目虚拟环境（.venv/bin/python），无法执行更新" >&2
  exit 1
fi

# 执行主流程，失败则回滚
if main; then
  exit 0
else
  rollback
  exit $?
fi
