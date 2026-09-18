"""Testable service lifecycle. Never terminate a process discovered by port/PID."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'tools' / 'database' / 'local' / 'desktop-assistant'
PORT = 5000
URL = f'http://127.0.0.1:{PORT}'


class AssistantError(RuntimeError):
    pass


def hidden_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def console_python():
    path = Path(sys.executable)
    return str(path.with_name('python.exe')) if path.name.lower() == 'pythonw.exe' else str(path)


class InstanceLock:
    """OS-owned lock; automatically released after crashes (no stale PID killing)."""
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('a+b')
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise AssistantError('桌面助手已经打开，请切换到现有助手窗口。') from None

    def close(self):
        self.file.close()


def require_free_port(port=PORT):
    with socket.socket() as probe:
        if os.name == 'nt':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise AssistantError(f'端口 {port} 已占用。请先在原启动窗口停止旧服务；助手不会强行结束它。') from None


def source_digest(root=ROOT):
    front = root / 'frontend'
    files = [front / name for name in ('package.json', 'package-lock.json', 'index.html', 'vite.config.js')]
    for directory in ('src', 'public'):
        files.extend(path for path in (front / directory).rglob('*') if path.is_file())
    # Vite environment files also affect output. Hash only, never log their values.
    files.extend(front.glob('.env*'))
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if path.is_file():
            digest.update(path.relative_to(front).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def check_runtime(python_exe, log):
    result = subprocess.run(
        [python_exe, '-X', 'utf8', '-m', 'desktop_assistant.service', '--check'],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=log, timeout=45, **hidden_options(),
    )
    try:
        payload = json.loads(result.stdout.decode('utf-8').strip())
    except (ValueError, UnicodeError):
        raise AssistantError('环境检查未完成，请查看运行日志。') from None
    if result.returncode or not payload.get('ok'):
        raise AssistantError(payload.get('error', '环境检查失败，请查看使用说明。'))
    return payload


def prepare_frontend(log, report, root=ROOT, local=LOCAL):
    fingerprint = source_digest(root)
    stamp = local / 'frontend.sha256'
    if (root / 'frontend/dist/index.html').is_file() and stamp.is_file() and stamp.read_text() == fingerprint:
        return
    node = shutil.which('node')
    vite = root / 'frontend/node_modules/vite/bin/vite.js'
    if not node or not vite.is_file():
        raise AssistantError('前端尚未准备好：请安装 Node.js，并按说明完成 npm ci。不会自动联网安装。')
    report('正在准备页面（首次或源码更新后约需数秒）…')
    env = dict(os.environ, VITE_API_BASE='/api')
    result = subprocess.run([node, str(vite), 'build'], cwd=root / 'frontend', env=env,
                            stdout=log, stderr=log, timeout=180, **hidden_options())
    if result.returncode or not (root / 'frontend/dist/index.html').is_file():
        raise AssistantError('页面构建失败，请查看日志；后端未启动。')
    stamp.write_text(fingerprint, encoding='ascii')


class Controller:
    def __init__(self, report=lambda message: None, port=PORT):
        self.report = report
        self.port = port
        self.url = f'http://127.0.0.1:{port}'
        self.process = None
        self.log = None
        self.instance = ''
        self.environment = {}

    def alive(self):
        return self.process is not None and self.process.poll() is None

    def ready(self):
        if not self.alive():
            return False
        try:
            # Bypass system HTTP proxies for local health checks.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(self.url + '/api/status/ready', timeout=2) as response:
                payload = json.load(response)
            return payload.get('status') == 'ready' and payload.get('instance') == self.instance
        except (OSError, ValueError):
            return False

    def start(self):
        if self.alive():
            return
        LOCAL.mkdir(parents=True, exist_ok=True)
        if self.log:
            self.log.close()
        # Separate runs for diagnostics; retention/archiving is explicit in the guide.
        self.log = (LOCAL / f'run-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}.log').open('ab', buffering=0)
        try:
            require_free_port(self.port)
            self.report('检查依赖、数据库连接与迁移版本…')
            python_exe = console_python()
            self.environment = check_runtime(python_exe, self.log)
            prepare_frontend(self.log, self.report)
            self.instance = uuid.uuid4().hex
            self.report('启动本机应用服务…')
            env = dict(os.environ, DESKTOP_INSTANCE_ID=self.instance, PYTHONIOENCODING='utf-8')
            self.process = subprocess.Popen(
                [python_exe, '-X', 'utf8', '-m', 'desktop_assistant.service', '--port', str(self.port)],
                cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=self.log, stderr=self.log, **hidden_options(),
            )
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if not self.alive():
                    raise AssistantError('应用启动失败，请查看运行日志。')
                if self.ready():
                    self.report('运行正常，可以打开系统。')
                    return
                time.sleep(.3)
            raise AssistantError('应用未在规定时间内就绪，请查看日志。')
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.alive():
            self.report('正在停止：等待执行中的请求完成，请勿关闭电脑…')
            try:
                self.process.stdin.write(b'stop\n')
                self.process.stdin.flush()
                self.process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                raise AssistantError('仍有请求执行或服务未响应，未强制结束。请稍后再次停止并查看日志。') from None
            except (BrokenPipeError, OSError):
                # A service that already exited is safe; otherwise retain its handle.
                if self.alive():
                    raise AssistantError('无法发送停止请求，服务未被强杀，请查看日志。') from None
        if self.process and self.process.stdin:
            self.process.stdin.close()
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
