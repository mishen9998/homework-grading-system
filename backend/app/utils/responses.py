"""统一响应格式工具模块。

企业级规范：所有接口应返回统一信封结构，便于前端统一处理与错误捕获。
    成功： {"code": 0,  "message": "...", "data": {...}}
    失败： {"code": -1, "message": "...", "error": "..."}
    分页： {"code": 0,  "message": "...", "data": {"items": [...], "total": N, "page": N, "per_page": N, "has_next": bool}}

注意：现有接口历史返回格式不一致，本模块供新接口与渐进式迁移使用，
未强制重构全部旧接口以避免破坏前端。
"""
from flask import jsonify


def success(data=None, message='操作成功', http_code=200):
    """统一成功响应。"""
    return jsonify({'code': 0, 'message': message, 'data': data}), http_code


def fail(message='操作失败', http_code=400, error=None, code=-1):
    """统一失败响应。error 可携带额外调试信息（生产环境应关闭）。"""
    resp = {'code': code, 'message': message}
    if error is not None:
        resp['error'] = error
    return jsonify(resp), http_code


def paginate(items, total, page, per_page, has_next, message='操作成功'):
    """统一分页响应。"""
    return jsonify({
        'code': 0,
        'message': message,
        'data': {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_next': has_next,
        }
    }), 200
