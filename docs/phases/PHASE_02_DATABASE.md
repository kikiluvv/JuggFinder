# Phase 02 — Database Layer

## Goal
Define the SQLAlchemy ORM model and async session setup so all subsequent phases have a typed, reusable data layer.

## Completion Criteria
- [ ] `Lead` model in `src/db/models.py` matches the schema in `INTEGRATION.md` exactly
- [ ] Async engine + `SessionLocal` factory in `src/db/session.py`
- [ ] `leads.db` is created automatically on first `create_all()` call
- [ ] `ai_issues` stored as a JSON string; deserialized to a list on read
- [ ] All field names and types match the reference SQL schema

---

## `src/db/models.py`

Define one table: `leads`. Every field from the reference schema must be present.

Key details:
- `place_id` — `TEXT UNIQUE` (nullable, since some listings may lack it)
- `ai_issues` — stored as `TEXT` (JSON-encoded list); use a SQLAlchemy `TypeDecorator` or serialize/deserialize at the service layer
- `status` — `TEXT`, default `"new"`, constrained to `["new", "reviewed", "interested", "archived"]`
- `created_at` / `updated_at` — `DATETIME`, use `server_default=func.now()` and `onupdate=func.now()`

---

## `src/db/session.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config.settings import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session
```

---

## `src/main.py` — `create_all` on startup

Call `Base.metadata.create_all(engine)` inside the FastAPI `lifespan` context manager (before the scheduler starts). This is the only migration mechanism — no Alembic needed.

---

## Done When
Running `uv run python -c "import asyncio; from src.db.session import engine; from src.db.models import Base; asyncio.run(Base.metadata.create_all(engine))"` creates `leads.db` with the correct schema (verify with `sqlite3 leads.db .schema`).
