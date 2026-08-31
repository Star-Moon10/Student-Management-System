<div align="center">

# Student Management System

<a href="README.md">简体中文</a>

<br><br>

[![Release](https://img.shields.io/github/v/release/Star-Moon10/Student-Management-System?display_name=tag&label=Release)](https://github.com/Star-Moon10/Student-Management-System/releases)
[![Validation](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml/badge.svg)](https://github.com/Star-Moon10/Student-Management-System/actions/workflows/validate.yml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Restricted%20Use-b42318)](LICENSE)

<br>

<a href="#quick-start">Quick Start</a> · <a href="#deployment-options">Deployment</a> · <a href="#online-updates">Updates</a> · <a href="docs/OPERATIONS.md">Operations</a> · <a href="https://github.com/Star-Moon10/Student-Management-System/issues">Issue Tracker</a>

</div>

A locally deployable student records system for school administration. It brings student records, Excel imports, related-material review, data lineage, audit recovery, backups, and a read-only AI assistant into one controlled workflow for teachers, administrators, and super administrators.

> [!IMPORTANT]
> **Authorization notice:** Source code is available only for evaluation, review, security assessment, and authorized development. No person or organization may use, deploy, copy, modify, distribute, provide as a service, or otherwise exploit this software without prior written authorization from the copyright holder. See [LICENSE](LICENSE).

## Key Features

1. **Complete record workflow**: Student records, batch imports, material review, exports, lineage, version history, and timelines.
2. **School-aware access control**: School, college, major, and class scopes consistently constrain lists, details, exports, source files, and AI.
3. **Auditable and recoverable**: Critical operations are recorded and support rollback, backups, restore drills, recycle-bin recovery, and interrupted-update recovery.
4. **Read-only AI collaboration**: Local AI supports natural-language search, aggregation, and controlled exports without database write access.
5. **Local operations first**: Windows launcher scripts, Docker Compose, encrypted backups, permission control, and visible update progress.

## Quick Start

### Windows Local Deployment

```bat
setup.bat
start-system.bat
```

Run `setup.bat` only for the first setup. For everyday use, run `start-system.bat` and open `http://127.0.0.1:8100`.

### Docker Compose

```bash
cp .env.example .env
# Replace JWT_SECRET before continuing.
docker compose up --build -d
docker compose exec app python -m app.seed_admin --username admin
```

Open `http://localhost:8100`. macOS users should also read [macOS and Local AI](#macos-and-local-ai).

### Deploy Without AI

```env
AI_ENABLED=false
```

Disabling AI does not affect records, imports, review, export, roles, audit, or backups.

## Feature Matrix

| Area | Included capabilities |
| --- | --- |
| Student records | Server-side pagination, combined filtering, batch export, field lineage, version history, and China Standard Time timelines. |
| Data import | Excel field mapping, preflight checks, row previews, conflict comparison, error-row retry, and batch rollback. |
| Related materials | Excel source-row cards, local-AI Word extraction, manual matching, batch review, and remark cards. |
| Access control | Super administrator, administrator, and teacher roles with school, college, major, and class scopes. |
| Audit and recovery | Audit trail, reversible changes, database backups, restore drills, source-document library, and recycle bin. |
| AI assistant | Natural-language query, aggregation, and controlled export. The AI can only read data in the caller's scope. |
| Online updates | Release validation, pre-update backups, visible progress, interrupted-update recovery, and rollback. |

## Roles and Data Scope

| Role | Primary responsibility | Data visibility |
| --- | --- | --- |
| Teacher | Query, export, import, and review submitted related materials. | Students in the account scope only. |
| Administrator | Manage teacher accounts and scopes; handle teacher-level operations and audit work. | Teacher-level authorized data. |
| Super administrator | Manage all accounts, controls, backup recovery, high-risk settings, update sources, and complete audit data. | All system data and records. |

School, college, major, and class rules are applied consistently to lists, details, source downloads, timelines, exports, and AI queries.

## Deployment Options

| Option | Best for | AI support |
| --- | --- | --- |
| Windows local | Office PCs and Windows intranet hosts | Project-local Ollama or existing local model |
| Docker Compose | Mac, Windows, or Linux hosts with Docker operations | Host or separate Ollama service |
| Docker without AI | Records, imports, review, export, and auditing only | AI disabled or degraded |

## Windows Local Deployment

1. Copy the full project folder. For a migration, retain `.env`, `data`, `storage`, `exports`, `backups`, `models`, `tools`, and `run`.
2. Run `setup.bat` once to create the virtual environment, install dependencies, and initialize the database without resetting existing records.
3. Run `start-system.bat` for everyday use. The browser opens `http://127.0.0.1:8100`.
4. Run `stop-system.bat` to stop the managed service.

The default service binds to localhost only. Use an HTTPS reverse proxy for network access. Do not expose the database, Ollama, or application port directly to the public Internet.

## Docker Deployment

Docker Compose starts the application core and MySQL:

```bash
cp .env.example .env
# Edit .env: replace JWT_SECRET at minimum.
docker compose up --build -d
docker compose exec app python -m app.seed_admin --username admin
```

Open `http://localhost:8100`. The `app.seed_admin` command asks interactively for the super administrator password.

### Docker Production Notes

- The MySQL credentials and connection string in `docker-compose.yml` are examples. Change both before production use, or refactor them to environment-variable substitution.
- The default Compose file persists MySQL, `storage`, and `exports`. Add `./backups:/app/backups` so backup files survive container recreation.
- `ENVIRONMENT=production` and `COOKIE_SECURE=true` require an HTTPS reverse proxy such as Nginx or Caddy.
- The in-app updater targets Windows local deployments. Update Docker deployments by rebuilding or replacing the image, then run `docker compose up --build -d`.

## macOS and Local AI

Docker Desktop for Mac can access a host Ollama service through `host.docker.internal`. Install and run Ollama on the **Mac host**, then pull a regular model:

```bash
ollama pull qwen2.5:7b
```

Set the following values in the `.env` used by Docker Compose:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
AI_ENABLED=true
```

The default `student-qwen-cuda:latest` is a Windows/CUDA-specific local configuration and is not automatically available on macOS. Apple Silicon users should run native Ollama to use Metal; Docker Desktop for macOS does not provide container GPU passthrough.

To deploy without AI:

```env
AI_ENABLED=false
```

Records, Excel import, review, export, roles, auditing, and backups continue to work. AI queries and Word AI extraction will be unavailable or routed to manual review.

## Deployment Notes

Copy `.env.example` to `.env` and replace `JWT_SECRET` at minimum. Production deployments need HTTPS, independent backups, and controlled access. Treat the database, source documents, and backup directories as important migration assets. See the [operations guide](docs/OPERATIONS.md) for detailed configuration.

## Online Updates

Only Windows local deployments use the in-app updater. After an administrator confirms an update, the system backs up existing data, shows progress, and restarts the service. If an update is interrupted, the next startup attempts to return the system to a working state. Update Docker deployments through the image or source workflow instead.

## Security and Operations

- Passwords use Argon2id; repeated failed sign-ins are rate-limited and temporarily lock an account.
- Sessions use HttpOnly cookies, JWTs, and CSRF checks. Idle sessions expire after five minutes.
- Student details, source downloads, exports, and AI queries enforce the same data-scope rules.
- Imports, reviews, exports, logins, system settings, and AI calls are audited.
- The AI can produce constrained query, aggregation, and export plans only. Database changes must be made by a human through the UI.
- Production operators should run backup and restore drills regularly.

## Documentation

- [Chinese README](README.md)
- [Operations and migration](docs/OPERATIONS.md)
- [Production deployment](docs/PRODUCTION.md)
- [Release and online updates](docs/RELEASING.md)
- [Release history](https://github.com/Star-Moon10/Student-Management-System/releases)

Use the documents above for detailed deployment, configuration, and maintenance procedures.

## License and Disclaimer

This is not a free-software or open-source-licensed project. Source visibility does not grant permission to use, deploy, or develop derivative work. Any use or distribution without prior written authorization from StarMoon is prohibited.

The system may process student personal information. Authorized operators remain responsible for compliance with applicable privacy, cybersecurity, education-administration, and internal school requirements, including access control, audit retention, backup recovery, and security assessment.
