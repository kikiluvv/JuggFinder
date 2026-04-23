"""
Outreach Phase B guardrails.

DB-backed settings control:
  - send enable/disable
  - daily send cap
  - allowed send time window
  - send timezone
  - suppression enforcement
  - allowed lead statuses
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.models import AppSetting, OutreachSendLog, OutreachSuppression

OUTREACH_SETTING_DEFAULTS: dict[str, str] = {
    "outreach_enabled": "false",
    "outreach_daily_send_cap": "25",
    "outreach_send_window_start": "09:00",
    "outreach_send_window_end": "17:00",
    "outreach_send_timezone": "America/Boise",
    "outreach_enforce_window": "true",
    "outreach_enforce_daily_cap": "true",
    "outreach_enforce_suppression": "true",
    "outreach_allowed_statuses": "interested,reviewed,new",
}


@dataclass
class OutreachPolicy:
    enabled: bool
    daily_send_cap: int
    send_window_start: str
    send_window_end: str
    send_timezone: str
    enforce_window: bool
    enforce_daily_cap: bool
    enforce_suppression: bool
    allowed_statuses: list[str]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


def parse_positive_int(value: str, default: int) -> int:
    try:
        n = int((value or "").strip())
        return n if n > 0 else default
    except Exception:
        return default


def parse_hhmm(value: str, default: str) -> str:
    raw = (value or "").strip()
    if len(raw) != 5 or ":" not in raw:
        return default
    h, m = raw.split(":", 1)
    if not (h.isdigit() and m.isdigit()):
        return default
    hour = int(h)
    minute = int(m)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return default


def parse_statuses(value: str, default_csv: str) -> list[str]:
    raw = (value or "").strip() or default_csv
    statuses = [s.strip() for s in raw.split(",") if s.strip()]
    valid = {"new", "reviewed", "interested", "archived"}
    filtered = [s for s in statuses if s in valid]
    return filtered or [s.strip() for s in default_csv.split(",") if s.strip()]


def _window_contains(now_t: time, start_t: time, end_t: time) -> bool:
    # Same-day window (e.g., 09:00-17:00)
    if start_t <= end_t:
        return start_t <= now_t <= end_t
    # Overnight window (e.g., 22:00-06:00)
    return now_t >= start_t or now_t <= end_t


def within_send_window(
    *,
    now_utc: datetime,
    timezone: str,
    start_hhmm: str,
    end_hhmm: str,
) -> bool:
    tz = ZoneInfo(timezone)
    local_now = now_utc.astimezone(tz)
    sh, sm = [int(x) for x in start_hhmm.split(":")]
    eh, em = [int(x) for x in end_hhmm.split(":")]
    return _window_contains(local_now.time(), time(sh, sm), time(eh, em))


async def _get_settings_map(db: AsyncSession) -> dict[str, str]:
    keys = list(OUTREACH_SETTING_DEFAULTS.keys())
    result = await db.execute(select(AppSetting).where(AppSetting.key.in_(keys)))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


async def get_outreach_policy(db: AsyncSession) -> OutreachPolicy:
    stored = await _get_settings_map(db)
    merged = {k: stored.get(k, v) for k, v in OUTREACH_SETTING_DEFAULTS.items()}

    timezone_raw = (merged["outreach_send_timezone"] or "").strip()
    try:
        ZoneInfo(timezone_raw)
        timezone = timezone_raw
    except Exception:
        timezone = OUTREACH_SETTING_DEFAULTS["outreach_send_timezone"]

    return OutreachPolicy(
        enabled=parse_bool(merged["outreach_enabled"], settings.outreach_send_enabled),
        daily_send_cap=parse_positive_int(
            merged["outreach_daily_send_cap"],
            25,
        ),
        send_window_start=parse_hhmm(
            merged["outreach_send_window_start"],
            OUTREACH_SETTING_DEFAULTS["outreach_send_window_start"],
        ),
        send_window_end=parse_hhmm(
            merged["outreach_send_window_end"],
            OUTREACH_SETTING_DEFAULTS["outreach_send_window_end"],
        ),
        send_timezone=timezone,
        enforce_window=parse_bool(merged["outreach_enforce_window"], True),
        enforce_daily_cap=parse_bool(merged["outreach_enforce_daily_cap"], True),
        enforce_suppression=parse_bool(merged["outreach_enforce_suppression"], True),
        allowed_statuses=parse_statuses(
            merged["outreach_allowed_statuses"],
            OUTREACH_SETTING_DEFAULTS["outreach_allowed_statuses"],
        ),
    )


async def upsert_outreach_settings(db: AsyncSession, updates: dict[str, str]) -> None:
    if not updates:
        return
    result = await db.execute(select(AppSetting).where(AppSetting.key.in_(list(updates.keys()))))
    existing = {r.key: r for r in result.scalars().all()}
    for key, value in updates.items():
        if key in existing:
            existing[key].value = value
        else:
            db.add(AppSetting(key=key, value=value))
    await db.commit()


async def is_suppressed(db: AsyncSession, email: str) -> bool:
    norm = normalize_email(email)
    result = await db.execute(select(OutreachSuppression).where(OutreachSuppression.email == norm))
    return result.scalar_one_or_none() is not None


async def count_sends_for_local_day(
    *,
    db: AsyncSession,
    timezone: str,
    now_utc: datetime | None = None,
) -> int:
    now = now_utc or datetime.now(UTC)
    tz = ZoneInfo(timezone)
    target_day = now.astimezone(tz).date()

    result = await db.execute(
        select(OutreachSendLog.sent_at).where(
            OutreachSendLog.status == "sent",
            OutreachSendLog.sent_at.isnot(None),
        )
    )
    rows = result.all()
    count = 0
    for (sent_at,) in rows:
        if sent_at is None:
            continue
        value = sent_at.replace(tzinfo=UTC) if sent_at.tzinfo is None else sent_at
        if value.astimezone(tz).date() == target_day:
            count += 1
    return count
