from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_and_downgrade_cycle(tmp_path: Path):
    backend_dir = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "alembic_test.sqlite3"
    async_url = f"sqlite+aiosqlite:///{db_file}"
    sync_url = f"sqlite:///{db_file}"

    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", async_url)
    alembic_cfg.attributes["configure_logger"] = False

    # Pass database_url via -x argument equivalent so env.py picks it up
    alembic_cfg.cmd_opts = type("Opts", (), {"x": [f"database_url={async_url}"]})()

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(sync_url)
    tables = set(inspect(engine).get_table_names())
    expected_tables = {
        "users",
        "refresh_tokens",
        "departments",
        "courses",
        "semesters",
        "subjects",
        "enrollments",
        "marks",
        "published_results",
        "audit_logs",
        "alembic_version",
    }
    assert expected_tables.issubset(tables)

    # 2. Downgrade back to base
    command.downgrade(alembic_cfg, "base")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert "users" not in tables_after_downgrade
    assert "published_results" not in tables_after_downgrade

    # 3. Re-upgrade to head to confirm clean repeatability
    command.upgrade(alembic_cfg, "head")
    tables_reupgraded = set(inspect(engine).get_table_names())
    assert expected_tables.issubset(tables_reupgraded)
    engine.dispose()
