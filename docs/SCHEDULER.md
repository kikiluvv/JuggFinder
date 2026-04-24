# Scheduler — Automated & Manual Scrape Triggers

## Overview
JuggFinder uses **APScheduler** (`apscheduler` package, `AsyncIOScheduler`) running inside the FastAPI process. There is no OS-level cron job or external scheduler required. As long as the FastAPI service is running, the daily scrape fires automatically.

## Scheduled Daily Job
- **Frequency:** Once per day
- **Default time:** 3:00 AM local time (configurable via `SCRAPE_SCHEDULE_TIME` in `.env`)
- **Categories scraped:** All configured categories (full run)
- **Behavior if service is offline:** The job does not run. It will resume on the next scheduled interval once the service restarts. There is no catch-up mechanism — missing a day is acceptable.

### APScheduler Configuration (FastAPI lifespan)
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_full_scrape,
        CronTrigger(hour=3, minute=0),  # configurable via env
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()
```

## Manual Scrape (UI-Triggered)
The dashboard provides a **"Scrape Now"** button that opens a category selection modal. The selected categories are sent to the API, which runs the scraper as a FastAPI `BackgroundTask`.

### API Endpoint
```
POST /scrape/start
Body: { "categories": ["all"] }
  or: { "categories": ["restaurants", "plumbers"] }
```

### Scrape Status Endpoint
```
GET /scrape/status
Response: { "running": true | false, "started_at": "...", "categories": [...] }
```
The frontend polls this endpoint every 5 seconds while a scrape is in progress to update the progress indicator in the UI.

## Category Configuration
Categories are defined in `src/config/categories.py` as a list of search query templates:
```python
CATEGORIES = [
    "restaurants",
    "auto repair",
    "hair salon",
    "plumbers",
    "electricians",
    "HVAC",
    "landscaping",
    "cleaning services",
    "contractors",
    "dentist",
    "chiropractor",
    "pet grooming",
    "local retail",
]
```
Each category is combined with the location string to form a Google Maps search query:
`"{category} Boise Idaho"`

## Concurrency Guard
Only one scrape job can run at a time. If the daily job fires while a manual scrape is already running (or vice versa), the new trigger is skipped and a warning is logged. This is enforced by a shared in-memory lock (`asyncio.Lock`).

## Logging
All scraper output is logged to:
- Console (stdout) — visible while the service is running
- `logs/scraper.log` — rotating file log, keeps last 7 days of history
