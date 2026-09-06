"""显式初始化空数据库；已有数据库需使用经过审核的迁移。"""
from run import app
from app import db
from sqlalchemy import inspect

if __name__ == '__main__':
    with app.app_context():
        if inspect(db.engine).get_table_names():
            raise SystemExit('目标数据库非空，初始化已停止；请使用数据库迁移流程。')
        db.create_all()
        print('Database initialized')
