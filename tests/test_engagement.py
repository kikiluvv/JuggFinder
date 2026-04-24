"""Engagement thread + timeline (Phase 17.1)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base, Engagement, EngagementEvent, Lead
from src.engagement.service import append_engagement_event, get_or_create_engagement


@pytest.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_or_create_engagement_idempotent(db: AsyncSession):
    db.add(Lead(name="Test", lead_score=5))
    await db.commit()
    res = await db.execute(select(Lead))
    lead = res.scalar_one()

    a = await get_or_create_engagement(db, lead_id=lead.id)
    await db.commit()
    b = await get_or_create_engagement(db, lead_id=lead.id)
    assert a.id == b.id

    cnt = await db.execute(select(Engagement))
    assert len(cnt.scalars().all()) == 1


@pytest.mark.asyncio
async def test_append_engagement_event_creates_row(db: AsyncSession):
    db.add(Lead(name="Biz", lead_score=8))
    await db.commit()
    res = await db.execute(select(Lead))
    lead = res.scalar_one()

    ev = await append_engagement_event(
        db,
        lead_id=lead.id,
        event_type="outreach_sent",
        payload={"subject": "Hello", "to_email": "a@b.co"},
        outreach_send_log_id=42,
    )
    await db.commit()

    assert ev.id > 0
    assert ev.event_type == "outreach_sent"
    assert ev.payload["subject"] == "Hello"
    assert ev.outreach_send_log_id == 42

    eng_rows = (await db.execute(select(Engagement))).scalars().all()
    assert len(eng_rows) == 1
    ev_rows = (await db.execute(select(EngagementEvent))).scalars().all()
    assert len(ev_rows) == 1
