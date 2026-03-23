from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from financeops.db.base import Base
# Import model modules covered by the current migration chain checks.
from financeops.db.models import ai_cost, tenants, users  # noqa: F401
from financeops.modules.closing_checklist import models as closing_checklist_models  # noqa: F401
from financeops.modules.compliance import models as compliance_models  # noqa: F401
from financeops.modules.expense_management import models as expense_management_models  # noqa: F401
from financeops.modules.working_capital import models as working_capital_models  # noqa: F401
from financeops.modules.budgeting import models as budgeting_models  # noqa: F401
from financeops.modules.forecasting import models as forecasting_models  # noqa: F401
from financeops.modules.scenario_modelling import models as scenario_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Ignore reflected-only legacy objects not represented in app metadata."""
    if reflected and compare_to is None:
        return False
    if name == "idx_erasure_log_tenant_created":
        return False
    if type_ == "index":
        table_name = getattr(getattr(object_, "table", None), "name", "")
        tracked_index_tables = {
            "ai_cost_events",
            "tenant_token_budgets",
            "checklist_templates",
            "checklist_template_tasks",
            "checklist_runs",
            "checklist_run_tasks",
            "wc_snapshots",
            "ar_line_items",
            "ap_line_items",
            "expense_policies",
            "expense_claims",
            "expense_approvals",
            "budget_versions",
            "budget_line_items",
            "forecast_runs",
            "forecast_assumptions",
            "forecast_line_items",
            "scenario_sets",
            "scenario_definitions",
            "scenario_results",
            "scenario_line_items",
        }
        return table_name in tracked_index_tables
    return True


def get_url() -> str:
    from financeops.config import settings
    return str(settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
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
