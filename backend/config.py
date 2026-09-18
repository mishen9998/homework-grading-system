import os
from datetime import timedelta


class BaseConfig:
    """基础配置：密钥统一从环境变量读取，无硬编码默认值。"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///homework.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 对 MySQL 开启断线重连和连接回收；SQLite 也可安全忽略这些连接池参数。
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20)),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 15)),
    }

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or ''
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL') or 'https://api.deepseek.com/v1/chat/completions'
    # Optional local multilingual embedding model. When empty, hybrid search
    # uses a deterministic on-host character vector and needs no model download.
    LOCAL_EMBEDDING_MODEL = os.environ.get('LOCAL_EMBEDDING_MODEL') or ''
    EMBEDDING_SERVICE_URL = os.environ.get('EMBEDDING_SERVICE_URL') or ''
    EMBEDDING_SERVICE_TOKEN = os.environ.get('EMBEDDING_SERVICE_TOKEN') or ''
    EMBEDDING_SERVICE_MODEL_ID = os.environ.get('EMBEDDING_SERVICE_MODEL_ID') or 'bge-small-zh-v1.5'
    EMBEDDING_SERVICE_TIMEOUT = float(os.environ.get('EMBEDDING_SERVICE_TIMEOUT', '5'))

    # Scalable local knowledge retrieval. Redis/Qdrant are optional; both have
    # safe database/in-process fallbacks for development.
    REDIS_URL = os.environ.get('REDIS_URL') or ''
    REDIS_CONNECT_TIMEOUT = float(os.environ.get('REDIS_CONNECT_TIMEOUT', '0.3'))
    REDIS_SOCKET_TIMEOUT = float(os.environ.get('REDIS_SOCKET_TIMEOUT', '0.5'))
    QDRANT_URL = os.environ.get('QDRANT_URL') or ''
    QDRANT_API_KEY = os.environ.get('QDRANT_API_KEY') or ''
    QDRANT_COLLECTION = os.environ.get('QDRANT_COLLECTION') or 'school_knowledge'
    QDRANT_CHUNK_COLLECTION = os.environ.get('QDRANT_CHUNK_COLLECTION') or 'school_knowledge_chunks'
    QDRANT_TIMEOUT = float(os.environ.get('QDRANT_TIMEOUT', '1.5'))
    KNOWLEDGE_CACHE_TTL = int(os.environ.get('KNOWLEDGE_CACHE_TTL', '120'))
    KNOWLEDGE_NEURAL_MIN_SCORE = float(os.environ.get('KNOWLEDGE_NEURAL_MIN_SCORE', '0.50'))
    KNOWLEDGE_CHUNK_CANDIDATES = int(os.environ.get('KNOWLEDGE_CHUNK_CANDIDATES', '600'))
    KNOWLEDGE_LEXICAL_CANDIDATES = int(os.environ.get('KNOWLEDGE_LEXICAL_CANDIDATES', '300'))
    KNOWLEDGE_VECTOR_CANDIDATES = int(os.environ.get('KNOWLEDGE_VECTOR_CANDIDATES', '80'))
    KNOWLEDGE_FALLBACK_CANDIDATES = int(os.environ.get('KNOWLEDGE_FALLBACK_CANDIDATES', '1500'))
    KNOWLEDGE_MYSQL_FULLTEXT = os.environ.get('KNOWLEDGE_MYSQL_FULLTEXT', 'true').lower() in ('1', 'true', 'yes')
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('RATE_LIMIT_WINDOW_SECONDS', '60'))
    KNOWLEDGE_QUERY_RATE_LIMIT = int(os.environ.get('KNOWLEDGE_QUERY_RATE_LIMIT', '60'))
    KNOWLEDGE_AGENT_RATE_LIMIT = int(os.environ.get('KNOWLEDGE_AGENT_RATE_LIMIT', '60'))
    DEEPSEEK_QUERY_RATE_LIMIT = int(os.environ.get('DEEPSEEK_QUERY_RATE_LIMIT', '10'))
    AI_ASYNC_ENABLED = os.environ.get('AI_ASYNC_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    AI_QUEUE_MAX_LENGTH = int(os.environ.get('AI_QUEUE_MAX_LENGTH', '1000'))
    AI_JOB_TTL_SECONDS = int(os.environ.get('AI_JOB_TTL_SECONDS', '3600'))
    AI_WORKER_HEARTBEAT_MAX_AGE = int(os.environ.get('AI_WORKER_HEARTBEAT_MAX_AGE', '20'))

    # CORS 白名单（逗号分隔），不再使用通配 "*"，按环境显式配置允许的前端来源
    CORS_ORIGINS = [
        o.strip() for o in os.environ.get(
            'CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000'
        ).split(',') if o.strip()
    ]

    # 文件上传大小上限（默认 16MB），防止大文件 DoS
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # 上传文件存储目录
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'tupian'

    # 日志级别
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # JSON 中文输出（便于调试与前端阅读）
    JSON_AS_ASCII = False
    AUTO_CREATE_TABLES = os.environ.get('AUTO_CREATE_TABLES', 'true').lower() in ('1', 'true', 'yes')
    PUBLIC_REGISTRATION = False


class DevelopmentConfig(BaseConfig):
    """开发环境：允许回退到弱默认密钥，仅用于本地调试。"""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'


class TestingConfig(BaseConfig):
    """测试环境：使用内存数据库。"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'
    SECRET_KEY = 'testing-secret-key'
    JWT_SECRET_KEY = 'testing-jwt-secret-key'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    KNOWLEDGE_QUERY_RATE_LIMIT = 10000
    KNOWLEDGE_AGENT_RATE_LIMIT = 10000
    DEEPSEEK_QUERY_RATE_LIMIT = 10000
    AI_ASYNC_ENABLED = False
    AUTO_CREATE_TABLES = True
    LOCAL_EMBEDDING_MODEL = ''
    EMBEDDING_SERVICE_URL = ''
    REDIS_URL = ''
    QDRANT_URL = ''


class ProductionConfig(BaseConfig):
    """生产环境：密钥必须由环境变量提供，缺失将在启动时被 create_app 拦截。"""
    DEBUG = False
    AUTO_CREATE_TABLES = False
    PUBLIC_REGISTRATION = False


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}


def get_config(config_name=None):
    """根据 FLASK_ENV / FLASK_CONFIG 选择配置类，默认开发环境。"""
    name = config_name or os.environ.get('FLASK_ENV') or os.environ.get('FLASK_CONFIG') or 'development'
    return config_map.get(name, DevelopmentConfig)


# 向后兼容：保留 Config 名称（默认指向开发配置），现有 import Config 不受影响
Config = DevelopmentConfig
