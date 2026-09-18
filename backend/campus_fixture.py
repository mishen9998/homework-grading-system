"""Deterministic, synthetic campus data for the isolated MySQL runtime only.

Run ``python campus_fixture.py seed|verify --profile small|full --output
/runtime/fixture.json``.  Credentials come from process environment only.  The
runtime identity guard runs before the application or any database connection.

The small academic workload is exactly 1/50 of full; five teaching organizations
and the six administrative identities remain.  The separate platform identity
requires one system organization under the existing authentication contract.
All business inserts and the ownership marker commit in one transaction.  No
rows are repaired, removed, or silently adopted.  A repeat seed only verifies.
An interrupted transaction may leave deterministic attachment files; matching
files are reusable, conflicting files are never overwritten or removed.

Hashes cover ordered, canonical fixture columns, excluding password hashes
(which contain random salt).  Verification is a strict baseline check: later
scenario mutations must be reconciled by their scenario-specific verifier.
This module does not claim that seeded identities have participated over HTTP.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Iterator


SEED = 20260917
FIXTURE_VERSION = 1
EPOCH = datetime(2026, 9, 17)
CREATED = EPOCH - timedelta(days=30)
BATCH_SIZE = 1000
PROFILES = {
    "small": {"students": 190, "teachers": 10, "classes": 5, "courses": 10},
    "full": {"students": 9500, "teachers": 500, "classes": 250, "courses": 500},
}
TABLE_ORDER = (
    "organizations", "organization_classes", "users", "courses",
    "course_enrollments", "assignments", "questions", "submissions", "answers",
)
PHASES = ("history_1", "history_2", "daily", "deadline")
ATTACHMENT_SIZES = (1024,) * 12 + (4096,) * 5 + (16384,) * 2 + (65536,)


class FixtureError(RuntimeError):
    """A safe error code plus counts/hashes, never SQL parameters or answers."""

    def __init__(self, code: str, details: dict | None = None):
        super().__init__(code)
        self.code = code
        self.details = details or {}


def canonical(value) -> bytes:
    def normalize(item):
        if isinstance(item, datetime):
            return item.isoformat(timespec="seconds")
        if isinstance(item, dict):
            return {key: normalize(part) for key, part in item.items()}
        if isinstance(item, (tuple, list)):
            return [normalize(part) for part in item]
        return item

    return json.dumps(normalize(value), sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def expected_counts(profile: str) -> dict:
    config = PROFILES[profile]
    students = config["students"]
    submissions = students * 27 // 5
    return {
        "organizations": 6,
        "academic_organizations": 5,
        "platform_organizations": 1,
        "organization_classes": config["classes"],
        "students": students,
        "teachers": config["teachers"],
        "organization_admins": 5,
        "platform_admins": 1,
        "academic_accounts": students + config["teachers"],
        "users": students + config["teachers"] + 6,
        "courses": config["courses"],
        "course_enrollments": students * 2,
        "assignments": config["courses"] * 4,
        "questions": config["courses"] * 40,
        "submissions": submissions,
        "answers": submissions * 10,
        "attachments": math.ceil(submissions / 10),
        "deadline_unsubmitted_students": students * 4 // 5,
    }


def student_position(profile: str, zero_index: int) -> tuple[int, int]:
    config = PROFILES[profile]
    return (zero_index // (config["students"] // 5) + 1,
            zero_index // 38 + 1)


def iter_identity_records(profile: str) -> Iterator[dict]:
    """Safe login selectors, usable by HTTP clients; no credential material."""
    for index in range(PROFILES[profile]["students"]):
        org, class_id = student_position(profile, index)
        yield {"id": index + 1, "organization_id": org,
               "organization_code": f"campus_{org:02d}",
               "username": f"student_{index + 1:05d}", "role": "student",
               "organization_class_id": class_id}
    for index in range(PROFILES[profile]["teachers"]):
        org = index // (PROFILES[profile]["teachers"] // 5) + 1
        yield {"id": 100001 + index, "organization_id": org,
               "organization_code": f"campus_{org:02d}",
               "username": f"teacher_{index + 1:05d}", "role": "teacher",
               "organization_class_id": None}
    for org in range(1, 6):
        yield {"id": 200000 + org, "organization_id": org,
               "organization_code": f"campus_{org:02d}",
               "username": f"org_admin_{org:02d}", "role": "admin",
               "organization_class_id": None}
    yield {"id": 300001, "organization_id": 6,
           "organization_code": "platform", "username": "platform_admin",
           "role": "platform_admin", "organization_class_id": None}


def iter_pending_deadline_targets(profile: str) -> Iterator[dict]:
    """Exactly one still-unsubmitted deadline assignment per eligible student."""
    for index in range(PROFILES[profile]["students"]):
        if index % 5 == 0:
            continue
        org, class_id = student_position(profile, index)
        course_id = class_id * 2 - 1
        yield {"organization_id": org, "student_id": index + 1,
               "course_id": course_id, "assignment_id": course_id * 4,
               "question_ids": list(range((course_id * 4 - 1) * 10 + 1,
                                          course_id * 40 + 1))}


def assignment_due_date(phase: int) -> datetime:
    return EPOCH + timedelta(days=(-14, -7, 3650, 3651)[phase])


def question_values(assignment_id: int, number: int) -> dict:
    operand = (SEED + assignment_id * 17 + number * 31) % 997
    kind = ("single_choice", "true_false", "fill_blank", "text")[(number - 1) % 4]
    correct = {"single_choice": "B", "true_false": "true",
               "fill_blank": str(operand + number),
               "text": f"synthetic result {operand + number}"}[kind]
    return {
        "question_type": kind,
        "content": f"[SYNTHETIC] Exercise {assignment_id}/{number}: {operand} + {number}.",
        "options": (json.dumps({"A": str(operand), "B": str(operand + number),
                                 "C": str(operand - number), "D": "0"},
                                sort_keys=True) if kind == "single_choice" else None),
        "correct_answer": correct,
    }


def expected_answer_text(assignment_id: int, number: int, student_id: int) -> str:
    question = question_values(assignment_id, number)
    if (student_id + number + SEED) % 7:
        return question["correct_answer"]
    return {"single_choice": "A", "true_false": "false", "fill_blank": "0",
            "text": f"synthetic alternative {student_id}/{number}"}[question["question_type"]]


def iter_submission_records(profile: str, run_id: str) -> Iterator[dict]:
    ordinal = 0
    for course_id in range(1, PROFILES[profile]["courses"] + 1):
        class_id = (course_id + 1) // 2
        first_index = (class_id - 1) * 38
        org, _ = student_position(profile, first_index)
        for phase in range(4):
            assignment_id = (course_id - 1) * 4 + phase + 1
            for index in range(first_index, first_index + 38):
                if phase == 2 and index % 2:
                    continue
                if phase == 3 and index % 5:
                    continue
                ordinal += 1
                yield {
                    "id": ordinal, "organization_id": org,
                    "assignment_id": assignment_id, "student_id": index + 1,
                    "content": f"[SYNTHETIC] seed={SEED}; submission={ordinal}",
                    "file_url": (f"/tupian/{attachment_name(run_id, ordinal)}"
                                 if (ordinal - 1) % 10 == 0 else None),
                    "score": None, "feedback": None, "overall_comment": None,
                    "comment_locked": False, "status": "submitted",
                    "submitted_at": (assignment_due_date(phase) - timedelta(days=1)
                                     if phase < 2 else EPOCH - timedelta(hours=1)),
                    "graded_at": None,
                }


def iter_rows(table_name: str, profile: str, run_id: str) -> Iterator[dict]:
    config = PROFILES[profile]
    if table_name == "organizations":
        for org in range(1, 7):
            yield {"id": org, "code": f"campus_{org:02d}" if org < 6 else "platform",
                   "name": f"SYNTHETIC Campus {org:02d}" if org < 6 else "SYNTHETIC Platform",
                   "status": "active", "expires_at": EPOCH + timedelta(days=7300),
                   "user_limit": 20000, "storage_limit_bytes": 1073741824,
                   "ai_monthly_token_limit": 0, "concurrent_task_limit": 16,
                   "ai_enabled": False, "created_at": CREATED, "updated_at": CREATED}
    elif table_name == "organization_classes":
        for index in range(config["classes"]):
            yield {"id": index + 1, "organization_id": index // (config["classes"] // 5) + 1,
                   "name": f"SYNTHETIC Class {index + 1:03d}", "created_at": CREATED}
    elif table_name == "users":
        for identity in iter_identity_records(profile):
            class_id = identity["organization_class_id"]
            yield {key: identity[key] for key in (
                       "id", "organization_id", "username", "role", "organization_class_id")} | {
                "email": f"{identity['username']}@synthetic.invalid",
                "is_active": True, "token_version": 1,
                "name": f"SYNTHETIC {identity['username']}", "avatar_url": None,
                "student_id": f"S{identity['id']:06d}" if identity["role"] == "student" else None,
                "teacher_id": f"T{identity['id'] - 100000:06d}" if identity["role"] == "teacher" else None,
                "phone": None, "qq": None,
                "class_name": f"SYNTHETIC Class {class_id:03d}" if class_id else None,
                "college": f"SYNTHETIC Faculty {(class_id - 1) // 10 + 1:02d}" if class_id else None,
                "friend_code": None, "created_at": CREATED,
            }
    elif table_name == "courses":
        for index in range(config["courses"]):
            class_id = index // 2 + 1
            yield {"id": index + 1, "organization_id": index // (config["courses"] // 5) + 1,
                   "name": f"SYNTHETIC Course {index + 1:03d}", "code": f"C26{index + 1:04d}",
                   "code_expiry": EPOCH + timedelta(days=7300), "teacher_id": 100001 + index,
                   "description": f"SYNTHETIC fixture seed {SEED}",
                   "class_name": f"SYNTHETIC Class {class_id:03d}",
                   "expected_students": 38, "created_at": CREATED}
    elif table_name == "course_enrollments":
        for index in range(config["students"]):
            org, class_id = student_position(profile, index)
            for offset in range(2):
                yield {"id": index * 2 + offset + 1, "organization_id": org,
                       "course_id": class_id * 2 - 1 + offset, "student_id": index + 1,
                       "joined_at": CREATED}
    elif table_name in ("assignments", "questions"):
        for course_id in range(1, config["courses"] + 1):
            org = (course_id - 1) // (config["courses"] // 5) + 1
            for phase in range(4):
                assignment_id = (course_id - 1) * 4 + phase + 1
                if table_name == "assignments":
                    yield {"id": assignment_id, "organization_id": org,
                           "title": f"SYNTHETIC {PHASES[phase]} course {course_id:03d}",
                           "description": f"SYNTHETIC phase={PHASES[phase]}; seed={SEED}",
                           "due_date": assignment_due_date(phase),
                           "teacher_id": 100000 + course_id, "course_id": course_id,
                           "total_score": 100, "created_at": EPOCH - timedelta(days=21),
                           "updated_at": EPOCH - timedelta(days=21)}
                else:
                    for number in range(1, 11):
                        yield {"id": (assignment_id - 1) * 10 + number,
                               "organization_id": org, "assignment_id": assignment_id,
                               "question_number": number, **question_values(assignment_id, number),
                               "image_url": None, "score": 10,
                               "created_at": EPOCH - timedelta(days=21)}
    elif table_name == "submissions":
        yield from iter_submission_records(profile, run_id)
    elif table_name == "answers":
        for submission in iter_submission_records(profile, run_id):
            for number in range(1, 11):
                yield {"id": (submission["id"] - 1) * 10 + number,
                       "organization_id": submission["organization_id"],
                       "submission_id": submission["id"],
                       "question_id": (submission["assignment_id"] - 1) * 10 + number,
                       "answer_text": expected_answer_text(submission["assignment_id"], number,
                                                           submission["student_id"]),
                       "answer_image_url": None, "is_correct": None, "score": None,
                       "feedback": None, "created_at": submission["submitted_at"],
                       "updated_at": submission["submitted_at"]}
    else:
        raise FixtureError("unknown_fixture_table")


def attachment_name(run_id: str, submission_id: int) -> str:
    return f"campus_{run_id}_s{submission_id:06d}.txt"


def attachment_bytes(submission_id: int, size: int) -> bytes:
    header = f"SYNTHETIC CAMPUS FIXTURE\nseed={SEED}\nsubmission_id={submission_id}\n".encode("ascii")
    unit = hashlib.sha256(header).hexdigest().encode("ascii") + b"\n"
    return (header + unit * ((size // len(unit)) + 1))[:size]


def attachment_entries(profile: str, run_id: str) -> Iterator[dict]:
    for index, submission_id in enumerate(range(1, expected_counts(profile)["submissions"] + 1, 10)):
        size = ATTACHMENT_SIZES[index % len(ATTACHMENT_SIZES)]
        yield {"submission_id": submission_id, "name": attachment_name(run_id, submission_id),
               "size_bytes": size, "sha256": hashlib.sha256(attachment_bytes(submission_id, size)).hexdigest()}


def checked_upload_root() -> Path:
    supplied = os.environ.get("UPLOAD_FOLDER", "")
    root = Path(supplied)
    if supplied != "/runtime/attachments" or root.is_symlink() or root.resolve() != Path("/runtime/attachments"):
        raise FixtureError("dedicated_attachment_directory_required")
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_attachments(profile: str, run_id: str, root: Path, *, create: bool) -> dict:
    entries = list(attachment_entries(profile, run_id))
    expected_names = {entry["name"] for entry in entries}
    unexpected = sum(1 for path in root.glob(f"campus_{run_id}_s*.txt")
                     if path.name not in expected_names)
    if unexpected:
        raise FixtureError("unexpected_owned_attachment_paths", {"count": unexpected})
    failures = []
    for entry in entries:
        path = root / entry["name"]
        if path.is_symlink() or path.resolve().parent != root:
            raise FixtureError("attachment_path_conflict")
        if create and not path.exists():
            try:
                with path.open("xb") as handle:
                    handle.write(attachment_bytes(entry["submission_id"], entry["size_bytes"]))
            except FileExistsError:
                pass
        if not path.is_file():
            failures.append({"submission_id": entry["submission_id"], "reason": "missing"})
            continue
        if path.stat().st_size != entry["size_bytes"]:
            failures.append({"submission_id": entry["submission_id"], "reason": "size"})
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            failures.append({"submission_id": entry["submission_id"], "reason": "sha256"})
    if failures:
        raise FixtureError("attachment_integrity_failed", {"failures": failures[:20], "failure_count": len(failures)})
    distribution = Counter(entry["size_bytes"] for entry in entries)
    return {"count": len(entries), "coverage_fraction": len(entries) / expected_counts(profile)["submissions"],
            "total_size_bytes": sum(entry["size_bytes"] for entry in entries),
            "size_distribution": {str(size): count for size, count in sorted(distribution.items())},
            "manifest_sha256": hashlib.sha256(canonical(entries)).hexdigest(), "files": entries}


def table_digest(rows: Iterator[dict]) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(canonical(row))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def expected_table_manifest(profile: str, run_id: str) -> dict:
    result = {}
    for name in TABLE_ORDER:
        count, digest = table_digest(iter_rows(name, profile, run_id))
        if count != expected_counts(profile)[name]:
            raise FixtureError("generator_count_invariant", {"table": name, "actual": count})
        result[name] = {"count": count, "sha256": digest,
                        "columns": sorted(next(iter_rows(name, profile, run_id)))}
    return result


def model_tables() -> dict:
    from app.models import (Answer, Assignment, Course, CourseEnrollment,
                            Organization, OrganizationClass, Question, Submission, User)
    return {model.__tablename__: model.__table__ for model in (
        Organization, OrganizationClass, User, Course, CourseEnrollment,
        Assignment, Question, Submission, Answer)}


def ownership_table():
    from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, String, Table
    return Table("campus_fixture_state", MetaData(),
                 Column("run_id", String(80), primary_key=True),
                 Column("fixture_version", Integer, nullable=False),
                 Column("seed", Integer, nullable=False),
                 Column("profile", String(20), nullable=False),
                 Column("status", String(20), nullable=False),
                 Column("expected_tables", JSON, nullable=False),
                 Column("credential_hash_sha256", String(64), nullable=False),
                 Column("attachment_manifest_sha256", String(64), nullable=False),
                 Column("created_at", DateTime, nullable=False))


def relational_checks(connection) -> dict:
    """Counts of invalid rows, foreign keys, identities and business duplicates."""
    from sqlalchemy import text
    checks = {
        "class_organization": "SELECT COUNT(*) FROM organization_classes c LEFT JOIN organizations o ON o.id=c.organization_id WHERE o.id IS NULL OR o.code='platform'",
        "user_organization": "SELECT COUNT(*) FROM users u LEFT JOIN organizations o ON o.id=u.organization_id WHERE o.id IS NULL OR ((u.role='platform_admin') <> (o.code='platform'))",
        "student_class": "SELECT COUNT(*) FROM users u LEFT JOIN organization_classes c ON c.id=u.organization_class_id WHERE u.role='student' AND (c.id IS NULL OR c.organization_id<>u.organization_id)",
        "course_teacher": "SELECT COUNT(*) FROM courses c LEFT JOIN users u ON u.id=c.teacher_id LEFT JOIN organizations o ON o.id=c.organization_id WHERE u.id IS NULL OR o.id IS NULL OR u.role<>'teacher' OR c.organization_id<>u.organization_id",
        "enrollment_membership": "SELECT COUNT(*) FROM course_enrollments e LEFT JOIN courses c ON c.id=e.course_id LEFT JOIN users u ON u.id=e.student_id WHERE c.id IS NULL OR u.id IS NULL OR u.role<>'student' OR e.organization_id<>c.organization_id OR e.organization_id<>u.organization_id",
        "assignment_teacher_course": "SELECT COUNT(*) FROM assignments a LEFT JOIN courses c ON c.id=a.course_id LEFT JOIN users u ON u.id=a.teacher_id WHERE c.id IS NULL OR u.id IS NULL OR u.role<>'teacher' OR a.organization_id<>c.organization_id OR a.organization_id<>u.organization_id OR a.teacher_id<>c.teacher_id",
        "question_assignment": "SELECT COUNT(*) FROM questions q LEFT JOIN assignments a ON a.id=q.assignment_id WHERE a.id IS NULL OR q.organization_id<>a.organization_id",
        "submission_identity_membership": "SELECT COUNT(*) FROM submissions s LEFT JOIN assignments a ON a.id=s.assignment_id LEFT JOIN users u ON u.id=s.student_id LEFT JOIN course_enrollments e ON e.course_id=a.course_id AND e.student_id=s.student_id WHERE a.id IS NULL OR u.id IS NULL OR e.id IS NULL OR u.role<>'student' OR s.organization_id<>a.organization_id OR s.organization_id<>u.organization_id OR s.organization_id<>e.organization_id",
        "answer_submission_question": "SELECT COUNT(*) FROM answers x LEFT JOIN submissions s ON s.id=x.submission_id LEFT JOIN questions q ON q.id=x.question_id WHERE s.id IS NULL OR q.id IS NULL OR x.organization_id<>s.organization_id OR x.organization_id<>q.organization_id OR s.assignment_id<>q.assignment_id",
        "duplicate_submissions": "SELECT COUNT(*) FROM (SELECT organization_id,assignment_id,student_id FROM submissions GROUP BY organization_id,assignment_id,student_id HAVING COUNT(*)<>1) d",
        "duplicate_answers": "SELECT COUNT(*) FROM (SELECT submission_id,question_id FROM answers GROUP BY submission_id,question_id HAVING COUNT(*)<>1) d",
        "duplicate_enrollments": "SELECT COUNT(*) FROM (SELECT course_id,student_id FROM course_enrollments GROUP BY course_id,student_id HAVING COUNT(*)<>1) d",
        "students_without_two_courses": "SELECT COUNT(*) FROM (SELECT u.id FROM users u LEFT JOIN course_enrollments e ON e.student_id=u.id WHERE u.role='student' GROUP BY u.id HAVING COUNT(e.id)<>2) d",
        "teachers_without_one_course": "SELECT COUNT(*) FROM (SELECT u.id FROM users u LEFT JOIN courses c ON c.teacher_id=u.id WHERE u.role='teacher' GROUP BY u.id HAVING COUNT(c.id)<>1) d",
        "classes_without_38_students": "SELECT COUNT(*) FROM (SELECT c.id FROM organization_classes c LEFT JOIN users u ON u.organization_class_id=c.id AND u.role='student' GROUP BY c.id HAVING COUNT(u.id)<>38) d",
        "courses_without_38_students": "SELECT COUNT(*) FROM (SELECT c.id FROM courses c LEFT JOIN course_enrollments e ON e.course_id=c.id GROUP BY c.id HAVING COUNT(e.id)<>38) d",
        "courses_without_four_assignments": "SELECT COUNT(*) FROM (SELECT c.id FROM courses c LEFT JOIN assignments a ON a.course_id=c.id GROUP BY c.id HAVING COUNT(a.id)<>4) d",
        "assignments_without_ten_questions": "SELECT COUNT(*) FROM (SELECT a.id FROM assignments a LEFT JOIN questions q ON q.assignment_id=a.id GROUP BY a.id HAVING COUNT(q.id)<>10) d",
        "submissions_without_ten_answers": "SELECT COUNT(*) FROM (SELECT s.id FROM submissions s LEFT JOIN answers x ON x.submission_id=s.id GROUP BY s.id HAVING COUNT(x.id)<>10) d",
        "invalid_submission_status": "SELECT COUNT(*) FROM submissions WHERE status IS NULL OR status<>'submitted'",
    }
    return {name: int(connection.execute(text(sql)).scalar_one()) for name, sql in checks.items()}


def verify_fixture(connection, profile: str, run_id: str, upload_root: Path,
                   state_table=None) -> dict:
    from sqlalchemy import select, text
    state_table = state_table if state_table is not None else ownership_table()
    states = connection.execute(select(state_table)).mappings().all()
    if len(states) != 1 or states[0]["run_id"] != run_id:
        raise FixtureError("fixture_ownership_missing_or_conflicting")
    state = states[0]
    if (state["profile"] != profile or state["seed"] != SEED
            or state["fixture_version"] != FIXTURE_VERSION or state["status"] != "complete"):
        raise FixtureError("fixture_profile_version_or_status_conflict")
    expected = expected_table_manifest(profile, run_id)
    if state["expected_tables"] != expected:
        raise FixtureError("persisted_expected_manifest_conflict")
    credential_hashes = connection.execute(text("SELECT DISTINCT password FROM users")).scalars().all()
    if (len(credential_hashes) != 1 or not isinstance(credential_hashes[0], str)
            or hashlib.sha256(credential_hashes[0].encode("utf-8")).hexdigest() != state["credential_hash_sha256"]):
        raise FixtureError("fixture_credential_hash_conflict")
    password = os.environ.get("CAMPUS_FIXTURE_PASSWORD")
    if password:
        from werkzeug.security import check_password_hash
        if not check_password_hash(credential_hashes[0], password):
            raise FixtureError("runtime_fixture_password_conflict")
    del password, credential_hashes
    actual = {}
    failures = []
    for name, table in model_tables().items():
        columns = expected[name]["columns"]
        query = select(*(table.c[column] for column in columns)).order_by(table.c.id)
        result = connection.execution_options(stream_results=True).execute(query)
        try:
            count, digest = table_digest((dict(row) for row in result.mappings()))
        finally:
            result.close()
            connection.execution_options(stream_results=False)
        actual[name] = {"count": count, "sha256": digest,
                        "expected_count": expected[name]["count"],
                        "expected_sha256": expected[name]["sha256"]}
        if count != expected[name]["count"] or digest != expected[name]["sha256"]:
            failures.append(name)
    relationships = relational_checks(connection)
    roles = dict(connection.execute(text("SELECT role, COUNT(*) FROM users GROUP BY role")).all())
    organization_counts = dict(connection.execute(text(
        "SELECT CASE WHEN code='platform' THEN 'platform_system' ELSE 'academic' END, COUNT(*) "
        "FROM organizations GROUP BY CASE WHEN code='platform' THEN 'platform_system' ELSE 'academic' END")).all())
    organization_counts["total_rows"] = sum(organization_counts.values())
    stages = {PHASES[int(phase)]: int(count) for phase, count in connection.execute(text(
        "SELECT MOD(a.id-1,4),COUNT(*) FROM submissions s JOIN assignments a ON a.id=s.assignment_id GROUP BY MOD(a.id-1,4)"))}
    deadline_pending = int(connection.execute(text(
        "SELECT COUNT(DISTINCT e.student_id) FROM course_enrollments e "
        "JOIN assignments a ON a.course_id=e.course_id AND MOD(a.id-1,4)=3 "
        "LEFT JOIN submissions s ON s.assignment_id=a.id AND s.student_id=e.student_id "
        "WHERE s.id IS NULL")).scalar_one())
    attachments = ensure_attachments(profile, run_id, upload_root, create=False)
    if attachments["manifest_sha256"] != state["attachment_manifest_sha256"]:
        raise FixtureError("persisted_attachment_manifest_conflict")
    counts = expected_counts(profile)
    if deadline_pending != counts["deadline_unsubmitted_students"]:
        failures.append("deadline_unsubmitted_students")
    if any(relationships.values()) or failures:
        raise FixtureError("baseline_verification_failed", {
            "failed_tables": failures, "tables": actual, "relationship_violations": relationships})
    return {
        "schema": "campus-fixture-manifest-v1", "status": "verified",
        "synthetic": True, "run_id": run_id, "seed": SEED,
        "fixture_version": FIXTURE_VERSION, "profile": profile,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_engine": connection.dialect.name,
        "expected_counts": counts, "actual_role_counts": roles,
        "actual_organization_counts": organization_counts,
        "tables": actual, "relationship_violations": relationships,
        "submissions_by_phase": stages, "deadline_unsubmitted_students": deadline_pending,
        "attachments": attachments,
        "fixture_content_sha256": hashlib.sha256(canonical(expected)).hexdigest(),
        "identity_contract": {
            "organizations": [f"campus_{i:02d}" for i in range(1, 6)],
            "student_username": "student_{global_one_based_index:05d}",
            "teacher_username": "teacher_{global_one_based_index:05d}",
            "password_source": "process environment CAMPUS_FIXTURE_PASSWORD (not recorded)",
            "academic_accounts_generated": counts["academic_accounts"],
            "http_participation": "not measured by fixture generation or SQL verification",
        },
        "calendar": {"epoch_utc": EPOCH.isoformat(),
                     "due_dates_utc": {phase: assignment_due_date(i).isoformat() for i, phase in enumerate(PHASES)},
                     "note": "Scenario tools explicitly set measured deadlines after verifying the baseline."},
        "hash_contract": "SHA-256 of ordered canonical JSON rows plus LF; fixture columns only; password excluded",
        "resources": {"insert_batch_rows": BATCH_SIZE,
                      "attachment_disk_bytes": attachments["total_size_bytes"],
                      "attachment_largest_bytes": max(ATTACHMENT_SIZES),
                      "database_disk_budget_bytes": 536870912 if profile == "full" else 67108864,
                      "database_disk_budget_is_estimate": True,
                      "small_academic_scale": "1/50; five academic organizations and six administrative accounts retained"},
        "replay_policy": "A repeat seed is strict verification; conflicts never repair or delete rows/files.",
    }


def seed_fixture(connection, profile: str, run_id: str, upload_root: Path,
                 state_table) -> tuple[dict, bool]:
    from sqlalchemy import func, select
    from werkzeug.security import generate_password_hash
    states = connection.execute(select(state_table)).mappings().all()
    if states:
        return verify_fixture(connection, profile, run_id, upload_root, state_table), False
    tables = model_tables()
    existing = {name: int(connection.execute(select(func.count()).select_from(table)).scalar_one())
                for name, table in tables.items()}
    if any(existing.values()):
        raise FixtureError("unowned_existing_business_data", {"table_counts": existing})
    password = os.environ.get("CAMPUS_FIXTURE_PASSWORD", "")
    if len(password) < 16 or len(password) > 256:
        raise FixtureError("runtime_fixture_password_required_16_to_256_characters")
    # A single run-scoped synthetic password keeps seeding bounded; the normal
    # application password verifier remains unchanged for every HTTP login.
    password_hash = generate_password_hash(password)
    del password
    attachments = ensure_attachments(profile, run_id, upload_root, create=True)
    expected = expected_table_manifest(profile, run_id)
    for name in TABLE_ORDER:
        batch = []
        for row in iter_rows(name, profile, run_id):
            if name == "users":
                row["password"] = password_hash
            batch.append(row)
            if len(batch) == BATCH_SIZE:
                connection.execute(tables[name].insert(), batch)
                batch.clear()
        if batch:
            connection.execute(tables[name].insert(), batch)
    connection.execute(state_table.insert().values(
        run_id=run_id, fixture_version=FIXTURE_VERSION, seed=SEED,
        profile=profile, status="complete", expected_tables=expected,
        credential_hash_sha256=hashlib.sha256(password_hash.encode("utf-8")).hexdigest(),
        attachment_manifest_sha256=attachments["manifest_sha256"], created_at=EPOCH))
    return verify_fixture(connection, profile, run_id, upload_root, state_table), True


def checked_output(value: str) -> Path:
    path = Path(value)
    root = Path("/runtime").resolve()
    if (not path.is_absolute() or path.suffix != ".json" or path.is_symlink()
            or root not in path.resolve().parents or path.resolve().parent == Path("/runtime/attachments")):
        raise FixtureError("output_must_be_runtime_json")
    return path


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise FixtureError("existing_output_not_owned_json") from None
        if not isinstance(previous, dict) or previous.get("run_id") != report["run_id"]:
            raise FixtureError("existing_output_run_conflict")
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seed", "verify"))
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    run_id = os.environ.get("CAMPUS_RUN_ID", "")
    output = None
    try:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{7,63}", run_id):
            raise FixtureError("dedicated_run_id_required")
        output = checked_output(args.output)
        from campus_runtime import assert_runtime_identity, create_campus_app
        assert_runtime_identity()
        app = create_campus_app()
        from app import db
        from sqlalchemy import inspect, text
        upload_root = checked_upload_root()
        with app.app_context(), db.engine.connect() as connection:
            if connection.dialect.name != "mysql":
                raise FixtureError("real_mysql_required")
            lock_name = "campus-fixture-" + hashlib.sha256(run_id.encode("ascii")).hexdigest()[:40]
            locked = connection.execute(text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": lock_name}).scalar_one()
            connection.commit()
            if locked != 1:
                raise FixtureError("fixture_run_already_locked")
            try:
                state_table = ownership_table()
                existing_tables = set(inspect(connection).get_table_names())
                connection.commit()
                if not existing_tables and args.command == "seed":
                    # Initialization is permitted only for a truly empty,
                    # identity-checked schema. Never fill holes in a partial
                    # schema or use create_all to hide an ambiguous upgrade.
                    db.metadata.create_all(connection)
                    connection.commit()
                    existing_tables = set(inspect(connection).get_table_names())
                    connection.commit()
                missing_business_tables = set(TABLE_ORDER) - existing_tables
                if missing_business_tables:
                    raise FixtureError("missing_or_partial_business_schema", {
                        "missing_tables": sorted(missing_business_tables)})
                exists = state_table.name in existing_tables
                if not exists:
                    if args.command == "verify":
                        raise FixtureError("fixture_not_seeded")
                    state_table.create(connection)
                    connection.commit()
                with connection.begin():
                    if args.command == "seed":
                        report, created = seed_fixture(connection, args.profile, run_id, upload_root, state_table)
                        report["action"] = "seeded" if created else "idempotent_verified"
                    else:
                        report = verify_fixture(connection, args.profile, run_id, upload_root, state_table)
                        report["action"] = "verified"
                write_report(output, report)
                print(json.dumps({"status": report["status"], "action": report["action"],
                                  "run_id": run_id, "profile": args.profile,
                                  "manifest": str(output), "tables": len(report["tables"]),
                                  "academic_accounts": report["expected_counts"]["academic_accounts"]}))
                return 0
            finally:
                connection.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name})
                connection.commit()
    except Exception as error:
        safe_error = error if isinstance(error, FixtureError) else FixtureError("fixture_operation_failed", {"exception_type": type(error).__name__})
        report = {"schema": "campus-fixture-error-v1", "status": "failed", "run_id": run_id,
                  "profile": args.profile, "command": args.command, "error": safe_error.code,
                  "details": safe_error.details}
        if output is not None:
            try:
                write_report(output, report)
            except Exception:
                pass
        print(json.dumps({"status": "failed", "error": safe_error.code,
                          "exception_type": type(error).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
