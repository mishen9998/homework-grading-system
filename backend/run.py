import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env（仅本地开发使用，生产环境应由系统环境变量注入）
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

from app import create_app
from config import get_config

app = create_app(get_config())
logger = app.logger


@app.route('/api/status/health', methods=['GET'])
def health_check():
    return {'status': 'healthy'}, 200


@app.route('/api/status/ready', methods=['GET'])
def readiness_check():
    from app import db
    from sqlalchemy import text
    try:
        db.session.execute(text('SELECT id FROM users LIMIT 1'))
        return {'status': 'ready'}, 200
    except Exception:
        db.session.rollback()
        return {'status': 'unavailable'}, 503


if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'development')
    logger.info(f'启动模式: {env}')
    logger.info(f'DeepSeek API Key 已配置: {bool(os.environ.get("DEEPSEEK_API_KEY"))}')
    logger.info('Starting Flask app on port 5000...')
    # 仅开发模式启用 debug；生产环境应通过 gunicorn 启动
    app.run(
        debug=(env == 'development'),
        host='127.0.0.1',
        port=5000,
        threaded=True,
        use_reloader=False
    )
