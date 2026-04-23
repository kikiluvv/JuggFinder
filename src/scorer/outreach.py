"""
Outreach drafter — Phase 15.

Uses the same Gemini/Groq infrastructure as src/scorer/ai.py to draft a
short, personalized first-contact message for a lead. Called on-demand
from the dashboard (POST /leads/{id}/draft-outreach) rather than during
the scrape so we don't burn AI quota on leads the user may never review.

Draft style intentionally:
  - 2-4 sentences, casual-professional
  - references a concrete observation from the signals (tech stack,
    copyright year, no mobile, no HTTPS, no website, etc.)
  - avoids hard-sell language
  - ends with a specific ask (not "let me know")
"""

import asyncio
from typing import Any

from google.genai import types as genai_types
from groq import APIError as GroqAPIError
from groq import RateLimitError as GroqRateLimitError

from src.config.settings import settings
from src.scorer.ai import _get_gemini, _get_groq, _is_rate_limit
from src.utils.logging import get_logger

logger = get_logger(__name__)


OUTREACH_PROMPT_TEMPLATE = """\
You are writing a cold outreach message on behalf of a freelance web developer based in \
Boise, Idaho.
Write a short email (2-4 sentences) to the owner of a small local business. Be friendly,
concrete, and reference ONE specific observation about their current web presence. End
with a low-pressure ask like "would you be open to a quick 15-min chat?". Do NOT include
a subject line, signature, greeting beyond "Hi" or "Hey", or any placeholder text like
[YOUR NAME]. Do not mention AI.

Business: {name}
Category: {category}
City: {city}
Rating: {rating} ({review_count} reviews)
Website: {website}
Website observations:
{observations}

Write the message now:\
"""


def _format_observations(lead: dict[str, Any]) -> str:
    """Turn the lead dict into a bulleted context block for the AI."""
    observations: list[str] = []

    website = lead.get("website_url")
    if not website:
        observations.append("- No website listed on their Google Maps profile.")
    else:
        if lead.get("has_ssl") is False:
            observations.append(
                "- Current site lacks HTTPS (browsers show a 'Not secure' warning)."
            )
        if lead.get("has_mobile_viewport") is False:
            observations.append("- No mobile viewport meta tag — site doesn't adapt to phones.")
        status = lead.get("website_status_code")
        if status is not None and status >= 400:
            observations.append(f"- Current site returns HTTP {status} (broken or down).")
        cy = lead.get("copyright_year")
        if cy is not None and isinstance(cy, int):
            observations.append(
                f"- Footer copyright reads {cy} — site hasn't been updated in a while."
            )
        tech = lead.get("tech_stack") or []
        if tech:
            observations.append(f"- Site appears to be built on: {', '.join(tech)}.")

    issues = lead.get("ai_issues") or []
    for issue in issues[:3]:
        observations.append(f"- AI detected: {issue}")

    if lead.get("is_claimed") is False:
        observations.append("- Google Business Profile is unclaimed.")

    pc = lead.get("photo_count")
    if isinstance(pc, int) and pc < 5:
        observations.append(f"- Only {pc} photos on their Google listing.")

    if not observations:
        observations.append("- No specific issues detected — keep the message generic but warm.")

    return "\n".join(observations)


def _build_prompt(lead: dict[str, Any]) -> str:
    return OUTREACH_PROMPT_TEMPLATE.format(
        name=lead.get("name") or "this business",
        category=lead.get("category") or "small business",
        city="Boise",
        rating=lead.get("rating") if lead.get("rating") is not None else "n/a",
        review_count=lead.get("review_count") if lead.get("review_count") is not None else "n/a",
        website=lead.get("website_url") or "(none)",
        observations=_format_observations(lead),
    )


async def _call_gemini_text(prompt: str) -> str:
    client = _get_gemini()
    config = genai_types.GenerateContentConfig(temperature=0.6)
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    return (response.text or "").strip()


async def _call_groq_text(prompt: str) -> str:
    client = _get_groq()
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    return (response.choices[0].message.content or "").strip()


async def draft_outreach(lead: dict[str, Any]) -> str:
    """
    Generate a 2-4 sentence outreach draft for a lead.

    Returns an empty string if both providers fail. Never raises.
    """
    prompt = _build_prompt(lead)

    # Gemini first
    try:
        text = await _call_gemini_text(prompt)
        if text:
            logger.debug(f"Drafted outreach via Gemini for lead id={lead.get('id')}")
            return text
    except Exception as e:
        if _is_rate_limit(e):
            logger.warning("Gemini rate limited on outreach — trying Groq.")
        else:
            logger.warning(f"Gemini outreach error ({e}) — trying Groq.")

    # Groq fallback
    try:
        text = await _call_groq_text(prompt)
        if text:
            logger.debug(f"Drafted outreach via Groq for lead id={lead.get('id')}")
            return text
    except GroqRateLimitError:
        logger.error("Groq rate limited — outreach draft unavailable.")
    except GroqAPIError as e:
        logger.error(f"Groq API error on outreach: {e}")
    except Exception as e:
        logger.error(f"Groq unexpected error on outreach: {e}")

    return ""
