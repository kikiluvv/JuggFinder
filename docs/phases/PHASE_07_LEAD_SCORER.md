# Phase 07 — Lead Scorer

## Goal
Apply the rubric-based scoring logic to produce the final `lead_score` (1–10) from the combined output of the evaluator and AI scorer. This is a pure function — no I/O, no async.

## Completion Criteria
- [ ] `calculate_lead_score(eval_result: dict, ai_result: dict) -> int` is a pure function
- [ ] Returns correct score for every condition in the rubric
- [ ] First matching condition wins (priority order enforced)
- [ ] Never raises an exception — defaults to `1` if no condition matches

---

## File: `src/scorer/lead.py`

### Rubric (from `INTEGRATION.md`, applied in priority order)

| Condition | Lead Score |
|---|---|
| No website URL at all | **10** |
| URL is a Facebook / Yelp / social media page | **9** |
| Website returns 4xx or 5xx HTTP status | **8** |
| Website exists but no HTTPS | **7** |
| Website has no mobile viewport meta tag | **6** |
| Website is outdated — AI score ≤ 4 | **5** |
| Website is mediocre — AI score 5–6 | **3** |
| Website is decent — AI score ≥ 7 | **1** |

### Implementation

```python
def calculate_lead_score(eval_result: dict, ai_result: dict) -> int:
    """
    Pure function. First matching condition wins.
    eval_result: output of evaluate_website()
    ai_result:   output of score_with_ai() — may have score=None
    """
    # Conditions 10, 9, 8 — set by evaluator as early_lead_score
    if eval_result.get("early_lead_score") is not None:
        return eval_result["early_lead_score"]

    # Condition 7 — no HTTPS
    if not eval_result.get("has_ssl"):
        return 7

    # Condition 6 — no mobile viewport
    if not eval_result.get("has_mobile_viewport"):
        return 6

    # Conditions 5, 3, 1 — based on AI score
    ai_score = ai_result.get("score")
    if ai_score is not None:
        if ai_score <= 4:
            return 5
        if ai_score <= 6:
            return 3
        return 1

    # AI score unavailable — fall back to a middle score
    return 3
```

---

## Note on Separation of Fields

`lead_score` (this module) and `ai_score` (Phase 06) are **separate fields** stored in the DB.

- `ai_score` = raw quality score from Gemini/Groq (1–10 scale, their interpretation)
- `lead_score` = composite opportunity score from the rubric above (how good is this as a sales lead)

Never mix them. Never overwrite one with the other.

---

## Done When
Unit tests cover every row of the rubric. `calculate_lead_score({"early_lead_score": 10}, {})` returns `10`. `calculate_lead_score({"has_ssl": True, "has_mobile_viewport": True}, {"score": 3})` returns `5`.
