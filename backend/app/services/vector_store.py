"""Optional on-premise Qdrant adapter used only for vector candidate lookup."""
import hashlib
import re
import threading
import time
from urllib.parse import quote

import requests
from flask import current_app


_READY = set()
_UNAVAILABLE_UNTIL = {}
_LOCK = threading.Lock()


def _settings(collection_key='QDRANT_COLLECTION', default='school_knowledge'):
    url = str(current_app.config.get('QDRANT_URL') or '').strip().rstrip('/')
    collection = str(current_app.config.get(collection_key) or default).strip()
    if not url or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', collection):
        return None
    headers = {'Content-Type': 'application/json'}
    api_key = str(current_app.config.get('QDRANT_API_KEY') or '').strip()
    if api_key:
        headers['api-key'] = api_key
    return url, collection, headers, float(current_app.config.get('QDRANT_TIMEOUT', 1.5))


def _encoder_key(encoder):
    return hashlib.sha256(encoder.encode('utf-8')).hexdigest()[:20]


def _mark_unavailable(settings, dimensions, seconds=15):
    marker = (settings[0], settings[1], dimensions)
    _READY.discard(marker)
    _UNAVAILABLE_UNTIL[marker] = time.monotonic() + seconds


def _ensure_collection(settings, dimensions, payload_fields=None):
    url, collection, headers, timeout = settings
    marker = (url, collection, dimensions)
    if marker in _READY:
        return True
    if time.monotonic() < _UNAVAILABLE_UNTIL.get(marker, 0):
        return False
    with _LOCK:
        if marker in _READY:
            return True
        endpoint = f'{url}/collections/{quote(collection)}'
        try:
            response = requests.get(endpoint, headers=headers, timeout=timeout)
            if response.status_code == 404:
                response = requests.put(endpoint, headers=headers, timeout=timeout,
                                        json={'vectors': {'size': dimensions, 'distance': 'Cosine'}})
                if response.status_code in (200, 201):
                    response = requests.get(endpoint, headers=headers, timeout=timeout)
            if response.status_code not in (200, 201):
                _UNAVAILABLE_UNTIL[marker] = time.monotonic() + 15
                return False
            result = response.json().get('result', {})
            details = result.get('config', {}).get('params', {}).get('vectors') if isinstance(result, dict) else None
            size = details.get('size') if isinstance(details, dict) else None
            if size is not None and int(size) != dimensions:
                current_app.logger.error('Qdrant 集合向量维度不匹配 collection=%s expected=%s actual=%s',
                                         collection, dimensions, size)
                _UNAVAILABLE_UNTIL[marker] = time.monotonic() + 60
                return False
            for field_name, field_schema in (payload_fields or (
                    ('library', 'keyword'), ('encoder', 'keyword'))):
                index_response = requests.put(
                    f'{endpoint}/index?wait=true', headers=headers, timeout=timeout,
                    json={'field_name': field_name, 'field_schema': field_schema})
                # 400 may mean the payload index already exists on older
                # Qdrant versions; collection search remains valid either way.
                if index_response.status_code not in (200, 201, 400):
                    current_app.logger.warning('Qdrant 载荷索引创建失败 field=%s status=%s',
                                               field_name, index_response.status_code)
            _READY.add(marker)
            _UNAVAILABLE_UNTIL.pop(marker, None)
            return True
        except (requests.RequestException, ValueError, TypeError) as exc:
            current_app.logger.warning('Qdrant 暂不可用，将使用数据库检索: %s', exc)
            _UNAVAILABLE_UNTIL[marker] = time.monotonic() + 15
            return False


def upsert_entries(entries, vectors, encoder):
    settings = _settings()
    if not settings or not entries or not vectors:
        return False
    if not _ensure_collection(settings, len(vectors[0])):
        return False
    url, collection, headers, timeout = settings
    points = [
        {'id': entry.id, 'vector': vector,
         'payload': {'entry_id': entry.id, 'library': entry.library,
                     'encoder': _encoder_key(encoder)}}
        for entry, vector in zip(entries, vectors) if entry.id is not None
    ]
    if not points:
        return False
    try:
        response = requests.put(f'{url}/collections/{quote(collection)}/points?wait=true',
                                headers=headers, timeout=max(timeout, 5), json={'points': points})
        if response.status_code not in (200, 201):
            _mark_unavailable(settings, len(vectors[0]))
            return False
        return True
    except (requests.RequestException, ValueError, TypeError) as exc:
        current_app.logger.warning('Qdrant 写入失败，数据库向量仍然可用: %s', exc)
        _mark_unavailable(settings, len(vectors[0]))
        return False


def search_entry_ids(vector, library, encoder, limit):
    settings = _settings()
    if not settings or not vector or not _ensure_collection(settings, len(vector)):
        return []
    url, collection, headers, timeout = settings
    body = {
        'vector': vector,
        'filter': {'must': [
            {'key': 'library', 'match': {'value': library}},
            {'key': 'encoder', 'match': {'value': _encoder_key(encoder)}},
        ]},
        'limit': int(limit),
        'with_payload': False,
        'with_vector': False,
    }
    try:
        response = requests.post(f'{url}/collections/{quote(collection)}/points/search',
                                 headers=headers, timeout=timeout, json=body)
        if response.status_code != 200:
            _mark_unavailable(settings, len(vector))
            return []
        return [int(item['id']) for item in response.json().get('result', []) if str(item.get('id', '')).isdigit()]
    except (requests.RequestException, ValueError, TypeError) as exc:
        current_app.logger.warning('Qdrant 查询失败，将使用数据库候选集: %s', exc)
        _mark_unavailable(settings, len(vector))
        return []


def delete_entry(entry_id):
    settings = _settings()
    if not settings or not entry_id:
        return False
    url, collection, headers, timeout = settings
    try:
        response = requests.post(f'{url}/collections/{quote(collection)}/points/delete?wait=true',
                                 headers=headers, timeout=timeout,
                                 json={'points': [int(entry_id)]})
        return response.status_code in (200, 201, 404)
    except requests.RequestException:
        return False


def upsert_chunks(chunks, vectors, encoder):
    settings = _settings('QDRANT_CHUNK_COLLECTION', 'school_knowledge_chunks')
    if not settings or not chunks or not vectors:
        return False
    fields = (('library', 'keyword'), ('encoder', 'keyword'), ('entry_id', 'integer'))
    if not _ensure_collection(settings, len(vectors[0]), fields):
        return False
    url, collection, headers, timeout = settings
    points = [{'id': chunk.id, 'vector': vector,
               'payload': {'entry_id': chunk.entry_id, 'library': chunk.library,
                           'encoder': _encoder_key(encoder)}}
              for chunk, vector in zip(chunks, vectors) if chunk.id is not None]
    try:
        response = requests.put(f'{url}/collections/{quote(collection)}/points?wait=true',
                                headers=headers, timeout=max(timeout, 5), json={'points': points})
        if response.status_code not in (200, 201):
            _mark_unavailable(settings, len(vectors[0]))
            return False
        return True
    except requests.RequestException as exc:
        current_app.logger.warning('Qdrant 知识切片写入失败: %s', exc)
        return False


def search_chunk_ids(vector, library, encoder, limit):
    settings = _settings('QDRANT_CHUNK_COLLECTION', 'school_knowledge_chunks')
    fields = (('library', 'keyword'), ('encoder', 'keyword'), ('entry_id', 'integer'))
    if not settings or not vector or not _ensure_collection(settings, len(vector), fields):
        return []
    url, collection, headers, timeout = settings
    body = {'vector': vector, 'filter': {'must': [
        {'key': 'library', 'match': {'value': library}},
        {'key': 'encoder', 'match': {'value': _encoder_key(encoder)}},
    ]}, 'limit': int(limit), 'with_payload': False, 'with_vector': False}
    try:
        response = requests.post(f'{url}/collections/{quote(collection)}/points/search',
                                 headers=headers, timeout=timeout, json=body)
        if response.status_code != 200:
            _mark_unavailable(settings, len(vector))
            return []
        return [int(item['id']) for item in response.json().get('result', [])
                if str(item.get('id', '')).isdigit()]
    except (requests.RequestException, ValueError, TypeError):
        _mark_unavailable(settings, len(vector))
        return []


def delete_entry_chunks(entry_id):
    settings = _settings('QDRANT_CHUNK_COLLECTION', 'school_knowledge_chunks')
    if not settings or not entry_id:
        return False
    url, collection, headers, timeout = settings
    try:
        response = requests.post(
            f'{url}/collections/{quote(collection)}/points/delete?wait=true',
            headers=headers, timeout=timeout,
            json={'filter': {'must': [{'key': 'entry_id', 'match': {'value': int(entry_id)}}]}})
        return response.status_code in (200, 201, 404)
    except requests.RequestException:
        return False
