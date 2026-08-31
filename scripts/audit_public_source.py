"""Fail closed when source publication or update packaging includes local data or secrets."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PUBLIC_DIRECTORIES = ("app", "scripts", "docs", "tests", ".github")
PUBLIC_FILES = {
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "VERSION",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.lock",
    "setup.bat",
    "start-system.bat",
    "stop-system.bat",
}
RUNTIME_DIRECTORIES = ("app", "scripts", "docs")
RUNTIME_FILES = {
    ".env.example",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "VERSION",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.lock",
    "setup.bat",
    "start-system.bat",
    "stop-system.bat",
}
FORBIDDEN_PATH_PARTS = {
    ".venv",
    ".pytest_cache",
    "backups",
    "data",
    "exports",
    "models",
    "resource",
    "run",
    "storage",
    "tmp",
    "tools",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE KEY-----"),
)


def allowed_files(root: Path, *, runtime: bool = False) -> list[Path]:
    directories = RUNTIME_DIRECTORIES if runtime else PUBLIC_DIRECTORIES
    files = RUNTIME_FILES if runtime else PUBLIC_FILES
    result: list[Path] = []
    for name in directories:
        target = root / name
        if target.is_dir():
            result.extend(
                path
                for path in target.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() not in {".pyc", ".pyo"}
            )
    result.extend(root / name for name in files if (root / name).is_file())
    return sorted(set(result))


def audit_files(root: Path, files: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in files:
        relative = path.resolve().relative_to(root.resolve())
        if any(part.lower() in FORBIDDEN_PATH_PARTS for part in relative.parts):
            issues.append(f"forbidden runtime path: {relative}")
            continue
        if path.suffix.lower() in {".db", ".sqlite", ".xlsx", ".xls", ".docx", ".doc", ".zip", ".enc", ".pem", ".key"}:
            issues.append(f"forbidden data or binary type: {relative}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"non-text source file: {relative}")
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(f"possible secret in {relative}: {pattern.pattern}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the safe source whitelist before public release.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--runtime", action="store_true", help="Audit the smaller runtime update-package whitelist.")
    args = parser.parse_args()
    root = args.root.resolve()
    files = allowed_files(root, runtime=args.runtime)
    issues = audit_files(root, files)
    if issues:
        print("PUBLIC SOURCE AUDIT FAILED", file=sys.stderr)
        print("\n".join(f"- {issue}" for issue in issues), file=sys.stderr)
        return 1
    print(f"PUBLIC SOURCE AUDIT PASSED: {len(files)} approved files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
