import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
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
    outreach_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outreach_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<AppSetting key={self.key!r}>"


class OutreachSuppression(Base):
    __tablename__ = "outreach_suppressions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<OutreachSuppression id={self.id} email={self.email!r}>"


class OutreachSendLog(Base):
    __tablename__ = "outreach_send_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_email: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # sent | blocked | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<OutreachSendLog id={self.id} to={self.to_email!r} status={self.status!r}>"


class Engagement(Base):
    """One conversation thread per lead + channel (e.g. email)."""

    __tablename__ = "engagements"
    __table_args__ = (UniqueConstraint("lead_id", "channel", name="uq_engagements_lead_channel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="email")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Engagement id={self.id} lead_id={self.lead_id} channel={self.channel!r}>"


class EngagementEvent(Base):
    """Append-only timeline row for an engagement."""

    __tablename__ = "engagement_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outreach_send_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EngagementEvent id={self.id} type={self.event_type!r}>"
