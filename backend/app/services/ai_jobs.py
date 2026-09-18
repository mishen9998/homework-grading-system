"""Redis-backed AI job queue with owner-scoped results and worker heartbeat."""
import hashlib
import json
import time
import uuid

from flask import current_app

from app.services.runtime_control import redis_client


QUEUE_KEY = 'homework:ai:queue'
PROCESSING_KEY = 'homework:ai:processing'
HEARTBEAT_KEY = 'homework:ai:worker:heartbeat'


class QueueFullError(RuntimeError):
    pass


def _job_key(job_id):
    return f'homework:ai:job:{job_id}'


def _dedupe_key(user_id, value):
    digest = hashlib.sha256(str(value).encode('utf-8')).hexdigest()
    return f'homework:ai:dedupe:{user_id}:{digest}'


def worker_available(client=None):
    client = client or redis_client()
    if client is None:
        return False
    try:
        heartbeat = float(client.get(HEARTBEAT_KEY) or 0)
        return time.time() - heartbeat <= float(current_app.config.get('AI_WORKER_HEARTBEAT_MAX_AGE', 20))
    except Exception:
        return False


def heartbeat():
    client = redis_client()
    if client is not None:
        client.setex(HEARTBEAT_KEY, 30, str(time.time()))


def enqueue_ai_job(kind, payload, user_id, dedupe=None):
    """Queue work only when a live worker is present; otherwise return None."""
    if not current_app.config.get('AI_ASYNC_ENABLED', True):
        return None
    client = redis_client()
    if client is None or not worker_available(client):
        return None
    maximum = max(10, int(current_app.config.get('AI_QUEUE_MAX_LENGTH', 1000)))
    if client.llen(QUEUE_KEY) >= maximum:
        raise QueueFullError('AI任务队列繁忙，请稍后再试')

    dedupe_redis_key = _dedupe_key(user_id, dedupe) if dedupe else None
    if dedupe_redis_key:
        existing = client.get(dedupe_redis_key)
        if existing:
            item = get_ai_job(existing)
            if item and item.get('status') in ('queued', 'running', 'completed'):
                return existing

    job_id = uuid.uuid4().hex
    ttl = max(300, int(current_app.config.get('AI_JOB_TTL_SECONDS', 3600)))
    now = str(time.time())
    pipe = client.pipeline()
    pipe.hset(_job_key(job_id), mapping={
        'id': job_id,
        'kind': str(kind),
        'user_id': str(int(user_id)),
        'status': 'queued',
        'payload': json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
        'created_at': now,
        'updated_at': now,
    })
    pipe.expire(_job_key(job_id), ttl)
    pipe.lpush(QUEUE_KEY, job_id)
    if dedupe_redis_key:
        pipe.setex(dedupe_redis_key, min(ttl, 600), job_id)
    pipe.execute()
    return job_id


def get_ai_job(job_id):
    client = redis_client()
    if client is None or not isinstance(job_id, str) or len(job_id) != 32:
        return None
    raw = client.hgetall(_job_key(job_id))
    if not raw:
        return None
    result = dict(raw)
    for name in ('payload', 'result'):
        if result.get(name):
            try:
                result[name] = json.loads(result[name])
            except (TypeError, ValueError):
                result[name] = None
    return result


def claim_ai_job(timeout=5):
    client = redis_client()
    if client is None:
        return None
    job_id = client.brpoplpush(QUEUE_KEY, PROCESSING_KEY, timeout=timeout)
    if not job_id:
        return None
    key = _job_key(job_id)
    if not client.exists(key):
        client.lrem(PROCESSING_KEY, 0, job_id)
        return None
    now = str(time.time())
    client.hset(key, mapping={'status': 'running', 'started_at': now, 'updated_at': now})
    return get_ai_job(job_id)


def _finish(job_id, status, result=None, error=''):
    client = redis_client()
    if client is None:
        return
    key = _job_key(job_id)
    ttl = max(300, int(current_app.config.get('AI_JOB_TTL_SECONDS', 3600)))
    values = {'status': status, 'updated_at': str(time.time()), 'finished_at': str(time.time())}
    if result is not None:
        values['result'] = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
    if error:
        values['error'] = str(error)[:2000]
    pipe = client.pipeline()
    pipe.hset(key, mapping=values)
    pipe.hdel(key, 'payload')
    pipe.expire(key, ttl)
    pipe.lrem(PROCESSING_KEY, 0, job_id)
    pipe.execute()


def complete_ai_job(job_id, result):
    _finish(job_id, 'completed', result=result)


def fail_ai_job(job_id, error):
    _finish(job_id, 'failed', error=error)


def queue_status():
    client = redis_client()
    if client is None:
        return {'available': False, 'worker': False, 'queued': 0, 'running': 0}
    return {
        'available': True,
        'worker': worker_available(client),
        'queued': int(client.llen(QUEUE_KEY)),
        'running': int(client.llen(PROCESSING_KEY)),
    }


def recover_stale_jobs(max_age_seconds=900):
    """Return jobs abandoned by a stopped worker to the ready queue."""
    client = redis_client()
    if client is None:
        return 0
    recovered = 0
    now = time.time()
    for job_id in client.lrange(PROCESSING_KEY, 0, -1):
        job = get_ai_job(job_id)
        if not job:
            client.lrem(PROCESSING_KEY, 0, job_id)
            continue
        started = float(job.get('started_at') or 0)
        if job.get('status') == 'running' and now - started <= max_age_seconds:
            continue
        pipe = client.pipeline()
        pipe.lrem(PROCESSING_KEY, 0, job_id)
        pipe.hset(_job_key(job_id), mapping={'status': 'queued', 'updated_at': str(now)})
        pipe.lpush(QUEUE_KEY, job_id)
        pipe.execute()
        recovered += 1
    return recovered
