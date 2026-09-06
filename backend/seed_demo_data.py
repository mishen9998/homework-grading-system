"""Create a realistic, repeatable demo workload without touching existing records.

All generated accounts use the sim26_ prefix so they can be recognized in the
admin console.  The script is idempotent: rerunning it fills missing records
and keeps already-created demo data intact.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from run import app
from app import db
from app.models import (
    Answer, Assignment, ChatMessage, Course, CourseEnrollment, CourseNote,
    CourseResource, Message, Question, Schedule, Submission, User,
)

PREFIX = 'sim26_'
DEMO_PASSWORD = 'Demo@2026!'
TEACHER_COUNT = 6
STUDENT_COUNT = 300
COURSES_PER_TEACHER = 2
STUDENTS_PER_COURSE = 50
SEED = 260907

TEACHER_NAMES = ['王老师', '陈老师', '刘老师', '赵老师', '周老师', '林老师']
COLLEGES = ['计算机学院', '经济管理学院', '外国语学院', '机械工程学院', '设计学院', '理学院']
COURSE_NAMES = [
    ('Python程序设计', '计算机基础与编程实践'),
    ('数据结构与算法', '从线性表到图算法的系统训练'),
    ('管理学原理', '组织管理、决策与案例分析'),
    ('大学英语写作', '学术写作与跨文化沟通'),
    ('机械设计基础', '机械零件、工程制图与设计方法'),
    ('大学物理', '力学、电磁学与实验数据分析'),
]
QUESTION_BANK = [
    ('single_choice', '下列哪项最能体现本章的核心概念？', {'A': '概念A', 'B': '概念B', 'C': '概念C', 'D': '概念D'}, 'B', 10),
    ('multiple_choice', '下列哪些做法符合规范？（多选）', {'A': '做法A', 'B': '做法B', 'C': '做法C', 'D': '做法D'}, 'A,C', 15),
    ('true_false', '该说法是否正确：实践和复盘是掌握本课程的重要方法。', None, 'true', 10),
    ('fill_blank', '请填写本课程中最重要的关键词：____。', None, '实践|方法', 10),
    ('text', '请结合课程内容，简要说明一个真实场景中的应用。', None, '能够结合课程概念说明场景、过程和结论。', 25),
    ('single_choice', '遇到复杂问题时，推荐的第一步是什么？', {'A': '直接猜测', 'B': '拆解问题并确认目标', 'C': '跳过分析', 'D': '复制他人答案'}, 'B', 10),
    ('true_false', '及时记录错误并根据反馈改进，有助于提升学习效果。', None, 'true', 10),
    ('text', '请写出本次学习中最需要继续练习的一项能力。', None, '表达清晰、内容具体，并给出改进计划。', 10),
]


def get_or_create_user(username, **values):
    user = User.query.filter_by(username=username).first()
    if user:
        changed = False
        for key, value in values.items():
            if value is not None and getattr(user, key, None) != value:
                setattr(user, key, value)
                changed = True
        if changed:
            db.session.flush()
        return user, False
    user = User(username=username, password=generate_password_hash(DEMO_PASSWORD), **values)
    db.session.add(user)
    db.session.flush()
    return user, True


def add_question_set(assignment):
    questions = Question.query.filter_by(assignment_id=assignment.id).order_by(Question.question_number).all()
    if questions:
        return questions, 0
    for number, (kind, content, options, answer, score) in enumerate(QUESTION_BANK, start=1):
        question = Question(
            assignment_id=assignment.id, question_number=number, question_type=kind,
            content=content, correct_answer=answer, score=score,
        )
        question.set_options(options)
        db.session.add(question)
    db.session.flush()
    return Question.query.filter_by(assignment_id=assignment.id).order_by(Question.question_number).all(), len(QUESTION_BANK)


def answer_for(question, student_index):
    # Mostly correct with a few predictable mistakes, which creates a useful
    # score distribution for the teacher statistics pages.
    mistake = student_index % 7 == 0
    if question.question_type == 'single_choice':
        return 'A' if mistake else question.correct_answer
    if question.question_type == 'multiple_choice':
        return 'A' if mistake else question.correct_answer
    if question.question_type == 'true_false':
        return 'false' if mistake else question.correct_answer
    if question.question_type == 'fill_blank':
        return '待补充' if mistake else '实践'
    return f'学生{student_index + 1}结合课堂案例完成了分析，并写下了自己的改进计划。'


def ensure_submission(assignment, student, student_index, questions, graded):
    submission = Submission.query.filter_by(assignment_id=assignment.id, student_id=student.id).first()
    if not submission:
        submission = Submission(
            assignment_id=assignment.id, student_id=student.id,
            content=f'模拟提交：{assignment.title}学习记录与作业说明（学生{student_index + 1}）。',
            submitted_at=datetime.utcnow() - timedelta(days=student_index % 12, hours=student_index % 8),
        )
        db.session.add(submission)
        db.session.flush()
    for question in questions:
        answer = Answer.query.filter_by(submission_id=submission.id, question_id=question.id).first()
        if not answer:
            text = answer_for(question, student_index)
            answer = Answer(submission_id=submission.id, question_id=question.id, answer_text=text)
            db.session.add(answer)
            db.session.flush()
        if graded:
            correct = answer.answer_text == question.correct_answer
            if question.question_type == 'text':
                correct = student_index % 7 != 0
                answer.score = question.score if correct else max(4, question.score - 6)
                answer.is_correct = None
                answer.feedback = '观点具体，结合了课堂内容。' if correct else '建议补充课程概念和具体依据。'
            else:
                answer.score = question.score if correct else 0
                answer.is_correct = correct
            answer.updated_at = datetime.utcnow()
    if graded:
        score = sum(answer.score or 0 for answer in submission.answers)
        submission.score = int(score)
        submission.status = 'graded'
        submission.graded_at = datetime.utcnow() - timedelta(days=student_index % 5)
        submission.feedback = '作业完成认真，主要知识点掌握较好。' if score >= 80 else '基础内容已经完成，建议结合错题继续复习。'
        submission.overall_comment = '本次作业已完成批改，请根据逐题反馈安排下一次练习。'
    else:
        submission.status = 'submitted'
    return submission


def ensure_misc_data(course, teacher, group_students, assignments):
    counts = {'resources': 0, 'notes': 0, 'messages': 0, 'chats': 0}
    for index, title in enumerate(['课程导学资料', '课后拓展阅读'], start=1):
        if not CourseResource.query.filter_by(course_id=course.id, title=title).first():
            db.session.add(CourseResource(
                course_id=course.id, title=title,
                description='模拟课程资料，供学生课前预习和课后复习。',
                url=f'https://example.edu.cn/sim26/{course.code.lower()}/resource-{index}',
                file_type='link', file_name=None,
            ))
            counts['resources'] += 1
    for student in group_students[:5]:
        title = f'{course.name}学习笔记'
        if not CourseNote.query.filter_by(course_id=course.id, student_id=student.id, title=title).first():
            db.session.add(CourseNote(
                course_id=course.id, student_id=student.id, title=title,
                content='记录本周课程重点、课堂问题和下一步复习计划。',
            ))
            counts['notes'] += 1
    assignment = assignments[0]
    for student in group_students:
        if not Message.query.filter_by(
            receiver_id=student.id, related_assignment_id=assignment.id,
            title='模拟课程作业提醒',
        ).first():
            db.session.add(Message(
                sender_id=teacher.id, receiver_id=student.id, title='模拟课程作业提醒',
                content=f'{course.name}的{assignment.title}已发布，请按时完成并提交。',
                message_type='assignment_reminder', related_assignment_id=assignment.id,
                related_course_id=course.id, is_read=(student.id % 3 == 0),
            ))
            counts['messages'] += 1
    for student in group_students[:3]:
        if not ChatMessage.query.filter_by(sender_id=student.id, receiver_id=teacher.id,
                                           content='老师好，我已经查看了本次作业要求。').first():
            db.session.add(ChatMessage(
                sender_id=student.id, receiver_id=teacher.id,
                content='老师好，我已经查看了本次作业要求。', is_read=True,
            ))
            counts['chats'] += 1
        if not ChatMessage.query.filter_by(sender_id=teacher.id, receiver_id=student.id,
                                           content='收到，有问题可以在课程讨论中留言。').first():
            db.session.add(ChatMessage(
                sender_id=teacher.id, receiver_id=student.id,
                content='收到，有问题可以在课程讨论中留言。', is_read=True,
            ))
            counts['chats'] += 1
    return counts


def seed():
    random.seed(SEED)
    now = datetime.utcnow()
    created = {'teachers': 0, 'students': 0, 'courses': 0, 'enrollments': 0,
               'assignments': 0, 'questions': 0, 'submissions': 0, 'graded': 0,
               'answers': 0, 'resources': 0, 'notes': 0, 'messages': 0, 'chats': 0}
    teachers = []
    for index in range(TEACHER_COUNT):
        teacher, was_created = get_or_create_user(
            f'{PREFIX}teacher_{index + 1:02d}',
            email=f'{PREFIX}teacher_{index + 1:02d}@example.edu.cn', name=TEACHER_NAMES[index],
            role='teacher', teacher_id=f'SIM-T{index + 1:02d}', college=COLLEGES[index],
            phone=f'1392607{index:04d}', friend_code=f'ST{index + 1:06d}',
        )
        teachers.append(teacher)
        created['teachers'] += int(was_created)
    students = []
    for index in range(STUDENT_COUNT):
        college = COLLEGES[index // 50]
        student, was_created = get_or_create_user(
            f'{PREFIX}student_{index + 1:03d}',
            email=f'{PREFIX}student_{index + 1:03d}@example.edu.cn', name=f'{college[:2]}学生{index + 1:03d}',
            role='student', student_id=f'SIM2026{index + 1:03d}',
            class_name=f'{college[:2]}26{index // 25 + 1:02d}', college=college,
            phone=f'1382607{index:04d}', friend_code=f'SD{index + 1:06d}',
        )
        students.append(student)
        created['students'] += int(was_created)
    db.session.flush()

    demo_courses = []
    for teacher_index, teacher in enumerate(teachers):
        for course_index in range(COURSES_PER_TEACHER):
            subject_index = teacher_index
            name, description = COURSE_NAMES[subject_index]
            code = f'SIM26-T{teacher_index + 1:02d}-C{course_index + 1}'
            course = Course.query.filter_by(code=code).first()
            if not course:
                course = Course(
                    name=f'{name}（模拟班{course_index + 1}）', code=code, teacher_id=teacher.id,
                    description=description, class_name=f'{COLLEGES[teacher_index]}模拟班{course_index + 1}',
                    expected_students=STUDENTS_PER_COURSE, code_expiry=now + timedelta(days=365),
                )
                db.session.add(course)
                db.session.flush()
                created['courses'] += 1
            group_start = teacher_index * STUDENTS_PER_COURSE
            group_students = students[group_start:group_start + STUDENTS_PER_COURSE]
            for student in group_students:
                if not CourseEnrollment.query.filter_by(course_id=course.id, student_id=student.id).first():
                    db.session.add(CourseEnrollment(course_id=course.id, student_id=student.id))
                    created['enrollments'] += 1
            assignments = []
            for assignment_index in range(2):
                title = f'{course.name}第{assignment_index + 1}次作业'
                assignment = Assignment.query.filter_by(course_id=course.id, title=title).first()
                if not assignment:
                    assignment = Assignment(
                        title=title, description='模拟教学作业：完成题目并结合课程内容写出学习反思。',
                        due_date=now - timedelta(days=10) if assignment_index == 0 else now + timedelta(days=7),
                        teacher_id=teacher.id, course_id=course.id, total_score=100,
                    )
                    db.session.add(assignment)
                    db.session.flush()
                    created['assignments'] += 1
                questions, new_questions = add_question_set(assignment)
                created['questions'] += new_questions
                assignments.append(assignment)
                submit_count = 50 if assignment_index == 0 else 35
                graded_count = 40 if assignment_index == 0 else 25
                for student_index, student in enumerate(group_students[:submit_count]):
                    before = Submission.query.filter_by(assignment_id=assignment.id, student_id=student.id).first()
                    submission = ensure_submission(assignment, student, student_index, questions, student_index < graded_count)
                    created['submissions'] += int(before is None)
                    created['graded'] += int(before is None and submission.status == 'graded')
                    created['answers'] += len(questions) if before is None else 0
            misc_created = ensure_misc_data(course, teacher, group_students, assignments)
            for key, value in misc_created.items():
                created[key] += value
            demo_courses.append(course)
    for teacher_index, teacher in enumerate(teachers):
        for course_index in range(COURSES_PER_TEACHER):
            course = demo_courses[teacher_index * COURSES_PER_TEACHER + course_index]
            if not Schedule.query.filter_by(teacher_id=str(teacher.id), course_name=course.name).first():
                db.session.add(Schedule(
                    week_day=(teacher_index + course_index) % 5 + 1, period=1 + course_index,
                    start_period=1 + course_index * 2, end_period=2 + course_index * 2,
                    course_name=course.name, teacher_name=teacher.name, teacher_id=str(teacher.id),
                    class_name=course.class_name, classroom=f'教学楼{teacher_index + 1}0{course_index + 1}',
                    start_week=1, end_week=18, semester_year='2026-2027', semester='秋季',
                    color=['#5B8FF9', '#61DDAA', '#65789B'][teacher_index % 3],
                ))
    db.session.commit()

    # Write a small local manifest so the administrator can log in to the demo
    # accounts without searching the database. It contains no production keys.
    manifest = {
        'generated_at_utc': datetime.utcnow().isoformat(),
        'prefix': PREFIX, 'password': DEMO_PASSWORD,
        'admin_note': '演示账号由 seed_demo_data.py 生成，请在管理员后台按 sim26_ 前缀筛选。',
        'teachers': [f'{PREFIX}teacher_{i:02d}' for i in range(1, TEACHER_COUNT + 1)],
        'students': [f'{PREFIX}student_{i:03d}' for i in range(1, STUDENT_COUNT + 1)],
        'counts': created,
    }
    Path(__file__).with_name('demo_seed_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    totals = {name: model.query.count() for name, model in {
        'users': User, 'courses': Course, 'enrollments': CourseEnrollment,
        'assignments': Assignment, 'questions': Question, 'submissions': Submission,
        'answers': Answer, 'resources': CourseResource, 'notes': CourseNote,
        'messages': Message, 'chats': ChatMessage, 'schedules': Schedule,
    }.items()}
    print(json.dumps({'created_this_run': created, 'database_totals': totals}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    with app.app_context():
        seed()
