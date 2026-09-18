"""Dedicated Redis AI worker. Run one or more copies independently."""
import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / '.env')

from app import create_app, db
from app.services.ai_jobs import (claim_ai_job, complete_ai_job, fail_ai_job,
                                  heartbeat, recover_stale_jobs)
from app.services.ai_tasks import execute_ai_task
from config import get_config


app = create_app(get_config())
logger = logging.getLogger('ai-worker')


def _heartbeat_loop():
    while True:
        with app.app_context():
            try:
                heartbeat()
            except Exception:
                logger.exception('AI worker heartbeat failed')
        time.sleep(5)


def main():
    with app.app_context():
        recovered = recover_stale_jobs()
        logger.info('AI worker started; recovered=%s', recovered)
        heartbeat()
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    while True:
        with app.app_context():
            job = None
            try:
                job = claim_ai_job(timeout=5)
                if not job:
                    continue
                result = execute_ai_task(job['kind'], job.get('payload') or {})
                db.session.remove()
                complete_ai_job(job['id'], result)
            except KeyboardInterrupt:
                return
            except Exception as exc:
                db.session.rollback()
                logger.exception('AI job failed kind=%s', job.get('kind') if job else 'unknown')
                if job:
                    fail_ai_job(job['id'], str(exc))
            finally:
                db.session.remove()


if __name__ == '__main__':
    main()
