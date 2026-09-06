"""Generate the canonical OpenAPI snapshot, or fail on drift with --check."""

import argparse
import json
from pathlib import Path

from app.core.settings import Settings
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schema = create_app(Settings(app_env="test")).openapi()
    for path, item in schema["paths"].items():
        if path.startswith("/api/v1/"):
            for operation in item.values():
                if isinstance(operation, dict):
                    operation["x-implementation-status"] = "planned"
    expected = json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output = Path(__file__).resolve().parents[3] / "contracts/openapi.json"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != expected:
            raise SystemExit("OpenAPI drift: run uv run python -m scripts.export_openapi")
        print("OpenAPI snapshot is current.")
    else:
        output.write_text(expected, encoding="utf-8", newline="\n")
        print("Wrote contracts/openapi.json")


if __name__ == "__main__":
    main()
