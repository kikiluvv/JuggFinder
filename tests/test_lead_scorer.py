"""
Tests for src/scorer/lead.py — calculate_lead_score().

Every row of the rubric from INTEGRATION.md is explicitly tested.
All tests are synchronous pure-function calls — no I/O, no fixtures.
"""

from src.scorer.lead import calculate_lead_score, calculate_opportunity_score


def _early(score: int) -> dict:
    """Build a minimal eval_result that triggers an early_lead_score."""
    return {"early_lead_score": score, "has_ssl": None, "has_mobile_viewport": None}


def _live(has_ssl: bool, has_viewport: bool) -> dict:
    """Build an eval_result for a live website that reached the AI scorer."""
    return {"early_lead_score": None, "has_ssl": has_ssl, "has_mobile_viewport": has_viewport}


def _ai(score: int | None) -> dict:
    return {"score": score, "issues": [], "summary": None}


# ---------------------------------------------------------------------------
# Rubric rows — each test verifies exactly one row
# ---------------------------------------------------------------------------


class TestRubricRows:
    def test_score_10_no_website(self):
        """No website URL → lead score 10."""
        assert calculate_lead_score(_early(10), _ai(None)) == 10

    def test_score_9_social_url(self):
        """Social/directory URL → lead score 9."""
        assert calculate_lead_score(_early(9), _ai(None)) == 9

    def test_score_8_http_error(self):
        """4xx/5xx HTTP status → lead score 8."""
        assert calculate_lead_score(_early(8), _ai(None)) == 8

    def test_score_7_no_https(self):
        """Live site without HTTPS → lead score 7."""
        assert calculate_lead_score(_live(has_ssl=False, has_viewport=True), _ai(7)) == 7

    def test_score_6_no_mobile_viewport(self):
        """HTTPS site without mobile viewport → lead score 6."""
        assert calculate_lead_score(_live(has_ssl=True, has_viewport=False), _ai(7)) == 6

    def test_score_5_ai_score_4(self):
        """AI score ≤ 4 → lead score 5."""
        assert calculate_lead_score(_live(True, True), _ai(4)) == 5

    def test_score_5_ai_score_1(self):
        """AI score = 1 (worst) → lead score 5."""
        assert calculate_lead_score(_live(True, True), _ai(1)) == 5

    def test_score_3_ai_score_5(self):
        """AI score = 5 → lead score 3."""
        assert calculate_lead_score(_live(True, True), _ai(5)) == 3

    def test_score_3_ai_score_6(self):
        """AI score = 6 → lead score 3."""
        assert calculate_lead_score(_live(True, True), _ai(6)) == 3

    def test_score_2_ai_score_7_without_biz(self):
        """AI score = 7 with no biz context → lead score 2 (upsell candidate)."""
        assert calculate_lead_score(_live(True, True), _ai(7)) == 2

    def test_score_2_ai_score_10_without_biz(self):
        """AI score = 10 with no biz context → lead score 2."""
        assert calculate_lead_score(_live(True, True), _ai(10)) == 2

    def test_score_1_well_established_override(self):
        """High AI score + many reviews + great rating → lead score 1 (skip).

        Directly covers the Bardenay / Fork false-positive case.
        """
        biz = {"review_count": 500, "rating": 4.7, "category": "restaurants"}
        assert calculate_lead_score(_live(True, True), _ai(9), biz) == 1

    def test_score_2_ai_high_but_few_reviews(self):
        """High AI score but few reviews — still an upsell candidate, not skip."""
        biz = {"review_count": 5, "rating": 4.9, "category": "restaurants"}
        assert calculate_lead_score(_live(True, True), _ai(9), biz) == 2

    def test_score_2_ai_high_but_mediocre_rating(self):
        """High AI score but mediocre rating — upsell candidate, not skip."""
        biz = {"review_count": 500, "rating": 3.8, "category": "restaurants"}
        assert calculate_lead_score(_live(True, True), _ai(9), biz) == 2


# ---------------------------------------------------------------------------
# Priority ordering — earlier conditions beat later ones
# ---------------------------------------------------------------------------


class TestPriorityOrder:
    def test_early_score_beats_ssl_check(self):
        """early_lead_score=10 wins even if has_ssl is False."""
        result = {"early_lead_score": 10, "has_ssl": False, "has_mobile_viewport": False}
        assert calculate_lead_score(result, _ai(1)) == 10

    def test_no_ssl_beats_no_viewport(self):
        """No HTTPS (score 7) wins over no viewport (score 6)."""
        assert calculate_lead_score(_live(has_ssl=False, has_viewport=False), _ai(7)) == 7

    def test_no_ssl_beats_ai_score(self):
        """No HTTPS wins over a bad AI score."""
        assert calculate_lead_score(_live(has_ssl=False, has_viewport=True), _ai(1)) == 7

    def test_no_viewport_beats_ai_score(self):
        """No viewport wins over a bad AI score."""
        assert calculate_lead_score(_live(has_ssl=True, has_viewport=False), _ai(1)) == 6


# ---------------------------------------------------------------------------
# AI score unavailable fallback
# ---------------------------------------------------------------------------


class TestAiScoreUnavailable:
    def test_null_ai_score_returns_3(self):
        """When AI score is None, fall back to 3 (mediocre)."""
        assert calculate_lead_score(_live(True, True), _ai(None)) == 3

    def test_empty_ai_result_returns_3(self):
        """Empty ai_result dict also falls back to 3."""
        assert calculate_lead_score(_live(True, True), {}) == 3


# ---------------------------------------------------------------------------
# Edge cases and robustness
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dicts_return_integer(self):
        """Completely empty inputs must return an integer, never raise."""
        result = calculate_lead_score({}, {})
        assert isinstance(result, int)

    def test_none_values_handled(self):
        """None values in eval_result don't crash."""
        result = {"early_lead_score": None, "has_ssl": None, "has_mobile_viewport": None}
        assert isinstance(calculate_lead_score(result, _ai(None)), int)

    def test_return_type_is_always_int(self):
        """Every code path returns a Python int."""
        cases = [
            (_early(10), _ai(None)),
            (_early(9), _ai(None)),
            (_early(8), _ai(None)),
            (_live(False, True), _ai(7)),
            (_live(True, False), _ai(7)),
            (_live(True, True), _ai(1)),
            (_live(True, True), _ai(4)),
            (_live(True, True), _ai(5)),
            (_live(True, True), _ai(6)),
            (_live(True, True), _ai(7)),
            (_live(True, True), _ai(10)),
            (_live(True, True), _ai(None)),
        ]
        for eval_r, ai_r in cases:
            r = calculate_lead_score(eval_r, ai_r)
            assert isinstance(r, int), f"Got {type(r)} for eval={eval_r}, ai={ai_r}"

    def test_score_always_in_valid_range(self):
        """Lead score must always be in 1–10."""
        cases = [
            (_early(10), _ai(None)),
            (_early(9), {}),
            (_early(8), {}),
            (_live(False, True), _ai(None)),
            (_live(True, False), _ai(None)),
            (_live(True, True), _ai(1)),
            (_live(True, True), _ai(10)),
            ({}, {}),
        ]
        for eval_r, ai_r in cases:
            r = calculate_lead_score(eval_r, ai_r)
            assert 1 <= r <= 10, f"Score {r} out of range for eval={eval_r}, ai={ai_r}"


# ---------------------------------------------------------------------------
# calculate_opportunity_score — finer 0-100 composite
# ---------------------------------------------------------------------------


class TestOpportunityScore:
    def test_clamped_to_valid_range(self):
        """opportunity_score is always in [0, 100]."""
        score = calculate_opportunity_score(
            _early(10),
            _ai(None),
            {"review_count": 0, "rating": 0, "category": "unknown"},
        )
        assert 0.0 <= score <= 100.0

    def test_high_review_high_rating_no_site_scores_near_top(self):
        """500-review 4.9-star HVAC with no site → near 100."""
        biz = {"review_count": 500, "rating": 4.9, "category": "HVAC", "is_claimed": False}
        score = calculate_opportunity_score(_early(10), _ai(None), biz)
        assert score >= 85

    def test_low_review_count_dampens_score(self):
        """Same category + no site, but 3 reviews ⇒ much lower score."""
        biz_few = {"review_count": 3, "rating": 4.9, "category": "HVAC"}
        biz_many = {"review_count": 500, "rating": 4.9, "category": "HVAC"}
        few = calculate_opportunity_score(_early(10), _ai(None), biz_few)
        many = calculate_opportunity_score(_early(10), _ai(None), biz_many)
        assert few < many

    def test_well_established_business_scores_low(self):
        """Bardenay-class lead → lead_score=1 via override → opp very low."""
        biz = {"review_count": 500, "rating": 4.7, "category": "restaurants"}
        score = calculate_opportunity_score(_live(True, True), _ai(9), biz)
        assert score <= 25

    def test_category_multiplier_applied(self):
        """Dentist scores higher than restaurant for identical signals."""
        eval_r = _early(10)
        ai_r = _ai(None)
        dentist = calculate_opportunity_score(
            eval_r, ai_r, {"review_count": 100, "rating": 4.5, "category": "dentist"}
        )
        restaurant = calculate_opportunity_score(
            eval_r, ai_r, {"review_count": 100, "rating": 4.5, "category": "restaurants"}
        )
        assert dentist > restaurant

    def test_rating_below_3_penalized_more_than_below_3_5(self):
        """<3.0 rating should get a stronger multiplier penalty than 3.0-3.49."""
        eval_r = _early(10)
        ai_r = _ai(None)
        common = {"review_count": 100, "category": "restaurants"}
        very_low = calculate_opportunity_score(eval_r, ai_r, {**common, "rating": 2.8})
        low = calculate_opportunity_score(eval_r, ai_r, {**common, "rating": 3.2})
        assert very_low < low

    def test_never_raises_on_garbage(self):
        """Handles None/missing fields gracefully."""
        score = calculate_opportunity_score({}, {}, {})
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0
