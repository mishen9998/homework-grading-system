from datetime import datetime
from app import db

class Schedule(db.Model):
    __tablename__ = 'schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    week_day = db.Column(db.Integer, nullable=False)
    period = db.Column(db.Integer, nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    teacher_name = db.Column(db.String(50), nullable=True)
    teacher_id = db.Column(db.String(50), nullable=True)
    class_name = db.Column(db.String(50), nullable=True)
    classroom = db.Column(db.String(50), nullable=True)
    start_week = db.Column(db.Integer, default=1)
    end_week = db.Column(db.Integer, default=20)
    semester_year = db.Column(db.String(20), nullable=True)
    semester = db.Column(db.String(20), nullable=True)
    start_period = db.Column(db.Integer, nullable=True)
    end_period = db.Column(db.Integer, nullable=True)
    color = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'week_day': self.week_day,
            'period': self.period,
            'course_name': self.course_name,
            'teacher_name': self.teacher_name,
            'teacher_id': self.teacher_id,
            'class_name': self.class_name,
            'classroom': self.classroom,
            'start_week': self.start_week,
            'end_week': self.end_week,
            'semester_year': self.semester_year,
            'semester': self.semester,
            'start_period': self.start_period,
            'end_period': self.end_period,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
