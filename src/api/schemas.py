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
    outreach_sent_at: datetime | None
    outreach_last_error: str | None
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


class OutreachSendRequest(BaseModel):
    subject: str | None = None
    body: str | None = None


class OutreachSendResponse(BaseModel):
    lead_id: int
    to_email: str
    subject: str
    sent_at: datetime


class SettingsResponse(BaseModel):
    # Keys are never returned (only "is set" flags)
    gemini_api_key_set: bool
    groq_api_key_set: bool

    gemini_model: str
    groq_model: str

    scrape_schedule_time: str
    scrape_location: str
    scrape_max_results: int
    scrape_headless: bool
    scrape_user_agent: str

    outreach_send_enabled: bool
    outreach_sender_name: str
    outreach_sender_email: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_tls: bool
    smtp_password_set: bool


class SettingsUpdateRequest(BaseModel):
    # Optional: only provided fields are updated.
    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    gemini_model: str | None = None
    groq_model: str | None = None

    scrape_schedule_time: str | None = None
    scrape_location: str | None = None
    scrape_max_results: int | None = None
    scrape_headless: bool | None = None
    scrape_user_agent: str | None = None

    outreach_send_enabled: bool | None = None
    outreach_sender_name: str | None = None
    outreach_sender_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool | None = None


class OutreachPolicyResponse(BaseModel):
    outreach_enabled: bool
    outreach_daily_send_cap: int
    outreach_send_window_start: str
    outreach_send_window_end: str
    outreach_send_timezone: str
    outreach_enforce_window: bool
    outreach_enforce_daily_cap: bool
    outreach_enforce_suppression: bool
    outreach_allowed_statuses: list[str]


class OutreachPolicyUpdateRequest(BaseModel):
    outreach_enabled: bool | None = None
    outreach_daily_send_cap: int | None = None
    outreach_send_window_start: str | None = None
    outreach_send_window_end: str | None = None
    outreach_send_timezone: str | None = None
    outreach_enforce_window: bool | None = None
    outreach_enforce_daily_cap: bool | None = None
    outreach_enforce_suppression: bool | None = None
    outreach_allowed_statuses: list[str] | None = None


class SuppressionItem(BaseModel):
    id: int
    email: str
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuppressionAddRequest(BaseModel):
    email: str
    reason: str | None = None
