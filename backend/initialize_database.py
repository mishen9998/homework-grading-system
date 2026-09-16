"""Versioned initialization/upgrade; never load .env or select an implicit database."""
import argparse
import json
import os
from pathlib import Path
from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import inspect
from app import db
from migrations.schema_support import preflight_database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--upgrade', action='store_true')
    modes.add_argument('--check', action='store_true')
    args = parser.parse_args()
    uri = os.environ.get('DATABASE_URL')
    if not uri:
        raise SystemExit('DATABASE_URL is required; implicit real databases are never selected.')
    application = Flask(__name__)
    application.config.update(SQLALCHEMY_DATABASE_URI=uri, SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(application)
    from app import models  # noqa: F401
    Migrate(application, db)
    with application.app_context():
        with db.engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            result = preflight_database(connection)
            if args.check:
                print(json.dumps(result, ensure_ascii=False))
                return
            if tables and not args.upgrade:
                raise SystemExit('Target is not empty; run --check and use --upgrade after backup.')
        upgrade(directory=str(Path(__file__).parent / 'migrations'))
        print('Database migrated to current revision')


if __name__ == '__main__':
    main()
