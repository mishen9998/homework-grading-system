from app import db
from datetime import datetime

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    code_expiry = db.Column(db.DateTime, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(db.Text)
    class_name = db.Column(db.String(100), nullable=True)
    expected_students = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    teacher = db.relationship('User', backref='courses_taught')
    enrollments = db.relationship('CourseEnrollment', back_populates='course', cascade='all, delete-orphan')
    resources = db.relationship('CourseResource', back_populates='course', cascade='all, delete-orphan')
    notes = db.relationship('CourseNote', back_populates='course', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'code_expiry': self.code_expiry.isoformat() if self.code_expiry else None,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.name if self.teacher else '',
            'description': self.description,
            'class_name': self.class_name,
            'expected_students': self.expected_students,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'assignment_count': 0,
            'resource_count': len(self.resources)
        }

class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    course = db.relationship('Course', back_populates='enrollments')
    student = db.relationship('User', backref='courses_enrolled')
    
    __table_args__ = (db.UniqueConstraint('course_id', 'student_id', name='unique_enrollment'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'student_id': self.student_id,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }

class CourseResource(db.Model):
    __tablename__ = 'course_resources'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    course = db.relationship('Course', back_populates='resources')
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'file_name': self.file_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CourseNote(db.Model):
    __tablename__ = 'course_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    course = db.relationship('Course', back_populates='notes')
    student = db.relationship('User', backref='notes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'course_id': self.course_id,
            'student_id': self.student_id,
            'title': self.title,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
