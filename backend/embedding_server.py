"""Small internal embedding service that combines concurrent requests into batches."""
import os
import queue
import threading
import time

from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer


MODEL_PATH = os.environ.get('LOCAL_EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')
MODEL_ID = os.environ.get('EMBEDDING_SERVICE_MODEL_ID', 'bge-small-zh-v1.5')
TOKEN = os.environ.get('EMBEDDING_SERVICE_TOKEN', '')
MAX_BATCH = max(1, int(os.environ.get('EMBEDDING_BATCH_SIZE', '128')))
WAIT_MS = max(1, int(os.environ.get('EMBEDDING_BATCH_WAIT_MS', '12')))
MAX_TEXTS = max(1, int(os.environ.get('EMBEDDING_MAX_TEXTS_PER_REQUEST', '128')))
MAX_CHARS = max(100, int(os.environ.get('EMBEDDING_MAX_CHARS', '4000')))

app = Flask(__name__)
model = SentenceTransformer(MODEL_PATH, local_files_only=os.path.exists(MODEL_PATH))
pending = queue.Queue(maxsize=int(os.environ.get('EMBEDDING_QUEUE_SIZE', '4096')))


class Work:
    def __init__(self, texts):
        self.texts = texts
        self.event = threading.Event()
        self.vectors = None
        self.error = None


def _batch_loop():
    while True:
        first = pending.get()
        items = [first]
        count = len(first.texts)
        deadline = time.monotonic() + WAIT_MS / 1000
        while count < MAX_BATCH:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                item = pending.get(timeout=remaining)
            except queue.Empty:
                break
            items.append(item)
            count += len(item.texts)
        flat = [text for item in items for text in item.texts]
        try:
            vectors = model.encode(flat, normalize_embeddings=True, show_progress_bar=False,
                                   batch_size=min(MAX_BATCH, len(flat)))
            offset = 0
            for item in items:
                size = len(item.texts)
                item.vectors = [[float(value) for value in vector]
                                for vector in vectors[offset:offset + size]]
                offset += size
        except Exception as exc:
            for item in items:
                item.error = str(exc)
        finally:
            for item in items:
                item.event.set()
                pending.task_done()


threading.Thread(target=_batch_loop, name='embedding-batcher', daemon=True).start()


@app.get('/health')
def health():
    return jsonify(ok=True, model=MODEL_ID, queued=pending.qsize())


@app.post('/encode')
def encode():
    if TOKEN and request.headers.get('Authorization') != f'Bearer {TOKEN}':
        return jsonify(error='unauthorized'), 401
    body = request.get_json(silent=True) or {}
    texts = body.get('texts')
    if not isinstance(texts, list) or not texts or len(texts) > MAX_TEXTS:
        return jsonify(error='texts must be a non-empty bounded list'), 400
    texts = [str(text)[:MAX_CHARS] for text in texts]
    work = Work(texts)
    try:
        pending.put_nowait(work)
    except queue.Full:
        return jsonify(error='embedding queue is full'), 503
    if not work.event.wait(float(os.environ.get('EMBEDDING_REQUEST_TIMEOUT', '30'))):
        return jsonify(error='embedding timeout'), 504
    if work.error:
        return jsonify(error=work.error), 500
    return jsonify(model=MODEL_ID, vectors=work.vectors)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('EMBEDDING_PORT', '8090')),
            threaded=True, use_reloader=False)
