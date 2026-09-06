from pathlib import Path

from app.contracts.models import FixtureBundle


def load_fixtures() -> FixtureBundle:
    root = Path(__file__).resolve().parents[4]
    return FixtureBundle.model_validate_json(
        (root / "contracts/examples/bootstrap.json").read_text(encoding="utf-8")
    )
