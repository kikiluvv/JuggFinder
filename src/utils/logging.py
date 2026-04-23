import logging
import logging.handlers
from pathlib import Path

from src.config.settings import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_file_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_DIR / "scraper.log",
    when="midnight",
    backupCount=7,
    encoding="utf-8",
)
_file_handler.setFormatter(_fmt)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)

_level = getattr(logging, settings.log_level.upper(), logging.INFO)

# Configure root logger directly so it works regardless of import order.
root = logging.getLogger()
root.setLevel(_level)
if not root.handlers:
    root.addHandler(_file_handler)
    root.addHandler(_console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Import this everywhere instead of using logging directly."""
    return logging.getLogger(name)
