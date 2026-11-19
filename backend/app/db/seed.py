import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.academic import Course, Department, Enrollment, Semester, Subject
from app.models.user import User, UserRole


@dataclass
class SeedSummary:
    admin_email: str
    faculty_email: str
    student_emails: list[str]
    department_code: str
    course_code: str
    semester_number: int
    subject_codes: list[str]


async def _get_or_create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
    enrollment_no: str | None = None,
) -> User:
    normalized = email.strip().lower()
    res = await db.execute(select(User).where(User.email == normalized))
    user = res.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        enrollment_no=enrollment_no,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_database(
    db: AsyncSession,
    *,
    admin_password: str | None = None,
    faculty_password: str | None = None,
    student1_password: str | None = None,
    student2_password: str | None = None,
) -> SeedSummary:
    """Idempotently seed initial roles, academic hierarchy, subjects, and enrollments."""
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@university.edu")
    faculty_email = os.getenv("SEED_FACULTY_EMAIL", "faculty@university.edu")
    student1_email = os.getenv("SEED_STUDENT1_EMAIL", "student1@university.edu")
    student2_email = os.getenv("SEED_STUDENT2_EMAIL", "student2@university.edu")

    resolved_admin_pw = admin_password or os.getenv("SEED_ADMIN_PASSWORD")
    resolved_faculty_pw = faculty_password or os.getenv("SEED_FACULTY_PASSWORD")
    resolved_student1_pw = student1_password or os.getenv("SEED_STUDENT1_PASSWORD")
    resolved_student2_pw = student2_password or os.getenv("SEED_STUDENT2_PASSWORD")

    if not all([resolved_admin_pw, resolved_faculty_pw, resolved_student1_pw, resolved_student2_pw]):
        raise RuntimeError(
            "Seed account passwords must be provided via environment variables "
            "(SEED_ADMIN_PASSWORD, SEED_FACULTY_PASSWORD, SEED_STUDENT1_PASSWORD, SEED_STUDENT2_PASSWORD)."
        )

    await _get_or_create_user(
        db,
        email=admin_email,
        password=resolved_admin_pw,
        full_name="Controller of Examinations",
        role=UserRole.ADMIN,
    )
    faculty = await _get_or_create_user(
        db,
        email=faculty_email,
        password=resolved_faculty_pw,
        full_name="Dr. Meera Patel",
        role=UserRole.FACULTY,
    )
    student1 = await _get_or_create_user(
        db,
        email=student1_email,
        password=resolved_student1_pw,
        full_name="Aarav Shah",
        role=UserRole.STUDENT,
        enrollment_no="ENR2026CS001",
    )
    student2 = await _get_or_create_user(
        db,
        email=student2_email,
        password=resolved_student2_pw,
        full_name="Diya Desai",
        role=UserRole.STUDENT,
        enrollment_no="ENR2026CS002",
    )

    dept_res = await db.execute(select(Department).where(Department.code == "CSE"))
    department = dept_res.scalar_one_or_none()
    if department is None:
        department = Department(code="CSE", name="Computer Science & Engineering")
        db.add(department)
        await db.flush()

    course_res = await db.execute(select(Course).where(Course.code == "BTCS"))
    course = course_res.scalar_one_or_none()
    if course is None:
        course = Course(
            department_id=department.id,
            code="BTCS",
            name="B.Tech Computer Science",
            duration_semesters=8,
        )
        db.add(course)
        await db.flush()

    sem_res = await db.execute(
        select(Semester).where(
            Semester.course_id == course.id,
            Semester.number == 1,
            Semester.academic_year == "2026-2027",
        )
    )
    semester = sem_res.scalar_one_or_none()
    if semester is None:
        semester = Semester(
            course_id=course.id,
            number=1,
            academic_year="2026-2027",
            is_active=True,
        )
        db.add(semester)
        await db.flush()

    sample_subjects = [
        ("CS101", "Data Structures & Algorithms", 4.0, 30.0, 70.0, 40.0),
        ("CS102", "Database Management Systems", 4.0, 30.0, 70.0, 40.0),
        ("CS103", "Computer Networks", 3.0, 30.0, 70.0, 40.0),
        ("CS104", "Applied Cryptography & Security", 3.0, 30.0, 70.0, 40.0),
    ]
    subject_codes: list[str] = []
    for code, name, credits, max_int, max_ext, passing in sample_subjects:
        sub_res = await db.execute(select(Subject).where(Subject.code == code))
        subject = sub_res.scalar_one_or_none()
        if subject is None:
            subject = Subject(
                semester_id=semester.id,
                faculty_id=faculty.id,
                code=code,
                name=name,
                credits=credits,
                max_internal=max_int,
                max_external=max_ext,
                passing_marks=passing,
            )
            db.add(subject)
        subject_codes.append(code)

    for student in (student1, student2):
        enr_res = await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.semester_id == semester.id,
            )
        )
        if enr_res.scalar_one_or_none() is None:
            db.add(
                Enrollment(
                    student_id=student.id,
                    semester_id=semester.id,
                    course_id=course.id,
                )
            )

    await db.commit()
    return SeedSummary(
        admin_email=admin_email,
        faculty_email=faculty_email,
        student_emails=[student1_email, student2_email],
        department_code=department.code,
        course_code=course.code,
        semester_number=semester.number,
        subject_codes=subject_codes,
    )


async def _cli_main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        summary = await seed_database(session)
        print(f"Seeded successfully: {summary}")


if __name__ == "__main__":
    asyncio.run(_cli_main())
