# Phase 08 — Scraper Pipeline

## Goal
Wire all previous stages (Maps scraper → website evaluator → AI scorer → lead scorer → DB write) into a single async pipeline function. This is the core orchestration layer that the scheduler and API both call.

## Completion Criteria
- [ ] `run_scrape(categories: list[str]) -> None` runs the full pipeline end-to-end
- [ ] One Chromium instance opened for the entire run, closed on completion
- [ ] Each business flows through all stages in sequence before the next is processed
- [ ] All DB writes are committed after each business (not batched) so partial runs are safe
- [ ] Concurrency lock prevents two pipeline runs at the same time
- [ ] Progress is logged at each stage
- [ ] Pipeline continues if any individual business fails at any stage

---

## File: `src/pipeline.py`

### Concurrency lock (module-level)

```python
import asyncio

_scrape_lock = asyncio.Lock()
_scrape_state: dict = {"running": False, "started_at": None, "categories": []}
```

Expose `_scrape_state` as the source of truth for `GET /scrape/status`.

### Main function

```python
async def run_scrape(categories: list[str]) -> None:
    if _scrape_lock.locked():
        raise RuntimeError("A scrape is already running.")

    async with _scrape_lock:
        _scrape_state.update({"running": True, "started_at": datetime.utcnow().isoformat(), "categories": categories})
        try:
            await _execute_scrape(categories)
        finally:
            _scrape_state.update({"running": False, "started_at": None, "categories": []})
```

### `_execute_scrape` logic

```python
async def _execute_scrape(categories: list[str]) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            async with SessionLocal() as db:
                for category in categories:
                    logger.info(f"Scraping category: {category}")
                    businesses = await scrape_category(category, db, browser)
                    for biz in businesses:
                        await _process_business(biz, db)
                    await asyncio.sleep(random.uniform(10, 20))
        finally:
            await browser.close()
```

### `_process_business` logic

```python
async def _process_business(biz: dict, db: AsyncSession) -> None:
    try:
        eval_result = await evaluate_website(biz.get("website_url"))
        ai_result = {"score": None, "issues": [], "summary": None}

        if not eval_result["skip_ai"] and eval_result.get("html_snippet"):
            ai_result = await score_with_ai(eval_result["html_snippet"])

        lead_score = calculate_lead_score(eval_result, ai_result)

        lead = Lead(
            place_id=biz.get("place_id"),
            name=biz["name"],
            category=biz.get("category"),
            address=biz.get("address"),
            phone=biz.get("phone"),
            website_url=eval_result.get("website_url"),
            rating=biz.get("rating"),
            review_count=biz.get("review_count"),
            has_ssl=eval_result.get("has_ssl"),
            has_mobile_viewport=eval_result.get("has_mobile_viewport"),
            website_status_code=eval_result.get("website_status_code"),
            copyright_year=eval_result.get("copyright_year"),
            ai_score=ai_result.get("score"),
            ai_issues=json.dumps(ai_result.get("issues", [])),
            ai_summary=ai_result.get("summary"),
            lead_score=lead_score,
            status="new",
        )
        db.add(lead)
        await db.commit()
        logger.info(f"Saved: {biz['name']} — score {lead_score}")

    except Exception as e:
        logger.error(f"Failed to process {biz.get('name', '?')}: {e}")
        await db.rollback()
```

---

## Done When
Calling `asyncio.run(run_scrape(["restaurants"]))` from the command line completes without crashing, and `leads.db` contains new rows with all fields populated.
