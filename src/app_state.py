"""
Shared application state that must be imported by both the FastAPI app entry
point and individual route modules without creating circular imports.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Global scheduler instance (started in src/main.py lifespan)
scheduler = AsyncIOScheduler()
