"""Lead CRUD routes — list, stats, detail, update, delete, export, rescan, draft."""

import csv
import io
import math
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    EngagementEventItem,
    EngagementTimelineResponse,
    LeadDetail,
    LeadsResponse,
    LeadSummary,
    LeadUpdate,
    OutreachDraftResponse,
    OutreachSendRequest,
    OutreachSendResponse,
    StatsResponse,
)
from src.db.models import Engagement, EngagementEvent, Lead, OutreachSendLog
from src.db.session import SessionLocal, get_db
from src.engagement.service import append_engagement_event
from src.outreach.email_sender import OutreachEmailError, send_outreach_email
from src.outreach.guardrails import (
    count_sends_for_local_day,
    get_outreach_policy,
    is_suppressed,
    normalize_email,
    within_send_window,
)
from src.pipeline import rescan_lead
from src.scorer.outreach import draft_outreach

router = APIRouter(prefix="/leads", tags=["leads"])

SORT_COLUMNS = {
    "lead_score": Lead.lead_score,
    "opportunity_score": Lead.opportunity_score,
    "created_at": Lead.created_at,
    "name": Lead.name,
    "category": Lead.category,
    "rating": Lead.rating,
    "review_count": Lead.review_count,
}


def _apply_filters(
    stmt,
    *,
    search: str | None,
    category: list[str],
    status: list[str],
    score_min: int,
    score_max: int,
    has_website: str,
):
    """Shared filter-builder used by listing and export."""
    if status:
        stmt = stmt.where(Lead.status.in_(status))
    else:
        stmt = stmt.where(Lead.status != "archived")

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Lead.name.ilike(pattern) | Lead.address.ilike(pattern))

    if category:
        stmt = stmt.where(Lead.category.in_(category))

    stmt = stmt.where(Lead.lead_score >= score_min, Lead.lead_score <= score_max)

    if has_website == "no":
        stmt = stmt.where(Lead.website_url.is_(None))
    elif has_website == "yes":
        stmt = stmt.where(Lead.website_url.isnot(None))
    elif has_website == "social":
        stmt = stmt.where(Lead.lead_score == 9)

    return stmt


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Use a naive local "today" for created_at comparison because SQLite's
    # func.now() writes local time without tzinfo. Mixing UTC and local
    # here used to silently miscount "new today" by ~6 hours.
    today_start = datetime.combine(date.today(), datetime.min.time())

    total_result = await db.execute(select(func.count()).where(Lead.status != "archived"))
    total = total_result.scalar_one() or 0

    new_today_result = await db.execute(
        select(func.count()).where(
            Lead.status == "new",
            Lead.created_at >= today_start,
        )
    )
    new_today = new_today_result.scalar_one() or 0

    avg_result = await db.execute(
        select(func.avg(Lead.lead_score)).where(Lead.status != "archived")
    )
    avg_score = round(avg_result.scalar_one() or 0.0, 1)

    return StatsResponse(total=total, new_today=new_today, avg_score=avg_score)


@router.get("", response_model=LeadsResponse)
async def list_leads(
    search: str | None = Query(None),
    category: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
    score_min: int = Query(default=1, ge=1, le=10),
    score_max: int = Query(default=10, ge=1, le=10),
    has_website: str = Query(default="all"),
    sort_by: str = Query(default="opportunity_score"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lead)
    stmt = _apply_filters(
        stmt,
        search=search,
        category=category,
        status=status,
        score_min=score_min,
        score_max=score_max,
        has_website=has_website,
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one() or 0

    col = SORT_COLUMNS.get(sort_by, Lead.opportunity_score)
    # Secondary sort by lead_score (desc) then id ensures stable ordering
    # when the primary column has many ties (NULLs on new columns).
    primary = col.desc() if sort_dir == "desc" else col.asc()
    stmt = stmt.order_by(primary, Lead.lead_score.desc(), Lead.id.desc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    leads = result.scalars().all()
    pages = max(1, math.ceil(total / page_size))

    return LeadsResponse(
        leads=[LeadSummary.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/export.csv")
async def export_leads_csv(
    search: str | None = Query(None),
    category: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
    score_min: int = Query(default=1, ge=1, le=10),
    score_max: int = Query(default=10, ge=1, le=10),
    has_website: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
):
    """Export filtered leads as CSV. Matches /leads filters exactly."""
    stmt = _apply_filters(
        select(Lead),
        search=search,
        category=category,
        status=status,
        score_min=score_min,
        score_max=score_max,
        has_website=has_website,
    ).order_by(Lead.opportunity_score.desc().nulls_last(), Lead.lead_score.desc())

    result = await db.execute(stmt)
    leads = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "lead_score",
            "opportunity_score",
            "name",
            "category",
            "google_categories",
            "address",
            "phone",
            "email",
            "website_url",
            "rating",
            "review_count",
            "hours",
            "photo_count",
            "is_claimed",
            "has_ssl",
            "has_mobile_viewport",
            "website_status_code",
            "copyright_year",
            "tech_stack",
            "ai_score",
            "ai_summary",
            "ai_issues",
            "business_description",
            "status",
            "notes",
            "created_at",
            "last_scanned_at",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                lead.id,
                lead.lead_score,
                lead.opportunity_score if lead.opportunity_score is not None else "",
                lead.name,
                lead.category or "",
                "; ".join(lead.google_categories or []),
                lead.address or "",
                lead.phone or "",
                lead.email or "",
                lead.website_url or "",
                lead.rating if lead.rating is not None else "",
                lead.review_count if lead.review_count is not None else "",
                lead.hours or "",
                lead.photo_count if lead.photo_count is not None else "",
                "" if lead.is_claimed is None else ("yes" if lead.is_claimed else "no"),
                "" if lead.has_ssl is None else ("yes" if lead.has_ssl else "no"),
                ""
                if lead.has_mobile_viewport is None
                else ("yes" if lead.has_mobile_viewport else "no"),
                lead.website_status_code if lead.website_status_code is not None else "",
                lead.copyright_year if lead.copyright_year is not None else "",
                "; ".join(lead.tech_stack or []),
                lead.ai_score if lead.ai_score is not None else "",
                lead.ai_summary or "",
                "; ".join(lead.ai_issues or []),
                lead.business_description or "",
                lead.status,
                lead.notes or "",
                lead.created_at.isoformat() if lead.created_at else "",
                lead.last_scanned_at.isoformat() if lead.last_scanned_at else "",
            ]
        )

    buffer.seek(0)
    filename = f"juggfinder-leads-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{lead_id}/engagement", response_model=EngagementTimelineResponse)
async def get_lead_engagement(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Ordered activity timeline (newest first) for the lead's default email engagement."""
    lead_check = await db.execute(select(Lead.id).where(Lead.id == lead_id))
    if lead_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    eng_result = await db.execute(
        select(Engagement).where(Engagement.lead_id == lead_id, Engagement.channel == "email")
    )
    eng = eng_result.scalar_one_or_none()
    if not eng:
        return EngagementTimelineResponse(
            lead_id=lead_id,
            channel="email",
            engagement_id=None,
            events=[],
        )

    ev_result = await db.execute(
        select(EngagementEvent)
        .where(EngagementEvent.engagement_id == eng.id)
        .order_by(EngagementEvent.created_at.desc())
    )
    rows = ev_result.scalars().all()
    return EngagementTimelineResponse(
        lead_id=lead_id,
        channel=eng.channel,
        engagement_id=eng.id,
        events=[EngagementEventItem.model_validate(r) for r in rows],
    )


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadDetail.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadDetail)
async def update_lead(lead_id: int, body: LeadUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if body.status is not None:
        lead.status = body.status
    if body.notes is not None:
        lead.notes = body.notes
    if body.outreach_draft is not None:
        lead.outreach_draft = body.outreach_draft

    await db.commit()
    await db.refresh(lead)
    return LeadDetail.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    await db.commit()
    return {"ok": True}


@router.post("/{lead_id}/rescan", response_model=LeadDetail)
async def rescan_endpoint(lead_id: int):
    """Re-run website evaluation + AI scoring for an existing lead."""
    updated = await rescan_lead(lead_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadDetail.model_validate(updated)


@router.post("/{lead_id}/draft-outreach", response_model=OutreachDraftResponse)
async def draft_outreach_endpoint(lead_id: int):
    """
    Generate and persist an AI-drafted outreach message for a lead.
    Overwrites any existing `outreach_draft`. Returns 502 if both
    providers fail.
    """
    async with SessionLocal() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        draft = await draft_outreach(
            {
                "id": lead.id,
                "name": lead.name,
                "category": lead.category,
                "website_url": lead.website_url,
                "has_ssl": lead.has_ssl,
                "has_mobile_viewport": lead.has_mobile_viewport,
                "website_status_code": lead.website_status_code,
                "copyright_year": lead.copyright_year,
                "tech_stack": lead.tech_stack,
                "ai_issues": lead.ai_issues,
                "is_claimed": lead.is_claimed,
                "photo_count": lead.photo_count,
                "rating": lead.rating,
                "review_count": lead.review_count,
            }
        )

        if not draft:
            raise HTTPException(
                status_code=502,
                detail="AI providers unavailable — try again in a minute.",
            )

        lead.outreach_draft = draft
        await db.commit()
        return OutreachDraftResponse(lead_id=lead.id, draft=draft)


@router.post("/{lead_id}/send-outreach", response_model=OutreachSendResponse)
async def send_outreach_endpoint(lead_id: int, body: OutreachSendRequest):
    """
    Send an outreach email for a lead using configured SMTP credentials.
    Uses explicit body/subject when provided, otherwise falls back to
    the saved outreach draft + generated subject.
    """
    async with SessionLocal() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        if not lead.email:
            raise HTTPException(status_code=400, detail="Lead has no email address to send to.")

        policy = await get_outreach_policy(db)
        recipient_email = normalize_email(lead.email)

        if not policy.enabled:
            raise HTTPException(
                status_code=400,
                detail="Outreach sending is disabled in outreach policy settings.",
            )

        if lead.status not in policy.allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Lead status '{lead.status}' not allowed for send. "
                    f"Allowed: {', '.join(policy.allowed_statuses)}"
                ),
            )

        now = datetime.now(UTC)
        if policy.enforce_window and not within_send_window(
            now_utc=now,
            timezone=policy.send_timezone,
            start_hhmm=policy.send_window_start,
            end_hhmm=policy.send_window_end,
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Current time is outside the configured outreach send window "
                    f"({policy.send_window_start}-{policy.send_window_end} {policy.send_timezone})."
                ),
            )

        if policy.enforce_daily_cap:
            sent_today = await count_sends_for_local_day(
                db=db,
                timezone=policy.send_timezone,
                now_utc=now,
            )
            if sent_today >= policy.daily_send_cap:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Daily outreach cap reached ({policy.daily_send_cap}) "
                        f"for timezone {policy.send_timezone}."
                    ),
                )

        if policy.enforce_suppression and await is_suppressed(db, recipient_email):
            raise HTTPException(
                status_code=400,
                detail="Recipient is on suppression list; not sending.",
            )

        note_text = (lead.notes or "").lower()
        if "do not contact" in note_text or "unsubscribe" in note_text:
            block_log = OutreachSendLog(
                lead_id=lead.id,
                to_email=recipient_email,
                subject=body.subject or "",
                body=(body.body or lead.outreach_draft or "")[:4000],
                status="blocked",
                error="do-not-contact in notes",
            )
            db.add(block_log)
            await db.flush()
            await append_engagement_event(
                db,
                lead_id=lead.id,
                event_type="outreach_blocked",
                payload={
                    "to_email": recipient_email,
                    "subject": body.subject or "",
                    "reason": "do-not-contact in notes",
                },
                outreach_send_log_id=block_log.id,
            )
            await db.commit()
            raise HTTPException(
                status_code=400,
                detail="Lead is marked do-not-contact in notes; not sending.",
            )

        message_body = (body.body or lead.outreach_draft or "").strip()
        if not message_body:
            raise HTTPException(
                status_code=400,
                detail="No outreach message body available. Draft one first or provide `body`.",
            )

        subject = (body.subject or f"Quick website idea for {lead.name}").strip()
        if not subject:
            raise HTTPException(status_code=400, detail="Email subject cannot be empty.")

        try:
            message_id = await send_outreach_email(
                to_email=recipient_email,
                subject=subject,
                body=message_body,
            )
        except OutreachEmailError as e:
            lead.outreach_last_error = str(e)
            fail_log = OutreachSendLog(
                lead_id=lead.id,
                to_email=recipient_email,
                subject=subject,
                body=message_body[:4000],
                status="failed",
                error=str(e),
            )
            db.add(fail_log)
            await db.flush()
            await append_engagement_event(
                db,
                lead_id=lead.id,
                event_type="outreach_failed",
                payload={
                    "to_email": recipient_email,
                    "subject": subject,
                    "error": str(e),
                },
                outreach_send_log_id=fail_log.id,
            )
            await db.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Unable to send outreach email: {e}",
            ) from e

        sent_at = datetime.now(UTC)
        lead.outreach_sent_at = sent_at
        lead.outreach_last_error = None
        # Persist whichever message body was used so the sent text remains visible/editable.
        lead.outreach_draft = message_body
        sent_log = OutreachSendLog(
            lead_id=lead.id,
            to_email=recipient_email,
            subject=subject,
            body=message_body[:4000],
            status="sent",
            message_id=message_id,
            sent_at=sent_at,
        )
        db.add(sent_log)
        await db.flush()
        await append_engagement_event(
            db,
            lead_id=lead.id,
            event_type="outreach_sent",
            payload={
                "to_email": recipient_email,
                "subject": subject,
                "message_id": message_id,
                "snippet": message_body[:240],
            },
            outreach_send_log_id=sent_log.id,
        )
        await db.commit()

        return OutreachSendResponse(
            lead_id=lead.id,
            to_email=recipient_email,
            subject=subject,
            sent_at=sent_at,
        )
