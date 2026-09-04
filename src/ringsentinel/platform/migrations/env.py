"""Connections are supplied by the migration CLI; credentials stay out of config files."""

from alembic import context

from ringsentinel.platform.models import Base

context.configure(connection=context.config.attributes["connection"], target_metadata=Base.metadata)
with context.begin_transaction():
    context.run_migrations()
