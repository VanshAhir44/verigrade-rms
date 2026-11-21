import asyncio
import re
import uuid
from datetime import timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.academic import Course, Department, Enrollment, Semester, Subject
from app.models.result import Mark, MarkStatus, PublishedResult
from app.models.user import User, UserRole
from app.schemas.academic import (
    StudentDashboardResponse,
    StudentSemesterResult,
    StudentSubjectResult,
)
from app.services.pdf_service import MarksheetData, MarksheetSubjectLine, generate_marksheet_pdf

router = APIRouter(prefix="/student", tags=["Student (Results & Transcripts)"])
student_guard = require_roles(UserRole.STUDENT)


@router.get("/results", response_model=StudentDashboardResponse)
async def get_student_results(
    student: User = Depends(student_guard),
    db: AsyncSession = Depends(get_db),
) -> StudentDashboardResponse:
    enrollments = (
        await db.execute(select(Enrollment).where(Enrollment.student_id == student.id))
    ).scalars().all()

    semester_items: list[StudentSemesterResult] = []

    for enr in enrollments:
        semester = (
            await db.execute(select(Semester).where(Semester.id == enr.semester_id))
        ).scalar_one()
        course = (
            await db.execute(select(Course).where(Course.id == enr.course_id))
        ).scalar_one()
        published = (
            await db.execute(
                select(PublishedResult).where(
                    PublishedResult.student_id == student.id,
                    PublishedResult.semester_id == semester.id,
                )
            )
        ).scalar_one_or_none()

        marks = (
            await db.execute(
                select(Mark).where(
                    Mark.student_id == student.id,
                    Mark.semester_id == semester.id,
                )
            )
        ).scalars().all()

        if published is not None:
            result_status = MarkStatus.PUBLISHED.value
            subjects_map = {
                s.id: s
                for s in (
                    await db.execute(select(Subject).where(Subject.semester_id == semester.id))
                )
                .scalars()
                .all()
            }
            subject_rows = [
                StudentSubjectResult(
                    subject_code=subjects_map[m.subject_id].code,
                    subject_name=subjects_map[m.subject_id].name,
                    credits=Decimal(str(subjects_map[m.subject_id].credits)),
                    internal_marks=Decimal(str(m.internal_marks)),
                    external_marks=Decimal(str(m.external_marks)),
                    total=Decimal(str(m.total)),
                    max_total=Decimal(str(subjects_map[m.subject_id].max_internal))
                    + Decimal(str(subjects_map[m.subject_id].max_external)),
                    grade=m.grade,
                    grade_point=Decimal(str(m.grade_point)) if m.grade_point is not None else None,
                    status=m.status,
                )
                for m in marks
                if m.subject_id in subjects_map
            ]
            subject_rows.sort(key=lambda r: r.subject_code)
            has_fail = any((r.grade or "F") == "F" for r in subject_rows)

            semester_items.append(
                StudentSemesterResult(
                    semester_id=semester.id,
                    semester_number=semester.number,
                    academic_year=semester.academic_year,
                    course_name=course.name,
                    result_status=result_status,
                    result_id=published.id,
                    sgpa=Decimal(str(published.sgpa)),
                    cgpa=Decimal(str(published.cgpa)),
                    overall_status="FAIL" if has_fail else "PASS",
                    result_hash_sha256=published.result_hash_sha256,
                    blockchain_tx_hash=published.blockchain_tx_hash,
                    block_number=published.block_number,
                    published_at=published.published_at,
                    subjects=subject_rows,
                )
            )
        else:
            if marks and all(m.status == MarkStatus.UNDER_REVIEW for m in marks):
                result_status = MarkStatus.UNDER_REVIEW.value
            else:
                result_status = MarkStatus.DRAFT.value
            semester_items.append(
                StudentSemesterResult(
                    semester_id=semester.id,
                    semester_number=semester.number,
                    academic_year=semester.academic_year,
                    course_name=course.name,
                    result_status=result_status,
                    subjects=[],
                )
            )

    # P1-4 fix: sort semesters chronologically BEFORE selecting latest_cgpa
    semester_items.sort(key=lambda s: (s.academic_year, s.semester_number))
    published_sorted = [s for s in semester_items if s.cgpa is not None]
    latest_cgpa: Decimal | None = published_sorted[-1].cgpa if published_sorted else None

    return StudentDashboardResponse(
        student_id=student.id,
        full_name=student.full_name,
        enrollment_no=student.enrollment_no,
        latest_cgpa=latest_cgpa,
        semesters=semester_items,
    )


@router.get("/results/{result_id}/pdf")
async def download_marksheet_pdf(
    result_id: uuid.UUID,
    student: User = Depends(student_guard),
    db: AsyncSession = Depends(get_db),
) -> Response:
    published = (
        await db.execute(select(PublishedResult).where(PublishedResult.id == result_id))
    ).scalar_one_or_none()
    if published is None:
        raise HTTPException(status_code=404, detail="Published result not found")
    if published.student_id != student.id:
        raise HTTPException(status_code=403, detail="You can only download your own marksheet")

    semester = (
        await db.execute(select(Semester).where(Semester.id == published.semester_id))
    ).scalar_one()
    course = (
        await db.execute(select(Course).where(Course.id == semester.course_id))
    ).scalar_one()
    department = (
        await db.execute(select(Department).where(Department.id == course.department_id))
    ).scalar_one()

    marks = (
        await db.execute(
            select(Mark).where(
                Mark.student_id == student.id,
                Mark.semester_id == semester.id,
            )
        )
    ).scalars().all()
    subjects_map = {
        s.id: s
        for s in (
            await db.execute(select(Subject).where(Subject.semester_id == semester.id))
        )
        .scalars()
        .all()
    }

    matched_pairs = [
        (m, subjects_map[m.subject_id]) for m in marks if m.subject_id in subjects_map
    ]
    matched_pairs.sort(key=lambda pair: pair[1].code)

    lines = []
    has_fail = False
    for m, sub in matched_pairs:
        max_total = Decimal(str(sub.max_internal)) + Decimal(str(sub.max_external))
        if (m.grade or "F") == "F":
            has_fail = True
        lines.append(
            MarksheetSubjectLine(
                code=sub.code,
                name=sub.name,
                credits=f"{Decimal(str(sub.credits)):.1f}",
                internal_marks=f"{Decimal(str(m.internal_marks)):.1f}",
                external_marks=f"{Decimal(str(m.external_marks)):.1f}",
                total=f"{Decimal(str(m.total)):.1f}",
                max_total=f"{max_total:.0f}",
                grade=m.grade or "F",
                grade_point=f"{Decimal(str(m.grade_point or 0)):.1f}",
                status="FAIL" if (m.grade or "F") == "F" else "PASS",
            )
        )

    base_url = (settings.PUBLIC_VERIFY_BASE_URL or "http://localhost:3000/verify").rstrip("/")
    verify_url = f"{base_url}/{published.id}"

    published_utc = (
        published.published_at
        if published.published_at.tzinfo is not None
        else published.published_at.replace(tzinfo=timezone.utc)
    )
    published_ist_str = published_utc.astimezone(ZoneInfo("Asia/Kolkata")).strftime(
        "%d %b %Y, %I:%M:%S %p IST"
    )

    marksheet_data = MarksheetData(
        result_id=str(published.id),
        student_name=student.full_name,
        enrollment_no=student.enrollment_no or "N/A",
        department_name=department.name,
        course_name=course.name,
        semester_number=semester.number,
        academic_year=semester.academic_year,
        sgpa=f"{Decimal(str(published.sgpa)):.2f}",
        cgpa=f"{Decimal(str(published.cgpa)):.2f}",
        overall_status="FAIL" if has_fail else "PASS",
        result_hash_sha256=published.result_hash_sha256,
        blockchain_tx_hash=published.blockchain_tx_hash or "N/A",
        block_number=published.block_number,
        published_at_iso=published_ist_str,
        verify_url=verify_url,
        subjects=lines,
    )

    # Offload CPU-bound ReportLab + QR generation from the async event loop (P2-12)
    pdf_bytes = await asyncio.to_thread(generate_marksheet_pdf, marksheet_data)

    safe_enr = re.sub(r"[^A-Za-z0-9._-]", "_", student.enrollment_no or str(student.id))
    filename = f"marksheet_{safe_enr}_sem{semester.number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
