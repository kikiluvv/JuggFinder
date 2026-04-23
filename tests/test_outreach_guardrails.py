from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base, OutreachSendLog
from src.outreach.guardrails import (
    count_sends_for_local_day,
    get_outreach_policy,
    normalize_email,
    upsert_outreach_settings,
    within_send_window,
)


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
async def test_policy_defaults_from_empty_settings_table(db: AsyncSession):
    policy = await get_outreach_policy(db)
    assert policy.enabled is False
    assert policy.daily_send_cap > 0
    assert policy.send_window_start == "09:00"
    assert policy.send_window_end == "17:00"
    assert policy.send_timezone == "America/Boise"
    assert "interested" in policy.allowed_statuses


@pytest.mark.asyncio
async def test_policy_overrides_from_settings_table(db: AsyncSession):
    await upsert_outreach_settings(
        db,
        {
            "outreach_enabled": "true",
            "outreach_daily_send_cap": "7",
            "outreach_send_window_start": "08:30",
            "outreach_send_window_end": "19:15",
            "outreach_send_timezone": "America/New_York",
            "outreach_enforce_window": "false",
            "outreach_enforce_daily_cap": "false",
            "outreach_enforce_suppression": "false",
            "outreach_allowed_statuses": "interested",
        },
    )
    policy = await get_outreach_policy(db)
    assert policy.enabled is True
    assert policy.daily_send_cap == 7
    assert policy.send_window_start == "08:30"
    assert policy.send_window_end == "19:15"
    assert policy.send_timezone == "America/New_York"
    assert policy.enforce_window is False
    assert policy.enforce_daily_cap is False
    assert policy.enforce_suppression is False
    assert policy.allowed_statuses == ["interested"]


def test_within_send_window_same_day():
    # 14:00 UTC is 08:00 in America/Boise (MDT).
    now = datetime(2026, 4, 23, 14, 0, tzinfo=UTC)
    assert within_send_window(
        now_utc=now,
        timezone="America/Boise",
        start_hhmm="07:00",
        end_hhmm="09:00",
    )
    assert not within_send_window(
        now_utc=now,
        timezone="America/Boise",
        start_hhmm="09:01",
        end_hhmm="18:00",
    )


def test_within_send_window_overnight():
    now = datetime(2026, 4, 23, 7, 30, tzinfo=UTC)  # 01:30 America/Boise
    assert within_send_window(
        now_utc=now,
        timezone="America/Boise",
        start_hhmm="22:00",
        end_hhmm="02:00",
    )


@pytest.mark.asyncio
async def test_count_sends_for_local_day(db: AsyncSession):
    db.add_all(
        [
            OutreachSendLog(
                to_email="a@example.com",
                subject="s1",
                body="b1",
                status="sent",
                sent_at=datetime(2026, 4, 23, 15, 0, tzinfo=UTC),
            ),
            OutreachSendLog(
                to_email="b@example.com",
                subject="s2",
                body="b2",
                status="sent",
                sent_at=datetime(2026, 4, 23, 21, 0, tzinfo=UTC),
            ),
            OutreachSendLog(
                to_email="c@example.com",
                subject="s3",
                body="b3",
                status="failed",
                sent_at=datetime(2026, 4, 23, 18, 0, tzinfo=UTC),
            ),
        ]
    )
    await db.commit()

    now = datetime(2026, 4, 23, 22, 0, tzinfo=UTC)
    count = await count_sends_for_local_day(db=db, timezone="America/Boise", now_utc=now)
    assert count == 2


def test_normalize_email():
    assert normalize_email("  Foo.Bar@Example.COM ") == "foo.bar@example.com"
