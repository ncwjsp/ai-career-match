from fastapi import APIRouter

from app.contracts.models import FixtureBundle
from app.modules.explanations.router import router as explanations_router
from app.modules.jobs.router import router as jobs_router
from app.modules.matching.router import router as matching_router
from app.modules.resume.router import router as resume_router
from app.testing.fixtures import load_fixtures

router = APIRouter()
router.include_router(explanations_router)
router.include_router(resume_router)
router.include_router(jobs_router)
router.include_router(matching_router)


@router.get("/dev/fixtures", response_model=FixtureBundle, tags=["development"])
def development_fixtures() -> FixtureBundle:
    """Synthetic, public test data only. This is not a candidate-data endpoint."""
    return load_fixtures()
