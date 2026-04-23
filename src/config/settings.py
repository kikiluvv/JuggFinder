from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- API keys (required) ---
    gemini_api_key: str
    groq_api_key: str

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./leads.db"

    # --- Scheduler ---
    scrape_schedule_time: str = "03:00"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Scraper tuning (overridable via env) ---
    scrape_location: str = "Boise Idaho"
    scrape_max_results: int = 60
    scrape_headless: bool = True
    # Optional UA override. If empty, the scraper rotates through a curated
    # pool of modern UAs to blend with real traffic.
    scrape_user_agent: str = ""

    # --- AI models (swappable when vendors deprecate) ---
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("gemini_api_key", "groq_api_key")
    @classmethod
    def keys_must_not_be_empty(cls, v: str, info: object) -> str:
        if not v or not v.strip():
            field = getattr(info, "field_name", "api_key")
            raise ValueError(
                f"{field} is required but not set. Add it to your .env file (see .env.example)."
            )
        return v

    @field_validator("scrape_schedule_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        try:
            hour, minute = v.split(":")
            if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError(
                f"SCRAPE_SCHEDULE_TIME must be HH:MM format (e.g. '03:00'), got: {v!r}"
            )
        return v

    @field_validator("scrape_max_results")
    @classmethod
    def validate_max_results(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError(f"SCRAPE_MAX_RESULTS must be 1–500, got: {v}")
        return v


settings = Settings()
