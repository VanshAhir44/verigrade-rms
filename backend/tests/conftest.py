import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Configure deterministic test signing key before importing app settings
os.environ.setdefault("JWT_SIGNING_KEY", "test-signing-key-for-pytest-suite-only-32chars")

from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed_database
from app.db.session import get_db
from app.main import create_app

# Ensure settings reflects the test signing key
settings.JWT_SIGNING_KEY = os.environ["JWT_SIGNING_KEY"]

TEST_ADMIN_PW = "AdminTest@2026!"
TEST_FACULTY_PW = "FacultyTest@2026!"
TEST_STUDENT1_PW = "Student1Test@2026!"
TEST_STUDENT2_PW = "Student2Test@2026!"


@pytest_asyncio.fixture
async def db_session(tmp_path) -> AsyncGenerator[AsyncSession, None]:
    db_file = tmp_path / "test_rms.sqlite3"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(db_url, echo=False)

    # Enable foreign key constraint enforcement on SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    await seed_database(
        db_session,
        admin_password=TEST_ADMIN_PW,
        faculty_password=TEST_FACULTY_PW,
        student1_password=TEST_STUDENT1_PW,
        student2_password=TEST_STUDENT2_PW,
    )
    return db_session


@pytest_asyncio.fixture
async def client(seeded_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield seeded_db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
