# Phase 10 — APScheduler Integration

## Goal
Register the daily scrape job inside the FastAPI process using APScheduler, wired through the `lifespan` context manager. No OS-level cron. No external scheduler.

## Completion Criteria
- [ ] Scheduler starts when FastAPI starts; shuts down cleanly on exit
- [ ] Daily job fires at the time specified by `SCRAPE_SCHEDULE_TIME` in `.env`
- [ ] Scheduled job calls `run_scrape(CATEGORIES)` — full category list
- [ ] If a manual scrape is already running when the daily job fires, the daily job is skipped (not queued)
- [ ] `create_all()` for the DB is also called inside `lifespan` before the scheduler starts

---

## File: `src/main.py` — Full Lifespan Setup

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from src.config.categories import CATEGORIES
from src.config.settings import settings
from src.db.models import Base
from src.db.session import engine
from src.pipeline import run_scrape

scheduler = AsyncIOScheduler()

def _parse_schedule_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute) integers."""
    hour, minute = time_str.split(":")
    return int(hour), int(minute)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create DB tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Register and start the daily scrape job
    hour, minute = _parse_schedule_time(settings.scrape_schedule_time)
    scheduler.add_job(
        run_scrape,
        CronTrigger(hour=hour, minute=minute),
        args=[CATEGORIES],
        id="daily_scrape",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late start
    )
    scheduler.start()

    yield  # App is running

    scheduler.shutdown(wait=False)

app = FastAPI(title="JuggFinder API", lifespan=lifespan)
```

---

## Concurrency: Daily Job + Manual Scrape

The `_scrape_lock` in `pipeline.py` handles this automatically. If the lock is already held (manual scrape running), `run_scrape()` raises `RuntimeError("A scrape is already running.")`. The scheduler should catch and log this:

```python
async def _scheduled_scrape():
    try:
        await run_scrape(CATEGORIES)
    except RuntimeError as e:
        logger.warning(f"Scheduled scrape skipped: {e}")
```

Pass `_scheduled_scrape` to `scheduler.add_job` instead of `run_scrape` directly, so the error is caught gracefully.

---

## Done When
Starting the FastAPI server logs a message confirming the scheduler is running and shows the next scheduled fire time. Verifying via `scheduler.get_jobs()` shows the daily job is registered.
