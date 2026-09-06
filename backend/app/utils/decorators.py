"""通用鉴权装饰器。

以数据库中的当前角色为准，避免旧 token 保留已撤销权限。
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity


def role_required(*roles):
    """角色鉴权装饰器：仅允许指定角色访问。

    用法：
        @bp.route('/admin/users')
        @role_required('admin')
        def get_users(): ...

        @bp.route('/grade')
        @role_required('teacher', 'admin')
        def grade(): ...
    """
    allowed = set(roles)

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            # 删除账号或调整权限后立即生效，不信任旧 token 中的角色。
            from app.models import User
            user = User.query.get(int(user_id)) if user_id else None
            role = user.role if user else None

            if role not in allowed:
                return jsonify({'error': '权限不足'}), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator
