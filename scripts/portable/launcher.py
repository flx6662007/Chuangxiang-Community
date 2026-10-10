"""Double-click entry point for an isolated, loopback-only review package.

Build: pyinstaller --clean --onefile --windowed --name 启动创享 launcher.py
Development: python launcher.py --package-root <unpacked review package>
Only the Python standard library is used by the launcher. Django lives in runtime/.
"""

from __future__ import annotations

import argparse
import atexit
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


APP_NAME = "创享社区 · 评审演示"
HEALTH_PATH = "/api/portable/health/"
DEMO_PASSWORD = "ReviewDemo!2026"
DEMO_EMAILS = ("cx.review.a@tongji.edu.cn", "cx.review.b@tongji.edu.cn")
ENV_KEYS = frozenset({
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "DEEPSEEK_PROXY_URL", "DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_MAX_OUTPUT_TOKENS",
})
SYSTEM_ENV_KEYS = frozenset({
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "PATH",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "SYSTEMDRIVE",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL",
})


class LauncherError(Exception):
    """A safe, user-facing error; never contains raw subprocess output."""


class Cancelled(Exception):
    pass


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def atomic_text(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + secrets.token_hex(6) + ".tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_review_env(path):
    """Read this package's explicit AI configuration, without dotenv discovery."""
    path = Path(path)
    if not path.exists():
        return {}
    values = {}
    for number, source in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = source.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if key not in ENV_KEYS:
            continue
        if not sep:
            raise LauncherError(f"review.env 第 {number} 行格式错误，请通过 AI 配置重新保存。")
        value = value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                raise LauncherError(f"review.env 第 {number} 行引号格式错误。") from None
        elif value.startswith("'"):
            if not value.endswith("'") or len(value) < 2:
                raise LauncherError(f"review.env 第 {number} 行引号格式错误。")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if not isinstance(value, str) or any(c in value for c in "\r\n\0"):
            raise LauncherError(f"review.env 第 {number} 行须为单行文本。")
        values[key] = value
    return values


def save_review_env(path, values):
    lines = ["# 私有评审 AI 配置。请勿提交版本库或公开发布。"]
    for key in sorted(ENV_KEYS):
        if key in values:
            value = values[key].strip()
            if any(c in value for c in "\r\n\0"):
                raise LauncherError("AI 配置必须使用单行文本。")
            lines.append(f"{key}={json.dumps(value, ensure_ascii=False)}")
    atomic_text(path, "\n".join(lines) + "\n")


def package_identity(root):
    manifest = root / "portable-manifest.json"
    if manifest.exists():
        try:
            identity = json.loads(manifest.read_text(encoding="utf-8-sig"))["package_id"]
        except (OSError, ValueError, KeyError, TypeError):
            raise LauncherError("评审包 portable-manifest.json 缺少有效 package_id。") from None
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", identity):
            raise LauncherError("评审包 package_id 格式错误。")
        return identity
    return "review-" + hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()[:20]


def choose_data_dir(root, identity):
    local = os.environ.get("LOCALAPPDATA")
    candidates = ([Path(local) / "ChuangxiangReview" / identity] if local else [])
    candidates.append(root / "user-data" / identity)
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / (".write-test-" + secrets.token_hex(6))
            probe.write_bytes(b"")
            probe.unlink()
            return candidate.resolve()
        except OSError:
            continue
    raise LauncherError("无法建立演示数据目录。请把评审包解压到有写入权限的文件夹。")


class InstanceLock:
    """An OS-released lock: a stale PID file can never cause another process to die."""

    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is None:
            return
        self.handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()
        self.handle = None


class WindowsChildJob:
    """Ask Windows to stop our children even if the launcher crashes."""

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinWorkingSet", ctypes.c_size_t),
                        ("MaxWorkingSet", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("Basic", BasicLimits), ("IO", IOCounters),
                        ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
                        ("PeakProcessMemory", ctypes.c_size_t), ("PeakJobMemory", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise LauncherError("Windows 无法建立演示进程保护，请重新启动启动器。")

    def add(self, process):
        if self.handle and not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            process.terminate()
            process.wait(timeout=10)
            raise LauncherError("Windows 无法保护演示服务进程，请重新启动启动器。")

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def choose_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def external_python_dll_directory():
    """Do not inject PyInstaller's temporary DLL directory into bundled Python."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetDllDirectoryW.argtypes = (wintypes.DWORD, wintypes.LPWSTR)
    api.GetDllDirectoryW.restype = wintypes.DWORD
    api.SetDllDirectoryW.argtypes = (wintypes.LPCWSTR,)
    api.SetDllDirectoryW.restype = wintypes.BOOL
    length = api.GetDllDirectoryW(0, None)
    buffer = ctypes.create_unicode_buffer(length + 1)
    api.GetDllDirectoryW(len(buffer), buffer)
    previous = buffer.value
    if not api.SetDllDirectoryW(None):
        raise LauncherError("无法初始化便携 Python 的 DLL 路径，请重新启动启动器。")
    try:
        yield
    finally:
        api.SetDllDirectoryW(previous or None)


def is_healthy(state, identity):
    if not isinstance(state, dict) or state.get("package_id") != identity:
        return False
    port = state.get("port")
    token = state.get("instance_token")
    if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(token, str) or len(token) < 32:
        return False
    try:
        # Explicitly bypass machine proxy settings, including for localhost.
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}{HEALTH_PATH}", timeout=1) as response:
            payload = json.loads(response.read(16385))
        return (payload.get("status") == "ok" and payload.get("package_id") == identity
                and secrets.compare_digest(str(payload.get("instance_token", "")), token))
    except (URLError, OSError, ValueError, TypeError, AttributeError):
        return False


def build_child_env(root, data_dir, identity, port, secret, token, values):
    env = {key: value for key, value in os.environ.items() if key.upper() in SYSTEM_ENV_KEYS}
    env.update({
        "DJANGO_SETTINGS_MODULE": "config.portable_settings",
        "PORTABLE_DATA_DIR": str(data_dir),
        "PORTABLE_FRONTEND_DIST": str(root / "app" / "frontend"),
        "PORTABLE_PACKAGE_ROOT": str(root),
        "PORTABLE_PACKAGE_ID": identity,
        "PORTABLE_PORT": str(port),
        "PORTABLE_SECRET_KEY": secret,
        "PORTABLE_INSTANCE_TOKEN": token,
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
    for key in ENV_KEYS:
        env["PORTABLE_" + key] = values.get(key, "")
    # Preserve backend defaults for optional parameters when they are not specified.
    for key in ENV_KEYS - {"DEEPSEEK_API_KEY"}:
        if not env["PORTABLE_" + key]:
            del env["PORTABLE_" + key]
    return env


CREATE_DEMO_USERS = '''
from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress
User = get_user_model()
with transaction.atomic():
    for pk, email in enumerate(("cx.review.a@tongji.edu.cn", "cx.review.b@tongji.edu.cn"), 1):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            user = User.objects.create_user(pk=pk, email=email, password="ReviewDemo!2026", wechat_id="cx_demo_" + str(pk))
        elif user.email != email:
            raise RuntimeError("Demo account identity conflict")
        EmailAddress.objects.update_or_create(user=user, email=email, defaults={"verified": True, "primary": True})
'''


class Controller:
    def __init__(self, root, emit):
        self.root = root.resolve()
        self.identity = package_identity(self.root)
        self.data_dir = choose_data_dir(self.root, self.identity)
        self.emit = emit
        self.lock = InstanceLock(self.data_dir / "launcher.lock")
        self.state_path = self.data_dir / "instance.json"
        self.log_path = self.data_dir / "launcher.log"
        self.cancel = threading.Event()
        self.process_guard = threading.Lock()
        self.process = None
        self.job = None
        self.state = None
        self.values = {}
        self.redacted_values = set()
        self.log_guard = threading.Lock()

    def log(self, message):
        # Raw settings, environments, keys and HTTP authorization must not enter logs.
        for value in sorted(self.redacted_values, key=len, reverse=True):
            if value:
                message = message.replace(value, "[已隐藏]")
        message = re.sub(r"(?i)(api[_-]?key|authorization|secret[_-]?key)(\s*[:=]\s*)[^\r\n]+", r"\1\2[已隐藏]", message)
        with self.log_guard:
            if self.log_path.exists() and self.log_path.stat().st_size > 2_000_000:
                self.log_path.write_text("", encoding="utf-8")
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(message.rstrip() + "\n")

    def start_child(self, arguments, env):
        with self.process_guard:
            if self.cancel.is_set():
                raise Cancelled()
            python = self.root / "runtime" / ("python.exe" if os.name == "nt" else "bin/python3")
            if not python.exists():
                raise LauncherError("评审包缺少 runtime/python.exe，请完整解压评审包后再启动。")
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            # Argument lists avoid shell quoting or command injection. No shell or terminal is opened.
            with external_python_dll_directory():
                process = subprocess.Popen(
                    [str(python), str(self.root / "app" / "backend" / "manage.py"), *arguments],
                    cwd=self.root / "app" / "backend", env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding="utf-8", errors="replace", **options,
                )
            self.process = process
            self.job.add(process)
            return process

    def command(self, arguments, env, label):
        self.emit("status", label)
        process = self.start_child(arguments, env)
        output, _ = process.communicate()
        if output:
            self.log(output)
        if self.cancel.is_set():
            raise Cancelled()
        if process.returncode:
            raise LauncherError(f"{label}失败。可使用“查看日志”查看已隐藏密钥的诊断信息。")

    def read_state(self):
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def acquire_or_reuse(self):
        for _ in range(600):
            if self.cancel.is_set():
                raise Cancelled()
            if self.lock.acquire():
                return True
            state = self.read_state()
            if is_healthy(state, self.identity):
                self.emit("reused", f"http://127.0.0.1:{state['port']}/")
                return False
            self.emit("status", "已有启动器正在准备演示，正在等待服务…")
            self.cancel.wait(0.5)
        raise LauncherError("已有启动器仍在准备或已停止响应。请检查已打开的启动窗口后重试。")

    def run(self):
        try:
            if not self.acquire_or_reuse():
                return
            self.job = WindowsChildJob()
            for path in (self.root / "app/backend/manage.py", self.root / "app/frontend/index.html", self.root / "data/public-fixture.json"):
                if not path.is_file():
                    raise LauncherError(f"评审包缺少 {path.relative_to(self.root)}，请完整解压评审包。")
            self.values = read_review_env(self.root / "review.env")
            self.emit("ai", "已配置 AI 密钥（联网调用）" if self.values.get("DEEPSEEK_API_KEY") else "未配置 AI 密钥；可浏览资料，AI 对话需配置")
            secret_path = self.data_dir / "django-secret.txt"
            if not secret_path.exists():
                atomic_text(secret_path, secrets.token_urlsafe(48))
            secret = secret_path.read_text(encoding="utf-8").strip()
            if len(secret) < 40:
                raise LauncherError("本地服务密钥文件无效，请检查演示数据目录中的 django-secret.txt。")
            token = secrets.token_urlsafe(32)
            self.redacted_values.update((secret, token, self.values.get("DEEPSEEK_API_KEY", ""), self.values.get("DEEPSEEK_PROXY_URL", "")))
            port = choose_port()
            env = build_child_env(self.root, self.data_dir, self.identity, port, secret, token, self.values)
            self.state = {"package_id": self.identity, "port": port, "instance_token": token, "status": "starting"}
            atomic_json(self.state_path, self.state)
            self.command(["migrate", "--noinput"], env, "正在准备本地数据库（首次约需 1–3 分钟）")
            # pk=1 is the synthetic author of public document revisions in the fixture.
            self.command(["shell", "--command", CREATE_DEMO_USERS], env, "正在准备两个专用演示账号")
            marker = self.data_dir / "public-data-loaded.json"
            if not marker.exists():
                self.command(["loaddata", str(self.root / "data/public-fixture.json")], env, "正在导入公开演示资料")
                atomic_json(marker, {"package_id": self.identity, "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            self.emit("status", "正在启动本机服务…")
            self.serve(env)
        except Cancelled:
            pass
        except LauncherError as error:
            self.emit("error", str(error))
        except Exception as error:
            # Exception strings can contain credentials. Keep unexpected diagnostics type-only.
            self.log("Unexpected launcher error: " + type(error).__name__)
            self.emit("error", "启动未完成，请确认评审包完整且位于可读取的目录。可使用“查看日志”查看诊断信息。")
        finally:
            self.stop_children()
            if self.lock.handle is not None:
                if self.read_state().get("instance_token") == (self.state or {}).get("instance_token"):
                    self.state_path.unlink(missing_ok=True)
                self.lock.close()
            self.emit("finished", "")

    def serve(self, env):
        # A free-port race can only fail this child; retry another ephemeral loopback port.
        for attempt in range(3):
            port = int(env["PORTABLE_PORT"])
            process = self.start_child(["runserver", f"127.0.0.1:{port}", "--noreload", "--nothreading"], env)
            reader = threading.Thread(target=self.drain_output, args=(process,), daemon=True)
            reader.start()
            deadline = time.monotonic() + 90
            while not self.cancel.is_set() and time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                if is_healthy(self.state, self.identity):
                    self.state["status"] = "ready"
                    atomic_json(self.state_path, self.state)
                    self.emit("ready", f"http://127.0.0.1:{port}/")
                    while not self.cancel.wait(0.5):
                        if process.poll() is not None:
                            raise LauncherError("演示服务意外退出。请查看日志后重新启动。")
                    raise Cancelled()
                self.cancel.wait(0.2)
            self.terminate_process(process)
            reader.join(timeout=2)
            if self.cancel.is_set():
                raise Cancelled()
            env["PORTABLE_PORT"] = str(choose_port())
            self.state["port"] = int(env["PORTABLE_PORT"])
            atomic_json(self.state_path, self.state)
        raise LauncherError("本机服务未能启动。请查看日志确认评审包依赖完整。")

    def drain_output(self, process):
        for line in process.stdout:
            self.log(line)

    @staticmethod
    def terminate_process(process):
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            except OSError:
                pass

    def stop_children(self):
        with self.process_guard:
            self.terminate_process(self.process)
            if self.job:
                self.job.close()
                self.job = None

    def request_stop(self):
        self.cancel.set()
        self.stop_children()


class LauncherWindow:
    def __init__(self, root_path):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.window = tk.Tk()
        self.window.title(APP_NAME)
        self.window.geometry("610x390")
        self.window.minsize(560, 370)
        self.window.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.events = queue.Queue()
        self.controller = Controller(root_path, lambda kind, text: self.events.put((kind, text)))
        self.url = ""
        self.closing = False
        self.done = False
        self.status = tk.StringVar(value="正在准备启动…")
        self.ai = tk.StringVar(value="正在检查 AI 配置…")
        self.address = tk.StringVar(value="服务仅在这台电脑的 127.0.0.1 上运行。")
        frame = ttk.Frame(self.window, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="创享社区", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w")
        ttk.Label(frame, text="本机评审演示", foreground="#666666").pack(anchor="w", pady=(0, 18))
        ttk.Label(frame, textvariable=self.status, wraplength=545).pack(anchor="w")
        ttk.Label(frame, textvariable=self.address, wraplength=545).pack(anchor="w", pady=(10, 12))
        ttk.Label(frame, textvariable=self.ai, wraplength=545).pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(20, 10))
        self.open_button = ttk.Button(buttons, text="打开演示页面", command=self.open_page, state="disabled")
        self.open_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="演示账号", command=self.show_accounts).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="AI 配置", command=self.configure_ai).pack(side="left")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", side="bottom")
        ttk.Button(bottom, text="查看日志", command=self.open_log).pack(side="left")
        ttk.Button(bottom, text="停止并退出", command=self.close).pack(side="right")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.worker = threading.Thread(target=self.controller.run, daemon=True)
        atexit.register(self.controller.request_stop)
        self.worker.start()
        self.window.after(100, self.poll)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind in ("status", "error"):
                    self.status.set(value)
                elif kind == "ai":
                    self.ai.set(value)
                elif kind in ("ready", "reused"):
                    self.url = value
                    self.status.set("演示已启动。关闭此窗口将停止本次演示服务。")
                    self.address.set(value)
                    self.open_button.configure(state="normal")
                    self.open_page()
                    if kind == "reused":
                        self.status.set("已打开正在运行的演示；本窗口即将关闭。")
                        self.window.after(800, self.window.destroy)
                        return
                elif kind == "finished":
                    self.done = True
                    if not self.closing:
                        self.open_button.configure(state="disabled")
        except queue.Empty:
            pass
        if self.closing and not self.worker.is_alive():
            self.window.destroy()
            return
        self.window.after(100, self.poll)

    def open_page(self):
        if self.url:
            webbrowser.open(self.url)

    def open_log(self):
        if not self.controller.log_path.exists():
            self.controller.log("启动器尚未产生服务日志。")
        if os.name == "nt":
            os.startfile(str(self.controller.log_path))
        else:
            webbrowser.open(self.controller.log_path.as_uri())

    def show_accounts(self):
        window = self.tk.Toplevel(self.window)
        window.title("专用演示账号")
        frame = self.ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        self.ttk.Label(frame, text="以下为本地生成的示例账号，均已完成演示邮箱验证。\n微信号 cx_demo_1 / cx_demo_2 也是示例数据，不会发送真实邮件。\n可用不同浏览器分别登录两个账号。", wraplength=480).pack(anchor="w", pady=(0, 12))
        for label, value in (("账号 A", DEMO_EMAILS[0]), ("账号 B", DEMO_EMAILS[1]), ("共同密码", DEMO_PASSWORD)):
            self.ttk.Label(frame, text=label).pack(anchor="w")
            entry = self.ttk.Entry(frame, width=48)
            entry.insert(0, value)
            entry.configure(state="readonly")
            entry.pack(fill="x", pady=(3, 10))
        self.ttk.Button(frame, text="关闭", command=window.destroy).pack(anchor="e")

    def configure_ai(self):
        from tkinter import messagebox
        try:
            values = read_review_env(self.controller.root / "review.env")
        except (LauncherError, OSError):
            values = {}
        window = self.tk.Toplevel(self.window)
        window.title("AI 配置（保存在本包 review.env）")
        frame = self.ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        self.ttk.Label(frame, text="仅保存到本评审包的私有 review.env。保存后请重新启动启动器。\n未配置密钥时，仍可浏览资料并体验演示账号。", wraplength=490).pack(anchor="w", pady=(0, 12))
        fields = {}
        for key, label, default in (("DEEPSEEK_API_KEY", "API 密钥", ""), ("DEEPSEEK_BASE_URL", "API 地址", "https://api.deepseek.com"), ("DEEPSEEK_MODEL", "模型名称", "deepseek-flash"), ("DEEPSEEK_PROXY_URL", "代理地址（可选）", "")):
            self.ttk.Label(frame, text=label).pack(anchor="w")
            field = self.tk.StringVar(value=values.get(key, default))
            self.ttk.Entry(frame, textvariable=field, width=58, show="●" if key == "DEEPSEEK_API_KEY" else "").pack(fill="x", pady=(3, 10))
            fields[key] = field

        def save():
            values.update({key: field.get() for key, field in fields.items()})
            try:
                save_review_env(self.controller.root / "review.env", values)
            except (OSError, LauncherError):
                messagebox.showerror("保存失败", "无法保存 review.env，请确认包目录可写且输入为单行文本。", parent=window)
                return
            self.ai.set("AI 配置已保存；关闭窗口并重新双击启动器后生效")
            window.destroy()

        self.ttk.Button(frame, text="保存配置", command=save).pack(anchor="e")

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.status.set("正在停止本次演示服务…")
        self.open_button.configure(state="disabled")
        threading.Thread(target=self.controller.request_stop, daemon=True).start()

    def run(self):
        self.window.mainloop()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--package-root", type=Path, help="已解压评审包目录（开发调试）")
    args = parser.parse_args()
    package_root = args.package_root or (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2])
    try:
        LauncherWindow(package_root).run()
    except Exception as error:
        # A native message box still works if Tk itself could not initialize.
        message = str(error) if isinstance(error, LauncherError) else "启动器无法打开。请完整解压评审包后重试。"
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        else:
            print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
