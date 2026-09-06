from datetime import datetime
from app import db
import json

class Question(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default='text')
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    options = db.Column(db.Text, nullable=True)
    correct_answer = db.Column(db.Text, nullable=True)
    score = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignment = db.relationship('Assignment', backref=db.backref('questions', lazy=True, cascade='all, delete-orphan', order_by='Question.question_number'))

    def get_options(self):
        if self.options:
            try:
                return json.loads(self.options)
            except:
                return None
        return None

    def set_options(self, options_dict):
        if options_dict:
            self.options = json.dumps(options_dict, ensure_ascii=False)
        else:
            self.options = None

    def to_dict(self):
        return {
            'id': self.id,
            'assignment_id': self.assignment_id,
            'question_number': self.question_number,
            'question_type': self.question_type,
            'content': self.content,
            'image_url': self.image_url,
            'options': self.get_options(),
            'correct_answer': self.correct_answer,
            'score': self.score,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
