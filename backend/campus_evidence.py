"""Non-secret environment and SQL size facts; never a performance/capacity claim."""
import importlib.metadata
import json
import os
import platform
from pathlib import Path

import redis
import requests
from sqlalchemy import text

from campus_runtime import create_campus_app, assert_runtime_identity


def main():
    identity = assert_runtime_identity()
    app = create_campus_app()
    from app import db
    with app.app_context():
        sql_version = db.session.execute(text('SELECT VERSION()')).scalar_one()
        size = db.session.execute(text('SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema=DATABASE()')).scalar_one()
        database = db.session.execute(text('SELECT DATABASE()')).scalar_one()
        client = redis.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True)
        keys = list(client.scan_iter())
        qdrant = requests.get(os.environ['QDRANT_URL'], timeout=3).json()
        report = {'run_id': identity['run_id'], 'python': platform.python_version(),
                  'mysql': sql_version, 'redis': client.info()['redis_version'],
                  'qdrant': qdrant['version'], 'database': database,
                  'mysql_table_allocated_bytes': int(size), 'redis_key_count': len(keys),
                  'redis_all_keys_in_run_namespace': all(k.startswith('campus_perf:' + identity['run_id'] + ':') for k in keys),
                  'dependencies': {name: importlib.metadata.version(name) for name in
                                   ('SQLAlchemy', 'Flask', 'pytest', 'redis', 'pandas', 'gunicorn')},
                  'external_ai_enabled': app.config['AI_ASYNC_ENABLED'],
                  'external_ai_key_configured': bool(app.config['DEEPSEEK_API_KEY']),
                  'external_connection_guard_installed': __import__('socket')._campus_guard,
                  'public_probe_performed': False, 'historical_blocked_checks_retried': False}
        Path('/runtime/environment.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == '__main__':
    main()
