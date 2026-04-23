"""
Async SQLAlchemy engine + session factory.

Also exposes a lightweight additive-column bootstrap (`ensure_schema`) so
new columns can be added to existing `leads.db` files without losing data.
This intentionally replaces a full Alembic migration pipeline for now —
JuggFinder runs locally with a single SQLite file, and the only schema
changes we make are *additive*. If we ever need column renames, drops, or
complex constraints, swap this for Alembic.
"""

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings
from src.db.models import Base, Lead
from src.utils.logging import get_logger

logger = get_logger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Additive-column migrations
# ---------------------------------------------------------------------------

# Maps column name → SQLite column-definition fragment. Every entry here is
# a new column added since the original schema shipped; all must be nullable
# or have a default so existing rows remain valid.
_ADDITIVE_COLUMNS: dict[str, str] = {
    "email": "TEXT",
    "hours": "TEXT",
    "google_categories": "TEXT NOT NULL DEFAULT '[]'",
    "business_description": "TEXT",
    "photo_count": "INTEGER",
    "is_claimed": "BOOLEAN",
    "tech_stack": "TEXT NOT NULL DEFAULT '[]'",
    "opportunity_score": "REAL",
    "outreach_draft": "TEXT",
    "outreach_sent_at": "DATETIME",
    "outreach_last_error": "TEXT",
    "last_scanned_at": "DATETIME",
}


async def ensure_schema() -> None:
    """
    Create the `leads` table if missing, then add any columns listed in
    `_ADDITIVE_COLUMNS` that aren't already present. Safe to call on every
    startup — all operations are idempotent.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _columns(sync_conn) -> set[str]:
            return {c["name"] for c in inspect(sync_conn).get_columns(Lead.__tablename__)}

        existing_cols = await conn.run_sync(_columns)

        added: list[str] = []
        for col_name, col_def in _ADDITIVE_COLUMNS.items():
            if col_name not in existing_cols:
                await conn.execute(
                    text(f"ALTER TABLE {Lead.__tablename__} ADD COLUMN {col_name} {col_def}")
                )
                added.append(col_name)

        if added:
            logger.info(f"Schema updated — added columns: {', '.join(added)}")
        else:
            logger.debug("Schema up to date — no column additions needed.")
