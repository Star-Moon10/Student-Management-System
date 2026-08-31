# Production Deployment

**[中文](PRODUCTION.zh-CN.md)**

This service can move from the bundled SQLite database to MySQL without changing the application code. Keep the project folder, `data`, `storage`, `backups`, `exports`, `.env`, and the model files together when moving an existing installation.

## Required environment settings

Create `.env` from `.env.example` on the server and set at least:

```ini
ENVIRONMENT=production
DATABASE_URL=mysql+pymysql://sms:strong-password@127.0.0.1:3306/student_management?charset=utf8mb4
JWT_SECRET=a-long-random-secret-at-least-32-characters
DATA_ENCRYPTION_KEY=a-valid-fernet-key
COOKIE_SECURE=true
BACKUP_ENCRYPT=true
BACKUP_OFFSITE_PATH=\\backup-server\student-system-backups
```

Generate the persistent data-encryption key once, then protect it like a database password. Changing `JWT_SECRET` or `DATA_ENCRYPTION_KEY` after data has been written makes encrypted data and backup packages unreadable.

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## TLS and network boundary

Run the application behind a reverse proxy that terminates HTTPS, forwards only to `127.0.0.1:8100`, and redirects HTTP to HTTPS. Do not expose port 8100 or MySQL to the public network. Restrict database and backup shares to the service account.

The application enables secure cookies and HTTPS redirect checks when `ENVIRONMENT=production`. The reverse proxy must send HTTPS traffic to the application; otherwise secure cookies will correctly prevent login over plain HTTP.

## Backups and recovery

Each scheduled backup contains the database and `storage` source files. With `BACKUP_ENCRYPT=true`, the package is encrypted before it is copied to `BACKUP_OFFSITE_PATH`. The operations page verifies package integrity, displays backup health, and raises an alert when the recent or off-site backup is unavailable.

Run one restore drill in a non-production copy before service launch. MySQL restores remain a maintenance-window operation using MySQL tooling; SQLite restores are available in the system settings UI.
