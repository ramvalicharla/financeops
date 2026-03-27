"""add entity_id backfill across remaining modules.

Revision ID: 0081_entity_id_backfill
Revises: 0080_locations_and_enrichment
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_trigger_name,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0081_entity_id_backfill"
down_revision: str | None = "0080_locations_and_enrichment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(sa.text("SELECT to_regclass(:name)"), {"name": index_name}).scalar_one_or_none()
        is not None
    )


def _constraint_exists(constraint_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(
            sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
            {"name": constraint_name},
        ).scalar_one_or_none()
        is not None
    )


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _append_only_trigger_exists(table_name: str) -> bool:
    bind = op.get_bind()
    trigger = append_only_trigger_name(table_name)
    return (
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = :table_name
                  AND t.tgname = :trigger_name
                  AND NOT t.tgisinternal
                LIMIT 1
                """
            ),
            {"table_name": table_name, "trigger_name": trigger},
        ).scalar_one_or_none()
        is not None
    )


def _execute_update_with_append_only_disabled(table_name: str, sql: str) -> None:
    has_trigger = _append_only_trigger_exists(table_name)
    if has_trigger:
        op.execute(sa.text(drop_trigger_sql(table_name)))
    try:
        op.execute(sa.text(sql))
    finally:
        if has_trigger:
            op.execute(sa.text(create_trigger_sql(table_name)))


def _add_entity_column(table_name: str) -> None:
    if not _column_exists(table_name, "entity_id"):
        op.add_column(table_name, sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True))


def _backfill_default_entity(table_name: str) -> None:
    _execute_update_with_append_only_disabled(
        table_name,
        f"""
        UPDATE {table_name} AS t
        SET entity_id = (
            SELECT e.id
            FROM cp_entities AS e
            WHERE e.tenant_id = t.tenant_id
            ORDER BY e.created_at ASC NULLS LAST, e.id ASC
            LIMIT 1
        )
        WHERE t.entity_id IS NULL
        """,
    )


def _assert_no_null_entity(table_name: str) -> None:
    remaining = op.get_bind().execute(
        sa.text(f"SELECT COUNT(1) FROM {table_name} WHERE entity_id IS NULL")
    ).scalar_one()
    if int(remaining) > 0:
        raise RuntimeError(
            f"Backfill failed for {table_name}: {remaining} rows still have NULL entity_id"
        )


def _ensure_fk(
    table_name: str,
    fk_name: str,
    *,
    ondelete: str | None = "RESTRICT",
) -> None:
    if _constraint_exists(fk_name):
        return
    op.create_foreign_key(
        fk_name,
        table_name,
        "cp_entities",
        ["entity_id"],
        ["id"],
        ondelete=ondelete,
    )


def _ensure_index(table_name: str, index_name: str, cols: list[str]) -> None:
    if not _index_exists(index_name):
        op.create_index(index_name, table_name, cols, unique=False)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    if _constraint_exists(constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    if _constraint_exists(constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _set_not_null(table_name: str) -> None:
    _assert_no_null_entity(table_name)
    op.alter_column(
        table_name,
        "entity_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )


def _drop_entity_column_if_exists(table_name: str) -> None:
    if _column_exists(table_name, "entity_id"):
        op.drop_column(table_name, "entity_id")


def _ensure_default_entities_for_backfill() -> None:
    # Some legacy tenants can have operational rows without control-plane entities.
    # Create one deterministic fallback organisation/entity per such tenant so
    # entity_id backfills can be completed and constrained as NOT NULL.
    op.execute(
        sa.text(
            """
            WITH missing AS (
                SELECT t.id AS tenant_id
                FROM iam_tenants AS t
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cp_entities AS e
                    WHERE e.tenant_id = t.id
                )
            )
            INSERT INTO cp_organisations (
                organisation_code,
                organisation_name,
                parent_organisation_id,
                supersedes_id,
                is_active,
                correlation_id,
                tenant_id,
                chain_hash,
                previous_hash,
                id,
                created_at
            )
            SELECT
                ('AUTO_ORG_' || SUBSTRING(REPLACE(m.tenant_id::text, '-', '') FROM 1 FOR 16))::varchar(64),
                'Auto Organisation',
                NULL,
                NULL,
                TRUE,
                '0081-auto-backfill',
                m.tenant_id,
                repeat('0', 64),
                repeat('0', 64),
                gen_random_uuid(),
                now()
            FROM missing AS m
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO cp_entities (
                entity_code,
                entity_name,
                organisation_id,
                group_id,
                base_currency,
                country_code,
                status,
                deactivated_at,
                correlation_id,
                tenant_id,
                chain_hash,
                previous_hash,
                id,
                created_at
            )
            SELECT
                ('AUTO_ENTITY_' || SUBSTRING(REPLACE(o.tenant_id::text, '-', '') FROM 1 FOR 13))::varchar(64),
                'Auto Entity',
                o.id,
                NULL,
                'INR',
                'IN',
                'active',
                NULL,
                '0081-auto-backfill',
                o.tenant_id,
                repeat('0', 64),
                repeat('0', 64),
                gen_random_uuid(),
                now()
            FROM cp_organisations AS o
            WHERE o.correlation_id = '0081-auto-backfill'
              AND NOT EXISTS (
                  SELECT 1
                  FROM cp_entities AS e
                  WHERE e.tenant_id = o.tenant_id
              )
            """
        )
    )


def upgrade() -> None:
    _ensure_default_entities_for_backfill()

    # expense_management
    _add_entity_column("expense_claims")
    _backfill_default_entity("expense_claims")
    _set_not_null("expense_claims")
    _ensure_fk("expense_claims", "fk_expense_claims_entity_id_cp_entities", ondelete="RESTRICT")
    _ensure_index("expense_claims", "idx_expense_claims_entity_id", ["tenant_id", "entity_id"])

    # cash_flow_forecast
    _add_entity_column("cash_flow_forecast_runs")
    _backfill_default_entity("cash_flow_forecast_runs")
    _set_not_null("cash_flow_forecast_runs")
    _ensure_fk(
        "cash_flow_forecast_runs",
        "fk_cash_flow_forecast_runs_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "cash_flow_forecast_runs",
        "idx_cash_flow_forecast_runs_entity_id",
        ["entity_id"],
    )

    _add_entity_column("cash_flow_forecast_assumptions")
    _execute_update_with_append_only_disabled(
        "cash_flow_forecast_assumptions",
        """
        UPDATE cash_flow_forecast_assumptions AS cfa
        SET entity_id = cfr.entity_id
        FROM cash_flow_forecast_runs AS cfr
        WHERE cfa.forecast_run_id = cfr.id
          AND cfa.entity_id IS NULL
        """,
    )
    _backfill_default_entity("cash_flow_forecast_assumptions")
    _set_not_null("cash_flow_forecast_assumptions")
    _ensure_fk(
        "cash_flow_forecast_assumptions",
        "fk_cash_flow_forecast_assumptions_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "cash_flow_forecast_assumptions",
        "idx_cash_flow_forecast_assumptions_entity_id",
        ["tenant_id", "entity_id"],
    )

    # closing_checklist
    _add_entity_column("checklist_runs")
    _backfill_default_entity("checklist_runs")
    _set_not_null("checklist_runs")
    _ensure_fk("checklist_runs", "fk_checklist_runs_entity_id_cp_entities", ondelete="RESTRICT")
    _ensure_index("checklist_runs", "idx_checklist_runs_entity", ["tenant_id", "entity_id"])
    _drop_unique_if_exists("checklist_runs", "uq_checklist_runs_tenant_period")
    if not _constraint_exists("uq_checklist_runs_tenant_entity_period"):
        op.create_unique_constraint(
            "uq_checklist_runs_tenant_entity_period",
            "checklist_runs",
            ["tenant_id", "entity_id", "period"],
        )

    _add_entity_column("checklist_run_tasks")
    _execute_update_with_append_only_disabled(
        "checklist_run_tasks",
        """
        UPDATE checklist_run_tasks AS crt
        SET entity_id = cr.entity_id
        FROM checklist_runs AS cr
        WHERE crt.run_id = cr.id
          AND crt.entity_id IS NULL
        """,
    )
    _backfill_default_entity("checklist_run_tasks")
    _set_not_null("checklist_run_tasks")
    _ensure_fk(
        "checklist_run_tasks",
        "fk_checklist_run_tasks_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "checklist_run_tasks",
        "idx_checklist_run_tasks_entity",
        ["tenant_id", "entity_id"],
    )

    # scenario_modelling
    _add_entity_column("scenario_sets")
    _backfill_default_entity("scenario_sets")
    _set_not_null("scenario_sets")
    _ensure_fk("scenario_sets", "fk_scenario_sets_entity_id_cp_entities", ondelete="RESTRICT")
    _ensure_index("scenario_sets", "idx_scenario_sets_tenant_entity", ["tenant_id", "entity_id"])

    _add_entity_column("scenario_definitions")
    _execute_update_with_append_only_disabled(
        "scenario_definitions",
        """
        UPDATE scenario_definitions AS sd
        SET entity_id = ss.entity_id
        FROM scenario_sets AS ss
        WHERE sd.scenario_set_id = ss.id
          AND sd.entity_id IS NULL
        """,
    )
    _backfill_default_entity("scenario_definitions")
    _set_not_null("scenario_definitions")
    _ensure_fk(
        "scenario_definitions",
        "fk_scenario_definitions_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "scenario_definitions",
        "idx_scenario_definitions_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("scenario_results")
    _execute_update_with_append_only_disabled(
        "scenario_results",
        """
        UPDATE scenario_results AS sr
        SET entity_id = ss.entity_id
        FROM scenario_sets AS ss
        WHERE sr.scenario_set_id = ss.id
          AND sr.entity_id IS NULL
        """,
    )
    _backfill_default_entity("scenario_results")
    _set_not_null("scenario_results")
    _ensure_fk(
        "scenario_results",
        "fk_scenario_results_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "scenario_results",
        "idx_scenario_results_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("scenario_line_items")
    _execute_update_with_append_only_disabled(
        "scenario_line_items",
        """
        UPDATE scenario_line_items AS sli
        SET entity_id = sr.entity_id
        FROM scenario_results AS sr
        WHERE sli.scenario_result_id = sr.id
          AND sli.entity_id IS NULL
        """,
    )
    _backfill_default_entity("scenario_line_items")
    _set_not_null("scenario_line_items")
    _ensure_fk(
        "scenario_line_items",
        "fk_scenario_line_items_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "scenario_line_items",
        "idx_scenario_line_items_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    # debt_covenants
    _add_entity_column("covenant_definitions")
    _backfill_default_entity("covenant_definitions")
    _set_not_null("covenant_definitions")
    _ensure_fk(
        "covenant_definitions",
        "fk_covenant_definitions_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "covenant_definitions",
        "idx_covenant_definitions_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("covenant_breach_events")
    _execute_update_with_append_only_disabled(
        "covenant_breach_events",
        """
        UPDATE covenant_breach_events AS cbe
        SET entity_id = cd.entity_id
        FROM covenant_definitions AS cd
        WHERE cbe.covenant_id = cd.id
          AND cbe.entity_id IS NULL
        """,
    )
    _backfill_default_entity("covenant_breach_events")
    _set_not_null("covenant_breach_events")
    _ensure_fk(
        "covenant_breach_events",
        "fk_covenant_breach_events_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "covenant_breach_events",
        "idx_covenant_breach_events_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    # digital_signoff
    _add_entity_column("director_signoffs")
    _backfill_default_entity("director_signoffs")
    _set_not_null("director_signoffs")
    _ensure_fk(
        "director_signoffs",
        "fk_director_signoffs_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "director_signoffs",
        "idx_director_signoffs_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    # statutory
    _add_entity_column("statutory_register_entries")
    _backfill_default_entity("statutory_register_entries")
    _set_not_null("statutory_register_entries")
    _ensure_fk(
        "statutory_register_entries",
        "fk_statutory_register_entries_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "statutory_register_entries",
        "idx_statutory_register_entries_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("statutory_filings")
    _backfill_default_entity("statutory_filings")
    _set_not_null("statutory_filings")
    _ensure_fk(
        "statutory_filings",
        "fk_statutory_filings_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "statutory_filings",
        "idx_statutory_filings_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    # multi_gaap
    _add_entity_column("multi_gaap_configs")
    _backfill_default_entity("multi_gaap_configs")
    _set_not_null("multi_gaap_configs")
    _ensure_fk(
        "multi_gaap_configs",
        "fk_multi_gaap_configs_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _drop_unique_if_exists("multi_gaap_configs", "multi_gaap_configs_tenant_id_key")
    _drop_unique_if_exists("multi_gaap_configs", "uq_multi_gaap_configs_tenant_id")
    if not _constraint_exists("uq_multi_gaap_configs_tenant_entity"):
        op.create_unique_constraint(
            "uq_multi_gaap_configs_tenant_entity",
            "multi_gaap_configs",
            ["tenant_id", "entity_id"],
        )
    _ensure_index(
        "multi_gaap_configs",
        "idx_multi_gaap_configs_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("multi_gaap_runs")
    _backfill_default_entity("multi_gaap_runs")
    _set_not_null("multi_gaap_runs")
    _ensure_fk(
        "multi_gaap_runs",
        "fk_multi_gaap_runs_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _drop_unique_if_exists("multi_gaap_runs", "uq_multi_gaap_runs_tenant_period_framework")
    if not _constraint_exists("uq_multi_gaap_runs_tenant_entity_period_framework"):
        op.create_unique_constraint(
            "uq_multi_gaap_runs_tenant_entity_period_framework",
            "multi_gaap_runs",
            ["tenant_id", "entity_id", "period", "gaap_framework"],
        )
    _drop_index_if_exists("idx_multi_gaap_runs_tenant_period_framework", "multi_gaap_runs")
    _ensure_index(
        "multi_gaap_runs",
        "idx_multi_gaap_runs_tenant_entity_period_framework",
        ["tenant_id", "entity_id", "period", "gaap_framework"],
    )

    # auditor_portal
    _add_entity_column("auditor_portal_access")
    _backfill_default_entity("auditor_portal_access")
    _set_not_null("auditor_portal_access")
    _ensure_fk(
        "auditor_portal_access",
        "fk_auditor_portal_access_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _drop_unique_if_exists(
        "auditor_portal_access",
        "uq_auditor_portal_access_tenant_email_engagement",
    )
    if not _constraint_exists("uq_auditor_portal_access_tenant_entity_email_engagement"):
        op.create_unique_constraint(
            "uq_auditor_portal_access_tenant_entity_email_engagement",
            "auditor_portal_access",
            ["tenant_id", "entity_id", "auditor_email", "engagement_name"],
        )
    _ensure_index(
        "auditor_portal_access",
        "idx_auditor_portal_access_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    _add_entity_column("auditor_requests")
    _execute_update_with_append_only_disabled(
        "auditor_requests",
        """
        UPDATE auditor_requests AS ar
        SET entity_id = apa.entity_id
        FROM auditor_portal_access AS apa
        WHERE ar.access_id = apa.id
          AND ar.entity_id IS NULL
        """,
    )
    _backfill_default_entity("auditor_requests")
    _set_not_null("auditor_requests")
    _ensure_fk(
        "auditor_requests",
        "fk_auditor_requests_entity_id_cp_entities",
        ondelete="RESTRICT",
    )
    _ensure_index(
        "auditor_requests",
        "idx_auditor_requests_tenant_entity",
        ["tenant_id", "entity_id"],
    )

    # gst
    _add_entity_column("gst_returns")
    _backfill_default_entity("gst_returns")
    _set_not_null("gst_returns")
    _ensure_fk("gst_returns", "fk_gst_returns_entity_id_cp_entities", ondelete=None)
    _ensure_index("gst_returns", "idx_gst_returns_entity_id", ["tenant_id", "entity_id"])

    _add_entity_column("gst_recon_items")
    _execute_update_with_append_only_disabled(
        "gst_recon_items",
        """
        UPDATE gst_recon_items AS gri
        SET entity_id = gr.entity_id
        FROM gst_returns AS gr
        WHERE gri.return_a_id = gr.id
          AND gri.entity_id IS NULL
        """,
    )
    _backfill_default_entity("gst_recon_items")
    _set_not_null("gst_recon_items")
    _ensure_fk("gst_recon_items", "fk_gst_recon_items_entity_id_cp_entities", ondelete=None)
    _ensure_index("gst_recon_items", "idx_gst_recon_entity_id", ["tenant_id", "entity_id"])

    # bank_reconciliation
    _add_entity_column("bank_statements")
    _backfill_default_entity("bank_statements")
    _set_not_null("bank_statements")
    _ensure_fk("bank_statements", "fk_bank_statements_entity_id_cp_entities", ondelete=None)
    _ensure_index("bank_statements", "idx_bank_stmts_entity_id", ["tenant_id", "entity_id"])

    _add_entity_column("bank_transactions")
    _execute_update_with_append_only_disabled(
        "bank_transactions",
        """
        UPDATE bank_transactions AS bt
        SET entity_id = bs.entity_id
        FROM bank_statements AS bs
        WHERE bt.statement_id = bs.id
          AND bt.entity_id IS NULL
        """,
    )
    _backfill_default_entity("bank_transactions")
    _set_not_null("bank_transactions")
    _ensure_fk("bank_transactions", "fk_bank_transactions_entity_id_cp_entities", ondelete=None)
    _ensure_index("bank_transactions", "idx_bank_txns_entity_id", ["tenant_id", "entity_id"])

    _add_entity_column("bank_recon_items")
    _execute_update_with_append_only_disabled(
        "bank_recon_items",
        """
        UPDATE bank_recon_items AS bri
        SET entity_id = bs.entity_id
        FROM bank_statements AS bs
        WHERE bri.statement_id = bs.id
          AND bri.entity_id IS NULL
        """,
    )
    _backfill_default_entity("bank_recon_items")
    _set_not_null("bank_recon_items")
    _ensure_fk("bank_recon_items", "fk_bank_recon_items_entity_id_cp_entities", ondelete=None)
    _ensure_index("bank_recon_items", "idx_bank_recon_entity_id", ["tenant_id", "entity_id"])


def downgrade() -> None:
    # bank_reconciliation
    _drop_index_if_exists("idx_bank_recon_entity_id", "bank_recon_items")
    _drop_constraint_if_exists("bank_recon_items", "fk_bank_recon_items_entity_id_cp_entities")
    _drop_entity_column_if_exists("bank_recon_items")

    _drop_index_if_exists("idx_bank_txns_entity_id", "bank_transactions")
    _drop_constraint_if_exists("bank_transactions", "fk_bank_transactions_entity_id_cp_entities")
    _drop_entity_column_if_exists("bank_transactions")

    _drop_index_if_exists("idx_bank_stmts_entity_id", "bank_statements")
    _drop_constraint_if_exists("bank_statements", "fk_bank_statements_entity_id_cp_entities")
    _drop_entity_column_if_exists("bank_statements")

    # gst
    _drop_index_if_exists("idx_gst_recon_entity_id", "gst_recon_items")
    _drop_constraint_if_exists("gst_recon_items", "fk_gst_recon_items_entity_id_cp_entities")
    _drop_entity_column_if_exists("gst_recon_items")

    _drop_index_if_exists("idx_gst_returns_entity_id", "gst_returns")
    _drop_constraint_if_exists("gst_returns", "fk_gst_returns_entity_id_cp_entities")
    _drop_entity_column_if_exists("gst_returns")

    # auditor_portal
    _drop_index_if_exists("idx_auditor_requests_tenant_entity", "auditor_requests")
    _drop_constraint_if_exists("auditor_requests", "fk_auditor_requests_entity_id_cp_entities")
    _drop_entity_column_if_exists("auditor_requests")

    _drop_index_if_exists("idx_auditor_portal_access_tenant_entity", "auditor_portal_access")
    _drop_unique_if_exists(
        "auditor_portal_access",
        "uq_auditor_portal_access_tenant_entity_email_engagement",
    )
    if not _constraint_exists("uq_auditor_portal_access_tenant_email_engagement"):
        op.create_unique_constraint(
            "uq_auditor_portal_access_tenant_email_engagement",
            "auditor_portal_access",
            ["tenant_id", "auditor_email", "engagement_name"],
        )
    _drop_constraint_if_exists("auditor_portal_access", "fk_auditor_portal_access_entity_id_cp_entities")
    _drop_entity_column_if_exists("auditor_portal_access")

    # multi_gaap
    _drop_index_if_exists(
        "idx_multi_gaap_runs_tenant_entity_period_framework",
        "multi_gaap_runs",
    )
    _drop_unique_if_exists("multi_gaap_runs", "uq_multi_gaap_runs_tenant_entity_period_framework")
    if not _constraint_exists("uq_multi_gaap_runs_tenant_period_framework"):
        op.create_unique_constraint(
            "uq_multi_gaap_runs_tenant_period_framework",
            "multi_gaap_runs",
            ["tenant_id", "period", "gaap_framework"],
        )
    _ensure_index(
        "multi_gaap_runs",
        "idx_multi_gaap_runs_tenant_period_framework",
        ["tenant_id", "period", "gaap_framework"],
    )
    _drop_constraint_if_exists("multi_gaap_runs", "fk_multi_gaap_runs_entity_id_cp_entities")
    _drop_entity_column_if_exists("multi_gaap_runs")

    _drop_index_if_exists("idx_multi_gaap_configs_tenant_entity", "multi_gaap_configs")
    _drop_unique_if_exists("multi_gaap_configs", "uq_multi_gaap_configs_tenant_entity")
    if not _constraint_exists("multi_gaap_configs_tenant_id_key"):
        op.create_unique_constraint(
            "multi_gaap_configs_tenant_id_key",
            "multi_gaap_configs",
            ["tenant_id"],
        )
    _drop_constraint_if_exists("multi_gaap_configs", "fk_multi_gaap_configs_entity_id_cp_entities")
    _drop_entity_column_if_exists("multi_gaap_configs")

    # statutory
    _drop_index_if_exists("idx_statutory_filings_tenant_entity", "statutory_filings")
    _drop_constraint_if_exists("statutory_filings", "fk_statutory_filings_entity_id_cp_entities")
    _drop_entity_column_if_exists("statutory_filings")

    _drop_index_if_exists("idx_statutory_register_entries_tenant_entity", "statutory_register_entries")
    _drop_constraint_if_exists(
        "statutory_register_entries",
        "fk_statutory_register_entries_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("statutory_register_entries")

    # digital_signoff
    _drop_index_if_exists("idx_director_signoffs_tenant_entity", "director_signoffs")
    _drop_constraint_if_exists("director_signoffs", "fk_director_signoffs_entity_id_cp_entities")
    _drop_entity_column_if_exists("director_signoffs")

    # debt_covenants
    _drop_index_if_exists("idx_covenant_breach_events_tenant_entity", "covenant_breach_events")
    _drop_constraint_if_exists(
        "covenant_breach_events",
        "fk_covenant_breach_events_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("covenant_breach_events")

    _drop_index_if_exists("idx_covenant_definitions_tenant_entity", "covenant_definitions")
    _drop_constraint_if_exists(
        "covenant_definitions",
        "fk_covenant_definitions_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("covenant_definitions")

    # scenario_modelling
    _drop_index_if_exists("idx_scenario_line_items_tenant_entity", "scenario_line_items")
    _drop_constraint_if_exists("scenario_line_items", "fk_scenario_line_items_entity_id_cp_entities")
    _drop_entity_column_if_exists("scenario_line_items")

    _drop_index_if_exists("idx_scenario_results_tenant_entity", "scenario_results")
    _drop_constraint_if_exists("scenario_results", "fk_scenario_results_entity_id_cp_entities")
    _drop_entity_column_if_exists("scenario_results")

    _drop_index_if_exists("idx_scenario_definitions_tenant_entity", "scenario_definitions")
    _drop_constraint_if_exists(
        "scenario_definitions",
        "fk_scenario_definitions_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("scenario_definitions")

    _drop_index_if_exists("idx_scenario_sets_tenant_entity", "scenario_sets")
    _drop_constraint_if_exists("scenario_sets", "fk_scenario_sets_entity_id_cp_entities")
    _drop_entity_column_if_exists("scenario_sets")

    # closing_checklist
    _drop_index_if_exists("idx_checklist_run_tasks_entity", "checklist_run_tasks")
    _drop_constraint_if_exists("checklist_run_tasks", "fk_checklist_run_tasks_entity_id_cp_entities")
    _drop_entity_column_if_exists("checklist_run_tasks")

    _drop_unique_if_exists("checklist_runs", "uq_checklist_runs_tenant_entity_period")
    if not _constraint_exists("uq_checklist_runs_tenant_period"):
        op.create_unique_constraint(
            "uq_checklist_runs_tenant_period",
            "checklist_runs",
            ["tenant_id", "period"],
        )
    _drop_index_if_exists("idx_checklist_runs_entity", "checklist_runs")
    _drop_constraint_if_exists("checklist_runs", "fk_checklist_runs_entity_id_cp_entities")
    _drop_entity_column_if_exists("checklist_runs")

    # cash_flow_forecast
    _drop_index_if_exists(
        "idx_cash_flow_forecast_assumptions_entity_id",
        "cash_flow_forecast_assumptions",
    )
    _drop_constraint_if_exists(
        "cash_flow_forecast_assumptions",
        "fk_cash_flow_forecast_assumptions_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("cash_flow_forecast_assumptions")

    _drop_index_if_exists("idx_cash_flow_forecast_runs_entity_id", "cash_flow_forecast_runs")
    _drop_constraint_if_exists(
        "cash_flow_forecast_runs",
        "fk_cash_flow_forecast_runs_entity_id_cp_entities",
    )
    _drop_entity_column_if_exists("cash_flow_forecast_runs")

    # expense_management
    _drop_index_if_exists("idx_expense_claims_entity_id", "expense_claims")
    _drop_constraint_if_exists("expense_claims", "fk_expense_claims_entity_id_cp_entities")
    _drop_entity_column_if_exists("expense_claims")
