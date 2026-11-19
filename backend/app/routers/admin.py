import csv
import io
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models.academic import Course, Department, Enrollment, Semester, Subject
from app.models.audit import AuditLog
from app.models.result import Mark, MarkStatus, PublishedResult
from app.models.user import User, UserRole
from app.schemas.academic import (
    AuditLogResponse,
    BulkCsvError,
    BulkCsvImportResponse,
    CourseCreate,
    CourseResponse,
    DepartmentCreate,
    DepartmentResponse,
    EnrollmentCreate,
    EnrollmentResponse,
    PublishedResultResponse,
    SemesterCreate,
    SemesterPublishResponse,
    SemesterResponse,
    SubjectCreate,
    SubjectResponse,
)
from app.services.blockchain_service import BlockchainService, compute_result_hash
from app.services.grading_service import calculate_cgpa, summarize_semester
from app.services.result_service import build_canonical_result_payload, get_blockchain_service
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/admin", tags=["Admin (Controller of Examinations)"])
admin_guard = require_roles(UserRole.ADMIN)


# --- Departments ---
@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    code = payload.code.strip().upper()
    existing = await db.execute(select(Department).where(Department.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Department code already exists")
    dept = Department(code=code, name=payload.name.strip())
    db.add(dept)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="DEPARTMENT_CREATED",
            entity_type="department",
            entity_id=str(dept.id),
            new_value_json={"code": dept.code, "name": dept.name},
        )
    )
    await db.commit()
    await db.refresh(dept)
    return DepartmentResponse.model_validate(dept)


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    _admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> list[DepartmentResponse]:
    rows = (await db.execute(select(Department).order_by(Department.code.asc()))).scalars().all()
    return [DepartmentResponse.model_validate(d) for d in rows]


# --- Courses ---
@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> CourseResponse:
    dept = (await db.execute(select(Department).where(Department.id == payload.department_id))).scalar_one_or_none()
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    code = payload.code.strip().upper()
    if (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Course code already exists")
    course = Course(
        department_id=dept.id,
        code=code,
        name=payload.name.strip(),
        duration_semesters=payload.duration_semesters,
    )
    db.add(course)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="COURSE_CREATED",
            entity_type="course",
            entity_id=str(course.id),
            new_value_json={"code": course.code, "name": course.name},
        )
    )
    await db.commit()
    await db.refresh(course)
    return CourseResponse.model_validate(course)


@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    _admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> list[CourseResponse]:
    rows = (await db.execute(select(Course).order_by(Course.code.asc()))).scalars().all()
    return [CourseResponse.model_validate(c) for c in rows]


# --- Semesters ---
@router.post("/semesters", response_model=SemesterResponse, status_code=status.HTTP_201_CREATED)
async def create_semester(
    payload: SemesterCreate,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> SemesterResponse:
    course = (await db.execute(select(Course).where(Course.id == payload.course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    existing = (
        await db.execute(
            select(Semester).where(
                Semester.course_id == course.id,
                Semester.number == payload.number,
                Semester.academic_year == payload.academic_year.strip(),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Semester already exists for this course and year")
    sem = Semester(
        course_id=course.id,
        number=payload.number,
        academic_year=payload.academic_year.strip(),
        is_active=payload.is_active,
    )
    db.add(sem)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="SEMESTER_CREATED",
            entity_type="semester",
            entity_id=str(sem.id),
            new_value_json={"course_id": str(sem.course_id), "number": sem.number, "academic_year": sem.academic_year},
        )
    )
    await db.commit()
    await db.refresh(sem)
    return SemesterResponse.model_validate(sem)


@router.get("/semesters", response_model=list[SemesterResponse])
async def list_semesters(
    _admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> list[SemesterResponse]:
    rows = (await db.execute(select(Semester).order_by(Semester.academic_year.desc(), Semester.number.asc()))).scalars().all()
    return [SemesterResponse.model_validate(s) for s in rows]


# --- Subjects ---
@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> SubjectResponse:
    sem = (await db.execute(select(Semester).where(Semester.id == payload.semester_id))).scalar_one_or_none()
    if sem is None:
        raise HTTPException(status_code=404, detail="Semester not found")
    if payload.faculty_id is not None:
        fac = (await db.execute(select(User).where(User.id == payload.faculty_id, User.role == UserRole.FACULTY))).scalar_one_or_none()
        if fac is None:
            raise HTTPException(status_code=404, detail="Assigned faculty user not found")
    if payload.passing_marks > (payload.max_internal + payload.max_external):
        raise HTTPException(status_code=422, detail="passing_marks cannot exceed max_internal + max_external")

    code = payload.code.strip().upper()
    if (await db.execute(select(Subject).where(Subject.code == code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Subject code already exists")

    subject = Subject(
        semester_id=sem.id,
        faculty_id=payload.faculty_id,
        code=code,
        name=payload.name.strip(),
        credits=payload.credits,
        max_internal=payload.max_internal,
        max_external=payload.max_external,
        passing_marks=payload.passing_marks,
    )
    db.add(subject)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="SUBJECT_CREATED",
            entity_type="subject",
            entity_id=str(subject.id),
            new_value_json={"code": subject.code, "name": subject.name, "credits": str(subject.credits)},
        )
    )
    await db.commit()
    await db.refresh(subject)
    return SubjectResponse.model_validate(subject)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    semester_id: Optional[uuid.UUID] = Query(default=None),
    _admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> list[SubjectResponse]:
    stmt = select(Subject).order_by(Subject.code.asc())
    if semester_id is not None:
        stmt = stmt.where(Subject.semester_id == semester_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [SubjectResponse.model_validate(s) for s in rows]


# --- Enrollments ---
@router.post("/enrollments", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    payload: EnrollmentCreate,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentResponse:
    student = (await db.execute(select(User).where(User.id == payload.student_id, User.role == UserRole.STUDENT))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    existing = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == payload.student_id,
                Enrollment.semester_id == payload.semester_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Student is already enrolled in this semester")
    enrollment = Enrollment(
        student_id=payload.student_id,
        semester_id=payload.semester_id,
        course_id=payload.course_id,
    )
    db.add(enrollment)
    await db.flush()
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="ENROLLMENT_CREATED",
            entity_type="enrollment",
            entity_id=str(enrollment.id),
            new_value_json={"student_id": str(payload.student_id), "semester_id": str(payload.semester_id)},
        )
    )
    await db.commit()
    await db.refresh(enrollment)
    return EnrollmentResponse.model_validate(enrollment)


# --- Bulk CSV User Import ---
@router.post("/users/bulk-csv", response_model=BulkCsvImportResponse)
async def bulk_import_users_csv(
    file: UploadFile = File(...),
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> BulkCsvImportResponse:
    """Imports Faculty/Student accounts from a CSV with columns: email,full_name,role,password,enrollment_no."""
    raw_bytes = await file.read()
    try:
        text_content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text_content))
    required_cols = {"email", "full_name", "role", "password"}
    if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain headers: {', '.join(sorted(required_cols))}",
        )

    created_count = 0
    errors: list[BulkCsvError] = []

    for row_num, row in enumerate(reader, start=2):
        email = (row.get("email") or "").strip().lower()
        full_name = (row.get("full_name") or "").strip()
        role_str = (row.get("role") or "").strip().lower()
        password = (row.get("password") or "").strip()
        enrollment_no = (row.get("enrollment_no") or "").strip() or None

        if not email or "@" not in email:
            errors.append(BulkCsvError(row=row_num, email=email or None, error="Invalid email"))
            continue
        if len(full_name) < 2:
            errors.append(BulkCsvError(row=row_num, email=email, error="full_name too short"))
            continue
        if len(password) < 8:
            errors.append(BulkCsvError(row=row_num, email=email, error="password must be at least 8 characters"))
            continue
        try:
            role = UserRole(role_str)
        except ValueError:
            errors.append(BulkCsvError(row=row_num, email=email, error=f"Invalid role '{role_str}'"))
            continue
        if role == UserRole.STUDENT and not enrollment_no:
            errors.append(BulkCsvError(row=row_num, email=email, error="enrollment_no required for student"))
            continue

        dup_email = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if dup_email:
            errors.append(BulkCsvError(row=row_num, email=email, error="Duplicate email"))
            continue
        if enrollment_no:
            dup_enr = (await db.execute(select(User).where(User.enrollment_no == enrollment_no))).scalar_one_or_none()
            if dup_enr:
                errors.append(BulkCsvError(row=row_num, email=email, error="Duplicate enrollment_no"))
                continue

        new_user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            enrollment_no=enrollment_no,
            is_active=True,
        )
        db.add(new_user)
        await db.flush()
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="USER_BULK_IMPORTED",
                entity_type="user",
                entity_id=str(new_user.id),
                new_value_json={"email": email, "role": role.value, "enrollment_no": enrollment_no},
            )
        )
        created_count += 1

    await db.commit()
    return BulkCsvImportResponse(created_count=created_count, errors=errors)


# --- Immutable Audit Logs ---
@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = (await db.execute(stmt)).scalars().all()
    return [AuditLogResponse.model_validate(a) for a in rows]


# --- One-Click Live Publish (DB Lock + Blockchain Hash + WebSocket Broadcast) ---
@router.post("/semesters/{semester_id}/publish", response_model=SemesterPublishResponse)
async def publish_semester_results(
    semester_id: uuid.UUID,
    admin: User = Depends(admin_guard),
    db: AsyncSession = Depends(get_db),
    blockchain: BlockchainService = Depends(get_blockchain_service),
) -> SemesterPublishResponse:
    semester = (await db.execute(select(Semester).where(Semester.id == semester_id))).scalar_one_or_none()
    if semester is None:
        raise HTTPException(status_code=404, detail="Semester not found")

    subjects = (
        await db.execute(select(Subject).where(Subject.semester_id == semester_id))
    ).scalars().all()
    if not subjects:
        raise HTTPException(status_code=400, detail="No subjects configured for this semester")
    subjects_by_id = {s.id: s for s in subjects}

    enrollments = (
        await db.execute(select(Enrollment).where(Enrollment.semester_id == semester_id))
    ).scalars().all()
    if not enrollments:
        raise HTTPException(status_code=400, detail="No students enrolled in this semester")

    published_records: list[PublishedResult] = []
    ws_notifications: list[tuple[str, dict]] = []

    for enrollment in enrollments:
        student = (await db.execute(select(User).where(User.id == enrollment.student_id))).scalar_one()

        already = (
            await db.execute(
                select(PublishedResult).where(
                    PublishedResult.student_id == student.id,
                    PublishedResult.semester_id == semester_id,
                )
            )
        ).scalar_one_or_none()
        if already is not None:
            published_records.append(already)
            continue

        marks = (
            await db.execute(
                select(Mark).where(
                    Mark.student_id == student.id,
                    Mark.semester_id == semester_id,
                )
            )
        ).scalars().all()

        if len(marks) < len(subjects):
            raise HTTPException(
                status_code=400,
                detail=f"Incomplete marks for student {student.enrollment_no or student.email}: "
                f"{len(marks)}/{len(subjects)} subjects entered",
            )

        not_submitted = [m for m in marks if m.status != MarkStatus.UNDER_REVIEW]
        if not_submitted:
            raise HTTPException(
                status_code=400,
                detail=f"All marks for student {student.enrollment_no or student.email} must be submitted (under_review) before publishing",
            )

        marks_with_subjects = [(m, subjects_by_id[m.subject_id]) for m in marks]
        sem_summary = summarize_semester(
            [
                (
                    sub.credits,
                    m.grade_point if m.grade_point is not None else Decimal("0"),
                    (m.grade or "F") != "F",
                )
                for m, sub in marks_with_subjects
            ]
        )

        # Compute cumulative CGPA across prior published semesters + current semester
        prior_published = (
            await db.execute(
                select(PublishedResult).where(
                    PublishedResult.student_id == student.id,
                    PublishedResult.semester_id != semester_id,
                )
            )
        ).scalars().all()

        sem_credit_sgpa_pairs: list[tuple[Decimal, Decimal]] = []
        for prev in prior_published:
            prev_subs = (
                await db.execute(select(Subject).where(Subject.semester_id == prev.semester_id))
            ).scalars().all()
            prev_credits = sum((Decimal(str(s.credits)) for s in prev_subs), Decimal("0"))
            if prev_credits > Decimal("0"):
                sem_credit_sgpa_pairs.append((prev_credits, Decimal(str(prev.sgpa))))
        sem_credit_sgpa_pairs.append((sem_summary.total_credits, sem_summary.sgpa))
        cgpa = calculate_cgpa(sem_credit_sgpa_pairs)

        result_uuid = uuid.uuid4()
        canonical_payload = build_canonical_result_payload(
            result_id=str(result_uuid),
            student=student,
            semester=semester,
            sgpa=sem_summary.sgpa,
            cgpa=cgpa,
            marks_with_subjects=marks_with_subjects,
        )
        result_hash = compute_result_hash(canonical_payload)

        # Anchor immutable SHA-256 hash on-chain
        receipt = blockchain.store_result_hash(str(result_uuid), result_hash)

        # Lock all marks as published
        now = utcnow()
        for m in marks:
            m.status = MarkStatus.PUBLISHED
            m.updated_at = now

        published = PublishedResult(
            id=result_uuid,
            student_id=student.id,
            semester_id=semester_id,
            sgpa=sem_summary.sgpa,
            cgpa=cgpa,
            result_hash_sha256=result_hash,
            blockchain_tx_hash=receipt.tx_hash,
            block_number=receipt.block_number,
            published_at=now,
            published_by=admin.id,
        )
        db.add(published)
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="RESULT_PUBLISHED",
                entity_type="published_result",
                entity_id=str(result_uuid),
                new_value_json={
                    "student_id": str(student.id),
                    "semester_id": str(semester_id),
                    "sgpa": str(sem_summary.sgpa),
                    "cgpa": str(cgpa),
                    "result_hash_sha256": result_hash,
                    "blockchain_tx_hash": receipt.tx_hash,
                    "block_number": receipt.block_number,
                },
            )
        )
        published_records.append(published)
        ws_notifications.append(
            (
                str(student.id),
                {
                    "event": "RESULT_PUBLISHED",
                    "result_id": str(result_uuid),
                    "semester_id": str(semester_id),
                    "semester_number": semester.number,
                    "academic_year": semester.academic_year,
                    "sgpa": str(sem_summary.sgpa),
                    "cgpa": str(cgpa),
                    "overall_status": sem_summary.overall_status,
                    "result_hash_sha256": result_hash,
                    "blockchain_tx_hash": receipt.tx_hash,
                    "block_number": receipt.block_number,
                    "published_at": now.isoformat(),
                },
            )
        )

    await db.commit()
    for rec in published_records:
        await db.refresh(rec)

    # Real-time WebSocket push to connected students (zero page reload)
    for student_id_str, payload_event in ws_notifications:
        await ws_manager.send_to_user(student_id_str, payload_event)

    return SemesterPublishResponse(
        semester_id=semester_id,
        published_count=len(published_records),
        results=[PublishedResultResponse.model_validate(r) for r in published_records],
    )
