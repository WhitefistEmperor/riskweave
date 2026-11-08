"""Connections are supplied by the migration CLI; credentials stay out of config files."""

from alembic import context

from ringsentinel.platform.models import Base

if context.is_offline_mode():
    # SQL-script generation for consoles such as Supabase's SQL editor: no connection
    # or credentials; the URL only selects the PostgreSQL dialect.
    context.configure(
        url="postgresql+psycopg://offline/postgres",
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
else:
    context.configure(
        connection=context.config.attributes["connection"], target_metadata=Base.metadata
    )
with context.begin_transaction():
    context.run_migrations()
