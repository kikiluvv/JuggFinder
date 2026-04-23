"""
Async integration tests for the deduplication logic in src/scraper/maps.py.

Uses a real in-memory SQLite database so we test the actual SQL queries,
not just mocks. These tests are fast and require no network access.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base, Lead
from src.scraper.maps import is_duplicate

# In-memory SQLite for tests — isolated per test function via fresh engine
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db():
    """Provide a fresh in-memory database session for each test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _insert_lead(db: AsyncSession, **kwargs) -> Lead:
    """Helper to insert a minimal Lead row for testing."""
    defaults = {
        "name": "Test Business",
        "lead_score": 5,
        "status": "new",
        "ai_issues": [],
    }
    defaults.update(kwargs)
    lead = Lead(**defaults)
    db.add(lead)
    await db.commit()
    return lead


# ---------------------------------------------------------------------------
# place_id deduplication
# ---------------------------------------------------------------------------


class TestDedupByPlaceId:
    async def test_no_duplicate_when_db_empty(self, db):
        biz = {"place_id": "ChIJabc123", "name": "New Business", "address": "123 Main St"}
        assert await is_duplicate(biz, db) is False

    async def test_detects_duplicate_by_place_id(self, db):
        await _insert_lead(db, place_id="ChIJabc123", name="Existing Biz")
        biz = {"place_id": "ChIJabc123", "name": "Different Name", "address": "Anywhere"}
        assert await is_duplicate(biz, db) is True

    async def test_different_place_id_not_duplicate(self, db):
        await _insert_lead(db, place_id="ChIJabc123", name="Biz A")
        biz = {"place_id": "ChIJxyz999", "name": "Biz A", "address": "Same address"}
        assert await is_duplicate(biz, db) is False

    async def test_place_id_takes_priority_over_name_address(self, db):
        """Even if name+address differ, a matching place_id is a duplicate."""
        await _insert_lead(
            db,
            place_id="ChIJabc123",
            name="Biz A",
            address="123 Main St",
        )
        biz = {
            "place_id": "ChIJabc123",
            "name": "Biz A Updated Name",  # name changed
            "address": "456 Other St",  # address changed
        }
        assert await is_duplicate(biz, db) is True

    async def test_hex_place_id_format(self, db):
        await _insert_lead(db, place_id="0x54aef872:0x6e7c1a7d", name="Old Biz")
        biz = {"place_id": "0x54aef872:0x6e7c1a7d", "name": "Old Biz"}
        assert await is_duplicate(biz, db) is True


# ---------------------------------------------------------------------------
# name + address fallback deduplication
# ---------------------------------------------------------------------------


class TestDedupByNameAddress:
    async def test_detects_duplicate_by_name_and_address(self, db):
        await _insert_lead(db, name="Joe's Diner", address="100 Grove St, Boise, ID")
        biz = {
            "place_id": None,  # no place_id
            "name": "Joe's Diner",
            "address": "100 Grove St, Boise, ID",
        }
        assert await is_duplicate(biz, db) is True

    async def test_same_name_different_address_not_duplicate(self, db):
        await _insert_lead(db, name="Joe's Diner", address="100 Grove St, Boise, ID")
        biz = {
            "place_id": None,
            "name": "Joe's Diner",
            "address": "200 Oak Ave, Boise, ID",  # different address
        }
        assert await is_duplicate(biz, db) is False

    async def test_different_name_same_address_not_duplicate(self, db):
        await _insert_lead(db, name="Joe's Diner", address="100 Grove St, Boise, ID")
        biz = {
            "place_id": None,
            "name": "Maria's Cafe",  # different name
            "address": "100 Grove St, Boise, ID",
        }
        assert await is_duplicate(biz, db) is False

    async def test_no_address_skips_name_address_check(self, db):
        """If address is None, we can't do name+address check — should not false-positive."""
        await _insert_lead(db, name="Joe's Diner", address="100 Grove St")
        biz = {
            "place_id": None,
            "name": "Joe's Diner",
            "address": None,  # unknown address
        }
        assert await is_duplicate(biz, db) is False

    async def test_no_place_id_falls_back_to_name_address(self, db):
        """Explicitly verify the fallback path is used when place_id is absent."""
        await _insert_lead(db, place_id=None, name="Boise Barber", address="50 Capitol Blvd")
        biz = {
            "place_id": None,
            "name": "Boise Barber",
            "address": "50 Capitol Blvd",
        }
        assert await is_duplicate(biz, db) is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDedupEdgeCases:
    async def test_empty_biz_dict_not_duplicate(self, db):
        assert await is_duplicate({}, db) is False

    async def test_biz_with_only_name_not_duplicate(self, db):
        """Only name, no place_id or address — can't match anything."""
        await _insert_lead(db, name="Solo Name Biz", address="123 St")
        biz = {"name": "Solo Name Biz"}
        assert await is_duplicate(biz, db) is False

    async def test_multiple_leads_in_db(self, db):
        """With multiple leads, only the matching one is detected."""
        await _insert_lead(db, place_id="ChIJ001", name="Biz One", address="1 St")
        await _insert_lead(db, place_id="ChIJ002", name="Biz Two", address="2 St")
        await _insert_lead(db, place_id="ChIJ003", name="Biz Three", address="3 St")

        assert await is_duplicate({"place_id": "ChIJ002"}, db) is True
        assert await is_duplicate({"place_id": "ChIJ999"}, db) is False

    async def test_idempotent_scrape_simulation(self, db):
        """
        Simulate a re-scrape: all previously-scraped businesses should be
        detected as duplicates, so nothing new is added.
        """
        businesses = [
            {"place_id": f"ChIJ{i:03d}", "name": f"Biz {i}", "address": f"{i} Main St"}
            for i in range(5)
        ]
        # First run: insert all
        for biz in businesses:
            await _insert_lead(db, **{k: v for k, v in biz.items() if k != "address"})

        # Second run: all should be duplicates
        for biz in businesses:
            assert await is_duplicate(biz, db) is True, f"Should be duplicate: {biz}"
