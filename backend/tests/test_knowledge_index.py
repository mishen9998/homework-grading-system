import unittest
from unittest.mock import patch

from app import create_app, db
from app.models import User, KnowledgeEntry, KnowledgeChunk
from app.services import knowledge_search as search
from app.services import runtime_control
from config import TestingConfig


class KnowledgeIndexTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.context = self.app.app_context()
        self.context.push()
        runtime_control._MEMORY_CACHE.clear()
        self.user = User(username='index-tester', password='unused', name='Test',
                         email='index@test.invalid', role='admin')
        db.session.add(self.user)
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def entry(self, title='图书馆借阅', content='借书证挂失请前往图书馆服务台。', status='approved'):
        item = KnowledgeEntry(library='student', category='其他', title=title,
                              content=content, status=status, author_id=self.user.id)
        db.session.add(item)
        db.session.flush()
        return item

    def test_chunk_bounds_overlap_and_original_text(self):
        content = '校园服务信息。' * 200 + '唯一尾段内容'
        passages = search.split_passages(content)
        self.assertGreater(len(passages), 2)
        self.assertTrue(all(len(passage) <= 360 and passage in content for passage in passages))
        self.assertTrue(passages[-1].endswith('唯一尾段内容'))
        for left, right in zip(passages, passages[1:]):
            self.assertEqual(left[-60:], right[:60])

    def test_unusual_overlap_still_makes_progress(self):
        passages = search.split_passages('句号。' * 15, size=12, overlap=11)
        self.assertLessEqual(len(passages), 45)
        self.assertTrue(all(len(passage) <= 12 for passage in passages))

    def test_common_word_cannot_admit_low_confidence_neural_result(self):
        entry = self.entry(title='学籍证明', content='申请在读证明。')
        search.index_entry(entry, commit=True)
        encoder = 'embedding-service:fixture:chunks-v1'
        entry.embedding_model = encoder
        chunk = KnowledgeChunk.query.first()
        chunk.embedding_model = encoder
        chunk.embedding = search._pack([1.0, 0.0])
        chunk.embedding_dim = 2
        db.session.commit()
        with patch.object(search, 'active_encoder_name', return_value=encoder), patch.object(search, 'encode_many', return_value=[[0.0, 1.0]]):
            ranked, _ = search.retrieve('student', '数学证明')
        self.assertEqual(ranked, [])

    def test_empty_library_does_not_load_model(self):
        with patch.object(search, 'active_encoder_name', side_effect=AssertionError('unnecessary model load')):
            self.assertEqual(search.retrieve('student', '图书馆在哪里')[0], [])

    def test_index_rebuild_idempotent_and_long_tail_found(self):
        entry = self.entry(content=('综合校园情况介绍。' * 500) + '借书证遗失请携带校园卡到图书馆挂失。')
        search.index_entry(entry, commit=True)
        count = KnowledgeChunk.query.count()
        self.assertGreater(count, 10)
        search.rebuild_embeddings(force=True)
        self.assertEqual(KnowledgeChunk.query.count(), count)
        ranked, _ = search.retrieve('student', '借书证遗失如何挂失')
        self.assertEqual(ranked[0]['entry'].id, entry.id)
        self.assertIn('携带校园卡', ranked[0]['passage'])

    def test_query_never_indexes_or_commits_documents(self):
        entry = self.entry()
        db.session.commit()
        with patch.object(search, 'index_entries', side_effect=AssertionError('query attempted indexing')):
            with patch.object(db.session, 'commit', side_effect=AssertionError('query attempted commit')):
                ranked, _ = search.retrieve('student', '图书馆借书证')
        self.assertEqual(ranked[0]['entry'].id, entry.id)
        self.assertIsNone(entry.embedding)

    def test_cache_detects_body_edits_without_explicit_version_bump(self):
        entry = self.entry()
        search.index_entry(entry, commit=True)
        search.retrieve('student', '图书馆挂失')
        entry.content = '图书馆借书证挂失请使用新线上服务。'
        db.session.commit()
        ranked, _ = search.retrieve('student', '图书馆挂失')
        self.assertIn('新线上服务', ranked[0]['passage'])
        self.assertEqual(ranked[0]['semantic_score'], 0)

    def test_withdrawn_entry_and_stale_vector_hits_not_returned(self):
        entry = self.entry()
        search.index_entry(entry, commit=True)
        chunk_id = KnowledgeChunk.query.first().id
        entry.status = 'rejected'
        db.session.commit()
        with patch.object(search, 'search_entry_ids', return_value=[entry.id]), patch.object(search, 'search_chunk_ids', return_value=[chunk_id]):
            ranked, _ = search.retrieve('student', '图书馆')
        self.assertEqual(ranked, [])

    def test_punctuation_skips_embedding_model(self):
        with patch.object(search, 'encode_many', side_effect=AssertionError('unexpected embedding')):
            self.assertEqual(search.retrieve('student', '！？!!!'), ([], []))

    def test_bad_remote_vector_and_mixed_dimensions_rejected(self):
        for vectors in ([[float('nan')]], [[1], [1, 2]], [[]]):
            with self.assertRaises(ValueError):
                search._validate_vectors(vectors)
        self.assertEqual(search._cosine([1, 0], [1]), 0.0)

    def test_other_model_vectors_not_reused(self):
        entry = self.entry()
        search.index_entry(entry, commit=True)
        entry.embedding_model = 'different-model'
        db.session.commit()
        ranked, _ = search.retrieve('student', '借书证挂失')
        self.assertEqual(ranked[0]['semantic_score'], 0)

    def test_attachment_not_loaded_with_search_candidate(self):
        from sqlalchemy import inspect
        entry = self.entry()
        entry.attachment = b'sensitive-file'
        db.session.commit()
        db.session.expunge_all()
        item = KnowledgeEntry.query.first()
        self.assertIn('attachment', inspect(item).unloaded)
