"""Shared cache and fixed-window limits with an in-process fallback.

Redis is optional. Development and tests keep working without another service;
production workers share cache versions and counters when REDIS_URL is set.
"""
import json
import threading
import time

from flask import current_app


_LOCK = threading.RLock()
_MEMORY_CACHE = {}
_MEMORY_COUNTERS = {}
_MEMORY_VERSIONS = {}
_REDIS_CLIENT = None
_REDIS_URL = None
_REDIS_RETRY_AT = 0.0


def _mark_redis_unavailable():
    global _REDIS_CLIENT, _REDIS_RETRY_AT
    _REDIS_CLIENT = None
    _REDIS_RETRY_AT = time.monotonic() + 15


def _redis():
    global _REDIS_CLIENT, _REDIS_URL, _REDIS_RETRY_AT
    url = str(current_app.config.get('REDIS_URL') or '').strip()
    if not url:
        return None
    if _REDIS_CLIENT is not None and _REDIS_URL == url:
        return _REDIS_CLIENT
    if _REDIS_URL == url and time.monotonic() < _REDIS_RETRY_AT:
        return None
    try:
        import redis
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=float(current_app.config.get('REDIS_CONNECT_TIMEOUT', 0.3)),
            socket_timeout=float(current_app.config.get('REDIS_SOCKET_TIMEOUT', 0.5)),
            decode_responses=True,
        )
        client.ping()
        _REDIS_CLIENT, _REDIS_URL, _REDIS_RETRY_AT = client, url, 0.0
        return client
    except Exception:
        _REDIS_CLIENT, _REDIS_URL = None, url
        _REDIS_RETRY_AT = time.monotonic() + 15
        return None


def redis_client():
    """Return the shared Redis client, or None when Redis is unavailable."""
    return _redis()


def cache_get(key):
    client = _redis()
    if client is not None:
        try:
            raw = client.get(f'homework:cache:{key}')
            return json.loads(raw) if raw else None
        except Exception:
            _mark_redis_unavailable()
    now = time.monotonic()
    with _LOCK:
        item = _MEMORY_CACHE.get(key)
        if not item or item[0] <= now:
            _MEMORY_CACHE.pop(key, None)
            return None
        return item[1]


def cache_set(key, value, ttl_seconds):
    ttl_seconds = max(1, int(ttl_seconds))
    client = _redis()
    if client is not None:
        try:
            client.setex(f'homework:cache:{key}', ttl_seconds,
                         json.dumps(value, ensure_ascii=False, separators=(',', ':')))
            return
        except Exception:
            _mark_redis_unavailable()
    with _LOCK:
        _MEMORY_CACHE[key] = (time.monotonic() + ttl_seconds, value)
        if len(_MEMORY_CACHE) > 4096:
            now = time.monotonic()
            for old_key, item in list(_MEMORY_CACHE.items()):
                if item[0] <= now:
                    _MEMORY_CACHE.pop(old_key, None)


def knowledge_version(library):
    key = f'homework:knowledge:version:{library}'
    client = _redis()
    if client is not None:
        try:
            value = client.get(key)
            if value is None:
                client.setnx(key, 1)
                return 1
            return int(value)
        except Exception:
            _mark_redis_unavailable()
    with _LOCK:
        return _MEMORY_VERSIONS.get(library, 1)


def bump_knowledge_version(library):
    key = f'homework:knowledge:version:{library}'
    client = _redis()
    if client is not None:
        try:
            return int(client.incr(key))
        except Exception:
            _mark_redis_unavailable()
    with _LOCK:
        value = _MEMORY_VERSIONS.get(library, 1) + 1
        _MEMORY_VERSIONS[library] = value
        return value


def check_rate_limit(scope, subject, limit, window_seconds=60):
    """Return (allowed, retry_after_seconds) for one user and operation."""
    limit = int(limit or 0)
    window_seconds = max(1, int(window_seconds or 60))
    if limit <= 0:
        return True, 0
    window = int(time.time()) // window_seconds
    key = f'{scope}:{subject}:{window}'
    client = _redis()
    if client is not None:
        redis_key = f'homework:limit:{key}'
        try:
            count = int(client.incr(redis_key))
            if count == 1:
                client.expire(redis_key, window_seconds + 2)
            retry_after = window_seconds - (int(time.time()) % window_seconds)
            return count <= limit, max(1, retry_after)
        except Exception:
            _mark_redis_unavailable()
    now = time.monotonic()
    with _LOCK:
        count, expires = _MEMORY_COUNTERS.get(key, (0, now + window_seconds + 2))
        count += 1
        _MEMORY_COUNTERS[key] = (count, expires)
        if len(_MEMORY_COUNTERS) > 8192:
            for old_key, item in list(_MEMORY_COUNTERS.items()):
                if item[1] <= now:
                    _MEMORY_COUNTERS.pop(old_key, None)
        return count <= limit, max(1, int(expires - now))
