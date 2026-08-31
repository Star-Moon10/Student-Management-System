"""Build a deterministic, data-free online-update package from the runtime whitelist."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from audit_public_source import RUNTIME_DIRECTORIES, RUNTIME_FILES, allowed_files, audit_files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_runtime(root: Path, staging: Path) -> list[Path]:
    copied: list[Path] = []
    for source in allowed_files(root, runtime=True):
        destination = staging / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the GitHub Release update assets.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--version", default="")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    version = args.version.strip().removeprefix("v") or (root / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("VERSION must not be empty")
    issues = audit_files(root, allowed_files(root, runtime=True))
    if issues:
        raise SystemExit("Unsafe release source:\n" + "\n".join(issues))

    staging = output / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    copied = copy_runtime(root, staging)
    manifest = {
        "format": 1,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_directories": list(RUNTIME_DIRECTORIES),
        "runtime_files": sorted(RUNTIME_FILES),
        "preserved_paths": [".env", "data", "storage", "exports", "backups", "models", "tools", "resource", "run", ".venv"],
        "files": {str(path.relative_to(staging)).replace("\\", "/"): sha256(path) for path in copied},
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    package = output / "student-management-update.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging).as_posix())
    digest = sha256(package)
    (output / "student-management-update.zip.sha256").write_text(f"{digest}  {package.name}\n", encoding="ascii")
    (output / "release-notes.md").write_text(
        f"# v{version}\n\n受控在线更新包。该包不包含配置、账号、学生数据、原始资料、备份或本地模型。\n",
        encoding="utf-8",
    )
    print(json.dumps({"version": version, "package": str(package), "sha256": digest, "files": len(copied)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
