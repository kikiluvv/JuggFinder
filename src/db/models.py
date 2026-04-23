import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class JsonList(TypeDecorator):
    """Stores a Python list as a JSON string in a TEXT column."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return "[]"
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list:
        if value is None:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    place_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Email is discovered during website evaluation (mailto links + contact page).
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Google Maps extra fields (raw text and structured signals)
    hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_categories: Mapped[list] = mapped_column(JsonList, nullable=False, default=list)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_claimed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Website evaluation signals
    has_ssl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_mobile_viewport: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    website_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    copyright_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tech_stack: Mapped[list] = mapped_column(JsonList, nullable=False, default=list)

    # AI scoring fields
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_issues: Mapped[list] = mapped_column(JsonList, nullable=False, default=list)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lead scoring
    # lead_score is the coarse 1-10 display bucket (see scorer/lead.py rubric).
    # opportunity_score is a finer 0-100 composite used for ranking.
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Outreach & workflow
    outreach_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Set whenever the website evaluator + AI scorer run for this lead.
    # Distinct from created_at because we want to rescan stale leads.
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Lead id={self.id} name={self.name!r} score={self.lead_score}>"
