# Phase 03 — Config & Categories

## Goal
Centralize all configuration so every module reads from a single source of truth. No magic strings scattered across the codebase.

## Completion Criteria
- [ ] `src/config/settings.py` loads all env vars with proper types and defaults
- [ ] `src/config/categories.py` exports the `CATEGORIES` list
- [ ] Importing `settings` from anywhere in `src/` works without error
- [ ] Missing required env vars (API keys) raise a clear error at startup, not at call time

---

## `src/config/settings.py`

Use `pydantic-settings` (`BaseSettings`) to load from `.env`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    groq_api_key: str
    database_url: str = "sqlite+aiosqlite:///./leads.db"
    scrape_schedule_time: str = "03:00"   # "HH:MM" format
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

> Note: add `pydantic-settings` to dependencies — `uv add pydantic-settings`.

---

## `src/config/categories.py`

```python
CATEGORIES: list[str] = [
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

These are the exact strings appended with `" Boise Idaho"` to form Maps search queries.

---

## Logging Setup

Configure a module-level logger in a shared utility (e.g., `src/utils/logging.py`) using Python's `logging` stdlib with a `RotatingFileHandler` targeting `logs/scraper.log`. All other modules import from this. Log level comes from `settings.log_level`.

---

## Done When
`from src.config.settings import settings` and `from src.config.categories import CATEGORIES` both import cleanly and values are correct when inspected.
