"""Initial normalized schema for Student Result Management System.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role_enum = sa.Enum("admin", "faculty", "student", name="user_role_enum")
    mark_status_enum = sa.Enum("draft", "under_review", "published", name="mark_status_enum")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("enrollment_no", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("enrollment_no", name="uq_users_enrollment_no"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_enrollment_no", "users", ["enrollment_no"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user_active", "refresh_tokens", ["user_id", "revoked_at"], unique=False)

    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
        sa.UniqueConstraint("code", name="uq_departments_code"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_index("ix_departments_code", "departments", ["code"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("duration_semesters", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_semesters > 0", name="ck_courses_course_duration_positive"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_courses_department_id_departments", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )
    op.create_index("ix_courses_department_id", "courses", ["department_id"], unique=False)
    op.create_index("ix_courses_code", "courses", ["code"], unique=True)

    op.create_table(
        "semesters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("number > 0", name="ck_semesters_semester_number_positive"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_semesters_course_id_courses", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_semesters"),
        sa.UniqueConstraint("course_id", "number", "academic_year", name="uq_semester_course_num_year"),
    )
    op.create_index("ix_semesters_course_id", "semesters", ["course_id"], unique=False)

    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("faculty_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("credits", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("max_internal", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("max_external", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("passing_marks", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("credits > 0", name="ck_subjects_subject_credits_positive"),
        sa.CheckConstraint("max_internal >= 0", name="ck_subjects_subject_max_internal_nonneg"),
        sa.CheckConstraint("max_external >= 0", name="ck_subjects_subject_max_external_nonneg"),
        sa.CheckConstraint("passing_marks >= 0", name="ck_subjects_subject_passing_marks_nonneg"),
        sa.ForeignKeyConstraint(["faculty_id"], ["users.id"], name="fk_subjects_faculty_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], name="fk_subjects_semester_id_semesters", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
        sa.UniqueConstraint("code", name="uq_subjects_code"),
    )
    op.create_index("ix_subjects_semester_id", "subjects", ["semester_id"], unique=False)
    op.create_index("ix_subjects_faculty_id", "subjects", ["faculty_id"], unique=False)
    op.create_index("ix_subjects_code", "subjects", ["code"], unique=True)

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_enrollments_course_id_courses", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], name="fk_enrollments_semester_id_semesters", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_enrollments_student_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_enrollments"),
        sa.UniqueConstraint("student_id", "semester_id", name="uq_enrollment_student_semester"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"], unique=False)
    op.create_index("ix_enrollments_semester_id", "enrollments", ["semester_id"], unique=False)
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"], unique=False)

    op.create_table(
        "marks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("internal_marks", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("external_marks", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("grade", sa.String(length=8), nullable=True),
        sa.Column("grade_point", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("status", mark_status_enum, nullable=False),
        sa.Column("entered_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("internal_marks >= 0", name="ck_marks_mark_internal_nonneg"),
        sa.CheckConstraint("external_marks >= 0", name="ck_marks_mark_external_nonneg"),
        sa.CheckConstraint("total >= 0", name="ck_marks_mark_total_nonneg"),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"], name="fk_marks_entered_by_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], name="fk_marks_semester_id_semesters", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_marks_student_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name="fk_marks_subject_id_subjects", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_marks"),
        sa.UniqueConstraint("student_id", "subject_id", "semester_id", name="uq_mark_student_subject_semester"),
    )
    op.create_index("ix_marks_student_id", "marks", ["student_id"], unique=False)
    op.create_index("ix_marks_subject_id", "marks", ["subject_id"], unique=False)
    op.create_index("ix_marks_semester_id", "marks", ["semester_id"], unique=False)
    op.create_index("ix_marks_status", "marks", ["status"], unique=False)
    op.create_index("ix_marks_entered_by", "marks", ["entered_by"], unique=False)
    op.create_index("ix_marks_semester_status", "marks", ["semester_id", "status"], unique=False)

    op.create_table(
        "published_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("semester_id", sa.Uuid(), nullable=False),
        sa.Column("sgpa", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("cgpa", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("result_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("blockchain_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("block_number", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint("sgpa >= 0 AND sgpa <= 10", name="ck_published_results_published_result_sgpa_range"),
        sa.CheckConstraint("cgpa >= 0 AND cgpa <= 10", name="ck_published_results_published_result_cgpa_range"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], name="fk_published_results_published_by_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], name="fk_published_results_semester_id_semesters", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_published_results_student_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_published_results"),
        sa.UniqueConstraint("student_id", "semester_id", name="uq_published_result_student_semester"),
    )
    op.create_index("ix_published_results_student_id", "published_results", ["student_id"], unique=False)
    op.create_index("ix_published_results_semester_id", "published_results", ["semester_id"], unique=False)
    op.create_index("ix_published_results_result_hash_sha256", "published_results", ["result_hash_sha256"], unique=False)
    op.create_index("ix_published_results_blockchain_tx_hash", "published_results", ["blockchain_tx_hash"], unique=False)
    op.create_index("ix_published_results_published_by", "published_results", ["published_by"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_audit_logs_actor_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("published_results")
    op.drop_table("marks")
    op.drop_table("enrollments")
    op.drop_table("subjects")
    op.drop_table("semesters")
    op.drop_table("courses")
    op.drop_table("departments")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    sa.Enum(name="mark_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role_enum").drop(op.get_bind(), checkfirst=True)
