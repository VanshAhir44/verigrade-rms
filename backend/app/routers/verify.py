import asyncio
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import enforce_verify_rate_limit
from app.db.session import get_db
from app.models.academic import Course, Department, Semester, Subject
from app.models.result import Mark, PublishedResult
from app.models.user import User
from app.schemas.academic import PublicVerificationResponse, StudentSubjectResult
from app.services.blockchain_service import BlockchainService, compute_result_hash
from app.services.result_service import build_canonical_result_payload, get_blockchain_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verify", tags=["Public Verification (No Auth)"])


@router.get(
    "/{result_id}",
    response_model=PublicVerificationResponse,
    dependencies=[Depends(enforce_verify_rate_limit)],
)
async def verify_published_result(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    blockchain: BlockchainService = Depends(get_blockchain_service),
) -> PublicVerificationResponse:
    """Recomputes SHA-256 hash from DB records and verifies it directly against ResultRegistry.sol."""
    published = (
        await db.execute(select(PublishedResult).where(PublishedResult.id == result_id))
    ).scalar_one_or_none()
    if published is None:
        raise HTTPException(status_code=404, detail="Result record not found")

    student = (
        await db.execute(select(User).where(User.id == published.student_id))
    ).scalar_one()
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
    marks_with_subjects = [(m, subjects_map[m.subject_id]) for m in marks if m.subject_id in subjects_map]

    # Live recomputation of canonical SHA-256 hash from current DB state
    canonical_payload = build_canonical_result_payload(
        result_id=str(published.id),
        student=student,
        semester=semester,
        sgpa=Decimal(str(published.sgpa)),
        cgpa=Decimal(str(published.cgpa)),
        marks_with_subjects=marks_with_subjects,
    )
    recomputed_hash = compute_result_hash(canonical_payload)

    # Non-blocking smart contract verification against ResultRegistry.sol (P1-10 fix)
    try:
        on_chain = await asyncio.to_thread(
            blockchain.verify_result_hash, str(published.id), recomputed_hash
        )
    except Exception:
        logger.exception("Blockchain RPC error during public verification for %s", result_id)
        raise HTTPException(
            status_code=503,
            detail="Blockchain verification service is temporarily unavailable. Please retry shortly.",
        )

    subject_rows = [
        StudentSubjectResult(
            subject_code=sub.code,
            subject_name=sub.name,
            credits=Decimal(str(sub.credits)),
            internal_marks=Decimal(str(m.internal_marks)),
            external_marks=Decimal(str(m.external_marks)),
            total=Decimal(str(m.total)),
            max_total=Decimal(str(sub.max_internal)) + Decimal(str(sub.max_external)),
            grade=m.grade,
            grade_point=Decimal(str(m.grade_point)) if m.grade_point is not None else None,
            status=m.status,
        )
        for m, sub in sorted(marks_with_subjects, key=lambda pair: pair[1].code)
    ]

    is_verified = bool(on_chain.is_valid and on_chain.exists)
    return PublicVerificationResponse(
        result_id=published.id,
        verification_status="VERIFIED ON-CHAIN" if is_verified else "TAMPERED / INVALID",
        is_valid=is_verified,
        student_name=student.full_name,
        enrollment_no=student.enrollment_no,
        course_name=course.name,
        department_name=department.name,
        semester_number=semester.number,
        academic_year=semester.academic_year,
        sgpa=Decimal(str(published.sgpa)),
        cgpa=Decimal(str(published.cgpa)),
        recomputed_hash_sha256=recomputed_hash,
        on_chain_hash_sha256=on_chain.stored_hash_sha256,
        blockchain_tx_hash=published.blockchain_tx_hash,
        block_number=on_chain.block_number or published.block_number,
        on_chain_timestamp=on_chain.timestamp,
        published_at=published.published_at,
        subjects=subject_rows,
    )
