import argparse
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal, init_db
from app.models import Role, User


def main() -> None:
    parser = argparse.ArgumentParser(description="Change the single super administrator")
    parser.add_argument("--username", required=True)
    parser.add_argument("--name", default="系统管理员")
    args = parser.parse_args()
    password = getpass.getpass("超级管理员新密码（至少 8 位）: ")
    if len(password) < 8:
        raise SystemExit("密码至少需要 8 位")
    init_db()
    with SessionLocal() as db:
        super_admin = db.scalar(select(User).where(User.super_admin_key == "super_admin"))
        username_owner = db.scalar(select(User).where(User.username == args.username))
        if username_owner and username_owner is not super_admin:
            raise SystemExit("该用户名已被其他账号使用")
        if super_admin:
            super_admin.username = args.username
            super_admin.display_name = args.name
            super_admin.password_hash = hash_password(password)
            super_admin.role = Role.SUPER_ADMIN
            super_admin.is_active = True
            super_admin.failed_login_count = 0
            super_admin.locked_until = None
        else:
            db.add(
                User(
                    username=args.username,
                    display_name=args.name,
                    password_hash=hash_password(password),
                    role=Role.SUPER_ADMIN,
                    super_admin_key="super_admin",
                )
            )
        db.commit()
    print("超级管理员已更新")


if __name__ == "__main__":
    main()
