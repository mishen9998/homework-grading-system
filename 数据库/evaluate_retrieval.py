"""Reproducible small development evaluation; ONLY an empty homework_eval_* DB."""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

from dotenv import dotenv_values
from manage import ROOT, configured_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--model', choices=['hash', 'local'], default='local')
    parser.add_argument('--qdrant', action='store_true')
    parser.add_argument('--reuse', action='store_true', help='只重测相同合成资料，不覆盖已有资料')
    parser.add_argument('--reindex', action='store_true', help='对已核对一致的合成样本重新建索引')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.database.startswith('homework_eval_'):
        raise ValueError('评测仅允许 homework_eval_ 前缀的新建空库')
    if args.output.exists():
        raise ValueError('报告已存在，请使用新文件名以保留历史结果')
    settings = dotenv_values(ROOT / 'backend' / '.env')
    url = configured_url(ROOT / 'backend' / '.env').set(database=args.database)
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['MKL_NUM_THREADS'] = '2'
    sys.path.insert(0, str(ROOT / 'backend'))
    from config import TestingConfig
    from app import create_app, db
    from app.models import User, KnowledgeEntry, KnowledgeChunk
    from app.services.knowledge_search import index_entries, retrieve, active_encoder_name
    from app.services.runtime_control import _MEMORY_CACHE
    class EvalConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = url
        AUTO_CREATE_TABLES = False
        LOCAL_EMBEDDING_MODEL = settings.get('LOCAL_EMBEDDING_MODEL', '') if args.model == 'local' else ''
        QDRANT_URL = settings.get('QDRANT_URL', '') if args.qdrant else ''
        QDRANT_API_KEY = settings.get('QDRANT_API_KEY', '')
        QDRANT_COLLECTION = args.database + '_entries'
        QDRANT_CHUNK_COLLECTION = args.database + '_chunks'
        LOG_LEVEL = 'WARNING'
    app = create_app(EvalConfig)
    fixture = json.loads((ROOT / 'backend/tests/fixtures/campus_retrieval.json').read_text(encoding='utf-8'))
    with app.app_context():
        if args.reuse:
            entries = []
            for title, content, _ in fixture['cases']:
                item = KnowledgeEntry.query.filter_by(title=title, library='student', status='approved').one()
                if item.content != content:
                    raise ValueError('评测资料与固定样本不一致')
                entries.append(item)
            if KnowledgeEntry.query.count() != len(entries):
                raise ValueError('评测库含额外资料，不能直接比较')
        elif User.query.count() or KnowledgeEntry.query.count():
            raise ValueError('评测库非空，拒绝覆盖或混入已有资料')
        else:
            user = User(username='evaluation', password='not-a-login', email='eval@test.invalid', role='admin', name='合成评测')
            db.session.add(user)
            db.session.flush()
            entries = []
            for title, content, _ in fixture['cases']:
                entry = KnowledgeEntry(title=title, content=content, category='其他', library='student',
                                       status='approved', author_id=user.id)
                db.session.add(entry)
                entries.append(entry)
            db.session.flush()
        started = time.perf_counter()
        if not args.reuse or args.reindex:
            index_entries(entries, commit=True)
        index_seconds = time.perf_counter() - started
        encoder = active_encoder_name()
        if args.model == 'local' and not encoder.startswith('sentence-transformers:'):
            raise RuntimeError('本地模型未成功加载，不能把 hash 降级当成神经模型结果')
        cold, warm, rows = [], [], []
        for entry, (_, _, question) in zip(entries, fixture['cases']):
            _MEMORY_CACHE.clear()
            started = time.perf_counter()
            ranked, _ = retrieve('student', question, limit=3)
            cold.append((time.perf_counter() - started) * 1000)
            ids = [item['entry'].id for item in ranked]
            rank = ids.index(entry.id) + 1 if entry.id in ids else None
            rows.append({'question': question, 'expected_title': entry.title,
                         'returned_titles': [item['entry'].title for item in ranked], 'rank': rank,
                         'scores': [{'lexical': item['lexical_score'], 'semantic': item['semantic_score']} for item in ranked],
                         'cold_ms': round(cold[-1], 2)})
            started = time.perf_counter()
            retrieve('student', question, limit=3)
            warm.append((time.perf_counter() - started) * 1000)
        negative = []
        for question in fixture['negative']:
            ranked, _ = retrieve('student', question, limit=3)
            negative.append({'question': question, 'returned': len(ranked),
                             'matches': [{'title': item['entry'].title, 'lexical': item['lexical_score'],
                                          'semantic': item['semantic_score']} for item in ranked]})
        n = len(rows)
        percentile = lambda values: sorted(values)[max(0, int(len(values) * .95 + .9999) - 1)]
        report = {'type': 'synthetic-development-set-not-independent-holdout',
                  'database': args.database, 'encoder': encoder, 'qdrant_enabled': args.qdrant,
                  'hardware': platform.processor(), 'python': platform.python_version(),
                  'documents': len(entries), 'chunks': KnowledgeChunk.query.count(),
                  'index_seconds_including_model_load': round(index_seconds, 3),
                  'reused_index': args.reuse,
                  'recall_at_3': sum(row['rank'] is not None for row in rows) / n,
                  'top1_accuracy': sum(row['rank'] == 1 for row in rows) / n,
                  'mrr_at_3': sum(1 / row['rank'] if row['rank'] else 0 for row in rows) / n,
                  'cold_p95_ms': round(percentile(cold), 2), 'warm_p95_ms': round(percentile(warm), 2),
                  'cold_median_ms': round(statistics.median(cold), 2),
                  'negative_empty': sum(row['returned'] == 0 for row in negative),
                  'negative_total': len(negative), 'cases': rows, 'negatives': negative}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key not in ('cases', 'negatives')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
