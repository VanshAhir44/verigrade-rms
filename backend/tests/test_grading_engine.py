from decimal import Decimal

import pytest

from app.services.grading_service import (
    calculate_cgpa,
    calculate_sgpa,
    evaluate_subject_mark,
    summarize_semester,
)


@pytest.mark.parametrize(
    "internal,external,expected_grade,expected_gp,expected_pass",
    [
        (28, 65, "O", Decimal("10.00"), True),
        (25, 58, "A+", Decimal("9.00"), True),
        (22, 50, "A", Decimal("8.00"), True),
        (20, 42, "B+", Decimal("7.00"), True),
        (18, 35, "B", Decimal("6.00"), True),
        (15, 28, "C", Decimal("5.00"), True),
        (10, 25, "F", Decimal("0.00"), False),
    ],
)
def test_evaluate_subject_mark_grade_bands(
    internal, external, expected_grade, expected_gp, expected_pass
):
    result = evaluate_subject_mark(
        internal_marks=internal,
        external_marks=external,
        max_internal=30,
        max_external=70,
        passing_marks=40,
    )
    assert result.total == Decimal(str(internal + external)).quantize(Decimal("0.01"))
    assert result.grade == expected_grade
    assert result.grade_point == expected_gp
    assert result.passed is expected_pass


def test_evaluate_subject_mark_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="max_internal"):
        evaluate_subject_mark(
            internal_marks=31, external_marks=50, max_internal=30, max_external=70, passing_marks=40
        )

    with pytest.raises(ValueError, match="max_external"):
        evaluate_subject_mark(
            internal_marks=20, external_marks=75, max_internal=30, max_external=70, passing_marks=40
        )

    with pytest.raises(ValueError, match="negative"):
        evaluate_subject_mark(
            internal_marks=-1, external_marks=50, max_internal=30, max_external=70, passing_marks=40
        )


def test_sgpa_summary_and_cgpa_calculations():
    # (4*10 + 4*9 + 3*8 + 3*7) / 14 = (40 + 36 + 24 + 21) / 14 = 121 / 14 = 8.6428 -> 8.64
    sem1_summary = summarize_semester(
        [
            (Decimal("4"), Decimal("10"), True),
            (Decimal("4"), Decimal("9"), True),
            (Decimal("3"), Decimal("8"), True),
            (Decimal("3"), Decimal("7"), True),
        ]
    )
    assert sem1_summary.sgpa == Decimal("8.64")
    assert sem1_summary.total_credits == Decimal("14.00")
    assert sem1_summary.earned_credits == Decimal("14.00")
    assert sem1_summary.backlogs == 0
    assert sem1_summary.overall_status == "PASS"

    # Semester with a backlog
    sem_fail = summarize_semester(
        [
            (Decimal("4"), Decimal("8"), True),
            (Decimal("4"), Decimal("0"), False),
        ]
    )
    assert sem_fail.sgpa == Decimal("4.00")
    assert sem_fail.earned_credits == Decimal("4.00")
    assert sem_fail.backlogs == 1
    assert sem_fail.overall_status == "FAIL"

    # Weighted CGPA across Sem 1 (14 cr, 8.64) and Sem 2 (16 cr, 9.25)
    # (14*8.64 + 16*9.25) / 30 = (120.96 + 148.00) / 30 = 268.96 / 30 = 8.9653 -> 8.97
    cgpa = calculate_cgpa([(Decimal("14"), Decimal("8.64")), (Decimal("16"), Decimal("9.25"))])
    assert cgpa == Decimal("8.97")
    assert calculate_sgpa([]) == Decimal("0.00")
