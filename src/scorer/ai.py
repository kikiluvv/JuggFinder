"""
AI scoring — Phase 06 + Phase 15 hardening.

Sends the cleaned HTML snippet to Gemini for a website quality score
(1–10). Falls back to Groq on rate-limit errors. Returns null equivalents
if both fail — never blocks the pipeline.

Phase 15 improvements:
  - Model names pulled from settings (swappable via env).
  - Gemini call uses response_mime_type=application/json with a strict
    response_schema — no more markdown fences to strip.
  - Typed rate-limit detection: google.genai.errors.ClientError (code
    429) and groq.RateLimitError. Substring matching kept as a fallback
    for future vendor changes.
  - On first Gemini 429: wait 60 s and retry once, per the spec in
    INTEGRATION.md, before switching to Groq for the rest of the session.
"""

import asyncio
import json
import re

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from groq import APIError as GroqAPIError
from groq import Groq
from groq import RateLimitError as GroqRateLimitError

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
You are evaluating a small business website to determine if it needs a professional redesign.
Analyze the following HTML content and return ONLY a valid JSON object — no explanation, no markdown.

HTML snippet (cleaned of scripts/styles, truncated to 3000 chars):
{html_snippet}

Respond with exactly this JSON format:
{{
  "score": <integer 1-10>,
  "issues": ["<issue1>", "<issue2>", ...],
  "summary": "<one sentence describing the website quality>"
}}

Scoring guide:
10 = modern, fast, mobile-friendly, professional design
 7 = functional but visually dated or lacking polish
 5 = clearly outdated, not mobile-friendly, or unprofessional
 3 = barely functional, very old design
 1 = broken, nearly non-existent, or completely unusable

A site that looks polished and professional SHOULD receive a high score (8-10) even if the HTML is minimal because the business is clearly well-served by it and is NOT a good redesign prospect. Don't penalize brevity.\
"""

# JSON schema enforced via Gemini's response_schema — eliminates the
# "model wrapped JSON in markdown" failure mode entirely.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["score", "issues", "summary"],
    "properties": {
        "score": {"type": "INTEGER"},
        "issues": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "summary": {"type": "STRING"},
    },
}

NULL_RESULT: dict = {"score": None, "issues": [], "summary": None}

# ---------------------------------------------------------------------------
# Session-level fallback state
# ---------------------------------------------------------------------------

_use_groq_fallback: bool = False
_gemini_retry_used: bool = False
GEMINI_RATE_LIMIT_SLEEP = 60.0  # seconds to wait before the one Gemini retry


def reset_session() -> None:
    """Reset session-level state. Call between scrape sessions and in tests."""
    global _use_groq_fallback, _gemini_retry_used
    _use_groq_fallback = False
    _gemini_retry_used = False


# ---------------------------------------------------------------------------
# Lazy-initialized API clients
# ---------------------------------------------------------------------------

_gemini_client: genai.Client | None = None
_groq_client: Groq | None = None


def reset_clients() -> None:
    """Drop cached clients so updated API keys/models take effect."""
    global _gemini_client, _groq_client
    _gemini_client = None
    _groq_client = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Safe JSON parser — exported for testing
# ---------------------------------------------------------------------------


def parse_ai_response(text: str) -> dict:
    """
    Parse an AI response string into a {score, issues, summary} dict.

    Handles:
    - Markdown code fences (```json ... ```) — residual safety net
    - Trailing/leading whitespace
    - Missing or zero score (mapped to None)
    - Any JSON parse failure → returns NULL_RESULT shape
    """
    try:
        clean = re.sub(r"```(?:json)?\s*|```", "", text).strip()
        data = json.loads(clean)
        raw_score = data.get("score")
        score = int(raw_score) if raw_score else None
        if score is not None and not (1 <= score <= 10):
            score = None
        return {
            "score": score,
            "issues": list(data.get("issues", [])),
            "summary": data.get("summary") or None,
        }
    except Exception:
        return dict(NULL_RESULT)


# ---------------------------------------------------------------------------
# Rate-limit detection
# ---------------------------------------------------------------------------


def _is_rate_limit(exc: Exception) -> bool:
    """
    Return True if `exc` represents a rate-limit / quota-exhausted error.

    Typed check first (ClientError.code == 429 for Gemini), substring
    fallback for future SDK changes and unusual error wrappers.
    """
    if isinstance(exc, genai_errors.ClientError):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code == 429:
            return True
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "ResourceExhausted" in msg


# ---------------------------------------------------------------------------
# API calls (sync SDKs wrapped in asyncio.to_thread)
# ---------------------------------------------------------------------------


async def _call_gemini(html_snippet: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(html_snippet=html_snippet[:3000])
    client = _get_gemini()
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.2,
    )
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    return parse_ai_response(response.text)


async def _call_groq(html_snippet: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(html_snippet=html_snippet[:3000])
    client = _get_groq()
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return parse_ai_response(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def score_with_ai(html_snippet: str) -> dict:
    """
    Score a website's HTML snippet using AI.

    Order of operations:
      1. Gemini — primary.
      2. On 429 / ResourceExhausted:
           - if we haven't used our one-shot 60s retry, sleep + retry
             Gemini. If that also 429s → flip to Groq for the session.
           - if the one-shot retry is already spent, flip to Groq.
      3. Groq — used for the rest of the session once triggered.
      4. If Groq also fails → return NULL_RESULT.

    Never raises — the pipeline must always continue.
    """
    global _use_groq_fallback, _gemini_retry_used

    if not _use_groq_fallback:
        try:
            result = await _call_gemini(html_snippet)
            logger.debug(f"Gemini scored: {result.get('score')}")
            return result
        except Exception as e:
            if _is_rate_limit(e):
                if not _gemini_retry_used:
                    _gemini_retry_used = True
                    logger.warning(
                        f"Gemini rate limited — sleeping {GEMINI_RATE_LIMIT_SLEEP}s and retrying once."
                    )
                    await asyncio.sleep(GEMINI_RATE_LIMIT_SLEEP)
                    try:
                        result = await _call_gemini(html_snippet)
                        logger.debug(f"Gemini (retry) scored: {result.get('score')}")
                        return result
                    except Exception as e2:
                        if _is_rate_limit(e2):
                            logger.warning("Gemini still rate limited — switching to Groq.")
                            _use_groq_fallback = True
                        else:
                            logger.error(f"Gemini retry non-rate-limit error: {e2}")
                            return dict(NULL_RESULT)
                else:
                    logger.warning("Gemini rate limited (retry spent) — switching to Groq.")
                    _use_groq_fallback = True
            else:
                logger.error(f"Gemini error (non-rate-limit): {e}")
                return dict(NULL_RESULT)

    # Groq path
    try:
        result = await _call_groq(html_snippet)
        logger.debug(f"Groq scored: {result.get('score')}")
        return result
    except GroqRateLimitError as e:
        logger.error(f"Groq rate limited: {e}")
        return dict(NULL_RESULT)
    except GroqAPIError as e:
        logger.error(f"Groq API error: {e}")
        return dict(NULL_RESULT)
    except Exception as e:
        logger.error(f"Groq unexpected error: {e}")
        return dict(NULL_RESULT)
