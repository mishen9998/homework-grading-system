"""Launched by the root .cmd. Locate a working interpreter; do not install anything."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    candidates = [ROOT / '.venv/Scripts/python.exe', ROOT / 'backend/venv/Scripts/python.exe', Path(sys.executable)]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    usable = []
    for executable in dict.fromkeys(candidates):
        if not executable.is_file():
            continue
        try:
            result = subprocess.run([str(executable), '-c', 'import tkinter; import sys; assert sys.version_info >= (3, 10)'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, **options)
            if result.returncode == 0:
                usable.append(executable)
        except (OSError, subprocess.TimeoutExpired):
            continue
    if not usable:
        print('Python 3.10+ with Tkinter is required. Please install Python from python.org.')
        return 1
    chosen = usable[0]
    for executable in usable:
        try:
            result = subprocess.run([str(executable), '-c', 'import flask, flask_migrate, pymysql, waitress'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, **options)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            chosen = executable
            break
    windowed = chosen.with_name('pythonw.exe')
    if windowed.is_file():
        chosen = windowed
    local = ROOT / '数据库/local/desktop-assistant'
    local.mkdir(parents=True, exist_ok=True)
    with (local / 'launcher.log').open('ab') as log:
        subprocess.Popen([str(chosen), '-X', 'utf8', '-m', 'desktop_assistant.app', *sys.argv[1:]],
                         cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, **options)
    return 0


if __name__ == '__main__':
    sys.exit(main())
