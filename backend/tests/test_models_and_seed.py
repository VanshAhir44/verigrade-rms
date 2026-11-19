import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.seed import seed_database
from app.models.academic import Course, Department, Enrollment, Semester, Subject
from app.models.user import User, UserRole
from tests.conftest import (
    TEST_ADMIN_PW,
    TEST_FACULTY_PW,
    TEST_STUDENT1_PW,
    TEST_STUDENT2_PW,
)


@pytest.mark.asyncio
async def test_seed_creates_expected_entities_and_is_idempotent(db_session: AsyncSession):
    first = await seed_database(
        db_session,
        admin_password=TEST_ADMIN_PW,
        faculty_password=TEST_FACULTY_PW,
        student1_password=TEST_STUDENT1_PW,
        student2_password=TEST_STUDENT2_PW,
    )
    # Run seed a second time to verify idempotency
    second = await seed_database(
        db_session,
        admin_password=TEST_ADMIN_PW,
        faculty_password=TEST_FACULTY_PW,
        student1_password=TEST_STUDENT1_PW,
        student2_password=TEST_STUDENT2_PW,
    )

    assert first.admin_email == second.admin_email
    assert len(second.subject_codes) == 4

    user_count = (await db_session.execute(select(func.count(User.id)))).scalar_one()
    dept_count = (await db_session.execute(select(func.count(Department.id)))).scalar_one()
    course_count = (await db_session.execute(select(func.count(Course.id)))).scalar_one()
    sem_count = (await db_session.execute(select(func.count(Semester.id)))).scalar_one()
    sub_count = (await db_session.execute(select(func.count(Subject.id)))).scalar_one()
    enr_count = (await db_session.execute(select(func.count(Enrollment.id)))).scalar_one()

    assert user_count == 4  # 1 admin + 1 faculty + 2 students
    assert dept_count == 1
    assert course_count == 1
    assert sem_count == 1
    assert sub_count == 4
    assert enr_count == 2


@pytest.mark.asyncio
async def test_unique_email_and_enrollment_constraints(seeded_db: AsyncSession):
    duplicate_email = User(
        email="admin@university.edu",
        password_hash=hash_password("SomeStrongPass1!"),
        full_name="Duplicate Admin",
        role=UserRole.ADMIN,
    )
    seeded_db.add(duplicate_email)
    with pytest.raises(IntegrityError):
        await seeded_db.commit()
    await seeded_db.rollback()

    duplicate_enrollment = User(
        email="student3@university.edu",
        password_hash=hash_password("SomeStrongPass1!"),
        full_name="Duplicate Enrollment Student",
        role=UserRole.STUDENT,
        enrollment_no="ENR2026CS001",
    )
    seeded_db.add(duplicate_enrollment)
    with pytest.raises(IntegrityError):
        await seeded_db.commit()
    await seeded_db.rollback()
