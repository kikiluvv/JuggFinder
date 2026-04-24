# Phase 04 — Google Maps Scraper

## Goal
Build the Playwright-based discovery stage that searches Google Maps for Boise businesses by category, extracts structured data, and deduplicates against the database before returning results.

## Completion Criteria
- [ ] `scrape_category(category: str, db: AsyncSession) -> list[dict]` works end-to-end
- [ ] Returns fields: `name`, `address`, `phone`, `website_url`, `rating`, `review_count`, `place_id`, `category`
- [ ] Skips businesses already in DB (checks `place_id` first, then `name + address`)
- [ ] Respects all sleep timings from `.cursorrules`
- [ ] One Chromium instance per scrape session (not per query)
- [ ] Handles scroll-to-load-more until results exhausted or `max_results` hit (default 60)
- [ ] All errors are caught and logged; scraper continues without crashing

---

## File: `src/scraper/maps.py`

### Key Design Points

**Query construction:**
```python
query = f"{category} Boise Idaho"
```

**Sleep policy (must be randomized):**
```python
import asyncio, random

await asyncio.sleep(random.uniform(2, 4))   # between page scrolls
await asyncio.sleep(random.uniform(10, 20)) # between category queries
```

**Playwright session:**
- Launch one Chromium browser at the pipeline level, pass the `page` object into the scraper.
- Use `browser.new_page()` per category query (so each query gets a clean context).
- `headless=True` is fine; set a realistic `user_agent`.

**Scrolling strategy:**
- After navigating to the Maps search results, locate the scrollable results sidebar (the `div` with role `feed` or the left-panel list).
- Scroll it in increments, waiting for new results to load each time.
- Stop scrolling when the result count stops increasing OR `max_results` is reached.

**Data extraction per listing:**
- Click each listing card to reveal the detail panel, then extract fields from the DOM.
- Or extract from the card directly if all fields are present — prefer clicking for completeness.

**Deduplication check (before yielding):**
```python
# Check place_id first
existing = await db.execute(select(Lead).where(Lead.place_id == place_id))
if existing.scalar_one_or_none():
    continue

# Fallback: name + address
existing = await db.execute(
    select(Lead).where(Lead.name == name, Lead.address == address)
)
if existing.scalar_one_or_none():
    continue
```

---

## Error Handling

- Wrap the entire category scrape in a `try/except` block.
- On `playwright.errors.TimeoutError` or any network error: log the error, return whatever results were collected so far.
- Never let one bad listing crash the whole category run.
- Use `tenacity` for any retry logic around page navigation or element waits.

---

## Done When
Running `scrape_category("restaurants", db)` returns at least a handful of real Boise restaurant records with valid fields, and re-running it skips all records already in the DB.
