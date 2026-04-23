"""Settings routes — env-backed config and DB-backed outreach policy."""

from datetime import UTC, datetime

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    OutreachPolicyResponse,
    OutreachPolicyUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
    SuppressionAddRequest,
    SuppressionItem,
)
from src.app_state import scheduler
from src.config.settings import reload_settings, settings
from src.db.models import OutreachSuppression
from src.db.session import get_db
from src.outreach.guardrails import (
    OUTREACH_SETTING_DEFAULTS,
    count_sends_for_local_day,
    get_outreach_policy,
    normalize_email,
    upsert_outreach_settings,
)
from src.scorer.ai import reset_clients
from src.utils.envfile import set_env_vars

router = APIRouter(tags=["settings"])


def _parse_schedule_time(time_str: str) -> tuple[int, int]:
    hour, minute = time_str.split(":")
    return int(hour), int(minute)


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(
        gemini_api_key_set=bool(settings.gemini_api_key and settings.gemini_api_key.strip()),
        groq_api_key_set=bool(settings.groq_api_key and settings.groq_api_key.strip()),
        gemini_model=settings.gemini_model,
        groq_model=settings.groq_model,
        scrape_schedule_time=settings.scrape_schedule_time,
        scrape_location=settings.scrape_location,
        scrape_max_results=settings.scrape_max_results,
        scrape_headless=settings.scrape_headless,
        scrape_user_agent=settings.scrape_user_agent,
        outreach_send_enabled=settings.outreach_send_enabled,
        outreach_sender_name=settings.outreach_sender_name,
        outreach_sender_email=settings.outreach_sender_email,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_password_set=bool(settings.smtp_password and settings.smtp_password.strip()),
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdateRequest):
    updates: dict[str, str] = {}

    # Secrets (write only)
    if body.gemini_api_key is not None and body.gemini_api_key.strip():
        updates["GEMINI_API_KEY"] = body.gemini_api_key.strip()
    if body.groq_api_key is not None and body.groq_api_key.strip():
        updates["GROQ_API_KEY"] = body.groq_api_key.strip()

    # Models
    if body.gemini_model is not None:
        updates["GEMINI_MODEL"] = body.gemini_model.strip()
    if body.groq_model is not None:
        updates["GROQ_MODEL"] = body.groq_model.strip()

    # Scheduler
    if body.scrape_schedule_time is not None:
        updates["SCRAPE_SCHEDULE_TIME"] = body.scrape_schedule_time.strip()

    # Scraper tuning
    if body.scrape_location is not None:
        updates["SCRAPE_LOCATION"] = body.scrape_location.strip()
    if body.scrape_max_results is not None:
        updates["SCRAPE_MAX_RESULTS"] = str(body.scrape_max_results)
    if body.scrape_headless is not None:
        updates["SCRAPE_HEADLESS"] = "true" if body.scrape_headless else "false"
    if body.scrape_user_agent is not None:
        updates["SCRAPE_USER_AGENT"] = body.scrape_user_agent.strip()

    # Outreach SMTP/env settings
    if body.outreach_send_enabled is not None:
        updates["OUTREACH_SEND_ENABLED"] = "true" if body.outreach_send_enabled else "false"
    if body.outreach_sender_name is not None:
        updates["OUTREACH_SENDER_NAME"] = body.outreach_sender_name.strip()
    if body.outreach_sender_email is not None:
        updates["OUTREACH_SENDER_EMAIL"] = body.outreach_sender_email.strip()
    if body.smtp_host is not None:
        updates["SMTP_HOST"] = body.smtp_host.strip()
    if body.smtp_port is not None:
        updates["SMTP_PORT"] = str(body.smtp_port)
    if body.smtp_username is not None:
        updates["SMTP_USERNAME"] = body.smtp_username.strip()
    if body.smtp_password is not None and body.smtp_password.strip():
        updates["SMTP_PASSWORD"] = body.smtp_password.strip()
    if body.smtp_use_tls is not None:
        updates["SMTP_USE_TLS"] = "true" if body.smtp_use_tls else "false"

    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update.")

    # 1) Persist to .env
    set_env_vars(".env", updates)

    # 2) Reload settings object in-place
    reload_settings()

    # 3) Apply runtime side effects
    reset_clients()

    # Reschedule daily job if the scheduler is running and job exists.
    try:
        job = scheduler.get_job("daily_scrape")
        if job is not None:
            hour, minute = _parse_schedule_time(settings.scrape_schedule_time)
            scheduler.reschedule_job("daily_scrape", trigger=CronTrigger(hour=hour, minute=minute))
    except Exception as e:
        # Don't fail the request for a reschedule hiccup; settings were persisted.
        raise HTTPException(status_code=500, detail=f"Settings saved, but reschedule failed: {e}")

    return await get_settings()


@router.get("/settings/outreach-policy", response_model=OutreachPolicyResponse)
async def get_outreach_policy_endpoint(db: AsyncSession = Depends(get_db)):
    policy = await get_outreach_policy(db)
    return OutreachPolicyResponse(
        outreach_enabled=policy.enabled,
        outreach_daily_send_cap=policy.daily_send_cap,
        outreach_send_window_start=policy.send_window_start,
        outreach_send_window_end=policy.send_window_end,
        outreach_send_timezone=policy.send_timezone,
        outreach_enforce_window=policy.enforce_window,
        outreach_enforce_daily_cap=policy.enforce_daily_cap,
        outreach_enforce_suppression=policy.enforce_suppression,
        outreach_allowed_statuses=policy.allowed_statuses,
    )


@router.patch("/settings/outreach-policy", response_model=OutreachPolicyResponse)
async def update_outreach_policy_endpoint(
    body: OutreachPolicyUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    updates: dict[str, str] = {}
    if body.outreach_enabled is not None:
        updates["outreach_enabled"] = "true" if body.outreach_enabled else "false"
    if body.outreach_daily_send_cap is not None:
        if body.outreach_daily_send_cap < 1:
            raise HTTPException(status_code=400, detail="outreach_daily_send_cap must be >= 1")
        updates["outreach_daily_send_cap"] = str(body.outreach_daily_send_cap)
    if body.outreach_send_window_start is not None:
        updates["outreach_send_window_start"] = body.outreach_send_window_start.strip()
    if body.outreach_send_window_end is not None:
        updates["outreach_send_window_end"] = body.outreach_send_window_end.strip()
    if body.outreach_send_timezone is not None:
        updates["outreach_send_timezone"] = body.outreach_send_timezone.strip()
    if body.outreach_enforce_window is not None:
        updates["outreach_enforce_window"] = "true" if body.outreach_enforce_window else "false"
    if body.outreach_enforce_daily_cap is not None:
        updates["outreach_enforce_daily_cap"] = (
            "true" if body.outreach_enforce_daily_cap else "false"
        )
    if body.outreach_enforce_suppression is not None:
        updates["outreach_enforce_suppression"] = (
            "true" if body.outreach_enforce_suppression else "false"
        )
    if body.outreach_allowed_statuses is not None:
        updates["outreach_allowed_statuses"] = ",".join(body.outreach_allowed_statuses)

    if not updates:
        raise HTTPException(status_code=400, detail="No outreach policy fields provided.")

    # Restrict to known keys so typos do not pollute app_settings.
    invalid = [k for k in updates if k not in OUTREACH_SETTING_DEFAULTS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid outreach setting keys: {invalid}")

    await upsert_outreach_settings(db, updates)
    return await get_outreach_policy_endpoint(db=db)


@router.get("/settings/outreach-policy/usage-today")
async def get_outreach_usage_today(db: AsyncSession = Depends(get_db)):
    policy = await get_outreach_policy(db)
    sent_today = await count_sends_for_local_day(db=db, timezone=policy.send_timezone)
    return {
        "timezone": policy.send_timezone,
        "sent_today": sent_today,
        "daily_cap": policy.daily_send_cap,
    }


@router.get("/settings/outreach-suppressions", response_model=list[SuppressionItem])
async def list_suppressions(
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OutreachSuppression).order_by(OutreachSuppression.created_at.desc())
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(OutreachSuppression.email.ilike(pattern))
    result = await db.execute(stmt)
    return [SuppressionItem.model_validate(row) for row in result.scalars().all()]


@router.post("/settings/outreach-suppressions", response_model=SuppressionItem)
async def add_suppression(body: SuppressionAddRequest, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email.")

    existing = await db.execute(
        select(OutreachSuppression).where(OutreachSuppression.email == email)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.reason = body.reason.strip() if body.reason else row.reason
        await db.commit()
        await db.refresh(row)
        return SuppressionItem.model_validate(row)

    row = OutreachSuppression(email=email, reason=body.reason.strip() if body.reason else None)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return SuppressionItem.model_validate(row)


@router.delete("/settings/outreach-suppressions/{suppression_id}")
async def delete_suppression(suppression_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OutreachSuppression).where(OutreachSuppression.id == suppression_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Suppression not found.")
    await db.delete(row)
    await db.commit()
    return {"ok": True, "deleted_at": datetime.now(UTC).isoformat()}
