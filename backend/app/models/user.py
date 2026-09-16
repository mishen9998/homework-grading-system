from datetime import datetime
from app import db
from app.models.organization import OrganizationOwned

class User(OrganizationOwned, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'username', name='uq_user_organization_username'),
        db.UniqueConstraint('organization_id', 'email', name='uq_user_organization_email'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    token_version = db.Column(db.Integer, nullable=False, default=1)
    organization_class_id = db.Column(db.Integer, db.ForeignKey('organization_classes.id'))
    organization = db.relationship('Organization')
    organization_class = db.relationship('OrganizationClass')
    name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(500), nullable=True)
    student_id = db.Column(db.String(20), nullable=True)
    teacher_id = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    qq = db.Column(db.String(20), nullable=True)
    class_name = db.Column(db.String(100), nullable=True)
    college = db.Column(db.String(100), nullable=True)
    friend_code = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assignments = db.relationship('Assignment', backref='teacher', lazy=True)
    submissions = db.relationship('Submission', backref='student', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'organization_code': self.organization.code if self.organization else None,
            'organization_name': self.organization.name if self.organization else None,
            'organization_class_id': self.organization_class_id,
            'is_active': self.is_active,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'name': self.name,
            'avatar_url': self.avatar_url,
            'student_id': self.student_id,
            'teacher_id': self.teacher_id,
            'phone': self.phone,
            'qq': self.qq,
            'class_name': self.class_name,
            'college': self.college,
            'friend_code': self.friend_code,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
