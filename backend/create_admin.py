"""Explicit platform bootstrap; never loads .env or promotes an existing user.

Run after database initialization with DATABASE_URL, SECRET_KEY and
JWT_SECRET_KEY set explicitly. Passwords are prompted, never CLI arguments.
"""
from getpass import getpass
import os

from app import create_app, db
from app.models import Organization, User
from app.routes.admin import clean_text, new_user, user_values
from app.services.organization_context import PolicyError, audit
from config import ProductionConfig


def create_platform_admin(username, password, email, name=None):
    """Create an independent platform account in the caller's app context."""
    try:
        organization = Organization.query.filter_by(code='platform').populate_existing().with_for_update().first()
        if organization is None:
            organization = Organization(code='platform', name='平台管理', status='active',
                                        expires_at=None, user_limit=100, storage_limit_bytes=0,
                                        ai_monthly_token_limit=0, concurrent_task_limit=0, ai_enabled=False)
            db.session.add(organization)
            db.session.flush()
        elif organization.status != 'active' or organization.expires_at is not None:
            raise ValueError('保留平台机构状态异常，已停止初始化')
        if User.query.filter(User.organization_id == organization.id,
                             User.role != 'platform_admin').with_for_update().first():
            raise ValueError('保留机构包含业务账号，已停止；不会提升旧管理员')
        values = user_values({'username': username, 'password': password, 'email': email,
                              'name': name or username, 'role': 'admin', 'is_active': True}, organization)
        values['role'] = 'platform_admin'
        user = new_user(values, organization)
        db.session.flush()
        audit('platform_admin.bootstrapped', actor=user, organization_id=organization.id,
              target_type='user', target_id=user.id, details={'independent_account': True})
        user_id = user.id
        db.session.commit()
        return user_id
    except Exception:
        db.session.rollback()
        raise


def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit('必须显式设置 DATABASE_URL；不会读取 .env 或使用默认数据库')

    class BootstrapConfig(ProductionConfig):
        SQLALCHEMY_DATABASE_URI = database_url
        AUTO_CREATE_TABLES = False

    try:
        app = create_app(BootstrapConfig)
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit('无法连接显式配置的数据库；请检查配置及迁移状态') from None
    username = clean_text(input('Platform username: '), 'username', 80, required=True)
    email = clean_text(input('Platform email: '), 'email', 120, required=True)
    password = getpass('Password (12+ characters, 3 character classes): ')
    if password != getpass('Repeat password: '):
        raise SystemExit('两次密码不一致')
    try:
        with app.app_context():
            create_platform_admin(username, password, email)
    except (PolicyError, ValueError) as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit('初始化失败；请检查显式配置、迁移状态或账号重复，不会自动修改旧账号') from None
    print('Platform administrator created. Login organization code: platform')


if __name__ == '__main__':
    main()
