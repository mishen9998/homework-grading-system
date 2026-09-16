"""Automatic local hybrid retrieval for approved knowledge entries."""
import hashlib
import math
import os
import re
import struct
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import requests

from flask import current_app
from sqlalchemy import or_, text as sql_text

from app import db
from app.models.knowledge import KnowledgeEntry
from app.services.runtime_control import cache_get, cache_set, knowledge_version
from app.services.vector_store import search_entry_ids, upsert_entries


SYNONYM_GROUPS = {
    '图书馆': ('图书馆', '阅览室', '图书楼', '借阅'),
    '楼层': ('楼层', '几楼', '哪一层', '所在楼', '位置'),
    '校规': ('校规', '校纪', '校训', '规章', '规定'),
    '处罚': ('处罚', '处分', '惩罚', '违纪处理', '违规处理'),
    '课程': ('课程', '科目', '网课', '线上课', '学习资源'),
    '缓考': ('缓考', '延期考试', '延考', '申请考试延期'),
    '作业': ('作业', '任务', '练习', '课后题'),
    '提交': ('提交', '交作业', '上交', '递交'),
    '批改': ('批改', '评分', '评阅', '阅卷'),
    '宿舍': ('宿舍', '寝室', '公寓', '住宿'),
    '食堂': ('食堂', '餐厅', '饭堂', '就餐'),
}

_GROUP_LOOKUP = {term: terms for terms in SYNONYM_GROUPS.values() for term in terms}
_CJK_RUN = re.compile(r'[\u4e00-\u9fff]+')
_WORD = re.compile(r'[a-z0-9_]{2,}', re.I)
_MODEL = None
_MODEL_TRIED = False
_MODEL_LOCK = threading.Lock()
_ENCODE_SEMAPHORE = threading.BoundedSemaphore(2)
HASH_ENCODER = 'hashed-char-ngram-v2'
_FULLTEXT_AVAILABLE = None
_FULLTEXT_LOCK = threading.Lock()


class EmbeddingUnavailable(RuntimeError):
    pass


def expand_query(message):
    message = (message or '').lower()
    tokens = set(_WORD.findall(message))
    for run in _CJK_RUN.findall(message):
        tokens.update(run[i:i + 2] for i in range(len(run) - 1))
        tokens.update(run[i:i + 3] for i in range(len(run) - 2))
    for term, group in _GROUP_LOOKUP.items():
        if term in message:
            tokens.update(group)
    for canonical, group in SYNONYM_GROUPS.items():
        if any(term in message for term in group):
            tokens.add(canonical)
    return sorted((token for token in tokens if 1 < len(token) <= 30), key=len, reverse=True)[:120]


def _features(text):
    text = (text or '').lower()
    features = _WORD.findall(text)
    for run in _CJK_RUN.findall(text):
        features.extend(run[i:i + 2] for i in range(len(run) - 1))
        features.extend(run[i:i + 3] for i in range(len(run) - 2))
    return features


def _load_model():
    global _MODEL, _MODEL_TRIED
    model_path = os.environ.get('LOCAL_EMBEDDING_MODEL', '').strip()
    if not model_path:
        return None
    if not _MODEL_TRIED:
        with _MODEL_LOCK:
            if not _MODEL_TRIED:
                _MODEL_TRIED = True
                try:
                    from sentence_transformers import SentenceTransformer
                    _MODEL = SentenceTransformer(model_path, local_files_only=True)
                except Exception:
                    _MODEL = None
    return _MODEL


@lru_cache(maxsize=4)
def _model_identifier(model_path_text):
    model_path = Path(model_path_text).resolve()
    signature = hashlib.sha256()
    for file_path in sorted(model_path.rglob('*')):
        if file_path.is_file() and file_path.suffix.lower() in {'.json', '.safetensors', '.bin'}:
            stat = file_path.stat()
            signature.update(str(file_path.relative_to(model_path)).encode('utf-8'))
            signature.update(f'{stat.st_size}:{stat.st_mtime_ns}'.encode('ascii'))
    return 'sentence-transformers:' + str(model_path).replace('\\', '/') + '#' + signature.hexdigest()[:12]


def active_encoder_name():
    remote_url = str(current_app.config.get('EMBEDDING_SERVICE_URL') or '').strip()
    if remote_url:
        return 'embedding-service:' + str(current_app.config.get(
            'EMBEDDING_SERVICE_MODEL_ID') or 'unknown')
    if _load_model() is None:
        return HASH_ENCODER
    return _model_identifier(os.environ['LOCAL_EMBEDDING_MODEL'])


@lru_cache(maxsize=8192)
def _hashed_vector(text, dimensions=256):
    vector = [0.0] * dimensions
    for feature in _features(text):
        digest = hashlib.blake2b(feature.encode('utf-8'), digest_size=8).digest()
        index = int.from_bytes(digest[:4], 'big') % dimensions
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def encode_many(texts):
    texts = [str(text or '') for text in texts]
    remote_url = str(current_app.config.get('EMBEDDING_SERVICE_URL') or '').strip().rstrip('/')
    if remote_url:
        headers = {}
        token = str(current_app.config.get('EMBEDDING_SERVICE_TOKEN') or '').strip()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        try:
            response = requests.post(
                f'{remote_url}/encode', json={'texts': texts}, headers=headers,
                timeout=float(current_app.config.get('EMBEDDING_SERVICE_TIMEOUT', 5)))
            response.raise_for_status()
            vectors = response.json().get('vectors')
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError('向量数量不匹配')
            return [[float(value) for value in vector] for vector in vectors]
        except (requests.RequestException, TypeError, ValueError) as exc:
            raise EmbeddingUnavailable(f'Embedding服务不可用: {exc}') from exc
    model = _load_model()
    if model is not None:
        with _ENCODE_SEMAPHORE:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False,
                                   batch_size=min(32, max(1, len(texts))))
        return [[float(value) for value in vector] for vector in vectors]
    return [_hashed_vector(text) for text in texts]


def _cosine(left, right):
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def _entry_text(entry):
    return f'{entry.category}\n{entry.title}\n{entry.content}'


def _fingerprint(entry):
    return hashlib.sha256(f'{entry.library}\0{_entry_text(entry)}'.encode('utf-8')).hexdigest()


def _pack(vector):
    return struct.pack(f'<{len(vector)}f', *vector)


def _unpack(blob, dimensions):
    if not blob or not dimensions or len(blob) != dimensions * 4:
        return None
    return list(struct.unpack(f'<{dimensions}f', blob))


def clear_embedding(entry):
    entry.embedding = None
    entry.embedding_dim = None
    entry.embedding_model = None
    entry.embedding_hash = None
    entry.embedded_at = None


def index_entries(entries, commit=False):
    """Index approved entries in a batch; rejected/pending entries are cleared."""
    approved = []
    for entry in entries:
        if entry.status == 'approved':
            approved.append(entry)
        else:
            clear_embedding(entry)
    encoder = active_encoder_name()
    if approved:
        try:
            vectors = encode_many([_entry_text(entry) for entry in approved])
        except EmbeddingUnavailable as exc:
            current_app.logger.warning('%s；本次仅保留关键词检索', exc)
            if commit:
                db.session.commit()
            return 0
        for entry, vector in zip(approved, vectors):
            entry.embedding = _pack(vector)
            entry.embedding_dim = len(vector)
            entry.embedding_model = encoder
            entry.embedding_hash = _fingerprint(entry)
            entry.embedded_at = datetime.utcnow()
        # Qdrant is an optional on-premise candidate index. MySQL remains the
        # source of truth and the persisted vectors remain a safe fallback.
        upsert_entries(approved, vectors, encoder)
    if commit:
        db.session.commit()
    return len(approved)


def index_entry(entry, commit=False):
    return index_entries([entry], commit=commit)


def embedding_is_current(entry, encoder=None):
    encoder = encoder or active_encoder_name()
    return bool(entry.status == 'approved' and entry.embedding and
                entry.embedding_model == encoder and entry.embedding_hash == _fingerprint(entry))


def rebuild_embeddings(library=None, force=False, batch_size=64):
    """Backfill missing/outdated approved vectors without DeepSeek."""
    indexed = 0
    encoder = active_encoder_name()
    last_id = 0
    while True:
        query = KnowledgeEntry.query.filter(KnowledgeEntry.status == 'approved', KnowledgeEntry.id > last_id)
        if library:
            query = query.filter_by(library=library)
        page = query.order_by(KnowledgeEntry.id.asc()).limit(batch_size).all()
        if not page:
            break
        stale = [entry for entry in page if force or not embedding_is_current(entry, encoder)]
        if stale:
            indexed += index_entries(stale)
            db.session.commit()
        current_entries = [entry for entry in page if entry not in stale]
        if current_entries:
            stored = [_unpack(entry.embedding, entry.embedding_dim) for entry in current_entries]
            valid = [(entry, vector) for entry, vector in zip(current_entries, stored) if vector]
            if valid:
                upsert_entries([item[0] for item in valid], [item[1] for item in valid], encoder)
        last_id = page[-1].id
    if db.session.new or db.session.dirty:
        db.session.commit()
    return indexed


def _lexical_score(tokens, entry):
    title = (entry.title or '').lower()
    content = (entry.content or '').lower()
    title_hits = sum(token in title for token in tokens)
    content_hits = sum(token in content for token in tokens)
    return min(1.0, (title_hits * 3 + content_hits) / max(3.0, len(tokens) * 2.0)) if tokens else 0.0


def _mysql_fulltext_available():
    global _FULLTEXT_AVAILABLE
    if db.engine.dialect.name != 'mysql' or not current_app.config.get('KNOWLEDGE_MYSQL_FULLTEXT', True):
        return False
    if _FULLTEXT_AVAILABLE is None:
        with _FULLTEXT_LOCK:
            if _FULLTEXT_AVAILABLE is None:
                count = db.session.execute(sql_text(
                    "SELECT COUNT(*) FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'knowledge_entries' "
                    "AND index_name = 'ft_knowledge_entries_title_content'"
                )).scalar()
                _FULLTEXT_AVAILABLE = bool(count)
    return _FULLTEXT_AVAILABLE


def _lexical_candidates(query, tokens, limit):
    if not tokens:
        return []
    if _mysql_fulltext_available():
        # Tokens come from the local tokenizer, so MySQL boolean operators from
        # raw user input never reach MATCH AGAINST.
        search_text = ' '.join(tokens[:40])
        predicate = sql_text(
            'MATCH(title, content) AGAINST (:knowledge_fts_query IN BOOLEAN MODE)')
        return query.filter(predicate).params(knowledge_fts_query=search_text).order_by(
            KnowledgeEntry.id.desc()).limit(limit).all()
    return query.filter(or_(*[
        or_(KnowledgeEntry.title.contains(token, autoescape=True),
            KnowledgeEntry.content.contains(token, autoescape=True)) for token in tokens
    ])).order_by(KnowledgeEntry.id.desc()).limit(limit).all()


def _restore_cached(query, cached):
    ids = [item.get('entry_id') for item in cached if isinstance(item, dict)]
    if not ids:
        return [] if cached == [] else None
    entries = query.filter(KnowledgeEntry.id.in_(ids)).all()
    by_id = {entry.id: entry for entry in entries}
    if len(by_id) != len(set(ids)):
        return None
    return [dict(item, entry=by_id[item['entry_id']]) for item in cached]


def _cache_payload(result):
    return [
        {
            'entry_id': item['entry'].id,
            'score': item['score'],
            'lexical_score': item['lexical_score'],
            'semantic_score': item['semantic_score'],
            'passage': item['passage'],
            'embedding_model': item['embedding_model'],
        }
        for item in result
    ]


def retrieve(library, message, limit=5):
    """Return ranked approved entries using lexical and persisted vector scores."""
    tokens = expand_query(message)
    query = KnowledgeEntry.query.filter_by(library=library, status='approved')
    encoder = active_encoder_name()
    cache_material = f'{library}\0{encoder}\0{knowledge_version(library)}\0{limit}\0{message.strip().lower()}'
    cache_key = 'knowledge-search:' + hashlib.sha256(cache_material.encode('utf-8')).hexdigest()
    cached = cache_get(cache_key)
    if cached is not None:
        restored = _restore_cached(query, cached)
        if restored is not None:
            return restored, tokens

    lexical_limit = max(20, min(2000, int(current_app.config.get('KNOWLEDGE_LEXICAL_CANDIDATES', 300))))
    vector_limit = max(20, min(500, int(current_app.config.get('KNOWLEDGE_VECTOR_CANDIDATES', 80))))
    fallback_limit = max(100, min(5000, int(current_app.config.get('KNOWLEDGE_FALLBACK_CANDIDATES', 1500))))
    candidates = []
    if tokens:
        candidates = _lexical_candidates(query, tokens, lexical_limit)

    try:
        query_vector = encode_many([message])[0]
    except EmbeddingUnavailable as exc:
        current_app.logger.warning('%s；查询降级为关键词检索', exc)
        query_vector = None
    vector_ids = search_entry_ids(query_vector, library, encoder, vector_limit) if query_vector else []
    if vector_ids:
        by_id = {entry.id: entry for entry in query.filter(KnowledgeEntry.id.in_(vector_ids)).all()}
        known = {entry.id for entry in candidates}
        for entry_id in vector_ids:
            if entry_id in by_id and entry_id not in known:
                candidates.append(by_id[entry_id])
                known.add(entry_id)

    # Safe fallback for development and for a temporarily unavailable/empty
    # vector service. The cap prevents request time from growing without bound.
    if not vector_ids and len(candidates) < max(limit * 3, 20):
        known = {entry.id for entry in candidates}
        for entry in query.order_by(KnowledgeEntry.id.desc()).limit(fallback_limit).all():
            if entry.id not in known:
                candidates.append(entry)
                known.add(entry.id)
    if not candidates:
        cache_set(cache_key, [], current_app.config.get('KNOWLEDGE_CACHE_TTL', 120))
        return [], tokens

    stale = [entry for entry in candidates if (not entry.embedding or entry.embedding_model != encoder or
                                                entry.embedding_hash != _fingerprint(entry))]
    if stale:
        index_entries(stale)
        db.session.commit()
    ranked = []
    for entry in candidates:
        vector = _unpack(entry.embedding, entry.embedding_dim)
        lexical = _lexical_score(tokens, entry)
        semantic = _cosine(query_vector, vector) if query_vector and vector else 0.0
        ranked.append((lexical * 0.52 + semantic * 0.48, lexical, semantic, entry))
    ranked.sort(key=lambda item: (item[0], item[3].id), reverse=True)

    result = []
    semantic_threshold = 0.52 if encoder.startswith('sentence-transformers:') else 0.34
    for score, lexical, semantic, entry in ranked:
        if lexical == 0 and semantic < semantic_threshold:
            continue
        passages = [entry.content[i:i + 800] for i in range(0, len(entry.content), 600)] or ['']
        passage = max(passages, key=lambda text: _lexical_score(tokens, type('Entry', (), {
            'title': entry.title, 'content': text,
        })()))
        result.append({'entry': entry, 'score': round(score, 4),
                       'lexical_score': round(lexical, 4), 'semantic_score': round(semantic, 4),
                       'passage': passage, 'embedding_model': encoder})
        if len(result) >= limit:
            break
    cache_set(cache_key, _cache_payload(result), current_app.config.get('KNOWLEDGE_CACHE_TTL', 120))
    return result, tokens
