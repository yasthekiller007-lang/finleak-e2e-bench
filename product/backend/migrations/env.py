import os
import re

from alembic import context

from app.core.config import get_settings
from app.db import models  # noqa: F401 - register all model tables
from app.db.base import Base
from app.db.session import create_database_engine
from app.db.types import ExactNumeric


def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, ExactNumeric):
        return f"sa.Numeric(precision={obj.impl.precision}, scale={obj.impl.scale})"
    return False


target_metadata = Base.metadata
settings = get_settings()
if settings.database_url is None:
    raise RuntimeError("Set FLA_DATABASE_URL before running migrations")

if context.is_offline_mode():
    context.configure(
        url=settings.database_url.unicode_string(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(settings)
    assert engine is not None
    try:
        with engine.connect() as connection:
            migration_role = os.environ.get("FLA_MIGRATION_ROLE")
            if migration_role:
                if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", migration_role):
                    raise RuntimeError("Migration role must be a safe dedicated identifier")
                quoted = connection.dialect.identifier_preparer.quote_identifier(migration_role)
                connection.exec_driver_sql("SET ROLE " + quoted)
                connection.commit()
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                render_item=render_item,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
