from datetime import datetime
from app import db
from app.models.organization import OrganizationOwned

class Answer(OrganizationOwned, db.Model):
    __tablename__ = 'answers'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=True)
    answer_image_url = db.Column(db.String(500), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = db.relationship('Submission', backref=db.backref('answers', lazy=True, cascade='all, delete-orphan'))
    question = db.relationship('Question', backref=db.backref('answers', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'question_id': self.question_id,
            'answer_text': self.answer_text,
            'answer_image_url': self.answer_image_url,
            'is_correct': self.is_correct,
            'score': self.score,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
