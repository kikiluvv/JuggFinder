"""FastAPI application entry point — includes scheduler, DB init, and all routes."""

from contextlib import asynccontextmanager

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.leads import router as leads_router
from src.api.routes.scrape import router as scrape_router
from src.api.routes.settings import router as settings_router
from src.app_state import scheduler
from src.config.categories import CATEGORIES
from src.config.settings import settings
from src.db.session import ensure_schema
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _parse_schedule_time(time_str: str) -> tuple[int, int]:
    hour, minute = time_str.split(":")
    return int(hour), int(minute)


async def _scheduled_scrape() -> None:
    """Wrapper for the daily job — catches RuntimeError if a scrape is already running."""
    from src.pipeline import run_scrape

    try:
        await run_scrape(CATEGORIES)
    except RuntimeError as e:
        logger.warning(f"Scheduled scrape skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JuggFinder starting up...")

    # 1. Ensure DB schema is current (create table + apply additive migrations)
    await ensure_schema()
    logger.info("Database ready.")

    # 2. Register and start the daily scrape job
    hour, minute = _parse_schedule_time(settings.scrape_schedule_time)
    scheduler.add_job(
        _scheduled_scrape,
        CronTrigger(hour=hour, minute=minute),
        id="daily_scrape",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    next_run = scheduler.get_job("daily_scrape").next_run_time
    logger.info(f"Scheduler running. Next daily scrape: {next_run}")

    yield

    scheduler.shutdown(wait=False)
    logger.info("JuggFinder shutting down.")


app = FastAPI(
    title="JuggFinder API",
    description="Local freelance lead generator for Boise, Idaho.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads_router)
app.include_router(scrape_router)
app.include_router(settings_router)

if settings.dev_pipeline_dry_run_enabled:
    from src.api.routes.dev_pipeline import router as dev_pipeline_router

    logger.warning(
        "DEV_PIPELINE_DRY_RUN_ENABLED is true — POST /dev/pipeline-dry-run is mounted. "
        "Disable before exposing this API to a network."
    )
    app.include_router(dev_pipeline_router, prefix="/dev", tags=["dev"])


@app.get("/health")
async def health():
    return {"status": "ok"}
