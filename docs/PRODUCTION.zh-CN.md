# 生产环境部署

**[English](PRODUCTION.md)**

服务可以从内置 SQLite 迁移到 MySQL，无需修改应用代码。迁移既有系统时，请将项目目录、`data`、`storage`、`backups`、`exports`、`.env` 和模型文件一起迁移。

## 必要环境变量

在服务器上从 `.env.example` 创建 `.env`，至少设置：

```ini
ENVIRONMENT=production
DATABASE_URL=mysql+pymysql://sms:strong-password@127.0.0.1:3306/student_management?charset=utf8mb4
JWT_SECRET=a-long-random-secret-at-least-32-characters
DATA_ENCRYPTION_KEY=a-valid-fernet-key
COOKIE_SECURE=true
BACKUP_ENCRYPT=true
BACKUP_OFFSITE_PATH=\\backup-server\student-system-backups
```

数据加密密钥应只生成一次，并按数据库密码等级保护。数据写入后再更改 `JWT_SECRET` 或 `DATA_ENCRYPTION_KEY`，会导致加密数据和备份包无法读取。

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## TLS 与网络边界

应用应运行在终止 HTTPS 的反向代理后，只转发至 `127.0.0.1:8100`，并把 HTTP 重定向到 HTTPS。不要向公网暴露 8100 或 MySQL。数据库和备份共享应仅允许服务账号访问。

当 `ENVIRONMENT=production` 时，应用会启用安全 Cookie 和 HTTPS 重定向检查。反向代理必须向应用转发 HTTPS 流量；否则安全 Cookie 会阻止通过明文 HTTP 登录。

## 备份与恢复

每份计划备份包含数据库和 `storage` 原始资料。启用 `BACKUP_ENCRYPT=true` 后，备份包会在复制到 `BACKUP_OFFSITE_PATH` 前加密。运维页面会校验备份完整性、显示健康状态，并在最近备份或异地备份不可用时发出告警。

服务上线前，应在非生产副本中至少执行一次恢复演练。MySQL 恢复属于维护窗口操作，应使用 MySQL 工具完成；SQLite 恢复可在系统设置界面操作。
