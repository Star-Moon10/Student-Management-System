# Student Management System

[![Release](https://img.shields.io/github/v/release/Star-Moon10/Student-Management-System?display_name=tag&label=Release)](https://github.com/Star-Moon10/Student-Management-System/releases)
[![Validation](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml/badge.svg)](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-Restricted%20Use-b42318)](LICENSE)

面向学校档案管理场景的本地部署学生信息管理系统。系统围绕学生主档案、原始资料、相关信息审核、数据导出、审计回溯和只读 AI 数据助手构建，适合由学校教师、普通管理员和超级管理员在受控环境中协作使用。

> **授权声明**：本仓库公开源码仅用于评估、审阅、安全检查和经授权的开发。**未经版权人书面许可，任何个人或组织不得使用、部署、复制、修改、分发或以其他方式利用本系统及其衍生成果。**详见 [LICENSE](LICENSE)。

## 目录

- [核心能力](#核心能力)
- [角色与数据边界](#角色与数据边界)
- [快速开始](#快速开始)
- [在线更新](#在线更新)
- [安全与运维](#安全与运维)
- [开发与发布](#开发与发布)
- [项目文档](#项目文档)
- [许可与免责声明](#许可与免责声明)

## 核心能力

| 模块 | 能力 |
| --- | --- |
| 学生档案 | 服务端分页、级联筛选、批量导出、字段来源、版本历史与中国标准时间线。 |
| 数据导入 | Excel 字段映射、预检、样本预览、冲突对比、错误行重试与批次撤回。 |
| 相关资料 | Excel 原始行卡片、Word 本地 AI 识别、人工匹配与批量审核。 |
| 权限管理 | 超级管理员、管理员、教师三级权限，以及学校、学院、专业、班级数据范围。 |
| 审计与恢复 | 操作审计、可撤回变更、自动备份、恢复演练、原始资料库与回收站。 |
| AI 数据助手 | 自然语言查询、统计和受控导出；AI 仅读取授权范围内的数据，不能写入数据库。 |
| 在线更新 | GitHub Release 校验、更新前备份、独立更新器、失败回滚与离线更新包。 |

## 角色与数据边界

| 角色 | 主要职责 | 可见范围 |
| --- | --- | --- |
| 教师 | 查询授权学生、导出、导入并审核本人提交的相关资料。 | 仅账号数据范围内的学生。 |
| 管理员 | 管理教师账号和数据范围，处理教师层面的审计、导入和日常运维。 | 教师层级及其授权数据。 |
| 超级管理员 | 管理全部账号、系统控制、备份恢复、高危设置、更新来源与全量审计。 | 全部系统数据与记录。 |

数据范围由学校、学院、专业和班级规则组成。教师和管理员在访问学生详情、来源文件、时间线、导出和 AI 查询时，都会自动受同一范围约束。

## 快速开始

### Windows 本地部署

适用于学校办公室电脑或局域网服务器的常规部署。

1. 将完整项目目录复制到目标电脑；迁移已有系统时必须同时保留 `.env`、`data`、`storage`、`backups`、`models` 和 `tools`。
2. 首次运行 `setup.bat`。它会创建虚拟环境、安装依赖并保留现有账号和数据库。
3. 日常运行 `start-system.bat`，浏览器将打开 `http://127.0.0.1:8100`。
4. 需要停止服务时运行 `stop-system.bat`。

`start-system.bat` 默认只绑定本机地址。需要由其他电脑访问时，请在反向代理后提供 HTTPS，而不是直接暴露数据库或本地模型服务。

### Docker Compose

适用于已有 Docker 运维能力的环境。

```powershell
Copy-Item .env.example .env
# 编辑 .env：至少替换 JWT_SECRET，并确认数据库配置
docker compose up --build -d
docker compose exec app python -m app.seed_admin --username admin
```

默认访问地址为 `http://localhost:8100`。生产环境必须配置 `ENVIRONMENT=production`、`COOKIE_SECURE=true` 和 HTTPS 反向代理。

### 本地 AI

本项目支持项目内隔离的 Ollama 运行时。迁移已有模型时保留 `models` 与 `tools`；新环境可在模型文件到位后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-project-ai.ps1
```

AI 不可用时，学生档案、导入、审核、导出和审计功能仍可使用；Word 相关资料会进入人工处理流程。

## 在线更新

管理员和超级管理员每次登录后会自动检查受控 GitHub Release。发现新版本时，系统仅显示“查看并安装”选项，不会自动下载、替换文件或重启服务。

安装更新时需要：

1. 管理员主动点击安装。
2. 输入任一超级管理员账号和密码。
3. 输入确认口令 `确认更新系统`。

更新器会下载 ZIP 与 SHA-256 校验文件、验证 `manifest.json` 与每个文件哈希、创建更新前数据库备份、替换代码白名单、安装依赖并执行健康检查。失败时会自动尝试回滚代码与数据库副本；如果更新期间断电、崩溃或更新进程被强制结束，下一次运行 `start-system.bat` 会检测未完成事务并在启动服务前自动恢复更新前版本。

更新过程不会覆盖或上传 `.env`、账号、`data`、`storage`、`exports`、`backups`、`models`、`tools`、`resource`、`run` 或 `.venv`。`start-system.bat`、`stop-system.bat` 和 `setup.bat` 也作为稳定引导层保留在本机，不会被在线更新包替换。管理员也可以在系统设置使用离线更新包。

## 安全与运维

- 密码使用 Argon2id 哈希；登录失败会限流并临时锁定账号。
- 会话使用 HttpOnly Cookie、JWT 与 CSRF 校验；无操作五分钟后自动退出。
- 学生敏感字段、原始文件下载、来源版本和 AI 查询都会执行数据范围校验。
- 导入、审核、导出、登录、系统设置和 AI 调用均会留下审计记录。
- AI 只能生成受约束的查询、统计和导出计划；涉及数据库修改时必须由人工在页面中执行。
- 发布构建会拒绝把密钥、账号、数据库、原始资料、备份和本地模型写入 GitHub 或更新 ZIP。

部署、TLS、备份恢复与迁移检查见 [docs/OPERATIONS.md](docs/OPERATIONS.md)。

## 开发与发布

### 本地开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
$env:DATABASE_URL = 'sqlite:///./data/student_management.db'
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8100
```

### 发布受控更新包

```powershell
python scripts\audit_public_source.py
python -m pytest -q
python scripts\build_release.py --output dist
```

日常代码提交只推送到 `main`，不会自动创建更新包或 GitHub Release。只有在明确需要发布时，才更新 `VERSION`、创建同名 Git 标签，例如 `v1.0.1`，并手动触发 GitHub 的“Publish controlled update”工作流，填写该标签。版本使用 `X.Y.Z`：最后一位 `Z` 只能是 `0-9`，因此 `v1.0.9` 的下一版必须是 `v1.1.0`。详细流程见 [docs/RELEASING.md](docs/RELEASING.md)。

## 项目文档

- [运维与迁移指南](docs/OPERATIONS.md)
- [生产部署说明](docs/PRODUCTION.md)
- [发布与在线更新](docs/RELEASING.md)
- [更新记录](https://github.com/Star-Moon10/Student-Management-System/releases)

## 许可与免责声明

本项目不是自由软件或开源软件许可项目。源码可见不代表获得使用、部署或二次开发许可。未经 StarMoon 事先书面授权，禁止任何形式的使用或传播。

系统涉及学生个人信息。授权使用者仍须自行遵守适用的数据保护、网络安全、教育管理和学校内部制度要求，并完成备份、访问控制、日志留存和安全评估。
