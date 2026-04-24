"""
Dev-only pipeline dry-run: seed TEST BUSINESS, optional AI draft, simulated send + inbound.

Does not call SMTP. Simulated `outreach_sent` is timeline-only (no `outreach_send_logs` row)
so daily caps and audit logs stay truthful for real sends.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.models import Lead
from src.engagement.service import append_engagement_event, record_inbound_received
from src.outreach.guardrails import normalize_email
from src.scorer.outreach import draft_outreach

# Stable synthetic Maps id so re-runs upsert the same dev lead row.
DEV_TEST_PLACE_ID = "dev:juggfinder-test-business"

STEP_ORDER = ("seed", "draft", "simulate_outreach_sent", "simulate_inbound")
VALID_STEPS = frozenset(STEP_ORDER)


def _canonical_steps(requested: list[str]) -> list[str]:
    wanted = {s.strip() for s in requested if s and s.strip()}
    return [s for s in STEP_ORDER if s in wanted]


async def _lead_to_draft_dict(lead: Lead) -> dict[str, Any]:
    return {
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


async def execute_dry_run(
    db: AsyncSession,
    *,
    steps: list[str],
    business_name: str,
    test_email: str,
) -> tuple[int | None, list[tuple[str, bool, str | None]]]:
    """
    Run selected steps in canonical order. Does not commit — caller commits.

    Returns (lead_id_or_none, list of (step, ok, error_detail)).
    """
    results: list[tuple[str, bool, str | None]] = []
    lead_id: int | None = None
    email_norm = normalize_email(test_email)

    for step in _canonical_steps(steps):
        if step == "seed":
            res = await db.execute(select(Lead).where(Lead.place_id == DEV_TEST_PLACE_ID))
            row = res.scalar_one_or_none()
            if row:
                row.name = business_name
                row.email = email_norm
                row.lead_score = 9
                if not row.category:
                    row.category = "test"
                await db.flush()
                lead_id = row.id
            else:
                lead = Lead(
                    place_id=DEV_TEST_PLACE_ID,
                    name=business_name,
                    email=email_norm,
                    lead_score=9,
                    category="test",
                    website_url=None,
                )
                db.add(lead)
                await db.flush()
                lead_id = lead.id
            results.append(("seed", True, None))
            continue

        if lead_id is None:
            results.append((step, False, "run seed first"))
            continue

        if step == "draft":
            res = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = res.scalar_one()
            text = await draft_outreach(await _lead_to_draft_dict(lead))
            if not text:
                results.append(("draft", False, "AI draft returned empty"))
            else:
                lead.outreach_draft = text
                await db.flush()
                results.append(("draft", True, None))
            continue

        if step == "simulate_outreach_sent":
            await append_engagement_event(
                db,
                lead_id=lead_id,
                event_type="outreach_sent",
                payload={
                    "dry_run": True,
                    "to_email": email_norm,
                    "subject": "Simulated outreach (dev dry-run)",
                    "snippet": "No SMTP — dev pipeline dry-run only.",
                },
            )
            results.append(("simulate_outreach_sent", True, None))
            continue

        if step == "simulate_inbound":
            to_addr = (
                (settings.outreach_sender_email or "").strip()
                or "dev-inbound-to@juggfinder.local"
            )
            await record_inbound_received(
                db,
                lead_id=lead_id,
                from_email=email_norm,
                to_email=to_addr,
                subject="Re: your note (dry-run)",
                body="Thanks for reaching out — this is a simulated reply for pipeline testing.",
                message_id="<dev-dry-run-inbound@juggfinder.local>",
            )
            results.append(("simulate_inbound", True, None))

    return lead_id, results
