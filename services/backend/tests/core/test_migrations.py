from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_database_migration_histories_are_independent():
    root = Path(__file__).resolve().parents[2]
    app = ScriptDirectory.from_config(Config(str(root / "alembic-app.ini")))
    jobs = ScriptDirectory.from_config(Config(str(root / "alembic-jobs.ini")))
    assert Path(app.dir).resolve() != Path(jobs.dir).resolve()
