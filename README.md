<div align="center">

# 学生档案管理系统

<a href="README.en.md">English</a>

<br><br>

[![Release](https://img.shields.io/github/v/release/Star-Moon10/Student-Management-System?display_name=tag&label=Release)](https://github.com/Star-Moon10/Student-Management-System/releases)
[![Validation](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml/badge.svg)](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Restricted%20Use-b42318)](LICENSE)

<br>

<a href="#快速开始">快速开始</a> · <a href="#部署方式">部署方式</a> · <a href="#在线更新">在线更新</a> · <a href="docs/OPERATIONS.md">运维文档</a> · <a href="https://github.com/Star-Moon10/Student-Management-System/issues">问题反馈</a>

</div>

面向学校档案管理场景的本地部署系统。它将学生主档案、Excel 导入、相关资料审核、来源追溯、审计回滚、数据库备份和只读 AI 数据助手放在同一套受控工作流中，适合教师、普通管理员和超级管理员协同使用。

> [!IMPORTANT]
> **授权声明**：本仓库公开源码仅供评估、审阅、安全检查和经授权开发。未经版权人书面许可，任何个人或组织不得使用、部署、复制、修改、分发、提供服务或以其他方式利用本系统及其衍生成果。详见 [LICENSE](LICENSE)。

## 主要能力

1. **完整档案工作流**：学生档案、批量导入、资料审核、导出、来源追溯、版本历史和时间线。
2. **按学校组织管理**：学校、学院、专业、班级四层数据范围统一约束列表、详情、导出、原始资料和 AI。
3. **可审计、可恢复**：关键操作留痕，支持撤回、备份、恢复演练、回收站和中断更新恢复。
4. **AI 只读协作**：本地 AI 支持自然语言检索、统计和受控导出，不具备数据库写入能力。
5. **面向本地运维**：Windows 一键启动、Docker Compose、加密备份、权限控制和可见更新进度。

## 快速开始

### Windows 本地部署

```bat
setup.bat
start-system.bat
```

首次运行 `setup.bat`，日常只运行 `start-system.bat`。浏览器会打开 `http://127.0.0.1:8100`。

### Docker Compose

```bash
cp .env.example .env
# 修改 JWT_SECRET 后继续
docker compose up --build -d
docker compose exec app python -m app.seed_admin --username admin
```

Docker 核心部署完成后访问 `http://localhost:8100`。macOS 用户请继续阅读 [macOS 与本地 AI](#macos-与本地-ai)。

### 无 AI 部署

```env
AI_ENABLED=false
```

关闭 AI 不影响学生档案、导入、审核、导出、权限、审计和备份。

## 功能清单

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

## 部署提示

复制 `.env.example` 为 `.env` 后，至少替换 `JWT_SECRET`。生产环境需要 HTTPS、独立备份和受控访问。数据库、原始资料和备份目录都属于重要资产，迁移系统时必须一起保留。详细配置说明见 [运维与迁移指南](docs/OPERATIONS.md)。

## 在线更新

仅 Windows 本地部署支持系统内在线更新。管理员确认安装后，系统会备份现有数据、显示更新进度并重启服务；异常中断时会在下一次启动时尝试恢复到可用状态。Docker 部署请按镜像或代码更新流程维护。

## 安全与运维

- 密码使用 Argon2id 哈希；连续登录失败会限流并临时锁定账号。
- 会话使用 HttpOnly Cookie、JWT 和 CSRF 校验；无操作五分钟后自动退出。
- 学生详情、来源下载、导出和 AI 查询都执行数据范围校验。
- 导入、审核、导出、登录、系统设置和 AI 调用均写入审计记录。
- AI 只能生成受约束的查询、统计和导出计划；数据库修改必须由人工在界面完成。
- 更新、备份和恢复均有可见状态。生产环境仍应定期执行恢复演练。

## 项目文档

- [英文 README](README.en.md)
- [运维与迁移指南](docs/OPERATIONS.md)
- [生产部署说明](docs/PRODUCTION.md)
- [发布与在线更新](docs/RELEASING.md)
- [更新记录](https://github.com/Star-Moon10/Student-Management-System/releases)

部署、配置和维护的详细操作请以以上文档为准。

## 许可与免责声明

本项目不是自由软件或开源软件许可项目。源码可见不代表获得使用、部署或二次开发许可。未经 StarMoon 事先书面授权，禁止任何形式的使用、部署或传播。

本系统可能处理学生个人信息。获授权的部署者仍须自行遵守适用的数据保护、网络安全、教育管理和学校内部制度要求，并完成访问控制、日志留存、备份恢复和安全评估。
