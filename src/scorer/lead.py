"""
Lead scorer — Phase 07 + Phase 15 rework.

Pure functions: no I/O, no async. Applies the rubric from INTEGRATION.md
and computes a 0–100 opportunity_score that accounts for review volume,
rating, category payout potential, copyright year, and contact reachability.

Two outputs:

  lead_score (int 1–10)
      Coarse bucket for display/filter. First-matching-priority rubric.
      Used for color-coding and the score-range slider.

  opportunity_score (float 0–100)
      Finer composite used for ranking. Same signals as lead_score plus
      monetary weighting (review_count × rating × category_multiplier).
      A 500-review 4.9-star HVAC with no website scores near 100; a
      3-review restaurant with no website scores around 45.

IMPORTANT: lead_score != ai_score. They are separate DB fields.
  ai_score         = raw website quality (Gemini/Groq)
  lead_score       = sales opportunity bucket
  opportunity_score = sales opportunity composite (0–100)
"""

from datetime import datetime

from src.config.categories import category_multiplier
from src.utils.logging import get_logger

logger = get_logger(__name__)

# A site-quality AI score this high + established business ⇒ the owner
# already has a solid web presence. These businesses will almost never pay
# for a redesign — floor them at the lowest lead bucket so they drop out
# of the default view. This is the direct fix for the Bardenay / Fork
# false-positives reported in manual review.
WELL_ESTABLISHED_REVIEW_FLOOR = 50
WELL_ESTABLISHED_RATING_FLOOR = 4.3
WELL_ESTABLISHED_AI_SCORE = 7  # AI score >= this AND above thresholds ⇒ skip

# Review-count thresholds. Businesses with trivial review counts are
# much riskier to pitch — they may not be actually operating.
MIN_CREDIBLE_REVIEWS = 10
STRONG_REVIEWS = 100
PREMIUM_REVIEWS = 500

CURRENT_YEAR = datetime.now().year


def calculate_lead_score(eval_result: dict, ai_result: dict, biz: dict | None = None) -> int:
    """
    Calculate the coarse lead score bucket (1–10) from evaluator, AI, and
    optional raw business fields (rating / review_count / category).

    Rubric (priority order — first match wins):
      10 — No website URL at all
       9 — URL is a social / directory / booking page
       8 — Website returns 4xx or 5xx
       7 — Website has no HTTPS
       6 — Website has no mobile viewport
       5 — AI score ≤ 4 (outdated/bad site)
       3 — AI score 5–6 (mediocre site)
       2 — AI score ≥ 7 (decent site — still an upsell candidate)
       3 — Fallback when AI score is unavailable

    Overrides:
       1 — Applied whenever the business is "well-established":
            AI score ≥ 7 AND review_count ≥ 50 AND rating ≥ 4.3. These
            are Bardenay-class false positives — great sites, happy
            customers, not in the market for a redesign.

    Args:
        eval_result: dict from evaluate_website()
        ai_result:   dict from score_with_ai() — score may be None
        biz:         optional raw business dict (for rating/review_count/
                     category overrides). Passing None keeps the old
                     behavior for existing callers/tests.
    Returns:
        Integer lead score 1–10. Never raises.
    """
    try:
        early = eval_result.get("early_lead_score")
        if early is not None:
            return int(early)

        if not eval_result.get("has_ssl"):
            return 7
        if not eval_result.get("has_mobile_viewport"):
            return 6

        ai_score = ai_result.get("score")

        # Well-established business override: solid site + real customer
        # base ⇒ not a redesign target. This directly addresses Bardenay,
        # Fork, and similar well-loved Boise businesses.
        if biz is not None and ai_score is not None and ai_score >= WELL_ESTABLISHED_AI_SCORE:
            review_count = biz.get("review_count") or 0
            rating = biz.get("rating") or 0.0
            if (
                review_count >= WELL_ESTABLISHED_REVIEW_FLOOR
                and rating >= WELL_ESTABLISHED_RATING_FLOOR
            ):
                return 1

        if ai_score is not None:
            if ai_score <= 4:
                return 5
            if ai_score <= 6:
                return 3
            # ai_score ≥ 7 without the well-established override — keep as
            # upsell candidate (SEO, new landing pages, etc.).
            return 2

        return 3

    except Exception:
        logger.exception("calculate_lead_score failed — defaulting to 3.")
        return 3


def calculate_opportunity_score(
    eval_result: dict,
    ai_result: dict,
    biz: dict,
) -> float:
    """
    Composite 0–100 score weighing website quality AND monetary potential.

    Formula (approximate):
        base      = coarse lead_score × 10                     # 10-100 band
        base     += copyright_age_bonus                        # -10 to +15
        base     += reachability_bonus                         # -10 to +10
        base     += photos_bonus                               # -5 to +5
        base     += unclaimed_bonus                            # 0 or +10
        base     *= review_confidence_multiplier               # 0.5 - 1.15
        base     *= rating_multiplier                          # 0.7 - 1.15
        base     *= category_multiplier                        # 0.85 - 1.5

    Returns a float clamped to [0.0, 100.0].

    Never raises — defaults to 50.0 on any exception.
    """
    try:
        bucket = calculate_lead_score(eval_result, ai_result, biz)
        # Start from the coarse bucket — scale so 10 ≈ 100, 1 ≈ 10.
        score = bucket * 10.0

        # Copyright year — stale footer is a huge redesign signal.
        cy = eval_result.get("copyright_year")
        if cy is not None and isinstance(cy, int):
            age = CURRENT_YEAR - cy
            if age >= 5:
                score += 15
            elif age >= 3:
                score += 8
            elif age <= 1:
                score -= 5  # currently-maintained site

        # Reachability — presence of a phone + email = easy outreach.
        reach = 0
        if biz.get("phone"):
            reach += 3
        if eval_result.get("email"):
            reach += 7
        else:
            reach -= 5
        score += reach

        # Photo count — Google lets owners upload photos for free. Under
        # 5 photos ⇒ owner has barely touched their listing ⇒ soft lead.
        pc = biz.get("photo_count")
        if isinstance(pc, int):
            if pc < 5:
                score -= 5
            elif pc > 50:
                score += 3

        # Unclaimed Google listing ⇒ even easier pitch.
        if biz.get("is_claimed") is False:
            score += 10

        # Review confidence — few reviews ⇒ unclear if business is viable.
        rc = biz.get("review_count") or 0
        if rc < MIN_CREDIBLE_REVIEWS:
            confidence = 0.5 + (rc / MIN_CREDIBLE_REVIEWS) * 0.35  # 0.5 - 0.85
        elif rc >= PREMIUM_REVIEWS:
            confidence = 1.15
        elif rc >= STRONG_REVIEWS:
            confidence = 1.1
        else:
            confidence = 0.85 + ((rc - MIN_CREDIBLE_REVIEWS) / STRONG_REVIEWS) * 0.25
        score *= confidence

        # Rating — low-rated businesses are cash-strapped, less likely to pay.
        rating = biz.get("rating")
        if isinstance(rating, (int, float)):
            if rating >= 4.7:
                score *= 1.15
            elif rating >= 4.3:
                score *= 1.05
            elif rating < 3.0:
                score *= 0.7
            elif rating < 3.5:
                score *= 0.8

        # Category payout multiplier — dentists/HVAC/plumbers pay more.
        score *= category_multiplier(biz.get("category"))

        return max(0.0, min(100.0, round(score, 1)))

    except Exception:
        logger.exception("calculate_opportunity_score failed — defaulting to 50.0.")
        return 50.0
