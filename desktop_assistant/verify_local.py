"""Opt-in read-only integration exercise on a separate loopback port; no AI calls."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from .core import Controller, ROOT, require_free_port


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-local', action='store_true', required=True)
    parser.add_argument('--port', type=int, default=5017)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('报告已存在，拒绝覆盖')
    require_free_port(args.port)
    control = Controller(port=args.port)
    checks = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path):
        try:
            with opener.open(control.url + path, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
    try:
        for cycle in range(2):
            start = time.monotonic()
            control.start()
            assert control.ready()
            pid = control.process.pid
            control.start()
            assert control.process.pid == pid
            assert get('/login')[0] == 200
            assert get('/teacher/home')[0] == 200
            assert get('/favicon.svg')[0] == 200
            assert get('/api/status/ready')[0] == 200
            assert get('/api/auth/me')[0] == 401
            assert get('/api/missing')[0] == 404
            assert get('/.env')[0] == 404
            checks.append({'cycle': cycle + 1, 'startup_seconds': round(time.monotonic() - start, 2),
                           'ready': True, 'duplicate_start_same_process': True,
                           'spa_assets_api_and_private_paths': 'passed'})
            if cycle == 0:
                control.stop()
            else:
                # Simulate parent pipe disappearing, not killing arbitrary processes.
                child = control.process
                child.stdin.close()
                child.wait(timeout=40)
                control.stop()
            require_free_port(args.port)
        report = {'scope': 'read-only local integration, not load/security acceptance',
                  'database': 'existing private configuration, no business writes',
                  'port': args.port, 'results': checks,
                  'stop_and_restart': 'passed', 'parent_pipe_eof_shutdown': 'passed'}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        control.stop()


if __name__ == '__main__':
    main()
