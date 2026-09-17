"""Isolated campus entry point. Does not read .env or fall back to SQLite."""
import json
import os
import re
import socket
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

def assert_runtime_identity():
    run_id = os.environ.get('CAMPUS_RUN_ID', '')
    if not re.fullmatch(r'[a-f0-9]{12}', run_id):
        raise RuntimeError('dedicated campus run identity required')
    identity = json.loads(Path('/runtime/identity.json').read_text())
    if identity.get('run_id') != run_id or identity.get('project') != 'campusperf-' + run_id:
        raise RuntimeError('runtime identity mismatch')
    sql = urlsplit(os.environ.get('DATABASE_URL', ''))
    redis = urlsplit(os.environ.get('REDIS_URL', ''))
    qdrant = urlsplit(os.environ.get('QDRANT_URL', ''))
    if (sql.scheme != 'mysql+pymysql' or sql.hostname != 'mysql' or sql.port != 3306
            or sql.path != '/campus_perf_' + run_id or sql.username != 'campus_runner'):
        raise RuntimeError('dedicated MySQL target required')
    if redis.scheme != 'redis' or redis.hostname != 'redis' or redis.port != 6379 or redis.path != '/0':
        raise RuntimeError('dedicated Redis target required')
    if qdrant.scheme != 'http' or qdrant.hostname != 'qdrant' or qdrant.port != 6333:
        raise RuntimeError('dedicated Qdrant target required')
    if os.environ.get('QDRANT_COLLECTION') != 'campus_perf_' + run_id:
        raise RuntimeError('dedicated collection required')
    return identity


def _block_external_connections():
    """Defense in depth alongside Docker's internal network; no external probe."""
    if getattr(socket, '_campus_guard', False):
        return
    allowed = {'127.0.0.1', '::1', 'localhost', 'mysql', 'redis', 'qdrant', 'backend'}
    for name in ('mysql', 'redis', 'qdrant', 'backend'):
        try:
            allowed.update(item[4][0] for item in socket.getaddrinfo(name, None))
        except socket.gaierror:
            pass
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def check(address):
        if isinstance(address, tuple) and str(address[0]) not in allowed:
            raise OSError('campus runtime disables external network connections')

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket._campus_guard = True


def create_campus_app():
    from flask import g, request
    identity = assert_runtime_identity()
    _block_external_connections()
    from app import create_app, db
    from config import ProductionConfig
    from sqlalchemy import text

    class CampusConfig(ProductionConfig):
        AUTO_CREATE_TABLES = False
        LOG_LEVEL = 'WARNING'
        DEEPSEEK_API_KEY = ''
        DEEPSEEK_API_URL = 'http://127.0.0.1:9/external-ai-disabled'
        AI_ASYNC_ENABLED = False
        REDIS_KEY_PREFIX = 'campus_perf:' + identity['run_id']
        UPLOAD_FOLDER = '/runtime/attachments'
        SQLALCHEMY_ENGINE_OPTIONS = dict(pool_pre_ping=True, pool_recycle=280,
                                        pool_size=5, max_overflow=5, pool_timeout=15,
                                        hide_parameters=True)

    app = create_app(CampusConfig)

    @app.before_request
    def timing_start():
        g.campus_started = time.perf_counter()
        value = request.headers.get('X-Campus-Trace', '')
        g.campus_trace = value if re.fullmatch('[a-f0-9]{32}', value) else uuid.uuid4().hex

    # Include identity/organization policy lookup in server processing time.
    app.before_request_funcs[None].remove(timing_start)
    app.before_request_funcs[None].insert(0, timing_start)

    @app.after_request
    def timing_end(response):
        elapsed = (time.perf_counter() - getattr(g, 'campus_started', time.perf_counter())) * 1000
        response.headers['Server-Timing'] = f'app;dur={elapsed:.3f}'
        response.headers['X-Campus-Run'] = identity['run_id']
        response.headers['X-Campus-Trace'] = getattr(g, 'campus_trace', uuid.uuid4().hex)
        return response

    @app.get('/api/status/health', endpoint='health_check')
    def health():
        return {'status': 'healthy', 'run_id': identity['run_id'], 'synthetic': True}

    @app.get('/api/status/ready', endpoint='readiness_check')
    def ready():
        import redis
        import requests
        try:
            sql_version = db.session.execute(text('SELECT VERSION()')).scalar_one()
            client = redis.Redis.from_url(app.config['REDIS_URL'], socket_timeout=2)
            client.ping()
            worker = client.get(f"campus_perf:{identity['run_id']}:worker:heartbeat")
            qresponse = requests.get(app.config['QDRANT_URL'] + '/healthz', timeout=2)
            qresponse.raise_for_status()
            status = bool(worker and time.time() - float(worker) < 20)
            return {'status': 'ready' if status else 'starting', 'run_id': identity['run_id'],
                    'mysql': sql_version, 'redis': client.info()['redis_version'],
                    'qdrant': 'healthy', 'worker': status, 'external_ai': 'disabled'}, 200 if status else 503
        except Exception:
            db.session.rollback()
            return {'status': 'unavailable', 'run_id': identity['run_id']}, 503

    return app


def worker():
    """Dependency heartbeat worker only; durable AI/index processing belongs elsewhere."""
    import redis
    from sqlalchemy import text
    from app import db
    app = create_campus_app()
    client = redis.Redis.from_url(app.config['REDIS_URL'], socket_timeout=2)
    with app.app_context():
        while True:
            try:
                db.session.execute(text('SELECT 1'))
                client.setex('campus_perf:' + os.environ['CAMPUS_RUN_ID'] + ':worker:heartbeat', 20, str(time.time()))
            except Exception:
                db.session.rollback()
            finally:
                db.session.remove()
            time.sleep(5)


if __name__ == '__main__':
    worker()
