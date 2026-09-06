from app.models.user import User
from app.models.assignment import Assignment
from app.models.submission import Submission
from app.models.course import Course, CourseEnrollment, CourseResource, CourseNote
from app.models.question import Question
from app.models.answer import Answer
from app.models.message import Message
from app.models.friendship import Friendship
from app.models.chat_message import ChatMessage
from app.models.schedule import Schedule
from app.models.knowledge import KnowledgeEntry

__all__ = ['User', 'Assignment', 'Submission', 'Course', 'CourseEnrollment', 'CourseResource', 'CourseNote', 'Question', 'Answer', 'Message', 'Friendship', 'ChatMessage', 'Schedule']
