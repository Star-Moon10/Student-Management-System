# 发布与在线更新

本项目发布的 GitHub 仓库只能保存软件源代码，不能保存本机配置、账号、学生数据、原始资料、备份或本地 AI 模型。

## 发布前检查

在项目根目录运行：

```powershell
python scripts/audit_public_source.py
python -m pytest -q
python scripts/build_release.py --output dist
```

发布器只会把 `app`、`scripts`、`docs` 以及少量启动与依赖文件写进 ZIP。它会生成 `manifest.json` 和 SHA-256 文件；更新器会逐文件验证这些内容。

## 发布版本

1. 修改根目录 `VERSION`，例如 `1.0.1`。版本使用 `X.Y.Z`，最后一位 `Z` 只能是 `0-9`；因此 `1.0.9` 后必须升级为 `1.1.0`。
2. 提交并推送到 `main`。
3. 创建同名标签 `v1.0.1` 并推送。
4. GitHub Actions 会运行安全审计和测试，然后创建 Release 并上传更新 ZIP 与 SHA-256。

管理员在系统设置的“软件在线更新”中检查 Release。安装需要任一超级管理员账号、密码和确认口令 `确认更新系统`。更新前会创建数据库备份；如替换、依赖安装或健康检查失败，独立更新器会尝试回滚程序文件和更新前数据库副本。

## 本地数据边界

更新器只替换程序白名单。`.env`、`data`、`storage`、`exports`、`backups`、`models`、`tools`、`resource`、`run` 和 `.venv` 始终保留在本机。不要把任何令牌写入提交内容；私有仓库令牌只应通过超级管理员页面保存，系统会加密后存储在本地数据库。
