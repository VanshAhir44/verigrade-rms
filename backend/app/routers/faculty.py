import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.base import utcnow
from app.db.session import get_db
from app.models.academic import Enrollment, Semester, Subject
from app.models.audit import AuditLog
from app.models.result import Mark, MarkStatus
from app.models.user import User, UserRole
from app.schemas.academic import (
    BatchMarksUpsertRequest,
    FacultyStudentMarkRow,
    FacultySubjectRosterResponse,
    MarkResponse,
    SubjectResponse,
    SubmitSubjectMarksResponse,
)
from app.services.grading_service import evaluate_subject_mark
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/faculty", tags=["Faculty (Marks Entry)"])
faculty_guard = require_roles(UserRole.FACULTY)


async def _get_assigned_subject(
    db: AsyncSession, subject_id: uuid.UUID, faculty: User
) -> Subject:
    subject = (
        await db.execute(select(Subject).where(Subject.id == subject_id))
    ).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    if subject.faculty_id != faculty.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this subject",
        )
    return subject


@router.get("/subjects", response_model=list[FacultySubjectRosterResponse])
async def list_assigned_subjects(
    faculty: User = Depends(faculty_guard),
    db: AsyncSession = Depends(get_db),
) -> list[FacultySubjectRosterResponse]:
    subjects = (
        await db.execute(
            select(Subject)
            .where(Subject.faculty_id == faculty.id)
            .order_by(Subject.code.asc())
        )
    ).scalars().all()

    response: list[FacultySubjectRosterResponse] = []
    for sub in subjects:
        semester = (
            await db.execute(select(Semester).where(Semester.id == sub.semester_id))
        ).scalar_one()
        enrollments = (
            await db.execute(
                select(Enrollment).where(Enrollment.semester_id == sub.semester_id)
            )
        ).scalars().all()
        marks = (
            await db.execute(
                select(Mark).where(
                    Mark.subject_id == sub.id,
                    Mark.semester_id == sub.semester_id,
                )
            )
        ).scalars().all()
        marks_by_student = {m.student_id: m for m in marks}

        student_rows: list[FacultyStudentMarkRow] = []
        for enr in enrollments:
            student = (
                await db.execute(select(User).where(User.id == enr.student_id))
            ).scalar_one()
            mark = marks_by_student.get(student.id)
            student_rows.append(
                FacultyStudentMarkRow(
                    student_id=student.id,
                    student_name=student.full_name,
                    enrollment_no=student.enrollment_no,
                    internal_marks=mark.internal_marks if mark else None,
                    external_marks=mark.external_marks if mark else None,
                    total=mark.total if mark else None,
                    grade=mark.grade if mark else None,
                    grade_point=mark.grade_point if mark else None,
                    status=mark.status if mark else None,
                )
            )

        response.append(
            FacultySubjectRosterResponse(
                subject=SubjectResponse.model_validate(sub),
                semester_number=semester.number,
                academic_year=semester.academic_year,
                students=student_rows,
            )
        )
    return response


@router.put("/subjects/{subject_id}/marks", response_model=list[MarkResponse])
async def upsert_subject_marks(
    subject_id: uuid.UUID,
    payload: BatchMarksUpsertRequest,
    faculty: User = Depends(faculty_guard),
    db: AsyncSession = Depends(get_db),
) -> list[MarkResponse]:
    subject = await _get_assigned_subject(db, subject_id, faculty)

    enrolled_ids = set(
        (
            await db.execute(
                select(Enrollment.student_id).where(Enrollment.semester_id == subject.semester_id)
            )
        )
        .scalars()
        .all()
    )

    saved_marks: list[Mark] = []
    for entry in payload.entries:
        if entry.student_id not in enrolled_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Student {entry.student_id} is not enrolled in this subject's semester",
            )

        try:
            evaluation = evaluate_subject_mark(
                internal_marks=entry.internal_marks,
                external_marks=entry.external_marks,
                max_internal=subject.max_internal,
                max_external=subject.max_external,
                passing_marks=subject.passing_marks,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        existing = (
            await db.execute(
                select(Mark).where(
                    Mark.student_id == entry.student_id,
                    Mark.subject_id == subject.id,
                    Mark.semester_id == subject.semester_id,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.status != MarkStatus.DRAFT:
                raise HTTPException(
                    status_code=409,
                    detail=f"Marks for student {entry.student_id} are locked ({existing.status.value})",
                )
            old_snapshot = {
                "internal_marks": str(existing.internal_marks),
                "external_marks": str(existing.external_marks),
                "total": str(existing.total),
                "grade": existing.grade,
            }
            existing.internal_marks = evaluation.internal_marks
            existing.external_marks = evaluation.external_marks
            existing.total = evaluation.total
            existing.grade = evaluation.grade
            existing.grade_point = evaluation.grade_point
            existing.entered_by = faculty.id
            existing.updated_at = utcnow()
            mark_obj = existing
            action = "MARK_UPDATED"
        else:
            old_snapshot = None
            mark_obj = Mark(
                student_id=entry.student_id,
                subject_id=subject.id,
                semester_id=subject.semester_id,
                internal_marks=evaluation.internal_marks,
                external_marks=evaluation.external_marks,
                total=evaluation.total,
                grade=evaluation.grade,
                grade_point=evaluation.grade_point,
                status=MarkStatus.DRAFT,
                entered_by=faculty.id,
            )
            db.add(mark_obj)
            await db.flush()
            action = "MARK_CREATED"

        db.add(
            AuditLog(
                actor_id=faculty.id,
                action=action,
                entity_type="mark",
                entity_id=str(mark_obj.id),
                old_value_json=old_snapshot,
                new_value_json={
                    "student_id": str(entry.student_id),
                    "subject_code": subject.code,
                    "internal_marks": str(evaluation.internal_marks),
                    "external_marks": str(evaluation.external_marks),
                    "total": str(evaluation.total),
                    "grade": evaluation.grade,
                    "grade_point": str(evaluation.grade_point),
                },
            )
        )
        saved_marks.append(mark_obj)

    await db.commit()
    for m in saved_marks:
        await db.refresh(m)
    return [MarkResponse.model_validate(m) for m in saved_marks]


@router.post("/subjects/{subject_id}/submit", response_model=SubmitSubjectMarksResponse)
async def submit_subject_marks_for_review(
    subject_id: uuid.UUID,
    faculty: User = Depends(faculty_guard),
    db: AsyncSession = Depends(get_db),
) -> SubmitSubjectMarksResponse:
    """Locks all draft marks for a subject and moves them to under_review for Admin approval."""
    subject = await _get_assigned_subject(db, subject_id, faculty)

    enrolled_ids = set(
        (
            await db.execute(
                select(Enrollment.student_id).where(Enrollment.semester_id == subject.semester_id)
            )
        )
        .scalars()
        .all()
    )
    marks = (
        await db.execute(
            select(Mark).where(
                Mark.subject_id == subject.id,
                Mark.semester_id == subject.semester_id,
            )
        )
    ).scalars().all()

    if len(marks) < len(enrolled_ids):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit: marks entered for {len(marks)}/{len(enrolled_ids)} enrolled students",
        )

    draft_marks = [m for m in marks if m.status == MarkStatus.DRAFT]
    if not draft_marks:
        raise HTTPException(status_code=409, detail="Marks have already been submitted or published")

    now = utcnow()
    for m in draft_marks:
        m.status = MarkStatus.UNDER_REVIEW
        m.updated_at = now

    db.add(
        AuditLog(
            actor_id=faculty.id,
            action="MARKS_SUBMITTED",
            entity_type="subject",
            entity_id=str(subject.id),
            new_value_json={"subject_code": subject.code, "submitted_count": len(draft_marks)},
        )
    )
    await db.commit()

    await ws_manager.broadcast_to_role(
        UserRole.ADMIN.value,
        {
            "event": "MARKS_SUBMITTED",
            "subject_id": str(subject.id),
            "subject_code": subject.code,
            "semester_id": str(subject.semester_id),
            "submitted_count": len(draft_marks),
        },
    )
    for student_id in enrolled_ids:
        await ws_manager.send_to_user(
            str(student_id),
            {
                "event": "STATUS_UPDATED",
                "semester_id": str(subject.semester_id),
                "subject_code": subject.code,
                "status": MarkStatus.UNDER_REVIEW.value,
            },
        )

    return SubmitSubjectMarksResponse(
        subject_id=subject.id,
        submitted_count=len(draft_marks),
        status=MarkStatus.UNDER_REVIEW,
    )
