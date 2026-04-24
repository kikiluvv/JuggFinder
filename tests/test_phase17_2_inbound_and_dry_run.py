"""Phase 17.2 — inbound capture API + dev pipeline dry-run (TEST BUSINESS fixture)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.dev_pipeline import router as dev_pipeline_router
from src.api.routes.leads import router as leads_router
from src.db.models import Base, Engagement, EngagementEvent, Lead
from src.db.session import get_db
from src.dev.pipeline_dry_run import DEV_TEST_PLACE_ID, execute_dry_run
from src.engagement.service import record_inbound_received

# Match defaults in settings / user pipeline test target
TEST_BUSINESS_NAME = "TEST BUSINESS"
TEST_EMAIL = "1kikiluvv@gmail.com"


@pytest.fixture
async def memory_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with Session() as session:
            yield session

    yield Session, override_get_db
    await engine.dispose()


@pytest.fixture
async def leads_api_client(memory_session_factory):
    """Leads routes only — no app lifespan (avoids touching real leads.db / scheduler)."""
    Session, override_get_db = memory_session_factory
    mini = FastAPI()
    mini.include_router(leads_router)
    mini.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=mini)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with Session() as s:
            s.add(
                Lead(
                    name=TEST_BUSINESS_NAME,
                    email=TEST_EMAIL,
                    lead_score=9,
                    category="test",
                )
            )
            await s.commit()
            res = await s.execute(select(Lead))
            lead_id = res.scalar_one().id
        yield ac, lead_id
    mini.dependency_overrides.clear()


@pytest.fixture
async def dev_only_client(memory_session_factory):
    """Mini ASGI app with only /dev routes so dry-run tests never need env flags."""
    Session, override_get_db = memory_session_factory
    mini = FastAPI()
    mini.include_router(dev_pipeline_router, prefix="/dev")
    mini.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=mini)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    mini.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_inbound_creates_timeline_event(leads_api_client):
    client, lead_id = leads_api_client
    payload = {
        "from_email": TEST_EMAIL,
        "to_email": "you@example.com",
        "subject": "Re: hello",
        "body": "Interested in learning more.",
        "message_id": "<abc@mail.gmail.com>",
    }
    r = await client.post(f"/leads/{lead_id}/inbound", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["lead_id"] == lead_id
    assert data["event"]["event_type"] == "inbound_received"
    assert data["event"]["payload"]["from_email"] == TEST_EMAIL.lower()
    assert "Interested" in data["event"]["payload"]["body"]

    g = await client.get(f"/leads/{lead_id}/engagement")
    assert g.status_code == 200
    evs = g.json()["events"]
    assert len(evs) == 1
    assert evs[0]["event_type"] == "inbound_received"


@pytest.mark.asyncio
async def test_post_inbound_404_unknown_lead(leads_api_client):
    client, _lead_id = leads_api_client
    r = await client.post(
        "/leads/99999/inbound",
        json={
            "from_email": TEST_EMAIL,
            "to_email": "x@y.com",
            "subject": "Hi",
            "body": "Body",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_record_inbound_unit(memory_session_factory):
    Session, _ = memory_session_factory
    async with Session() as db:
        db.add(Lead(name="X", lead_score=5))
        await db.commit()
        res = await db.execute(select(Lead))
        lid = res.scalar_one().id
        ev = await record_inbound_received(
            db,
            lead_id=lid,
            from_email=TEST_EMAIL,
            to_email="owner@test.com",
            subject="Hello",
            body="Reply text",
        )
        await db.commit()
        assert ev.event_type == "inbound_received"


@pytest.mark.asyncio
async def test_execute_dry_run_default_steps(memory_session_factory):
    Session, _ = memory_session_factory
    async with Session() as db:
        lead_id, results = await execute_dry_run(
            db,
            steps=["seed", "simulate_outreach_sent", "simulate_inbound"],
            business_name=TEST_BUSINESS_NAME,
            test_email=TEST_EMAIL,
        )
        await db.commit()
        assert lead_id is not None
        assert all(ok for _s, ok, _d in results)
        row = (
            await db.execute(select(Lead).where(Lead.place_id == DEV_TEST_PLACE_ID))
        ).scalar_one()
        assert row.name == TEST_BUSINESS_NAME
        assert row.email == TEST_EMAIL.lower()

    async with Session() as db:
        eng = (
            await db.execute(select(Engagement).where(Engagement.lead_id == lead_id))
        ).scalar_one()
        evs = (
            (
                await db.execute(
                    select(EngagementEvent)
                    .where(EngagementEvent.engagement_id == eng.id)
                    .order_by(EngagementEvent.id.asc()),
                )
            )
            .scalars()
            .all()
        )
    types = [e.event_type for e in evs]
    assert "outreach_sent" in types
    assert "inbound_received" in types
    assert any(
        e.event_type == "outreach_sent"
        and e.payload
        and e.payload.get("dry_run") is True
        for e in evs
    )


@pytest.mark.asyncio
async def test_execute_dry_run_draft_mocked(monkeypatch, memory_session_factory):
    async def fake_draft(_lead: dict) -> str:
        return "Mocked outreach draft for tests."

    monkeypatch.setattr("src.dev.pipeline_dry_run.draft_outreach", fake_draft)
    Session, _ = memory_session_factory
    async with Session() as db:
        lead_id, results = await execute_dry_run(
            db,
            steps=["seed", "draft"],
            business_name=TEST_BUSINESS_NAME,
            test_email=TEST_EMAIL,
        )
        await db.commit()
        assert lead_id is not None
        by_step = {s: (ok, d) for s, ok, d in results}
        assert by_step["seed"][0] is True
        assert by_step["draft"][0] is True

    async with Session() as db:
        lead = (await db.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
        assert "Mocked outreach" in (lead.outreach_draft or "")


@pytest.mark.asyncio
async def test_dev_pipeline_http_endpoint(dev_only_client):
    r = await dev_only_client.post(
        "/dev/pipeline-dry-run",
        json={"steps": ["seed", "simulate_outreach_sent"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["lead_id"] is not None
    assert all(x["ok"] for x in body["results"])
