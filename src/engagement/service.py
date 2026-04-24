"""Helpers to create engagements and append timeline events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Engagement, EngagementEvent

DEFAULT_CHANNEL = "email"


async def get_or_create_engagement(
    db: AsyncSession,
    *,
    lead_id: int,
    channel: str = DEFAULT_CHANNEL,
) -> Engagement:
    result = await db.execute(
        select(Engagement).where(
            Engagement.lead_id == lead_id,
            Engagement.channel == channel,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    eng = Engagement(lead_id=lead_id, channel=channel)
    db.add(eng)
    await db.flush()
    return eng


async def append_engagement_event(
    db: AsyncSession,
    *,
    lead_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
    outreach_send_log_id: int | None = None,
    channel: str = DEFAULT_CHANNEL,
) -> EngagementEvent:
    """Append one event; ensures the engagement row exists."""
    eng = await get_or_create_engagement(db, lead_id=lead_id, channel=channel)
    eng.updated_at = datetime.now(UTC)
    event = EngagementEvent(
        engagement_id=eng.id,
        event_type=event_type,
        payload=payload,
        outreach_send_log_id=outreach_send_log_id,
    )
    db.add(event)
    await db.flush()
    return event
