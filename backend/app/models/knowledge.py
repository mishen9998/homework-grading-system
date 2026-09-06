from datetime import datetime
from app import db


class KnowledgeEntry(db.Model):
    __tablename__ = 'knowledge_entries'
    __table_args__ = (
        db.Index('ix_knowledge_entries_library_status_id', 'library', 'status', 'id'),
        db.Index('ix_knowledge_entries_library_status_created', 'library', 'status', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    library = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.String(1000), nullable=False, default='')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    review_note = db.Column(db.String(1000), nullable=False, default='')
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    filename = db.Column(db.String(255))
    attachment = db.Column(db.LargeBinary(length=5 * 1024 * 1024))
    embedding = db.Column(db.LargeBinary(length=64 * 1024))
    embedding_dim = db.Column(db.Integer)
    embedding_model = db.Column(db.String(255))
    embedding_hash = db.Column(db.String(64), index=True)
    embedded_at = db.Column(db.DateTime)
    author = db.relationship('User', foreign_keys=[author_id])

    def to_dict(self, detail=False):
        from app.services.privacy import detect_sensitive_types

        result = {key: getattr(self, key) for key in
                  ('id', 'library', 'category', 'title', 'source_url', 'author_id',
                   'status', 'review_note', 'reviewer_id', 'filename')}
        result.update(author_name=self.author.name if self.author else '已注销用户',
                      created_at=self.created_at.isoformat(),
                      reviewed_at=self.reviewed_at.isoformat() if self.reviewed_at else None,
                      excerpt=self.content[:160])
        result['semantic_indexed'] = bool(self.embedding and self.embedding_hash)
        result['privacy_flags'] = detect_sensitive_types(f'{self.title}\n{self.content}')
        if detail:
            result['content'] = self.content
        return result
