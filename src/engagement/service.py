"""Helpers to create engagements and append timeline events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Engagement, EngagementEvent
from src.outreach.guardrails import normalize_email

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


async def record_inbound_received(
    db: AsyncSession,
    *,
    lead_id: int,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    message_id: str | None = None,
    channel: str = DEFAULT_CHANNEL,
) -> EngagementEvent:
    """Persist a manual or webhook-captured inbound message on the timeline."""
    body_stored = (body or "")[:16000]
    payload: dict[str, str | None] = {
        "from_email": normalize_email(from_email),
        "to_email": normalize_email(to_email),
        "subject": subject.strip(),
        "body": body_stored,
    }
    if message_id:
        payload["message_id"] = message_id.strip()
    return await append_engagement_event(
        db,
        lead_id=lead_id,
        event_type="inbound_received",
        payload=payload,
        channel=channel,
    )
