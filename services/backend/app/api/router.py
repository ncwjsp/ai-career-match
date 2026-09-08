from fastapi import APIRouter

from app.api.planned import router as planned_router
from app.contracts.models import FixtureBundle
from app.modules.explanations.router import router as explanations_router
from app.testing.fixtures import load_fixtures

router = APIRouter()
router.include_router(explanations_router)
router.include_router(planned_router)


@router.get("/dev/fixtures", response_model=FixtureBundle, tags=["development"])
def development_fixtures() -> FixtureBundle:
    """Synthetic, public test data only. This is not a candidate-data endpoint."""
    return load_fixtures()
