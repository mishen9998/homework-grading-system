from datetime import datetime
from app import db

class Submission(db.Model):
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(500), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    overall_comment = db.Column(db.Text, nullable=True)
    comment_locked = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='submitted')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    graded_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'assignment_id': self.assignment_id,
            'student_id': self.student_id,
            'content': self.content,
            'file_url': self.file_url,
            'score': self.score,
            'feedback': self.feedback,
            'overall_comment': self.overall_comment,
            'comment_locked': self.comment_locked,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat(),
            'graded_at': self.graded_at.isoformat() if self.graded_at else None
        }
