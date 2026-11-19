from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Sequence

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class GradeRule:
    min_percentage: Decimal
    letter: str
    grade_point: Decimal


DEFAULT_GRADING_RULES: tuple[GradeRule, ...] = (
    GradeRule(Decimal("90"), "O", Decimal("10.00")),
    GradeRule(Decimal("80"), "A+", Decimal("9.00")),
    GradeRule(Decimal("70"), "A", Decimal("8.00")),
    GradeRule(Decimal("60"), "B+", Decimal("7.00")),
    GradeRule(Decimal("50"), "B", Decimal("6.00")),
    GradeRule(Decimal("40"), "C", Decimal("5.00")),
    GradeRule(Decimal("0"), "F", Decimal("0.00")),
)


@dataclass(frozen=True)
class SubjectEvaluation:
    internal_marks: Decimal
    external_marks: Decimal
    total: Decimal
    max_total: Decimal
    percentage: Decimal
    grade: str
    grade_point: Decimal
    passed: bool


@dataclass(frozen=True)
class SemesterSummary:
    sgpa: Decimal
    total_credits: Decimal
    earned_credits: Decimal
    backlogs: int
    overall_status: str  # "PASS" or "FAIL"


def _to_decimal(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def evaluate_subject_mark(
    *,
    internal_marks: float | int | str | Decimal,
    external_marks: float | int | str | Decimal,
    max_internal: float | int | str | Decimal,
    max_external: float | int | str | Decimal,
    passing_marks: float | int | str | Decimal,
    rules: Sequence[GradeRule] = DEFAULT_GRADING_RULES,
) -> SubjectEvaluation:
    internal = _to_decimal(internal_marks)
    external = _to_decimal(external_marks)
    max_int = _to_decimal(max_internal)
    max_ext = _to_decimal(max_external)
    passing = _to_decimal(passing_marks)

    if internal < Decimal("0") or external < Decimal("0"):
        raise ValueError("Marks cannot be negative")
    if internal > max_int:
        raise ValueError(f"Internal marks ({internal}) cannot exceed max_internal ({max_int})")
    if external > max_ext:
        raise ValueError(f"External marks ({external}) cannot exceed max_external ({max_ext})")

    max_total = (max_int + max_ext).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if max_total <= Decimal("0"):
        raise ValueError("Total maximum marks must be greater than zero")

    total = (internal + external).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    percentage = ((total / max_total) * Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    if total < passing:
        return SubjectEvaluation(
            internal_marks=internal,
            external_marks=external,
            total=total,
            max_total=max_total,
            percentage=percentage,
            grade="F",
            grade_point=Decimal("0.00"),
            passed=False,
        )

    matched_grade = "F"
    matched_point = Decimal("0.00")
    sorted_rules = sorted(rules, key=lambda r: r.min_percentage, reverse=True)
    for rule in sorted_rules:
        if percentage >= rule.min_percentage:
            matched_grade = rule.letter
            matched_point = rule.grade_point.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            break

    # P1-1 fix: if student met subject's configured passing_marks even below 40% of max_total,
    # assign the lowest passing grade instead of contradicting passing_marks with "F".
    if matched_grade == "F":
        passing_rules = [r for r in sorted_rules if r.letter != "F"]
        if passing_rules:
            lowest_pass = passing_rules[-1]
            matched_grade = lowest_pass.letter
            matched_point = lowest_pass.grade_point.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            matched_grade = "P"
            matched_point = Decimal("4.00")

    return SubjectEvaluation(
        internal_marks=internal,
        external_marks=external,
        total=total,
        max_total=max_total,
        percentage=percentage,
        grade=matched_grade,
        grade_point=matched_point,
        passed=True,
    )


def calculate_sgpa(
    subject_credits_and_points: Iterable[tuple[float | int | str | Decimal, float | int | str | Decimal]],
) -> Decimal:
    weighted_sum = Decimal("0")
    total_credits = Decimal("0")
    for credits_raw, gp_raw in subject_credits_and_points:
        credits = _to_decimal(credits_raw)
        gp = _to_decimal(gp_raw)
        if credits <= Decimal("0"):
            raise ValueError("Subject credits must be positive")
        weighted_sum += credits * gp
        total_credits += credits

    if total_credits == Decimal("0"):
        return Decimal("0.00")

    return (weighted_sum / total_credits).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def summarize_semester(
    subject_rows: Iterable[
        tuple[float | int | str | Decimal, float | int | str | Decimal, bool]
    ],
) -> SemesterSummary:
    """Takes iterable of (credits, grade_point, passed) tuples and returns SemesterSummary."""
    weighted_sum = Decimal("0")
    total_credits = Decimal("0")
    earned_credits = Decimal("0")
    backlogs = 0

    for credits_raw, gp_raw, passed in subject_rows:
        credits = _to_decimal(credits_raw)
        gp = _to_decimal(gp_raw)
        total_credits += credits
        weighted_sum += credits * gp
        if passed:
            earned_credits += credits
        else:
            backlogs += 1

    sgpa = (
        (weighted_sum / total_credits).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if total_credits > Decimal("0")
        else Decimal("0.00")
    )
    return SemesterSummary(
        sgpa=sgpa,
        total_credits=total_credits.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        earned_credits=earned_credits.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        backlogs=backlogs,
        overall_status="PASS" if backlogs == 0 and total_credits > Decimal("0") else "FAIL",
    )


def calculate_cgpa(
    semester_credits_and_sgpas: Iterable[
        tuple[float | int | str | Decimal, float | int | str | Decimal]
    ],
) -> Decimal:
    """Credit-weighted CGPA across multiple semesters."""
    return calculate_sgpa(semester_credits_and_sgpas)
