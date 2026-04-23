"""Pydantic schemas for all API request/response bodies."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class LeadSummary(BaseModel):
    id: int
    name: str
    category: str | None
    lead_score: int
    opportunity_score: float | None
    website_url: str | None
    email: str | None
    phone: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadDetail(LeadSummary):
    address: str | None
    rating: float | None
    review_count: int | None
    hours: str | None
    google_categories: list[str]
    business_description: str | None
    photo_count: int | None
    is_claimed: bool | None
    has_ssl: bool | None
    has_mobile_viewport: bool | None
    website_status_code: int | None
    copyright_year: int | None
    tech_stack: list[str]
    ai_score: int | None
    ai_issues: list[str]
    ai_summary: str | None
    outreach_draft: str | None
    notes: str | None
    updated_at: datetime
    last_scanned_at: datetime | None

    model_config = {"from_attributes": True}


class LeadUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    outreach_draft: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        valid = {"new", "reviewed", "interested", "archived"}
        if v is not None and v not in valid:
            raise ValueError(f"status must be one of {valid}")
        return v


class LeadsResponse(BaseModel):
    leads: list[LeadSummary]
    total: int
    page: int
    pages: int


class StatsResponse(BaseModel):
    total: int
    new_today: int
    avg_score: float


class ScrapeStartRequest(BaseModel):
    categories: list[str]

    @field_validator("categories")
    @classmethod
    def must_not_be_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("categories must contain at least one entry")
        return v


class ScrapeStatusResponse(BaseModel):
    running: bool
    started_at: str | None
    categories: list[str]
    # Phase 15 progress fields
    current_category: str | None = None
    categories_done: int = 0
    categories_total: int = 0
    businesses_processed: int = 0
    new_leads: int = 0
    selector_health: dict = {}
    error: str | None = None


class CategoriesResponse(BaseModel):
    categories: list[str]


class OutreachDraftResponse(BaseModel):
    lead_id: int
    draft: str
