# 本地控制中心

`launcher.py` 是学生档案平台的本地桌面控制中心，负责：

- 启动、停止和重启本地服务；
- 执行首次安装、依赖修复和数据库初始化；
- 查看服务、AI 和更新日志；
- 检查 Python、端口、数据库、AI 与备份状态；
- 通过本地桌面程序检查和安装软件更新。

它使用系统自带 Tkinter，不依赖浏览器或桌面网络框架。桌面更新会调用项目本地更新器，并要求超级管理员凭证。

## 构建 Windows EXE

先运行项目根目录的 `setup.bat`，然后执行：

```bat
desktop\build-launcher.bat
```

生成文件位于 `dist\StudentRecordsControlCenter.exe`。建议把 EXE 放在项目根目录中运行，这样它可以发现 `.env`、`.venv`、`run` 和更新脚本。
