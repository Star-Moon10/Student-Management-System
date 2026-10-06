"""Privileged local actions for the desktop control center."""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select

from app.core.security import verify_password
from app.db import SessionLocal
from app.main import _schedule_update
from app.models import Role, User
from app.services.updates import check_for_update


def update_from_stdin() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == username, User.role == Role.SUPER_ADMIN, User.is_active.is_(True)))
        if not user or not verify_password(password, user.password_hash):
            print(json.dumps({"ok": False, "error": "超级管理员账号或密码不正确"}, ensure_ascii=False))
            return 2
        result = check_for_update(db)
        release = result.get("release") if isinstance(result.get("release"), dict) else None
        if not release or not release.get("update_ready"):
            print(json.dumps({"ok": False, "error": result.get("message") or "没有可用的受控更新包"}, ensure_ascii=False))
            return 3
        if not release.get("is_newer"):
            print(json.dumps({"ok": False, "error": "当前已经是最新版本"}, ensure_ascii=False))
            return 4
        outcome = _schedule_update(db, user, user, None, release=release)
        print(json.dumps({"ok": True, **outcome, "target_version": release.get("tag_name")}, ensure_ascii=False))
        return 0
    finally:
        db.close()


def check_from_local() -> int:
    db = SessionLocal()
    try:
        print(json.dumps(check_for_update(db), ensure_ascii=False))
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "update"))
    args = parser.parse_args()
    if args.command == "check":
        return check_from_local()
    if args.command == "update":
        return update_from_stdin()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
