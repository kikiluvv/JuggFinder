"""Scrape control routes — POST /scrape/start, GET /scrape/status, GET /categories."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.schemas import CategoriesResponse, ScrapeStartRequest, ScrapeStatusResponse
from src.config.categories import CATEGORIES
from src.pipeline import get_scrape_state, run_scrape

router = APIRouter(tags=["scrape"])


@router.post("/scrape/start")
async def start_scrape(body: ScrapeStartRequest, background_tasks: BackgroundTasks):
    state = get_scrape_state()
    if state["running"]:
        raise HTTPException(status_code=409, detail="Scrape already in progress")

    background_tasks.add_task(run_scrape, body.categories)
    return {"ok": True, "message": f"Scrape started for: {body.categories}"}


@router.get("/scrape/status", response_model=ScrapeStatusResponse)
async def scrape_status():
    return ScrapeStatusResponse(**get_scrape_state())


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories():
    return CategoriesResponse(categories=CATEGORIES)
