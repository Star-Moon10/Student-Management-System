# Releases and Online Updates

**[中文](RELEASING.md)**

The GitHub repository may contain source code only. It must not contain local configuration, accounts, student data, original documents, backups, or local AI models.

## Pre-release checks

Run from the project root:

```powershell
python scripts/audit_public_source.py
python -m pytest -q
python scripts/build_release.py --output dist
```

The builder writes only `app`, `scripts`, `docs`, and a small root-file whitelist into the ZIP. It produces `manifest.json` and a SHA-256 file; the updater validates every included file.

## Publishing a version

1. Update the root `VERSION`, for example `1.0.1`. Versions use `X.Y.Z`; the final `Z` segment is limited to `0-9`, so `1.0.9` must be followed by `1.1.0`.
2. Commit and push `main`.
3. Create and push the matching tag, for example `v1.0.1`.
4. Manually run the GitHub Actions **Publish controlled update** workflow and enter that tag. The workflow audits source, runs tests, creates the Release, and uploads the ZIP plus SHA-256 file.

Administrators check Releases from **System Settings → Online Updates**. Installation requires a super administrator account, password, and the confirmation phrase `确认更新系统`. The updater creates a database backup before installation; if replacement, dependency installation, or the health check fails, it attempts to restore the previous application code and SQLite database copy.

## Local data boundary

The updater replaces only its program whitelist. `.env`, `data`, `storage`, `exports`, `backups`, `models`, `tools`, `resource`, `run`, and `.venv` stay local. Never commit tokens. Tokens for private update repositories should be stored only through the super administrator UI, where they are encrypted in the local database.
