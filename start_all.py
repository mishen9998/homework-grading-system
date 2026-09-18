import os
import sys
import subprocess
import time
import webbrowser
import signal
import shutil
import socket
import json
import argparse
from pathlib import Path

backend_process = None
frontend_process = None

REQUIRED_BACKEND_MODULES = (
    'flask',
    'flask_sqlalchemy',
    'flask_jwt_extended',
    'requests',
    'openpyxl',
    'pymysql',
)

def cleanup(signum=None, frame=None, exit_code=0):
    print("\n正在停止本启动器创建的服务...")
    global backend_process, frontend_process
    
    if frontend_process:
        try:
            frontend_process.terminate()
            frontend_process.wait(timeout=3)
        except:
            try:
                frontend_process.kill()
            except:
                pass
    
    if backend_process:
        try:
            backend_process.terminate()
            backend_process.wait(timeout=3)
        except:
            try:
                backend_process.kill()
            except:
                pass
    
    print("本启动器创建的服务已停止")
    sys.exit(exit_code)

def require_free_port(port):
    """Never terminate an unrelated application just because it uses our port."""
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError as exc:
            raise RuntimeError(f'端口 {port} 已占用，请确认并手动停止对应服务；未终止任何进程') from exc

def wait_for_backend(timeout=30):
    import urllib.request
    import urllib.error
    
    print("  等待后端服务就绪", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5000/api/status/ready",
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status != 200 or json.load(response).get('status') != 'ready':
                    raise ValueError('数据库尚未就绪')
            print(" ✓")
            return True
        except (OSError, ValueError):
            print(".", end="", flush=True)
            time.sleep(1)
    print(" ✗")
    return False

def wait_for_frontend(timeout=15):
    import urllib.request
    
    print("  等待前端服务就绪", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen("http://localhost:3000", timeout=2)
            print(" ✓")
            return True
        except:
            print(".", end="", flush=True)
            time.sleep(1)
    print(" ✗")
    return False


def is_backend_python_usable(python_exe, backend_dir):
    """检查解释器本身和后端关键依赖，避免误用已失效的虚拟环境。"""
    check_code = 'import ' + ', '.join(REQUIRED_BACKEND_MODULES)
    try:
        result = subprocess.run(
            [python_exe, '-c', check_code],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=8,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def choose_backend_python(backend_dir):
    """按可靠性选择后端 Python，兼容从 PyCharm 或命令行启动。"""
    candidates = []
    project_venv_python = backend_dir / 'venv' / 'Scripts' / 'python.exe'
    if project_venv_python.exists():
        candidates.append((str(project_venv_python), '项目虚拟环境'))

    system_python = shutil.which('python')
    if system_python:
        candidates.append((system_python, '系统Python'))

    if sys.executable:
        candidates.append((sys.executable, '当前Python'))

    checked = set()
    for python_exe, label in candidates:
        if python_exe in checked:
            continue
        checked.add(python_exe)
        if is_backend_python_usable(python_exe, backend_dir):
            if label != '项目虚拟环境':
                print(f'项目虚拟环境不可用，切换到{label}: {python_exe}')
            else:
                print(f'使用虚拟环境Python: {python_exe}')
            return python_exe

    raise RuntimeError(
        '找不到可用的后端Python环境。请先执行：'
        ' python -m pip install -r backend\\requirements.txt'
    )

def main():
    global backend_process, frontend_process
    
    parser = argparse.ArgumentParser(description='本地开发启动器，不会自动结束已有进程')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"
    
    python_exe = choose_backend_python(backend_dir)
    
    print("=" * 60)
    print("        作业管理系统 - 一键启动")
    print("=" * 60)
    
    print("\n[1/5] 检查端口占用...")
    require_free_port(5000)
    require_free_port(3000)
    
    print("\n[2/5] 启动后端服务 (端口 5000)...")
    backend_process = subprocess.Popen(
        [python_exe, "run.py"],
        cwd=backend_dir,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    if not wait_for_backend(timeout=30):
        print("\n❌ 后端服务启动失败，请检查 backend/run.py")
        cleanup(exit_code=1)
        return
    
    print("\n[3/5] 启动前端服务 (端口 3000)...")
    frontend_process = subprocess.Popen(
        [shutil.which('node') or 'node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--strictPort'],
        cwd=frontend_dir,
        text=True,
        encoding='utf-8',
        errors='replace',
        shell=False
    )
    
    if not wait_for_frontend(timeout=15):
        print("\n❌ 前端未就绪，请检查 frontend 日志。")
        cleanup(exit_code=1)
    
    print("\n" + "=" * 60)
    print("        ✅ 启动完成！")
    print("=" * 60)
    print()
    print("  后端地址：http://localhost:5000")
    print("  前端地址：http://localhost:3000")
    print()
    print("  使用已有应用账号登录；数据库服务账号不能用于网页登录。")
    print()
    print("  按 Ctrl+C 停止所有服务")
    print("=" * 60)
    
    time.sleep(1)
    if not args.no_browser:
        webbrowser.open("http://localhost:3000")
    
    print("\n服务运行中，请保持此窗口打开...")
    
    while True:
        time.sleep(1)
        if backend_process.poll() is not None:
            print("\n⚠️ 后端服务已停止，请检查日志；不进行无限重启。")
            cleanup(exit_code=1)
        if frontend_process.poll() is not None:
            print("\n⚠️ 前端服务已停止，请检查日志。")
            cleanup(exit_code=1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    try:
        main()
    except Exception as exc:
        print(f'启动失败（{type(exc).__name__}），请检查端口、依赖和配置。')
        cleanup(exit_code=1)
