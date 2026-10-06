"""Local desktop control center for Student Management System."""

from __future__ import annotations

import json
import os
import queue
import getpass
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
RUN = ROOT / "run"
VERSION_FILE = ROOT / "VERSION"
REPOSITORY = "Star-Moon10/Student-Management-System"
PORT = 8100

BG = "#111522"
SIDEBAR = "#151b2a"
PANEL = "#202536"
PANEL_ALT = "#252b3e"
LINE = "#3a4258"
TEXT = "#f5f7ff"
MUTED = "#9ca7c5"
BLUE = "#8ca7ff"
GREEN = "#68e6bb"
AMBER = "#f1c36f"
RED = "#ef888c"


def read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "未知"


def is_running() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8")).get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def run_command(command: list[str], output: queue.Queue[str] | None = None) -> subprocess.Popen:
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if output is not None and process.stdout:
        def read_output() -> None:
            for line in process.stdout:
                output.put(line.rstrip())
            output.put(f"[process exited: {process.wait()}]")
        threading.Thread(target=read_output, daemon=True).start()
    return process


class ControlCenter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("学籍档案 · 本地控制中心")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(bg=BG)
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.current_page = "概览"
        self.log_source = "服务日志"
        self.auto_refresh_logs = True
        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self._build_styles()
        self._build_shell()
        self._show_page("概览")
        self.after(600, self._poll)
        self.after(1000, self._refresh_status)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Glass.TEntry", fieldbackground="#2a3042", foreground=TEXT, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("Glass.TCombobox", fieldbackground="#2a3042", foreground=TEXT, bordercolor=LINE, arrowcolor=MUTED)
        style.configure("Glass.Horizontal.TProgressbar", troughcolor="#30374d", background=BLUE, bordercolor="#30374d", lightcolor=BLUE, darkcolor=BLUE)

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=236)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="学籍档案", bg=SIDEBAR, fg=TEXT, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w", padx=32, pady=(30, 0))
        tk.Label(self.sidebar, text="LOCAL CONTROL CENTER", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=34, pady=(3, 40))
        for name, mark in (("概览", "01"), ("安装与修复", "02"), ("日志", "03"), ("诊断", "04"), ("设置", "05")):
            button = tk.Button(self.sidebar, text=f"{name:<8} {mark}", anchor="w", command=lambda item=name: self._show_page(item), bg=SIDEBAR, fg=MUTED, activebackground="#303657", activeforeground=TEXT, relief="flat", bd=0, font=("Microsoft YaHei UI", 12), padx=28, pady=14, cursor="hand2")
            button.pack(fill="x", padx=16, pady=2)
            self.nav_buttons[name] = button
        tk.Frame(self.sidebar, bg=LINE, height=1).pack(fill="x", padx=32, pady=(64, 24))
        tk.Label(self.sidebar, text="当前实例", bg=SIDEBAR, fg=MUTED, font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=32)
        tk.Label(self.sidebar, text="Student Management", bg=SIDEBAR, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=32, pady=(10, 4))
        self.sidebar_status = tk.Label(self.sidebar, text="● 本地服务检查中", bg=SIDEBAR, fg=GREEN, font=("Microsoft YaHei UI", 10))
        self.sidebar_status.pack(anchor="w", padx=32)

        self.workspace = tk.Frame(self, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)
        header = tk.Frame(self.workspace, bg=BG, height=96)
        header.pack(fill="x")
        header.pack_propagate(False)
        left = tk.Frame(header, bg=BG)
        left.pack(side="left", padx=34, pady=26)
        self.eyebrow = tk.Label(left, text="控制中心", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10, "bold"))
        self.eyebrow.pack(anchor="w")
        self.page_title = tk.Label(left, text="概览", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 25, "bold"))
        self.page_title.pack(anchor="w", pady=(3, 0))
        self.header_status = tk.Label(header, text=f"v{read_version()}  ● 正常", bg="#1f3b38", fg=GREEN, font=("Microsoft YaHei UI", 10, "bold"), padx=14, pady=7)
        self.header_status.pack(side="right", padx=34, pady=32)
        self.content = tk.Frame(self.workspace, bg=BG)
        self.content.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        self._create_pages()

    def _panel(self, parent, **kwargs):
        return tk.Frame(parent, bg=kwargs.pop("bg", PANEL), highlightbackground=kwargs.pop("highlightbackground", LINE), highlightthickness=1, bd=0, **kwargs)

    def _label(self, parent, text_value, size=12, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text_value, bg=parent.cget("bg"), fg=color, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"), **kwargs)

    def _button(self, parent, text_value, command, accent=False, **kwargs):
        return tk.Button(parent, text=text_value, command=command, bg=BLUE if accent else PANEL_ALT, fg="#10152b" if accent else TEXT, activebackground="#abc0ff" if accent else "#39425e", activeforeground="#10152b" if accent else TEXT, relief="flat", bd=0, cursor="hand2", font=("Microsoft YaHei UI", 11, "bold"), padx=18, pady=10, **kwargs)

    def _create_pages(self) -> None:
        self.pages["概览"] = self._create_overview()
        self.pages["安装与修复"] = self._create_install()
        self.pages["日志"] = self._create_logs()
        self.pages["诊断"] = self._create_diagnostics()
        self.pages["设置"] = self._create_settings()

    def _create_overview(self):
        page = tk.Frame(self.content, bg=BG)
        hero = self._panel(page, height=190)
        hero.pack(fill="x", pady=(0, 18))
        hero.pack_propagate(False)
        inner = tk.Frame(hero, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=24, pady=22)
        status_column = tk.Frame(inner, bg=PANEL)
        status_column.pack(side="left", fill="both", expand=True)
        self._label(status_column, "系统状态", 12, MUTED, True).pack(anchor="w")
        self.overview_status = self._label(status_column, "服务运行中", 28, GREEN, True)
        self.overview_status.pack(anchor="w", pady=(8, 2))
        self.overview_detail = self._label(status_column, "学生学籍管理平台 · 本地服务状态良好", 12, MUTED)
        self.overview_detail.pack(anchor="w")
        actions = tk.Frame(inner, bg=PANEL)
        actions.pack(side="right", fill="y", padx=(20, 0))
        self._label(actions, "本地服务", 10, MUTED, True).pack(anchor="e")
        self._button(actions, "打开主系统  ↗", self.open_dashboard, accent=True).pack(anchor="e", pady=(18, 0))

        health = tk.Frame(page, bg=BG)
        health.pack(fill="x", pady=(0, 18))
        self.health_vars = {}
        for index, (key, label, color) in enumerate((("service", "服务状态", GREEN), ("database", "数据库", BLUE), ("ai", "AI 运行环境", GREEN), ("backup", "备份", AMBER))):
            card = self._panel(health, width=220, height=104)
            card.pack(side="left", fill="both", expand=True, padx=(0 if index == 0 else 8, 8 if index < 3 else 0))
            card.pack_propagate(False)
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x", padx=20, pady=(18, 0))
            tk.Label(top, text="●", bg=PANEL, fg=color, font=("Segoe UI", 16)).pack(side="left")
            self._label(top, label, 11, MUTED, True).pack(side="left", padx=(7, 0))
            value = self._label(card, "检查中", 18, TEXT, True)
            value.pack(anchor="w", padx=20, pady=(11, 0))
            self.health_vars[key] = value

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True)
        queue_panel = self._panel(lower)
        queue_panel.pack(side="left", fill="both", expand=True, padx=(0, 9))
        self._label(queue_panel, "执行队列", 17, TEXT, True).pack(anchor="w", padx=24, pady=(22, 4))
        self._label(queue_panel, "最近后台任务与平台动作", 11, MUTED).pack(anchor="w", padx=24, pady=(0, 14))
        for label, state, color in (("数据库备份任务", "已完成", GREEN), ("学籍数据同步", "已完成", GREEN), ("AI 学籍信息校验", "准备中", BLUE), ("导入新生数据", "等待中", AMBER)):
            row = tk.Frame(queue_panel, bg="#282e40")
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text="●", bg="#282e40", fg=color, font=("Segoe UI", 13)).pack(side="left", padx=(12, 4), pady=7)
            self._label(row, label, 11, TEXT, True).pack(side="left", pady=7)
            self._label(row, state, 10, color, True).pack(side="right", padx=12, pady=7)
        controls = self._panel(lower, width=310)
        controls.pack(side="right", fill="y")
        self._label(controls, "服务控制", 17, TEXT, True).pack(anchor="w", padx=24, pady=(22, 4))
        self._label(controls, "本地服务 · 可安全操作", 11, MUTED).pack(anchor="w", padx=24, pady=(0, 16))
        self._button(controls, "▶  启动服务", self.start_service, accent=True).pack(fill="x", padx=24, pady=5)
        self._button(controls, "↻  重启服务", self.restart_service).pack(fill="x", padx=24, pady=5)
        self._button(controls, "■  停止服务", self.stop_service).pack(fill="x", padx=24, pady=5)
        return page

    def _create_install(self):
        page = tk.Frame(self.content, bg=BG)
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        self._label(panel, "安装与修复", 22, TEXT, True).pack(anchor="w", padx=28, pady=(26, 4))
        self._label(panel, "初始化环境、修复依赖或重新检查本地服务。", 12, MUTED).pack(anchor="w", padx=28, pady=(0, 22))
        self.install_log = scrolledtext.ScrolledText(panel, bg="#151a29", fg="#d7def7", insertbackground=TEXT, relief="flat", bd=0, font=("Cascadia Mono", 10), height=20)
        self.install_log.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        buttons = tk.Frame(panel, bg=PANEL)
        buttons.pack(fill="x", padx=28, pady=(0, 24))
        self._button(buttons, "运行安装 / 修复", self.run_setup, accent=True).pack(side="left")
        self._button(buttons, "初始化数据库", self.init_database).pack(side="left", padx=10)
        return page

    def _create_logs(self):
        page = tk.Frame(self.content, bg=BG)
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(0, 12))
        self.log_choice = ttk.Combobox(bar, values=["服务日志", "AI 日志", "更新状态"], state="readonly", width=18)
        self.log_choice.set("服务日志")
        self.log_choice.pack(side="left")
        self.log_choice.bind("<<ComboboxSelected>>", lambda _: self.refresh_logs())
        self.auto_logs = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="自动刷新", variable=self.auto_logs, bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT, selectcolor=PANEL, font=("Microsoft YaHei UI", 10)).pack(side="left", padx=16)
        self._button(bar, "清空显示", lambda: self.log_view.delete("1.0", "end")).pack(side="right")
        self.log_view = scrolledtext.ScrolledText(page, bg="#151a29", fg="#cbd5f1", insertbackground=TEXT, relief="flat", bd=0, font=("Cascadia Mono", 10))
        self.log_view.pack(fill="both", expand=True)
        return page

    def _create_diagnostics(self):
        page = tk.Frame(self.content, bg=BG)
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        self._label(panel, "诊断", 22, TEXT, True).pack(anchor="w", padx=28, pady=(26, 4))
        self._label(panel, "快速检查运行环境、端口、数据库和 AI 服务。", 12, MUTED).pack(anchor="w", padx=28, pady=(0, 24))
        self.diag_rows = {}
        for key, label in (("python", "Python 环境"), ("port", "8100 服务端口"), ("database", "数据库"), ("ai", "AI 服务"), ("backup", "最近备份")):
            row = tk.Frame(panel, bg="#282e40")
            row.pack(fill="x", padx=28, pady=5)
            self._label(row, label, 12, TEXT, True).pack(side="left", padx=16, pady=12)
            status = self._label(row, "未检查", 11, MUTED, True)
            status.pack(side="right", padx=16, pady=12)
            self.diag_rows[key] = status
        self._button(panel, "重新检查", self.refresh_diagnostics, accent=True).pack(anchor="w", padx=28, pady=22)
        return page

    def _create_settings(self):
        page = tk.Frame(self.content, bg=BG)
        panel = self._panel(page)
        panel.pack(fill="both", expand=True)
        self._label(panel, "设置", 22, TEXT, True).pack(anchor="w", padx=28, pady=(26, 4))
        self._label(panel, "桌面控制中心的启动行为和本地服务偏好。", 12, MUTED).pack(anchor="w", padx=28, pady=(0, 22))
        self.launch_browser = tk.BooleanVar(value=True)
        self.start_ai = tk.BooleanVar(value=True)
        for variable, label in ((self.launch_browser, "服务启动后打开主系统"), (self.start_ai, "启动平台时尝试启动本地 AI")):
            tk.Checkbutton(panel, text=label, variable=variable, bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=TEXT, selectcolor="#303657", font=("Microsoft YaHei UI", 12)).pack(anchor="w", padx=28, pady=8)
        self._label(panel, "项目目录", 11, MUTED, True).pack(anchor="w", padx=28, pady=(24, 4))
        self._label(panel, str(ROOT), 11, TEXT).pack(anchor="w", padx=28)
        self._label(panel, "控制中心更新", 11, MUTED, True).pack(anchor="w", padx=28, pady=(24, 4))
        self.update_status = self._label(panel, "在线更新将在桌面控制中心执行", 11, GREEN)
        self.update_status.pack(anchor="w", padx=28)
        self._button(panel, "检查软件更新", self.check_update, accent=True).pack(anchor="w", padx=28, pady=18)
        self.update_progress = ttk.Progressbar(panel, mode="determinate", maximum=100, style="Glass.Horizontal.TProgressbar")
        self.update_progress.pack(fill="x", padx=28, pady=(0, 6))
        self.update_progress.pack_forget()
        return page

    def _show_page(self, name: str) -> None:
        self.current_page = name
        self.page_title.configure(text=name)
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            button.configure(bg="#303657" if key == name else SIDEBAR, fg=TEXT if key == name else MUTED)
        if name == "日志":
            self.refresh_logs()
        if name == "诊断":
            self.refresh_diagnostics()

    def _run_script(self, script_name: str, log_target=None) -> None:
        if os.name == "nt":
            command = ["cmd", "/c", str(ROOT / script_name)]
        else:
            command = ["bash", str(ROOT / script_name)]
        run_command(command, self.output_queue if log_target is not None else None)

    def start_service(self):
        self._run_script("start-system.bat" if os.name == "nt" else "start-system.sh")

    def stop_service(self):
        self._run_script("stop-system.bat" if os.name == "nt" else "stop-system.sh")

    def restart_service(self):
        self.stop_service()
        self.after(1200, self.start_service)

    def open_dashboard(self):
        webbrowser.open(f"http://127.0.0.1:{PORT}")

    def run_setup(self):
        script = "setup.bat" if os.name == "nt" else "setup.sh"
        if os.name == "nt":
            self._run_script(script, self.install_log)
        else:
            self._run_script(script, self.install_log)

    def init_database(self):
        python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
        run_command([str(python), "-c", "from app.db import init_db; init_db()"], self.output_queue)

    def refresh_logs(self):
        sources = {"服务日志": RUN / "server.log", "AI 日志": RUN / "ollama.log", "更新状态": RUN / "update-status.json"}
        path = sources.get(self.log_choice.get(), sources["服务日志"])
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[-30000:]
        except OSError:
            content = "暂无日志。"
        self.log_view.delete("1.0", "end")
        self.log_view.insert("end", content)
        self.log_view.see("end")

    def refresh_diagnostics(self):
        self.diag_rows["python"].configure(text=sys.version.split()[0], fg=GREEN)
        online = is_running()
        self.diag_rows["port"].configure(text="正常" if online else "未运行", fg=GREEN if online else AMBER)
        self.diag_rows["database"].configure(text="已配置", fg=GREEN if (ROOT / "data").exists() else AMBER)
        self.diag_rows["ai"].configure(text="可用" if (RUN / "ollama.pid").exists() else "未启动", fg=GREEN if (RUN / "ollama.pid").exists() else AMBER)
        self.diag_rows["backup"].configure(text="已配置" if (ROOT / "backups").exists() else "未配置", fg=GREEN if (ROOT / "backups").exists() else AMBER)

    def check_update(self):
        self.update_status.configure(text="正在检查 GitHub Release…", fg=BLUE)
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _project_python(self) -> Path:
        return ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")

    def _check_update_worker(self) -> None:
        process = subprocess.run([str(self._project_python()), "desktop/control_cli.py", "check"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            payload = json.loads(process.stdout or "{}")
        except json.JSONDecodeError:
            payload = {"configured": False, "message": process.stderr or "更新检查失败"}
        self.after(0, lambda: self._handle_update_check(payload))

    def _handle_update_check(self, payload: dict) -> None:
        release = payload.get("release") or {}
        if not release.get("update_ready"):
            self.update_status.configure(text=payload.get("message") or "没有可用更新", fg=MUTED)
            return
        if not release.get("is_newer"):
            self.update_status.configure(text=f"当前已是最新版本（{payload.get('current_version', read_version())}）", fg=GREEN)
            return
        target = release.get("tag_name") or "新版本"
        if not messagebox.askyesno("发现更新", f"发现 {target}，是否现在安装？\n安装前会自动备份并重启服务。"):
            self.update_status.configure(text=f"已发现 {target}，等待安装", fg=AMBER)
            return
        username = simpledialog.askstring("超级管理员验证", "请输入超级管理员账号：", parent=self)
        if not username:
            return
        password = simpledialog.askstring("超级管理员验证", "请输入超级管理员密码：", show="*", parent=self)
        if not password:
            return
        self.update_progress.pack(fill="x", padx=28, pady=(0, 6))
        self.update_status.configure(text=f"正在启动 {target} 更新…", fg=BLUE)
        threading.Thread(target=self._update_worker, args=(username, password), daemon=True).start()

    def _update_worker(self, username: str, password: str) -> None:
        process = subprocess.Popen([str(self._project_python()), "desktop/control_cli.py", "update"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        stdout, _ = process.communicate(json.dumps({"username": username, "password": password}), timeout=30)
        try:
            result = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            result = {"ok": False, "error": stdout or "更新启动失败"}
        self.after(0, lambda: self._handle_update_started(result))

    def _handle_update_started(self, result: dict) -> None:
        if not result.get("ok"):
            self.update_progress.pack_forget()
            self.update_status.configure(text=result.get("error") or "更新启动失败", fg=RED)
            return
        self.update_status.configure(text=result.get("message") or "更新已启动", fg=BLUE)
        self._watch_update_status()

    def _watch_update_status(self) -> None:
        try:
            status = json.loads((RUN / "update-status.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            status = {}
        progress = max(0, min(100, int(status.get("progress") or 0)))
        self.update_progress["value"] = progress
        self.update_status.configure(text=f"{status.get('message') or '更新处理中'}  {progress}%", fg=GREEN if status.get("state") == "completed" else BLUE)
        if status.get("state") in {"completed", "failed", "rolled_back"}:
            if status.get("state") == "completed":
                self.update_status.configure(text="更新完成，服务将自动重启", fg=GREEN)
            return
        self.after(1000, self._watch_update_status)

    def _refresh_status(self):
        online = is_running()
        label = "● 服务运行中" if online else "● 服务已停止"
        color = GREEN if online else AMBER
        self.sidebar_status.configure(text=label, fg=color)
        self.header_status.configure(text=f"v{read_version()}  ● {'正常' if online else '已停止'}", fg=color)
        self.overview_status.configure(text="服务运行中" if online else "服务已停止", fg=GREEN if online else AMBER)
        self.overview_detail.configure(text="学生学籍管理平台 · 本地服务状态良好" if online else "学生学籍管理平台 · 等待启动服务")
        self.health_vars["service"].configure(text="运行中" if online else "已停止", fg=GREEN if online else AMBER)
        self.health_vars["database"].configure(text="SQLite · 正常" if (ROOT / "data").exists() else "未初始化", fg=GREEN if (ROOT / "data").exists() else AMBER)
        self.health_vars["ai"].configure(text="Ollama · 可用" if (RUN / "ollama.pid").exists() else "未启动", fg=GREEN if (RUN / "ollama.pid").exists() else AMBER)
        self.health_vars["backup"].configure(text="已配置" if (ROOT / "backups").exists() else "未配置", fg=GREEN if (ROOT / "backups").exists() else AMBER)
        self.after(3000, self._refresh_status)

    def _poll(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if hasattr(self, "install_log"):
                    self.install_log.insert("end", line + "\n")
                    self.install_log.see("end")
        except queue.Empty:
            pass
        if getattr(self, "auto_logs", None) and self.auto_logs.get() and self.current_page == "日志":
            self.refresh_logs()
        self.after(1000, self._poll)


if __name__ == "__main__":
    app = ControlCenter()
    app.mainloop()
