from datetime import datetime
from app import db
from app.models.organization import OrganizationOwned

class Message(OrganizationOwned, db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default='notification')
    related_assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    related_course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    related_assignment = db.relationship('Assignment', backref='messages')
    related_course = db.relationship('Course', backref='messages')
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.name if self.sender else None,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.name if self.receiver else None,
            'title': self.title,
            'content': self.content,
            'message_type': self.message_type,
            'related_assignment_id': self.related_assignment_id,
            'related_course_id': self.related_course_id,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
