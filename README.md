# 学生档案管理系统

[![Release](https://img.shields.io/github/v/release/Star-Moon10/Student-Management-System?display_name=tag&label=Release)](https://github.com/Star-Moon10/Student-Management-System/releases)
[![Validation](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml/badge.svg)](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-Restricted%20Use-b42318)](LICENSE)

面向学校档案管理场景的本地部署系统。系统将学生主档案、Excel 导入、相关资料审核、来源追溯、审计回滚、数据库备份和只读 AI 数据助手放在同一套受控工作流中，适合教师、普通管理员和超级管理员协同使用。

**English documentation: [README.en.md](README.en.md)**

> **授权声明**：本仓库公开源码仅供评估、审阅、安全检查和经授权开发。未经版权人书面许可，任何个人或组织不得使用、部署、复制、修改、分发、提供服务或以其他方式利用本系统及其衍生成果。详见 [LICENSE](LICENSE)。

## 目录

- [核心能力](#核心能力)
- [角色与数据边界](#角色与数据边界)
- [部署方式](#部署方式)
- [Windows 本地部署](#windows-本地部署)
- [Docker 部署](#docker-部署)
- [macOS 与本地 AI](#macos-与本地-ai)
- [配置与数据持久化](#配置与数据持久化)
- [在线更新](#在线更新)
- [安全与运维](#安全与运维)
- [开发与发布](#开发与发布)
- [许可与免责声明](#许可与免责声明)

## 核心能力

| 模块 | 能力 |
| --- | --- |
| 学生档案 | 服务端分页、组合筛选、批量导出、字段来源、版本历史与中国标准时间线。 |
| 数据导入 | Excel 字段映射、预检、样本预览、冲突对比、错误行重试与批次撤回。 |
| 相关资料 | Excel 原始行词条、Word 本地 AI 识别、人工匹配、批量审核与备注卡片。 |
| 权限范围 | 超级管理员、管理员、教师三级权限；学校、学院、专业和班级范围统一应用。 |
| 审计与恢复 | 操作审计、可撤回变更、数据库备份、恢复演练、原始资料库与回收站。 |
| AI 数据助手 | 自然语言查询、统计和受控导出；AI 仅读取调用人授权范围，不能写库。 |
| 在线更新 | Release 校验、更新前备份、可见进度、启动前中断恢复和失败回滚。 |

## 角色与数据边界

| 角色 | 主要职责 | 可见范围 |
| --- | --- | --- |
| 教师 | 查询、导出、导入学生数据；审核本人导入的相关资料。 | 仅自身数据范围内的学生。 |
| 管理员 | 管理教师账号和数据范围，处理教师层面的日常审计和运维。 | 教师层级及其授权数据。 |
| 超级管理员 | 管理全部账号、系统控制、备份恢复、高危设置、更新来源和全量审计。 | 全部系统数据与记录。 |

学校、学院、专业和班级范围会在列表、详情、来源下载、时间线、导出和 AI 查询中统一生效。

## 部署方式

| 方式 | 适用场景 | AI 支持 |
| --- | --- | --- |
| Windows 本地部署 | 办公室电脑、Windows 校园内网服务器 | 项目内 Ollama 或已有模型 |
| Docker Compose | 有 Docker 运维能力的 Mac、Windows 或 Linux 主机 | 宿主机或独立 Ollama |
| Docker 无 AI | 只需要档案、导入、审核、导出和审计 | AI 功能关闭或降级 |

## Windows 本地部署

1. 复制完整项目目录。迁移已有系统时保留 `.env`、`data`、`storage`、`exports`、`backups`、`models`、`tools` 和 `run`。
2. 首次运行 `setup.bat`。它会创建虚拟环境、安装依赖、初始化数据库，并保留已有账号和学生数据。
3. 日常运行 `start-system.bat`，浏览器将打开 `http://127.0.0.1:8100`。
4. 停止服务时运行 `stop-system.bat`。

默认仅绑定本机地址。要让其他电脑访问，请在反向代理后提供 HTTPS；不要直接公开数据库、Ollama 或应用端口。

## Docker 部署

Docker Compose 可启动应用核心与 MySQL：

```bash
cp .env.example .env
# 编辑 .env：至少替换 JWT_SECRET
docker compose up --build -d
docker compose exec app python -m app.seed_admin --username admin
```

访问地址为 `http://localhost:8100`。`app.seed_admin` 会交互式要求设置超级管理员密码。

### Docker 生产注意事项

- `docker-compose.yml` 中的 MySQL 密码和应用连接串是示例值。生产部署必须同时修改两处，或改为由环境变量注入。
- 当前 Compose 持久化 MySQL、`storage` 和 `exports`。生产环境应额外挂载 `./backups:/app/backups`，避免容器重建后丢失备份文件。
- `ENVIRONMENT=production` 与 `COOKIE_SECURE=true` 必须配合 Nginx、Caddy 等 HTTPS 反向代理使用。
- 系统内在线更新器面向 Windows 本地部署。Docker 部署应通过更新代码或镜像后运行 `docker compose up --build -d` 更新。

## macOS 与本地 AI

### Mac Docker 部署

Docker Desktop for Mac 可通过 `host.docker.internal` 访问宿主机 Ollama。Mac 用户应在**宿主机**安装 Ollama，而不是运行项目中的 Windows PowerShell AI 脚本。

1. 安装并启动 Ollama for macOS。
2. 在 Mac 终端拉取常规模型：

   ```bash
   ollama pull qwen2.5:7b
   ```

3. 在 Docker 使用的 `.env` 中设置：

   ```env
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=qwen2.5:7b
   AI_ENABLED=true
   ```

4. 再执行 Docker Compose 启动命令。

项目默认的 `student-qwen-cuda:latest` 是 Windows/CUDA 本地配置，不能在 macOS 上自动获得。Apple Silicon 用户应运行原生 Ollama 使用 Metal；Docker Desktop for Mac 不提供容器 GPU 透传。

### 不使用 AI

在 `.env` 设置：

```env
AI_ENABLED=false
```

学生档案、Excel 导入、审核、导出、权限、审计和备份仍可正常使用；AI 查询和 Word AI 识别会显示为降级或转入人工处理。

## 配置与数据持久化

复制 `.env.example` 为 `.env` 并替换所有示例密钥。至少应配置：

| 配置 | 用途 | 要求 |
| --- | --- | --- |
| `JWT_SECRET` | 登录令牌签名 | 使用长随机字符串，不能使用示例值。 |
| `DATABASE_URL` | 数据库连接 | Windows 默认 SQLite；Docker 默认 MySQL。 |
| `COOKIE_SECURE` | HTTPS Cookie | 生产 HTTPS 必须为 `true`。 |
| `DATA_ENCRYPTION_KEY` | 备份与敏感内容加密 | 可选，生产环境建议设置并妥善保管。 |
| `AI_ENABLED` | 是否启用本地 AI | 没有 Ollama 时设为 `false`。 |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | 模型连接 | 按部署平台填写。 |

| 路径 | 内容 | 迁移或备份要求 |
| --- | --- | --- |
| `.env` | 密钥和部署配置 | 必须私下保存，绝不提交 Git。 |
| `data` 或 MySQL 卷 | 数据库 | 必须备份。 |
| `storage` | 上传的原始资料 | 必须备份。 |
| `backups` | 加密备份包 | 建议复制到独立存储。 |
| `models` / `tools` | Windows 项目内 AI 模型与运行时 | 仅 Windows 本地 AI 需要。 |
| `exports` | 生成的导出文件 | 按学校保留策略处理。 |

## 在线更新

仅 Windows 本地部署支持系统内在线更新。管理员或超级管理员登录后会自动检查 GitHub Release；系统只提示可用版本，绝不会自行下载、替换或重启。

安装需要：

1. 管理员主动点击“查看并安装”。
2. 输入任一超级管理员账号和密码。
3. 输入确认口令 `确认更新系统`。

更新器会校验 ZIP、SHA-256 和文件清单，先创建加密备份，再替换应用代码、安装依赖并执行健康检查。更新过程显示下载、校验、备份、替换、安装和重启进度。

如果更新器在完成健康检查前崩溃、断电或被强制结束，下一次正常运行 `start-system.bat` 会检测未完成事务并恢复更新前代码；SQLite 部署还会恢复更新前数据库副本。更新包不会覆盖 `.env`、学生数据、原始资料、备份、模型、工具或稳定启动脚本。

## 安全与运维

- 密码使用 Argon2id 哈希；连续登录失败会限流并临时锁定账号。
- 会话使用 HttpOnly Cookie、JWT 和 CSRF 校验；无操作五分钟后自动退出。
- 学生详情、来源下载、导出和 AI 查询都执行数据范围校验。
- 导入、审核、导出、登录、系统设置和 AI 调用均写入审计记录。
- AI 只能生成受约束的查询、统计和导出计划；数据库修改必须由人工在界面完成。
- 更新、备份和恢复均有可见状态。生产环境仍应定期执行恢复演练。

## 开发与发布

### 本地开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
$env:DATABASE_URL = 'sqlite:///./data/student_management.db'
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8100
```

### 发布版本

日常改动只提交并推送 `main`，不会自动打包或发布。

需要发布时：

1. 修改 `VERSION`，使用 `X.Y.Z`，例如 `1.0.1`。
2. 最后一位 `Z` 仅允许 `0-9`；因此 `v1.0.9` 的下一版必须是 `v1.1.0`。
3. 提交代码并创建同名标签，例如 `v1.0.1`。
4. 在 GitHub Actions 手动运行 **Publish controlled update**，填写该标签。

发布工作流会执行源码安全审计、测试和更新包构建，再上传 ZIP 与 SHA-256。详见 [docs/RELEASING.md](docs/RELEASING.md)。

## 项目文档

- [英文 README](README.en.md)
- [运维与迁移指南](docs/OPERATIONS.md)
- [生产部署说明](docs/PRODUCTION.md)
- [发布与在线更新](docs/RELEASING.md)
- [更新记录](https://github.com/Star-Moon10/Student-Management-System/releases)

## 许可与免责声明

本项目不是自由软件或开源软件许可项目。源码可见不代表获得使用、部署或二次开发许可。未经 StarMoon 事先书面授权，禁止任何形式的使用、部署或传播。

本系统可能处理学生个人信息。获授权的部署者仍须自行遵守适用的数据保护、网络安全、教育管理和学校内部制度要求，并完成访问控制、日志留存、备份恢复和安全评估。
