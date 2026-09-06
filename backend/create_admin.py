"""在服务器终端交互创建管理员，密码不进入命令行参数。"""
from getpass import getpass
from run import app
from app import db
from app.models import User
from app.routes.auth import generate_friend_code
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    username = input('Admin username: ').strip()
    password = getpass('Password (12+ characters): ')
    if not username or len(password) < 12 or password != getpass('Repeat password: '):
        raise SystemExit('Invalid username or password')
    with app.app_context():
        if User.query.filter_by(username=username).first():
            raise SystemExit('Account already exists')
        db.session.add(User(username=username, name=username, role='admin',
            email=username + '@example.com', teacher_id=username,
            password=generate_password_hash(password), friend_code=generate_friend_code()))
        db.session.commit()
        print('Admin created')
