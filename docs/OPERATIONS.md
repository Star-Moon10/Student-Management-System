# Student Management System Operations

**[中文](OPERATIONS.zh-CN.md)**

## New machine checklist

1. Copy the complete project directory, including `.env`, `data`, `storage`, `exports`, `backups`, `models`, and `tools`.
2. Install Python 3.12 or newer, then run `setup.bat` once.
3. Confirm `data/student_management.db` exists and the model manifest or GGUF is present if local AI is required.
4. Start with `start-system.bat` and open `http://127.0.0.1:8100`.
5. Log in and verify student count, a source document, one export preview, the AI status indicator, and the latest backup.

Do not delete `.env` during migration. It contains the JWT and data-encryption settings that allow the copied database and encrypted values to remain usable.

## HTTPS deployment

The app should remain bound to `127.0.0.1` behind a reverse proxy. A minimal Caddy arrangement is:

```text
students.example.edu {
    reverse_proxy 127.0.0.1:8100
}
```

Set these values in the server `.env`:

```text
ENVIRONMENT=production
COOKIE_SECURE=true
JWT_SECRET=<new-long-random-secret>
DATA_ENCRYPTION_KEY=<stable-fernet-key>
```

The proxy handles certificates and HTTPS. Do not expose ports 3306 or 11434 to the public network. Use a firewall rule to allow only the proxy and trusted administration network.

## Backup and recovery

Create a backup from **系统设置 → 数据库备份**. Run **校验** and then **演练** on a backup before relying on it. The drill extracts and validates a copy in an isolated location without changing the active database. A real restore first creates a recovery point and writes an audit record; after restoring, restart the application and verify the student count and the AI status.

Backup deletion is intentionally separate from export cleanup. Export cleanup only removes generated `.xlsx`/`.csv` files older than the selected retention period. It never removes original materials, student records, model files, or database backups.

## AI operation boundary

The local model plans natural-language queries and explains results. The server performs the scoped database query, aggregation, source attribution, export confirmation, and permission checks. AI cannot modify or delete the database. Requests involving modification should be completed manually in the platform; the resulting manual operation is audited and reversible when a complete snapshot exists.

Administrators can inspect the AI caller, question, output, data sources, local model name, and server-side response time from **审计与 AI 记录**. AI and audit records are restricted to administrators and the super administrator.

## Routine verification

- Check the green or degraded AI indicator before using model-assisted import.
- Review the related-information queue after each Word or related Excel import.
- Use the import report preview and error CSV for unmatched rows; unresolved rows must be handled in the manual matching queue.
- Review open system alerts and failed background tasks.
- Run an audit-chain integrity check after restoring a backup.
- Use the super administrator system status panel to watch disk usage and clean old generated exports.

## Offline dependencies

Lucide icons are served from `app/static/vendor/lucide.min.js`. The project-local Ollama runtime and model are under `tools/ollama` and `models/ollama` or `models/imports`. Once those directories are copied, normal startup does not require internet access; Python packages must already be installed in `.venv` or available from the configured package mirror.
