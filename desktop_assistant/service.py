"""Loopback-only Waitress entry point, static SPA and cooperative shutdown."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def load_application():
    from dotenv import load_dotenv, dotenv_values
    config_path = ROOT / 'backend/.env'
    values = dotenv_values(config_path)
    if not values.get('DATABASE_URL'):
        raise ValueError('请先配置 backend/.env 的 DATABASE_URL；助手不会自动新建或切换数据库。')
    load_dotenv(config_path, override=True)
    os.environ['FLASK_ENV'] = 'production'
    os.environ['AUTO_CREATE_TABLES'] = 'false'
    sys.path.insert(0, str(ROOT / 'backend'))
    from app import create_app
    from config import ProductionConfig
    return create_app(ProductionConfig)


def database_ready(app, full=False):
    from app import db
    from sqlalchemy import text, inspect
    from alembic.script import ScriptDirectory
    with app.app_context():
        try:
            db.session.execute(text('SELECT id FROM users LIMIT 1'))
            actual = set(db.session.execute(text('SELECT version_num FROM alembic_version')).scalars())
            expected = set(ScriptDirectory(str(ROOT / 'backend/migrations')).get_heads())
            if actual != expected:
                raise ValueError('数据库迁移版本不匹配，请先按数据库迁移指南升级。')
            if full:
                inspector = inspect(db.engine)
                for table in db.metadata.sorted_tables:
                    columns = {column['name'] for column in inspector.get_columns(table.name)}
                    if not set(table.columns.keys()).issubset(columns):
                        raise ValueError('数据库缺少必要字段，请按数据库迁移指南检查。')
            return True
        finally:
            db.session.remove()


def install_web_routes(app, dist, instance):
    from flask import abort, jsonify, send_from_directory
    dist = Path(dist).resolve()

    @app.get('/api/status/health')
    def health():
        return {'status': 'healthy', 'mode': 'desktop', 'instance': instance}

    @app.get('/api/status/ready')
    def ready():
        try:
            database_ready(app)
            return {'status': 'ready', 'instance': instance}
        except Exception:
            return jsonify({'status': 'unavailable'}), 503

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path=''):
        # Serve only build assets and explicit SPA routes, never project files.
        if '\\' in path or ':' in path or '..' in path.split('/') or path.startswith('.'):
            abort(404)
        if path.startswith('assets/') or path in ('favicon.ico', 'favicon.svg', 'logo.png'):
            if not (dist / path).resolve().is_relative_to(dist):
                abort(404)
            response = send_from_directory(dist, path)
            response.cache_control.public = True
            response.cache_control.max_age = 86400
            return response
        if path and path.split('/')[0] not in {'login', 'register', 'loading', 'student', 'teacher', 'admin'}:
            abort(404)
        response = send_from_directory(dist, 'index.html')
        response.headers['Cache-Control'] = 'no-store'
        return response


class DrainRequests:
    def __init__(self, application):
        self.application = application
        self.condition = threading.Condition()
        self.active = 0
        self.stopping = False

    def __call__(self, environ, start_response):
        def response():
            # Increment only when the server starts consuming the iterable;
            # closing an unstarted generator must not leak an active request.
            with self.condition:
                admitted = not self.stopping
                if admitted:
                    self.active += 1
            if not admitted:
                start_response('503 Service Unavailable', [('Content-Type', 'application/json'), ('Retry-After', '5')])
                yield b'{"error":"Service is stopping"}'
                return
            result = None
            try:
                result = self.application(environ, start_response)
                yield from result
            finally:
                try:
                    if hasattr(result, 'close'):
                        result.close()
                finally:
                    with self.condition:
                        self.active -= 1
                        self.condition.notify_all()
        return response()

    def drain(self, timeout=30):
        with self.condition:
            self.stopping = True
            finished = self.condition.wait_for(lambda: self.active == 0, timeout)
            if not finished:
                self.stopping = False
            return finished


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    try:
        from waitress import create_server
        app = load_application()
        database_ready(app, full=True)
        if args.check:
            print(json.dumps({'ok': True, 'database': '已连接，结构检查通过',
                              'ai': '外部 AI worker 不由桌面助手启动'}, ensure_ascii=False))
            return 0
        if not (ROOT / 'frontend/dist/index.html').is_file():
            raise ValueError('缺少前端构建产物，请重新通过桌面助手启动。')
        install_web_routes(app, ROOT / 'frontend/dist', os.environ.get('DESKTOP_INSTANCE_ID', ''))
        draining = DrainRequests(app)
        server = create_server(draining, host='127.0.0.1', port=args.port, threads=8,
                               max_request_body_size=app.config['MAX_CONTENT_LENGTH'],
                               expose_tracebacks=False, channel_timeout=60)
        serving = threading.Thread(target=server.run, daemon=True)
        serving.start()
        while serving.is_alive():
            # stdin is a private parent-child pipe, not an HTTP shutdown endpoint.
            line = sys.stdin.readline()
            if not line or line.strip() == 'stop':
                if draining.drain():
                    server.close()
                    server.task_dispatcher.shutdown(timeout=5)
                    print('服务已安全停止。', flush=True)
                    return 0
                print('仍有正在执行的请求，已取消本次停止；未强杀。', flush=True)
                if not line:
                    time.sleep(1)  # Parent is gone: keep draining until writes finish.
        return 1
    except ImportError:
        print(json.dumps({'ok': False, 'error': '缺少运行依赖，请按桌面助手使用说明安装依赖（包括 waitress）。'}, ensure_ascii=False))
    except ValueError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
    except Exception as exc:
        # Never expose SQL parameters, URL passwords or configuration values.
        print(json.dumps({'ok': False, 'error': f'运行检查失败（{type(exc).__name__}）。请检查 MySQL 服务、连接配置及迁移版本。'}, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main())
