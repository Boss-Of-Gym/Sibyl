import asyncio
from logging.config import fileConfig
from typing import Literal

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.schema import SchemaItem

from alembic import context
from sibyl.dependency_analysis.adapters import db_models as dependency_analysis_models  # noqa: F401
from sibyl.engineering_metrics.adapters import db_models as engineering_metrics_models  # noqa: F401
from sibyl.identity.adapters import db_models as identity_models  # noqa: F401
from sibyl.ingestion.adapters import db_models as ingestion_models  # noqa: F401
from sibyl.platform.config import get_settings
from sibyl.platform.db import Base
from sibyl.pr_analysis.adapters import db_models as pr_analysis_models  # noqa: F401
from sibyl.regression_prediction.adapters import (
    db_models as regression_prediction_models,  # noqa: F401
)
from sibyl.root_cause_analysis.adapters import db_models as root_cause_analysis_models  # noqa: F401
from sibyl.test_intelligence.adapters import db_models as test_intelligence_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def include_object(
    object: SchemaItem,
    name: str | None,
    type_: Literal[
        "schema", "table", "column", "index", "unique_constraint", "foreign_key_constraint"
    ],
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    schema_filter = context.get_x_argument(as_dictionary=True).get("schema")
    if schema_filter is None:
        return True
    if type_ != "table":
        return True
    return getattr(object, "schema", None) == schema_filter


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
