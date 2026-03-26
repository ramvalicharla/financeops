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
from financeops.modules.compliance import gdpr_models as compliance_gdpr_models  # noqa: F401
from financeops.modules.expense_management import models as expense_management_models  # noqa: F401
from financeops.modules.working_capital import models as working_capital_models  # noqa: F401
from financeops.modules.budgeting import models as budgeting_models  # noqa: F401
from financeops.modules.forecasting import models as forecasting_models  # noqa: F401
from financeops.modules.scenario_modelling import models as scenario_models  # noqa: F401
from financeops.modules.backup import models as backup_models  # noqa: F401
from financeops.modules.fdd import models as fdd_models  # noqa: F401
from financeops.modules.ppa import models as ppa_models  # noqa: F401
from financeops.modules.ma_workspace import models as ma_workspace_models  # noqa: F401
from financeops.modules.cash_flow_forecast import models as cash_flow_forecast_models  # noqa: F401
from financeops.modules.tax_provision import models as tax_provision_models  # noqa: F401
from financeops.modules.debt_covenants import models as debt_covenants_models  # noqa: F401
from financeops.modules.transfer_pricing import models as transfer_pricing_models  # noqa: F401
from financeops.modules.digital_signoff import models as digital_signoff_models  # noqa: F401
from financeops.modules.statutory import models as statutory_models  # noqa: F401
from financeops.modules.multi_gaap import models as multi_gaap_models  # noqa: F401
from financeops.modules.auditor_portal import models as auditor_portal_models  # noqa: F401
from financeops.modules.coa import models as coa_models  # noqa: F401
from financeops.modules.org_setup import models as org_setup_models  # noqa: F401
from financeops.modules.fixed_assets import models as fixed_assets_models  # noqa: F401
from financeops.modules.prepaid_expenses import models as prepaid_expenses_models  # noqa: F401
from financeops.modules.invoice_classifier import models as invoice_classifier_models  # noqa: F401

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
            "compliance_controls",
            "compliance_events",
            "gdpr_consent_records",
            "gdpr_data_requests",
            "gdpr_breach_records",
            "backup_run_log",
            "fdd_engagements",
            "fdd_sections",
            "fdd_findings",
            "ppa_engagements",
            "ppa_allocations",
            "ppa_intangibles",
            "ma_workspaces",
            "ma_workspace_members",
            "ma_valuations",
            "ma_dd_items",
            "ma_documents",
            "fa_asset_classes",
            "fa_assets",
            "fa_depreciation_runs",
            "fa_revaluations",
            "fa_impairments",
            "prepaid_schedules",
            "prepaid_amortisation_entries",
            "invoice_classifications",
            "classification_rules",
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
