"""Dev-only routes — mounted only when `dev_pipeline_dry_run_enabled` is true."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.db.session import get_db
from src.dev.pipeline_dry_run import VALID_STEPS, execute_dry_run

router = APIRouter()


class DryRunRequest(BaseModel):
    """Subset of steps to run, in canonical order (seed → draft → simulate send → inbound)."""

    steps: list[str] = Field(
        default_factory=lambda: ["seed", "simulate_outreach_sent", "simulate_inbound"],
    )

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: list[str]) -> list[str]:
        if not v:
            return ["seed", "simulate_outreach_sent", "simulate_inbound"]
        bad = [s for s in v if s not in VALID_STEPS]
        if bad:
            raise ValueError(f"Unknown steps: {bad}. Valid: {sorted(VALID_STEPS)}")
        return v


class DryRunStepResult(BaseModel):
    step: str
    ok: bool
    detail: str | None = None


class DryRunResponse(BaseModel):
    lead_id: int | None
    results: list[DryRunStepResult]


@router.post("/pipeline-dry-run", response_model=DryRunResponse)
async def pipeline_dry_run(
    body: DryRunRequest,
    db: AsyncSession = Depends(get_db),
) -> DryRunResponse:
    """
    Seed or refresh the dev test lead, then optionally draft (real AI), simulate a sent
    email on the timeline only, and simulate an inbound reply. Never uses SMTP.
    """
    lead_id, raw = await execute_dry_run(
        db,
        steps=body.steps,
        business_name=settings.dev_pipeline_test_business_name,
        test_email=settings.dev_pipeline_test_email,
    )
    await db.commit()

    results = [DryRunStepResult(step=s, ok=o, detail=d) for s, o, d in raw]
    return DryRunResponse(lead_id=lead_id, results=results)
