"""Explicit schema upgrade; no application startup side effects on business data."""
import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

from manage import ROOT, configured_url, validate_name, server_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / 'backend' / '.env')
    parser.add_argument('--database', required=True)
    parser.add_argument('--create-empty', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    validate_name(args.database)
    url = configured_url(args.env_file).set(database=args.database)
    if not args.apply:
        print(json.dumps({'target': args.database, 'will_create_empty': args.create_empty, 'applied': False}))
        return
    if args.create_empty:
        server = create_engine(server_url(url))
        try:
            with server.begin() as connection:
                if connection.scalar(text('SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name'), {'name': args.database}):
                    raise ValueError('目标库已存在，不允许空库初始化覆盖')
                connection.execute(text(f'CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
        finally:
            server.dispose()
    load_dotenv(args.env_file)
    sys.path.insert(0, str(ROOT / 'backend'))
    from config import get_config
    from app import create_app, db
    from flask_migrate import upgrade
    class MaintenanceConfig(get_config()):
        SQLALCHEMY_DATABASE_URI = url
        AUTO_CREATE_TABLES = False
    app = create_app(MaintenanceConfig)
    with app.app_context():
        existing = set(inspect(db.engine).get_table_names())
        if not existing:
            # The historical first migration only alters existing core tables.
            # Bootstrap a truly empty schema, then run (not stamp) every revision.
            db.create_all()
        elif not {'users', 'assignments', 'submissions', 'courses'}.issubset(existing):
            raise ValueError('目标不是已知完整业务库，拒绝猜测修复残缺核心表')
        upgrade(directory=str(ROOT / 'backend' / 'migrations'))
        inspector = inspect(db.engine)
        missing = {}
        for table in db.metadata.sorted_tables:
            actual = {column['name'] for column in inspector.get_columns(table.name)}
            absent = sorted(set(table.columns.keys()) - actual)
            if absent:
                missing[table.name] = absent
        if missing:
            raise ValueError('仍有缺失字段，保留现场且不要启动应用：' + json.dumps(missing))
        print(json.dumps({'database': args.database, 'migration': db.session.execute(text('SELECT version_num FROM alembic_version')).scalars().all(), 'missing_columns': missing}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(str(exc))
        sys.exit(1)
    except Exception as exc:
        print('升级失败，保留现场；异常类型：' + type(exc).__name__)
        sys.exit(1)
