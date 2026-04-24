# Phase 14 — End-to-End Integration & Verification

## Goal
Run the full system from a cold start, verify that all components work together, and confirm the app is usable as a daily lead discovery tool.

## Completion Criteria
- [ ] Cold start from scratch (empty DB) works without manual intervention
- [ ] Manual scrape from the UI produces records visible in the table within minutes
- [ ] Scheduled job is registered and fires at the correct time (verify via scheduler logs)
- [ ] All API endpoints return correct data under realistic conditions
- [ ] Deduplication works — re-running the same category produces no duplicate rows
- [ ] AI scorer fallback works — can be tested by temporarily setting a bogus Gemini key
- [ ] Lead table renders and filters correctly with real data
- [ ] Side drawer shows full detail for a selected lead
- [ ] Status and notes changes persist across page refresh
- [ ] Scraping indicator appears when a scrape runs and disappears when it finishes
- [ ] `ruff check src/` returns zero errors

---

## Cold Start Checklist

1. Copy `.env.example` to `.env` and fill in real API keys
2. `uv run playwright install chromium`
3. `uv run uvicorn src.main:app --reload --port 8000` — confirm DB created, scheduler started
4. `cd frontend && npm run dev` — confirm UI loads at `localhost:5173`
5. Click "Scrape Now" → select one category → click "Start Scrape"
6. Watch the scraping indicator appear
7. Wait for the scrape to finish (1 category ≈ 2–5 minutes)
8. Confirm leads appear in the table with scores, websites, and statuses
9. Click a lead — confirm all fields in the drawer are populated
10. Change a status — confirm it persists on refresh

---

## Smoke Test Scenarios

| Scenario | Expected Result |
|---|---|
| Scrape with no API keys | AI fields are `null`, lead scores still assigned from rubric |
| Re-scrape same category | No new rows added (dedup blocks all) |
| Network down during scrape | Scraper logs errors, continues, partial results saved |
| Two simultaneous scrape triggers | Second trigger returns 409, first continues unaffected |
| Gemini 429 during session | Groq takes over; `ai_score` still populated |
| Both AI APIs fail | `ai_score = null`, lead still saved with rubric-based score |
| Lead table with 0 results | Empty state shown, not an error |
| Filter to Score 8–10 | Only no-website / social / broken-website leads shown |

---

## Performance Notes

- A full 13-category scrape at 60 results/category ≈ 780 businesses ≈ 15–30 minutes (most time is sleeps + AI calls).
- The UI should remain fully responsive during a background scrape (it's all async).
- If the AI rate limit is consistently hit, consider reducing AI calls or accepting more `null` ai_scores.

---

## Final Cleanup Before Calling It Done

- [ ] Remove any `print()` debug statements — use the logger
- [ ] All `TODO` comments resolved or filed as known limitations
- [ ] `ruff format src/` applied
- [ ] `README.md` has complete setup and run instructions
- [ ] `.env` is in `.gitignore` and never committed
- [ ] `leads.db` is in `.gitignore`
- [ ] `logs/` is in `.gitignore`
