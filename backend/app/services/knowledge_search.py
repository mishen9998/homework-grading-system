"""Automatic local hybrid retrieval for approved knowledge entries."""
import hashlib
import math
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
from app.models.knowledge import KnowledgeChunk, KnowledgeEntry
from app.services.runtime_control import cache_get, cache_set, knowledge_version
from app.services.vector_store import (search_entry_ids, upsert_entries, search_chunk_ids,
                                       upsert_chunks, delete_entry_chunks)


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
_MODEL_PATH = None
_ENCODE_SEMAPHORE = threading.BoundedSemaphore(2)
HASH_ENCODER = 'hashed-char-ngram-v3-chunks'
_FULLTEXT_AVAILABLE = {}
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
    return sorted((token for token in tokens if 1 < len(token) <= 30), key=lambda token: (-len(token), token))[:120]


def _features(text):
    text = (text or '').lower()
    features = _WORD.findall(text)
    for run in _CJK_RUN.findall(text):
        features.extend(run[i:i + 2] for i in range(len(run) - 1))
        features.extend(run[i:i + 3] for i in range(len(run) - 2))
    return features


def _load_model():
    global _MODEL, _MODEL_TRIED, _MODEL_PATH
    model_path = str(current_app.config.get('LOCAL_EMBEDDING_MODEL') or '').strip()
    if not model_path:
        return None
    if not _MODEL_TRIED or _MODEL_PATH != model_path:
        with _MODEL_LOCK:
            if not _MODEL_TRIED or _MODEL_PATH != model_path:
                _MODEL_TRIED = True
                _MODEL_PATH = model_path
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
        if file_path.is_file() and file_path.suffix.lower() in {'.json', '.safetensors', '.bin', '.txt', '.model', '.onnx'}:
            signature.update(file_path.relative_to(model_path).as_posix().encode('utf-8'))
            with file_path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    signature.update(block)
    # Same weights remain compatible after moving to another machine/path.
    return 'sentence-transformers:sha256-' + signature.hexdigest()[:24]


def active_encoder_name():
    remote_url = str(current_app.config.get('EMBEDDING_SERVICE_URL') or '').strip()
    if remote_url:
        return 'embedding-service:' + str(current_app.config.get(
            'EMBEDDING_SERVICE_MODEL_ID') or 'unknown') + ':chunks-v1'
    if _load_model() is None:
        return HASH_ENCODER
    return _model_identifier(str(current_app.config['LOCAL_EMBEDDING_MODEL'])) + ':chunks-v1'


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
            return _validate_vectors(vectors)
        except (requests.RequestException, TypeError, ValueError) as exc:
            raise EmbeddingUnavailable(f'Embedding服务不可用: {exc}') from exc
    model = _load_model()
    if model is not None:
        try:
            with _ENCODE_SEMAPHORE:
                vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False,
                                       batch_size=min(32, max(1, len(texts))))
            return _validate_vectors(vectors)
        except Exception as exc:
            raise EmbeddingUnavailable('本地模型计算失败') from exc
    return [_hashed_vector(text) for text in texts]


def _validate_vectors(vectors):
    """Reject malformed embeddings instead of silently zipping wrong dimensions."""
    result = []
    dimensions = None
    for vector in vectors:
        converted = [float(value) for value in vector]
        if not converted or any(not math.isfinite(value) for value in converted):
            raise ValueError('向量为空或包含非有限数')
        dimensions = dimensions or len(converted)
        if len(converted) != dimensions or dimensions > 16384:
            raise ValueError('向量维度不一致或超限')
        length = math.sqrt(sum(value * value for value in converted))
        result.append([value / length for value in converted] if length else converted)
    return result


def _cosine(left, right):
    if len(left) != len(right):
        return 0.0
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
    values = list(struct.unpack(f'<{dimensions}f', blob))
    return values if all(math.isfinite(value) for value in values) else None


def clear_embedding(entry):
    entry.embedding = None
    entry.embedding_dim = None
    entry.embedding_model = None
    entry.embedding_hash = None
    entry.embedded_at = None
    if entry.id:
        KnowledgeChunk.query.filter_by(entry_id=entry.id).delete(synchronize_session=False)
        delete_entry_chunks(entry.id)


def split_passages(content, size=360, overlap=60):
    """Bound passages to the local Chinese encoder context; retain exact text."""
    if size <= overlap or overlap < 0:
        raise ValueError('分块大小必须大于重叠长度')
    passages, start = [], 0
    while start < len(content):
        end = min(start + size, len(content))
        if end < len(content):
            boundary = max(content.rfind(mark, start + size // 2, end) for mark in ('\n', '。', '！', '？', '；'))
            if boundary >= 0:
                end = boundary + 1
        passages.append(content[start:end])
        if end == len(content):
            break
        start = max(start + 1, end - overlap)
    return passages or ['']


def index_entries(entries, commit=False):
    """Index approved entries in a batch; rejected/pending entries are cleared."""
    db.session.flush()
    approved = []
    for entry in entries:
        if entry.status == 'approved':
            approved.append(entry)
        else:
            clear_embedding(entry)
    encoder = active_encoder_name()
    if approved:
        jobs = [(entry, position, passage) for entry in approved
                for position, passage in enumerate(split_passages(entry.content))]
        try:
            vectors = []
            # Bound both local model batches and remote request size.
            for offset in range(0, len(jobs), 32):
                vectors.extend(encode_many([f'{entry.category}\n{entry.title[:100]}\n{passage}'
                                            for entry, _, passage in jobs[offset:offset + 32]]))
        except EmbeddingUnavailable as exc:
            current_app.logger.warning('%s；本次仅保留关键词检索', exc)
            if commit:
                db.session.commit()
            return 0
        chunks, per_entry = [], {entry.id: [] for entry in approved}
        for entry in approved:
            KnowledgeChunk.query.filter_by(entry_id=entry.id).delete(synchronize_session=False)
            delete_entry_chunks(entry.id)
        for (entry, position, passage), vector in zip(jobs, vectors):
            chunk = KnowledgeChunk(entry_id=entry.id, library=entry.library, chunk_index=position,
                content=passage, content_hash=hashlib.sha256(passage.encode('utf-8')).hexdigest(),
                embedding=_pack(vector), embedding_dim=len(vector), embedding_model=encoder)
            db.session.add(chunk)
            chunks.append(chunk)
            per_entry[entry.id].append(vector)
        document_vectors = []
        for entry in approved:
            parts = per_entry[entry.id]
            vector = _validate_vectors([[sum(values) / len(parts) for values in zip(*parts)]])[0]
            document_vectors.append(vector)
            entry.embedding = _pack(vector)
            entry.embedding_dim = len(vector)
            entry.embedding_model = encoder
            entry.embedding_hash = _fingerprint(entry)
            entry.embedded_at = datetime.utcnow()
        # Qdrant is an optional on-premise candidate index. MySQL remains the
        # source of truth and the persisted vectors remain a safe fallback.
        db.session.flush()
        upsert_entries(approved, document_vectors, encoder)
        for offset in range(0, len(chunks), 64):
            upsert_chunks(chunks[offset:offset + 64], vectors[offset:offset + 64], encoder)
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
        chunk_entry_ids = {row[0] for row in db.session.query(KnowledgeChunk.entry_id).filter(
            KnowledgeChunk.entry_id.in_([entry.id for entry in page]),
            KnowledgeChunk.embedding_model == encoder).distinct()}
        stale = [entry for entry in page if force or not embedding_is_current(entry, encoder)
                 or entry.id not in chunk_entry_ids]
        if stale:
            indexed += index_entries(stale)
            db.session.commit()
        current_entries = [entry for entry in page if entry not in stale]
        if current_entries:
            stored = [_unpack(entry.embedding, entry.embedding_dim) for entry in current_entries]
            valid = [(entry, vector) for entry, vector in zip(current_entries, stored) if vector]
            if valid:
                upsert_entries([item[0] for item in valid], [item[1] for item in valid], encoder)
            chunks = KnowledgeChunk.query.filter(KnowledgeChunk.entry_id.in_([entry.id for entry in current_entries]),
                                                 KnowledgeChunk.embedding_model == encoder).all()
            for offset in range(0, len(chunks), 64):
                batch = chunks[offset:offset + 64]
                vectors = [_unpack(chunk.embedding, chunk.embedding_dim) for chunk in batch]
                if all(vectors):
                    upsert_chunks(batch, vectors, encoder)
        last_id = page[-1].id
    if db.session.new or db.session.dirty:
        db.session.commit()
    return indexed


def _lexical_score(tokens, entry):
    return _lexical_text_score(tokens, entry.title, entry.content)


def _lexical_text_score(tokens, title, content):
    title = (title or '').lower()
    content = (content or '').lower()
    title_hits = sum(token in title for token in tokens)
    content_hits = sum(token in content for token in tokens)
    return min(1.0, (title_hits * 3 + content_hits) / max(3.0, len(tokens) * 2.0)) if tokens else 0.0


def _mysql_fulltext_available():
    if db.engine.dialect.name != 'mysql' or not current_app.config.get('KNOWLEDGE_MYSQL_FULLTEXT', True):
        return False
    engine_key = str(db.engine.url.render_as_string(hide_password=True))
    if engine_key not in _FULLTEXT_AVAILABLE:
        with _FULLTEXT_LOCK:
            if engine_key not in _FULLTEXT_AVAILABLE:
                count = db.session.execute(sql_text(
                    "SELECT COUNT(*) FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'knowledge_entries' "
                    "AND index_name = 'ft_knowledge_entries_title_content'"
                )).scalar()
                _FULLTEXT_AVAILABLE[engine_key] = bool(count)
    return _FULLTEXT_AVAILABLE[engine_key]


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
            sql_text('MATCH(title, content) AGAINST (:knowledge_fts_query IN BOOLEAN MODE) DESC'),
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
    if any(item.get('fingerprint') != _fingerprint(by_id[item['entry_id']]) for item in cached):
        return None
    return [dict(item, entry=by_id[item['entry_id']]) for item in cached]


def _cache_payload(result):
    return [
        {
            'entry_id': item['entry'].id,
            'fingerprint': _fingerprint(item['entry']),
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
    limit = max(1, min(20, int(limit)))
    tokens = expand_query(message)
    if not tokens:
        return [], []
    query = KnowledgeEntry.query.filter_by(library=library, status='approved')
    if query.with_entities(KnowledgeEntry.id).first() is None:
        return [], tokens
    encoder = active_encoder_name()
    database_key = hashlib.sha256(str(db.engine.url.render_as_string(hide_password=True)).encode()).hexdigest()
    neural_floor = float(current_app.config.get('KNOWLEDGE_NEURAL_MIN_SCORE', 0.50))
    cache_material = f'chunk-rank-v2\0{neural_floor}\0{database_key}\0{library}\0{encoder}\0{knowledge_version(library)}\0{limit}\0{message.strip().lower()}'
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
    chunk_ids = search_chunk_ids(query_vector, library, encoder, vector_limit) if query_vector else []
    # Passage hits are more precise for long documents; the document index is
    # only a compatibility fallback, avoiding a second HTTP query on a hit.
    vector_ids = search_entry_ids(query_vector, library, encoder, vector_limit) if query_vector and not chunk_ids else []
    if chunk_ids:
        parents = db.session.query(KnowledgeChunk.entry_id).join(KnowledgeEntry).filter(
            KnowledgeChunk.id.in_(chunk_ids), KnowledgeChunk.library == library,
            KnowledgeChunk.embedding_model == encoder, KnowledgeEntry.library == library,
            KnowledgeEntry.status == 'approved').distinct().all()
        vector_ids = list(dict.fromkeys(vector_ids + [row[0] for row in parents]))
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

    # Query is strictly read-only. Index with the maintenance command, never
    # encode hundreds of stale documents during a student's question.
    current_ids = [entry.id for entry in candidates if embedding_is_current(entry, encoder)]
    chunks_by_entry = {}
    if current_ids:
        chunk_limit = max(100, min(2000, int(current_app.config.get('KNOWLEDGE_CHUNK_CANDIDATES', 600))))
        chunk_query = KnowledgeChunk.query.filter(KnowledgeChunk.entry_id.in_(current_ids),
            KnowledgeChunk.library == library, KnowledgeChunk.embedding_model == encoder)
        chunks = chunk_query.filter(KnowledgeChunk.id.in_(chunk_ids)).limit(vector_limit).all() if chunk_ids else []
        seen = {chunk.id for chunk in chunks}
        lexical_chunks = chunk_query.filter(or_(*[KnowledgeChunk.content.contains(token, autoescape=True)
                                                  for token in tokens[:40]])).order_by(KnowledgeChunk.id.desc()).limit(chunk_limit).all()
        chunks.extend(chunk for chunk in lexical_chunks if chunk.id not in seen)
        if not chunk_ids and len(chunks) < chunk_limit:
            seen = {chunk.id for chunk in chunks}
            chunks.extend(chunk for chunk in chunk_query.order_by(KnowledgeChunk.id.desc()).limit(chunk_limit - len(chunks)).all()
                          if chunk.id not in seen)
        for chunk in chunks:
            chunks_by_entry.setdefault(chunk.entry_id, []).append(chunk)
    ranked = []
    for entry in candidates:
        lexical = _lexical_score(tokens, entry)
        choices = []
        for chunk in chunks_by_entry.get(entry.id, []):
            if hashlib.sha256(chunk.content.encode('utf-8')).hexdigest() != chunk.content_hash:
                continue
            vector = _unpack(chunk.embedding, chunk.embedding_dim)
            semantic = _cosine(query_vector, vector) if query_vector and vector else 0.0
            passage_lexical = _lexical_text_score(tokens, entry.title, chunk.content)
            choices.append((passage_lexical * 0.52 + semantic * 0.48, semantic, chunk.content))
        if not choices:
            choices = [(_lexical_text_score(tokens, entry.title, passage), 0.0, passage)
                       for passage in split_passages(entry.content)]
        _, semantic, passage = max(choices, key=lambda item: item[0])
        ranked.append((lexical * 0.52 + semantic * 0.48, lexical, semantic, entry, passage))
    ranked.sort(key=lambda item: (item[0], item[3].id), reverse=True)

    result = []
    semantic_threshold = 0.52 if encoder.startswith(('sentence-transformers:', 'embedding-service:')) else 0.34
    for score, lexical, semantic, entry, passage in ranked:
        has_neural_evidence = (query_vector is not None and entry.id in chunks_by_entry
                               and encoder.startswith(('sentence-transformers:', 'embedding-service:')))
        if has_neural_evidence and semantic < neural_floor:
            continue
        if lexical == 0 and semantic < semantic_threshold:
            continue
        result.append({'entry': entry, 'score': round(score, 4),
                       'lexical_score': round(lexical, 4), 'semantic_score': round(semantic, 4),
                       'passage': passage, 'embedding_model': encoder})
        if len(result) >= limit:
            break
    cache_set(cache_key, _cache_payload(result), current_app.config.get('KNOWLEDGE_CACHE_TTL', 120))
    return result, tokens
