import os
import sys
import subprocess
import time
import webbrowser
import signal
import shutil
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

def cleanup(signum=None, frame=None):
    print("\n正在停止所有服务...")
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
    
    print("所有服务已停止")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def kill_port(port):
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                f'netstat -ano | findstr :{port} | findstr LISTENING',
                capture_output=True, text=True, shell=True
            )
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(f'taskkill /F /PID {pid}', capture_output=True, shell=True)
                        print(f"  已清理端口 {port} (PID: {pid})")
        except:
            pass

def wait_for_backend(timeout=30):
    import urllib.request
    import urllib.error
    
    print("  等待后端服务就绪", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5000/api/status/health",
                method='GET'
            )
            urllib.request.urlopen(req, timeout=2)
            print(" ✓")
            return True
        except urllib.error.HTTPError:
            print(" ✓")
            return True
        except:
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
    
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"
    
    python_exe = choose_backend_python(backend_dir)
    
    print("=" * 60)
    print("        作业管理系统 - 一键启动")
    print("=" * 60)
    
    print("\n[1/5] 清理端口占用...")
    kill_port(5000)
    kill_port(3000)
    time.sleep(1)
    
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
        cleanup()
        return
    
    print("\n[3/5] 启动前端服务 (端口 3000)...")
    frontend_process = subprocess.Popen(
        "npm run dev",
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        shell=True
    )
    
    if not wait_for_frontend(timeout=15):
        print("\n⚠️ 前端启动较慢，请稍后刷新页面")
    
    print("\n" + "=" * 60)
    print("        ✅ 启动完成！")
    print("=" * 60)
    print()
    print("  后端地址：http://localhost:5000")
    print("  前端地址：http://localhost:3000")
    print()
    print("  测试账号：")
    print("    老师 - 20260001 / 123456")
    print("    学生 - student1 / 123456")
    print()
    print("  按 Ctrl+C 停止所有服务")
    print("=" * 60)
    
    time.sleep(1)
    webbrowser.open("http://localhost:3000")
    
    print("\n服务运行中，请保持此窗口打开...")
    
    while True:
        time.sleep(1)
        if backend_process.poll() is not None:
            print("\n⚠️ 后端服务意外停止，正在重启...")
            backend_process = subprocess.Popen(
                [python_exe, "run.py"],
                cwd=backend_dir,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            wait_for_backend(timeout=20)

if __name__ == "__main__":
    main()
