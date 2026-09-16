import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from config import Config

db = SQLAlchemy()
jwt = JWTManager()

# Flask-Migrate 用于数据库迁移管理（替代手动 migrate_*.py 脚本）；
# 未安装时降级为仅 db.create_all 兜底，避免因缺依赖导致应用无法启动。
try:
    from flask_migrate import Migrate
    migrate = Migrate()
    _HAS_FLASK_MIGRATE = True
except ImportError:
    migrate = None
    _HAS_FLASK_MIGRATE = False


def _setup_logging(app):
    """配置应用日志：控制台 + 轮转文件，统一格式，替代散落的 print。"""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # 替换 Flask 默认 handler，避免重复输出
    app.logger.handlers = []
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    # 降低第三方库噪音
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def _register_error_handlers(app):
    """注册全局错误处理器，统一异常响应，避免向前端泄露内部堆栈。"""

    @app.errorhandler(413)
    def handle_too_large(e):
        app.logger.warning(f'上传文件超限 path={request.path}')
        return jsonify({'error': '上传文件过大'}), 413

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        app.logger.warning(f'HTTP {e.code} {e.name} path={request.path} desc={e.description}')
        return jsonify({'error': e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        # 记录完整堆栈到日志，便于排查
        app.logger.exception(f'未处理异常 path={request.path} method={request.method}')
        # 仅在调试模式下返回详情，生产环境返回通用提示
        if app.debug:
            return jsonify({'error': str(e)}), 500
        return jsonify({'error': '服务器内部错误'}), 500


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 生产环境密钥强制校验：缺失则启动失败（拒绝用默认弱密钥上线）
    if app.config.get('DEBUG') is False and not app.config.get('TESTING'):
        if not app.config.get('SECRET_KEY') or not app.config.get('JWT_SECRET_KEY'):
            raise RuntimeError(
                '生产/非调试环境必须通过环境变量设置 SECRET_KEY 与 JWT_SECRET_KEY'
            )
        for key in ('SECRET_KEY', 'JWT_SECRET_KEY'):
            if len(app.config[key]) < 32 or app.config[key].startswith(('please-change', 'dev-', 'jwt-secret')):
                raise RuntimeError(f'{key} 必须使用至少32字符的随机密钥')

    _setup_logging(app)

    db.init_app(app)
    jwt.init_app(app)

    if _HAS_FLASK_MIGRATE:
        migrate.init_app(app, db)
        app.logger.info('Flask-Migrate 已启用，使用 `flask db migrate/upgrade` 管理表结构')
    else:
        app.logger.warning('未安装 Flask-Migrate，建议 pip install Flask-Migrate 启用数据库迁移')

    # CORS 收紧：使用配置中的白名单，不再使用通配 "*"
    CORS(
        app,
        resources={r"/*": {
            "origins": app.config.get('CORS_ORIGINS', []),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }}
    )

    # JWT 异常回调：用日志替代 print，避免泄露 token 内容
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        app.logger.info('JWT token 已过期')
        return jsonify({'error': 'Token已过期'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        app.logger.info(f'JWT token 无效: {error}')
        return jsonify({'error': 'Token无效'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        app.logger.info(f'缺少 JWT token: {error}')
        return jsonify({'error': '缺少认证token'}), 401

    from app.models import (
        User, Assignment, Submission, Course, CourseEnrollment,
        CourseResource, CourseNote, Question, Answer
    )
    from app.routes import auth, assignments, courses, questions, admin, friends, ai_assistant
    app.register_blueprint(auth.bp)
    app.register_blueprint(assignments.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(questions.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(friends.bp)
    app.register_blueprint(ai_assistant.bp)
    from app.routes import ai_jobs
    app.register_blueprint(ai_jobs.bp)
    from app.routes import knowledge
    app.register_blueprint(knowledge.bp)
    from app.routes import chats, schedules
    app.register_blueprint(chats.bp)
    app.register_blueprint(schedules.bp)
    from app.routes.organizations import platform_bp, organization_bp
    app.register_blueprint(platform_bp)
    app.register_blueprint(organization_bp)
    from app.services.organization_context import register_organization_context
    register_organization_context(app)

    upload_folder = os.path.join(os.path.dirname(__file__), 'tupian')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.logger.info(f'Upload folder path: {upload_folder}')

    @app.route('/tupian/<filename>')
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(upload_folder, filename)

    with app.app_context():
        # 注意：建议使用 Flask-Migrate 管理表结构，db.create_all 仅作首次初始化兜底
        if app.config.get('AUTO_CREATE_TABLES', True):
            db.create_all()
        if db.engine.dialect.name == 'sqlite':
            result = db.session.execute(text('PRAGMA journal_mode=WAL')).scalar()
            app.logger.info(f'SQLite WAL 模式已启用: {result}')
        else:
            app.logger.info(f'数据库连接已建立: {db.engine.dialect.name}')

    _register_error_handlers(app)

    app.logger.info('应用启动完成')
    return app
