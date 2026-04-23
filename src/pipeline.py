"""
Scraper pipeline — Phase 08 + Phase 15.

Orchestrates the full lead generation flow:
  Maps scraper → Website evaluator → AI scorer → Lead scorer → DB write

This module owns the concurrency lock and the scrape state dict. Both
the scheduler and the API call run_scrape().

Phase 15 additions:
  - Shared SelectorHealth object tracked per run and exposed via
    GET /scrape/status for drift detection.
  - Progress telemetry: current_category, categories_done, categories_total,
    businesses_processed, new_leads, started_at — polled by the UI.
  - Per-row DB session so one bad lead never corrupts the whole run.
  - Writes all new Phase 15 fields (email, hours, google_categories,
    business_description, photo_count, is_claimed, tech_stack,
    opportunity_score, last_scanned_at).
  - Per-lead rescan helper (rescan_lead) powers POST /leads/{id}/rescan.
  - CaptchaEncountered aborts the run with a clear log.
"""

import asyncio
import random
from copy import deepcopy
from datetime import UTC, datetime

from playwright.async_api import BrowserContext, async_playwright

from src.config.settings import settings
from src.db.models import Lead
from src.db.session import SessionLocal
from src.scorer.ai import reset_session, score_with_ai
from src.scorer.lead import calculate_lead_score, calculate_opportunity_score
from src.scraper.evaluator import evaluate_website
from src.scraper.maps import (
    CaptchaEncountered,
    SelectorHealth,
    build_context,
    scrape_category,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Concurrency guard + live state
# ---------------------------------------------------------------------------

_scrape_lock = asyncio.Lock()

_INITIAL_STATE: dict = {
    "running": False,
    "started_at": None,
    "categories": [],
    "current_category": None,
    "categories_done": 0,
    "categories_total": 0,
    "businesses_processed": 0,
    "new_leads": 0,
    "selector_health": {},
    "error": None,
}

_scrape_state: dict = dict(_INITIAL_STATE)


def get_scrape_state() -> dict:
    """Return a deep copy of the current scrape state for the API."""
    return deepcopy(_scrape_state)


def _reset_state() -> None:
    _scrape_state.update(deepcopy(_INITIAL_STATE))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_lead(biz: dict, eval_result: dict, ai_result: dict) -> Lead:
    """
    Build a Lead ORM object from the combined signal dicts.

    Shared between the scrape pipeline and rescan_lead so the mapping
    stays in one place.
    """
    lead_score = calculate_lead_score(eval_result, ai_result, biz)
    opportunity = calculate_opportunity_score(eval_result, ai_result, biz)

    return Lead(
        place_id=biz.get("place_id"),
        name=biz["name"],
        category=biz.get("category"),
        address=biz.get("address"),
        phone=biz.get("phone"),
        email=eval_result.get("email"),
        website_url=eval_result.get("website_url"),
        rating=biz.get("rating"),
        review_count=biz.get("review_count"),
        hours=biz.get("hours"),
        google_categories=biz.get("google_categories") or [],
        business_description=biz.get("business_description"),
        photo_count=biz.get("photo_count"),
        is_claimed=biz.get("is_claimed"),
        has_ssl=eval_result.get("has_ssl"),
        has_mobile_viewport=eval_result.get("has_mobile_viewport"),
        website_status_code=eval_result.get("website_status_code"),
        copyright_year=eval_result.get("copyright_year"),
        tech_stack=eval_result.get("tech_stack") or [],
        ai_score=ai_result.get("score"),
        ai_issues=ai_result.get("issues", []),
        ai_summary=ai_result.get("summary"),
        lead_score=lead_score,
        opportunity_score=opportunity,
        status="new",
        last_scanned_at=datetime.now(UTC),
    )


async def _process_business(biz: dict) -> None:
    """
    Run a single business through evaluation → AI scoring → DB write.

    Uses a fresh DB session per lead so one failure can't poison the run.
    """
    name = biz.get("name", "?")
    try:
        eval_result = await evaluate_website(biz.get("website_url"))

        ai_result: dict = {"score": None, "issues": [], "summary": None}
        if not eval_result["skip_ai"] and eval_result.get("html_snippet"):
            ai_result = await score_with_ai(eval_result["html_snippet"])

        lead = _build_lead(biz, eval_result, ai_result)

        async with SessionLocal() as db:
            try:
                db.add(lead)
                await db.commit()
                _scrape_state["new_leads"] += 1
                logger.info(
                    f"Saved: {name} — lead_score={lead.lead_score}, "
                    f"opp={lead.opportunity_score}, ai={ai_result.get('score')}"
                )
            except Exception:
                await db.rollback()
                raise

    except Exception as e:
        logger.error(f"Failed to process '{name}': {e}", exc_info=True)

    finally:
        _scrape_state["businesses_processed"] += 1


async def _execute_scrape(
    categories: list[str],
    context: BrowserContext,
    health: SelectorHealth,
) -> None:
    """Run the scrape loop across the given categories. Raises CaptchaEncountered."""
    async with SessionLocal() as dedup_db:
        for i, category in enumerate(categories):
            _scrape_state["current_category"] = category
            _scrape_state["categories_done"] = i
            logger.info(f"[{i + 1}/{len(categories)}] Scraping: '{category}'")
            try:
                businesses = await scrape_category(category, dedup_db, context, health)
            except CaptchaEncountered:
                _scrape_state["error"] = "captcha"
                raise
            except Exception as e:
                logger.error(f"Category '{category}' failed entirely: {e}", exc_info=True)
                _scrape_state["categories_done"] = i + 1
                continue

            logger.info(f"[{category}] {len(businesses)} new businesses to process.")

            for biz in businesses:
                await _process_business(biz)

            _scrape_state["categories_done"] = i + 1
            _scrape_state["selector_health"] = health.to_dict()

            # Polite inter-category pause (skip after the last one)
            if i < len(categories) - 1:
                pause = random.uniform(10, 20)
                logger.debug(f"Pausing {pause:.1f}s before next category.")
                await asyncio.sleep(pause)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_scrape(categories: list[str]) -> None:
    """
    Run a full scrape pipeline for the given categories.

    Raises RuntimeError if a scrape is already running (caller should catch).
    """
    from src.config.categories import CATEGORIES

    if categories == ["all"] or "all" in categories:
        categories = CATEGORIES

    if _scrape_lock.locked():
        raise RuntimeError("A scrape is already running.")

    async with _scrape_lock:
        reset_session()
        _reset_state()
        _scrape_state.update(
            {
                "running": True,
                "started_at": datetime.now(UTC).isoformat(),
                "categories": list(categories),
                "categories_total": len(categories),
            }
        )
        health = SelectorHealth()
        logger.info(
            f"Scrape started — {len(categories)} categories: {categories} "
            f"(headless={settings.scrape_headless}, location={settings.scrape_location!r})"
        )

        try:
            async with async_playwright() as pw:
                # "new" headless mode is less fingerprintable than Chromium's
                # legacy headless. Disable automation-control banner via args.
                launch_args = ["--disable-blink-features=AutomationControlled"]
                if settings.scrape_headless:
                    browser = await pw.chromium.launch(
                        headless=True,
                        args=launch_args + ["--headless=new"],
                    )
                else:
                    browser = await pw.chromium.launch(headless=False, args=launch_args)

                context = await build_context(browser)
                try:
                    await _execute_scrape(categories, context, health)
                finally:
                    await context.close()
                    await browser.close()

        except CaptchaEncountered as e:
            logger.critical(f"Scrape aborted — {e}")
        except Exception as e:
            logger.error(f"Scrape aborted with error: {e}", exc_info=True)
            _scrape_state["error"] = str(e)
        finally:
            _scrape_state["selector_health"] = health.to_dict()
            _scrape_state.update(
                {
                    "running": False,
                    "current_category": None,
                }
            )
            logger.info(
                f"Scrape finished — {_scrape_state['new_leads']} new leads, "
                f"{_scrape_state['businesses_processed']} processed, "
                f"health={_scrape_state['selector_health']}"
            )


async def rescan_lead(lead_id: int) -> Lead | None:
    """
    Re-run website evaluation + AI scoring + lead scoring for an existing
    lead. Preserves status, notes, outreach_draft, created_at; updates
    everything else.

    Returns the updated Lead or None if not found.
    """
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            return None

        biz = {
            "place_id": lead.place_id,
            "name": lead.name,
            "category": lead.category,
            "address": lead.address,
            "phone": lead.phone,
            "website_url": lead.website_url,
            "rating": lead.rating,
            "review_count": lead.review_count,
            "hours": lead.hours,
            "google_categories": lead.google_categories,
            "business_description": lead.business_description,
            "photo_count": lead.photo_count,
            "is_claimed": lead.is_claimed,
        }

        eval_result = await evaluate_website(lead.website_url)
        ai_result: dict = {"score": None, "issues": [], "summary": None}
        if not eval_result["skip_ai"] and eval_result.get("html_snippet"):
            ai_result = await score_with_ai(eval_result["html_snippet"])

        lead.email = eval_result.get("email")
        lead.has_ssl = eval_result.get("has_ssl")
        lead.has_mobile_viewport = eval_result.get("has_mobile_viewport")
        lead.website_status_code = eval_result.get("website_status_code")
        lead.copyright_year = eval_result.get("copyright_year")
        lead.tech_stack = eval_result.get("tech_stack") or []
        lead.ai_score = ai_result.get("score")
        lead.ai_issues = ai_result.get("issues", [])
        lead.ai_summary = ai_result.get("summary")
        lead.lead_score = calculate_lead_score(eval_result, ai_result, biz)
        lead.opportunity_score = calculate_opportunity_score(eval_result, ai_result, biz)
        lead.last_scanned_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(lead)
        return lead
