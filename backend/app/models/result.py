import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class MarkStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PUBLISHED = "published"


class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    internal_marks: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    external_marks: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0.0)
    grade: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    grade_point: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    status: Mapped[MarkStatus] = mapped_column(
        Enum(MarkStatus, name="mark_status_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=MarkStatus.DRAFT,
        index=True,
    )
    entered_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    subject: Mapped["Subject"] = relationship(foreign_keys=[subject_id])
    semester: Mapped["Semester"] = relationship(foreign_keys=[semester_id])
    entered_by_user: Mapped["User"] = relationship(foreign_keys=[entered_by])

    __table_args__ = (
        UniqueConstraint(
            "student_id", "subject_id", "semester_id", name="uq_mark_student_subject_semester"
        ),
        CheckConstraint("internal_marks >= 0", name="mark_internal_nonneg"),
        CheckConstraint("external_marks >= 0", name="mark_external_nonneg"),
        CheckConstraint("total >= 0", name="mark_total_nonneg"),
        Index("ix_marks_semester_status", "semester_id", "status"),
    )


class PublishedResult(Base):
    __tablename__ = "published_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sgpa: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    cgpa: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    result_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blockchain_tx_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    block_number: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    published_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    semester: Mapped["Semester"] = relationship(foreign_keys=[semester_id])
    publisher: Mapped["User"] = relationship(foreign_keys=[published_by])

    __table_args__ = (
        UniqueConstraint("student_id", "semester_id", name="uq_published_result_student_semester"),
        CheckConstraint("sgpa >= 0 AND sgpa <= 10", name="published_result_sgpa_range"),
        CheckConstraint("cgpa >= 0 AND cgpa <= 10", name="published_result_cgpa_range"),
    )
