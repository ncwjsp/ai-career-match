"""Independent jobs database migrations. Owner: M2."""

from alembic import context
from sqlalchemy import MetaData, create_engine
from sqlalchemy.pool import NullPool

from app.core.settings import Settings

# Domain owner replaces this with their models' metadata in C-01/B-09.
target_metadata = MetaData()
database_url = Settings().job_database_url.get_secret_value()

if context.is_offline_mode():
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url, poolclass=NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
