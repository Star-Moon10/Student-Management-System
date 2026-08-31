# Student Management System

A secure, locally deployable student information management system. It supports Excel import/upsert with cell-level provenance, Word extraction with a local AI review workflow, audited manual edits, XLSX exports, role-based access, and a local Ollama assistant. The web UI also provides cascaded filters, saved filters, export previews, template history, related-import rollback, per-student batch editing, backup validation drills, and administrator-only AI/audit visibility.

## Quick start

1. Copy `.env.example` to `.env` and replace `JWT_SECRET` with a long random value.
2. Start MySQL and the application with `docker compose up --build`.
3. Create or change the single super administrator: `docker compose exec app python -m app.seed_admin --username admin`.
4. Visit `http://localhost:8100` and sign in.

For a no-Docker development start, create a virtual environment, run `pip install -e .[dev]`, set `DATABASE_URL=sqlite:///./data/student_management.db`, then run `uvicorn app.main:app --reload`.

On a new Windows computer, run `setup.bat` once to create the virtual environment, install dependencies, initialize the local database, and configure the copied local AI model when available. For normal use afterwards, double-click `start-system.bat` to start the server and open the browser. Use `stop-system.bat` to close the tracked server process.

## Controlled online updates

The system settings page contains a controlled update panel for administrators and super administrators. It checks the public GitHub Release feed at `Star-Moon10/Student-Management-System`, downloads only the signed-by-checksum release package, validates the manifest and every included file, creates a database backup, then restarts the local service. An online update requires a super administrator credential and the phrase `确认更新系统`.

Only the source whitelist (`app`, `scripts`, `docs`, and selected root files) is updated. `.env`, accounts, `data`, `storage`, `exports`, `backups`, `models`, `tools`, `resource`, `run`, and `.venv` stay local and are never included in GitHub releases. Super administrators can change the repository/channel and optionally keep an encrypted GitHub token for private releases. The same control also accepts a locally built offline ZIP package.

To publish a version, run `python scripts/build_release.py` from a clean source checkout, attach the generated `student-management-update.zip` and `.sha256` files to a GitHub Release whose tag is newer than `VERSION`. The build refuses runtime data or secret-like content before it writes the package.

## Project-local AI

Run `powershell -ExecutionPolicy Bypass -File scripts\setup-project-ai.ps1` once after cloning or migrating the project. It installs the Ollama Windows runtime into `tools\ollama`, imports the supplied GGUF model, and creates the CUDA-targeted `student-qwen-cuda:latest` configuration in `models\ollama`. These folders are intentionally ignored by Git because they are large binaries, but copying the whole project directory preserves them. `start-system.bat` and `stop-system.bat` start and stop the project-local AI service automatically.

## Local AI

Install Ollama on the host and pull the recommended model:

```powershell
ollama pull qwen2.5:7b-instruct-q5_0
```

The application uses the model only to produce a constrained JSON tool request or a Word-import extraction candidate. Database queries, exports, updates, and permission checks stay in the server. If Ollama is unavailable, normal management features continue working and Word imports are queued for manual review.

## Security model

- Passwords use Argon2id; failed sign-in attempts are rate limited and temporarily lock an account.
- Login sessions use signed, short-lived JWTs in HttpOnly cookies plus CSRF protection. Set `COOKIE_SECURE=true` behind HTTPS.
- TLS termination belongs in a reverse proxy such as Nginx or Caddy in production. Never expose MySQL or Ollama to the public internet.
- Uploaded originals are stored by content hash; every import, edit and export is written to the audit log.
- AI cannot execute arbitrary SQL or mutate student records. Import candidates require review before they are applied.
- The browser logs out after five minutes without user activity; background status polling does not keep an idle session alive.
- Generated export files can be previewed before creation and cleaned by retention period from the super administrator settings.
- Every student changed by a batch edit gets an independent version and reversible `update` audit record.

## Production transport and migration

The bundled `start-system.bat` intentionally binds to `127.0.0.1` and uses HTTP for local operation. For a server reachable by other machines, put the app behind a TLS reverse proxy and keep Uvicorn, MySQL, and Ollama on private addresses. Set `ENVIRONMENT=production`, `COOKIE_SECURE=true`, and a new long `JWT_SECRET`; the app will redirect HTTP to HTTPS and will not start with the development secret.

When moving to another computer, copy `.env`, `data`, `storage`, `exports`, `backups`, `models`, and `tools` together with the application. Run `setup.bat` once, then use `start-system.bat` normally. `setup.bat` keeps an existing `.env` and database; it does not reset accounts or student records.

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for the reverse proxy checklist, backup recovery drill, offline AI setup, retention housekeeping, and post-migration verification.

## Limits of this version

Excel `.xlsx` and Word `.docx` are accepted. Legacy `.xls`/`.doc` must be converted before upload. Add an antivirus scanner and object storage encryption before handling high-sensitivity production data.
