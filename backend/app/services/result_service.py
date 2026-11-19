from decimal import Decimal
from functools import lru_cache
from typing import Any, Sequence

from app.models.academic import Semester, Subject
from app.models.result import Mark
from app.models.user import User
from app.services.blockchain_service import BlockchainService


def _fmt2(value: Any) -> str:
    return f"{Decimal(str(value)):.2f}"


def build_canonical_result_payload(
    *,
    result_id: str,
    student: User,
    semester: Semester,
    sgpa: Decimal,
    cgpa: Decimal,
    marks_with_subjects: Sequence[tuple[Mark, Subject]],
) -> dict[str, Any]:
    """Builds the deterministic canonical dictionary hashed before on-chain anchoring and verification."""
    subject_entries = sorted(
        [
            {
                "subject_code": subject.code,
                "credits": _fmt2(subject.credits),
                "internal_marks": _fmt2(mark.internal_marks),
                "external_marks": _fmt2(mark.external_marks),
                "total": _fmt2(mark.total),
                "grade": mark.grade or "F",
                "grade_point": _fmt2(mark.grade_point if mark.grade_point is not None else 0),
            }
            for mark, subject in marks_with_subjects
        ],
        key=lambda item: item["subject_code"],
    )

    return {
        "result_id": result_id,
        "student_id": str(student.id),
        "enrollment_no": student.enrollment_no or "",
        "semester_id": str(semester.id),
        "semester_number": semester.number,
        "academic_year": semester.academic_year,
        "sgpa": _fmt2(sgpa),
        "cgpa": _fmt2(cgpa),
        "subjects": subject_entries,
    }


@lru_cache(maxsize=1)
def _cached_blockchain_service() -> BlockchainService:
    return BlockchainService()


def get_blockchain_service() -> BlockchainService:
    """FastAPI dependency returning a cached BlockchainService instance."""
    return _cached_blockchain_service()
