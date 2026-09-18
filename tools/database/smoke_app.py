"""Exercise the normal journey in an EMPTY homework_smoke_* MySQL database."""
import argparse
import json
from pathlib import Path
import sys

from manage import ROOT, HERE, configured_url, restrict_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--serve', action='store_true', help='验证后仅监听本机 5000，供前端页面演练')
    parser.add_argument('--serve-existing', action='store_true', help='只启动已存在的合成测试库，不新增数据')
    args = parser.parse_args()
    if not args.database.startswith('homework_smoke_'):
        raise ValueError('只能使用 homework_smoke_ 前缀的全新空库')
    sys.path.insert(0, str(ROOT / 'backend'))
    sys.path.insert(0, str(ROOT / 'backend/tests'))
    from config import TestingConfig
    from app import create_app, db
    from app.models import User
    from test_teaching_flow import exercise_teaching_flow
    class SmokeConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = configured_url(ROOT / 'backend/.env').set(database=args.database)
        AUTO_CREATE_TABLES = False
        LOG_LEVEL = 'WARNING'
    app = create_app(SmokeConfig)
    with app.app_context():
        if args.serve_existing:
            if User.query.count() != 3 or {user.username for user in User.query.all()} != {'smoke_teacher', 'smoke_student', 'smoke_admin'}:
                raise ValueError('不是已知的三账号合成测试库')
        elif User.query.count():
            raise ValueError('目标库非空，拒绝混入已有用户')
        if not args.serve_existing:
            steps, credentials = exercise_teaching_flow(app)
            folder = HERE / 'local' / args.database
            restrict_directory(folder)
            (folder / 'accounts.local.json').write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding='utf-8')
            (ROOT / 'docs/reports/教学流程验证.json').write_text(json.dumps({'database': args.database, 'synthetic_only': True,
                'passed_steps': len(steps), 'steps': steps}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'database': args.database, 'passed_steps': len(steps), 'credentials_file': str(folder / 'accounts.local.json')}, ensure_ascii=False), flush=True)
    if args.serve or args.serve_existing:
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
