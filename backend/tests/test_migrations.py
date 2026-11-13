"""La migrazione iniziale produce lo stesso schema dei modelli SQLAlchemy."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.core.config import BACKEND_DIR, get_settings
from app.db.base import Base
from sqlalchemy import create_engine


def test_migration_matches_models(tmp_path: Path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 'migr.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(config, "head")
        engine = create_engine(url)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": False})
            diff = compare_metadata(context, Base.metadata)
        assert diff == [], diff
        command.downgrade(config, "base")
    finally:
        get_settings.cache_clear()
