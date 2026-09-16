"""Frozen pre-SaaS schema and read-only migration checks (no application models).

Never import live ORM metadata here: later releases must not change old migrations.
The legacy snapshot reflects the schema present before revision fde30f938654.
"""
import json
from urllib.parse import unquote, urlsplit

import sqlalchemy as sa


BUSINESS_TABLES = (
    'users', 'courses', 'assignments', 'submissions', 'questions', 'answers',
    'course_enrollments', 'course_resources', 'course_notes', 'messages',
    'friendships', 'chat_messages', 'schedules', 'knowledge_entries', 'knowledge_chunks',
)
BASE_TABLES = set(BUSINESS_TABLES) - {'knowledge_entries', 'knowledge_chunks'}


def legacy_metadata(include_knowledge=False, include_chunks=False):
    """Explicit, immutable schema for empty bootstrap and synthetic legacy tests."""
    m = sa.MetaData()
    def c(name, type_, nullable=True, **kw):
        return sa.Column(name, type_, nullable=nullable, **kw)
    def pk():
        return c('id', sa.Integer(), False, primary_key=True)
    def ref(name, target, nullable=False):
        return sa.Column(name, sa.Integer(), sa.ForeignKey(target), nullable=nullable)
    def created():
        return c('created_at', sa.DateTime())
    def table(name, *columns):
        return sa.Table(name, m, pk(), *columns)
    table('users', c('username', sa.String(80), False, unique=True),
          c('password', sa.String(200), False), c('email', sa.String(120), False, unique=True),
          c('role', sa.String(20), False), c('name', sa.String(100), False),
          c('avatar_url', sa.String(500)), c('student_id', sa.String(20)),
          c('teacher_id', sa.String(20)), c('phone', sa.String(20)), c('qq', sa.String(20)),
          c('class_name', sa.String(100)), c('college', sa.String(100)),
          c('friend_code', sa.String(10)), created())
    table('courses', c('name', sa.String(100), False), c('code', sa.String(20), False, unique=True),
          c('code_expiry', sa.DateTime()), ref('teacher_id', 'users.id'),
          c('description', sa.Text()), c('class_name', sa.String(100)),
          c('expected_students', sa.Integer()), created())
    table('assignments', c('title', sa.String(200), False), c('description', sa.Text()),
          c('due_date', sa.DateTime(), False), ref('teacher_id', 'users.id'),
          ref('course_id', 'courses.id', True), c('total_score', sa.Integer()), created(),
          c('updated_at', sa.DateTime()))
    table('submissions', ref('assignment_id', 'assignments.id'), ref('student_id', 'users.id'),
          c('content', sa.Text()), c('file_url', sa.String(500)), c('score', sa.Integer()),
          c('feedback', sa.Text()), c('overall_comment', sa.Text()),
          c('comment_locked', sa.Boolean()), c('status', sa.String(20)),
          c('submitted_at', sa.DateTime()), c('graded_at', sa.DateTime()))
    table('questions', ref('assignment_id', 'assignments.id'),
          c('question_number', sa.Integer(), False), c('question_type', sa.String(20), False),
          c('content', sa.Text(), False), c('image_url', sa.String(500)),
          c('options', sa.Text()), c('correct_answer', sa.Text()), c('score', sa.Integer()), created())
    table('answers', ref('submission_id', 'submissions.id'), ref('question_id', 'questions.id'),
          c('answer_text', sa.Text()), c('answer_image_url', sa.String(500)),
          c('is_correct', sa.Boolean()), c('score', sa.Integer()), c('feedback', sa.Text()),
          created(), c('updated_at', sa.DateTime()))
    table('course_enrollments', ref('course_id', 'courses.id'), ref('student_id', 'users.id'),
          c('joined_at', sa.DateTime()),
          sa.UniqueConstraint('course_id', 'student_id', name='unique_enrollment'))
    table('course_resources', ref('course_id', 'courses.id'), c('title', sa.String(200), False),
          c('description', sa.Text()), c('url', sa.String(500), False),
          c('file_type', sa.String(50)), c('file_size', sa.Integer()),
          c('file_name', sa.String(255)), created())
    table('course_notes', ref('course_id', 'courses.id'), ref('student_id', 'users.id'),
          c('title', sa.String(200), False), c('content', sa.Text(), False), created(),
          c('updated_at', sa.DateTime()))
    table('messages', ref('sender_id', 'users.id'), ref('receiver_id', 'users.id'),
          c('title', sa.String(200), False), c('content', sa.Text(), False),
          c('message_type', sa.String(50)), ref('related_assignment_id', 'assignments.id', True),
          ref('related_course_id', 'courses.id', True), c('is_read', sa.Boolean()), created())
    table('friendships', ref('user_id', 'users.id'), ref('friend_id', 'users.id'),
          c('status', sa.String(20)), created(), c('updated_at', sa.DateTime()),
          sa.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'))
    table('chat_messages', ref('sender_id', 'users.id'), ref('receiver_id', 'users.id'),
          c('content', sa.Text()), c('message_type', sa.String(20)), c('file_url', sa.String(500)),
          c('file_name', sa.String(255)), c('file_size', sa.Integer()),
          c('is_read', sa.Boolean()), created())
    table('schedules', c('week_day', sa.Integer(), False), c('period', sa.Integer(), False),
          c('course_name', sa.String(100), False), c('teacher_name', sa.String(50)),
          c('teacher_id', sa.String(50)), c('class_name', sa.String(50)),
          c('classroom', sa.String(50)), c('start_week', sa.Integer()), c('end_week', sa.Integer()),
          c('semester_year', sa.String(20)), c('semester', sa.String(20)),
          c('start_period', sa.Integer()), c('end_period', sa.Integer()),
          c('color', sa.String(20)), created())
    if include_knowledge:
        table('knowledge_entries', c('library', sa.String(20), False, index=True),
              c('category', sa.String(50), False), c('title', sa.String(200), False),
              c('content', sa.Text(), False), c('source_url', sa.String(1000), False),
              ref('author_id', 'users.id'), c('status', sa.String(20), False, index=True),
              c('review_note', sa.String(1000), False), ref('reviewer_id', 'users.id', True),
              c('created_at', sa.DateTime(), False), c('reviewed_at', sa.DateTime()),
              c('filename', sa.String(255)), c('attachment', sa.LargeBinary(5 * 1024 * 1024)),
              c('embedding', sa.LargeBinary(64 * 1024)), c('embedding_dim', sa.Integer()),
              c('embedding_model', sa.String(255)), c('embedding_hash', sa.String(64), index=True),
              c('embedded_at', sa.DateTime()),
              sa.Index('ix_knowledge_entries_library_status_id', 'library', 'status', 'id'),
              sa.Index('ix_knowledge_entries_library_status_created', 'library', 'status', 'created_at'))
    if include_chunks:
        table('knowledge_chunks', sa.Column('entry_id', sa.Integer(),
              sa.ForeignKey('knowledge_entries.id', ondelete='CASCADE'), nullable=False),
              c('library', sa.String(20), False), c('chunk_index', sa.Integer(), False),
              c('content', sa.Text(), False), c('content_hash', sa.String(64), False, index=True),
              c('embedding', sa.LargeBinary(64 * 1024), False),
              c('embedding_dim', sa.Integer(), False), c('embedding_model', sa.String(255), False),
              c('embedded_at', sa.DateTime(), False),
              sa.UniqueConstraint('entry_id', 'chunk_index', name='uq_knowledge_chunk_position'),
              sa.Index('ix_knowledge_chunks_library_entry', 'library', 'entry_id'),
              sa.Index('ix_knowledge_chunks_model_id', 'embedding_model', 'id'))
    return m


def migration_issues(connection):
    """Return identifiers and reasons, never answer text, passwords or personal data."""
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    business = tables.intersection(BUSINESS_TABLES)
    if not business:
        return [] if not tables - {'alembic_version'} else [{'type': 'unknown_database_schema'}]
    issues = []
    missing = BASE_TABLES - tables
    if missing:
        return [{'type': 'missing_legacy_tables', 'tables': sorted(missing)}]
    columns = {table: {col['name'] for col in inspector.get_columns(table)} for table in business}
    def record(kind, sql):
        rows = connection.execute(sa.text(sql)).mappings().all()
        if rows:
            issues.append({'type': kind, 'records': [dict(row) for row in rows]})
    record('invalid_user_role', "SELECT id FROM users WHERE role NOT IN ('student','teacher','admin','platform_admin')")
    if 'organization_id' not in columns['users']:
        record('legacy_platform_role', "SELECT id FROM users WHERE role='platform_admin'")
    elif 'organizations' in tables:
        record('platform_role_organization_conflict', "SELECT u.id FROM users u JOIN organizations o "
               "ON u.organization_id=o.id WHERE (u.role='platform_admin' AND o.code!='platform') "
               "OR (u.role!='platform_admin' AND o.code='platform')")
        for table in business:
            if 'organization_id' in columns[table]:
                record('orphan_' + table + '_organization',
                       f'SELECT child.id FROM {table} child LEFT JOIN organizations parent '
                       'ON child.organization_id=parent.id WHERE child.organization_id IS NOT NULL AND parent.id IS NULL')
        if 'organization_class_id' in columns['users'] and 'organization_classes' in tables:
            record('user_class_organization_conflict', 'SELECT u.id FROM users u JOIN organization_classes c '
                   'ON u.organization_class_id=c.id WHERE u.organization_id != c.organization_id')
    for table, keys in (('submissions', ['assignment_id', 'student_id']),
                        ('answers', ['submission_id', 'question_id'])):
        group = ', '.join(keys)
        record('duplicate_' + table, f'SELECT {group}, COUNT(*) AS count FROM {table} '
               f'GROUP BY {group} HAVING COUNT(*) > 1')
    # Use the immutable foreign-key graph, not whatever constraints happen to be installed.
    for table in legacy_metadata(include_knowledge=True, include_chunks=True).sorted_tables:
        if table.name not in business:
            continue
        for fk in table.foreign_keys:
            parent, parent_col = fk.target_fullname.split('.')
            col = fk.parent.name
            if col not in columns[table.name]:
                issues.append({'type': 'missing_legacy_column', 'table': table.name, 'column': col})
                continue
            if parent not in tables:
                issues.append({'type': 'missing_parent_table', 'table': parent})
                continue
            record('orphan_' + table.name + '_' + col,
                   f'SELECT child.id FROM {table.name} child LEFT JOIN {parent} parent '
                   f'ON child.{col}=parent.{parent_col} WHERE child.{col} IS NOT NULL AND parent.{parent_col} IS NULL')
            if 'organization_id' in columns[table.name] and 'organization_id' in columns.get(parent, set()):
                record('cross_organization_' + table.name + '_' + col,
                       f'SELECT child.id FROM {table.name} child JOIN {parent} parent '
                       f'ON child.{col}=parent.{parent_col} WHERE child.organization_id != parent.organization_id')
    record('assignment_teacher_conflict', 'SELECT a.id FROM assignments a JOIN courses c '
           'ON c.id=a.course_id WHERE a.teacher_id != c.teacher_id')
    record('assignment_without_course', 'SELECT id FROM assignments WHERE course_id IS NULL')
    record('answer_assignment_conflict', 'SELECT a.id FROM answers a JOIN questions q '
           'ON q.id=a.question_id JOIN submissions s ON s.id=a.submission_id '
           'WHERE q.assignment_id != s.assignment_id')
    # Paths are not followed and files are not read. Only valid legacy references are accepted.
    for table, col in (('users', 'avatar_url'), ('questions', 'image_url'),
                       ('answers', 'answer_image_url'), ('submissions', 'file_url'),
                       ('course_resources', 'url'), ('chat_messages', 'file_url')):
        if col not in columns.get(table, set()):
            continue
        for row in connection.execute(sa.text(f'SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL')).mappings():
            raw = row[col]
            if not raw:
                continue
            value = unquote(str(raw))
            parsed = urlsplit(value)
            safe_external = parsed.scheme in ('http', 'https') and bool(parsed.netloc)
            safe_local = (not parsed.scheme and not parsed.netloc and '\\' not in value and
                          '\x00' not in value and '..' not in parsed.path.split('/') and
                          (parsed.path.startswith('/tupian/') or parsed.path.startswith('/uploads/') or
                           parsed.path.startswith('/api/')))
            if not (safe_external or safe_local):
                issues.append({'type': 'invalid_attachment_reference', 'table': table, 'id': row['id'], 'column': col})
    return issues


def preflight_database(connection):
    issues = migration_issues(connection)
    if issues:
        raise RuntimeError('Migration preflight refused; no records were deleted or reclassified: ' +
                           json.dumps(issues, ensure_ascii=False, default=str))
    return {'status': 'pass', 'issues': []}
