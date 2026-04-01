"""fx_multi_currency_ias21

Revision ID: 0103_fx_multi_currency_ias21
Revises: 0102_coa_upload_management
Create Date: 2026-04-01

IAS 21 first-pass support:
- FX rate master table for SPOT/AVERAGE/CLOSING rates
- Journal line FX extension fields
- Accounting revaluation run history
- Consolidation translation run history + per-entity CTA results
- Seed CTA reserve account in global CoA templates (idempotent)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0103_fx_multi_currency_ias21"
down_revision = "0102_coa_upload_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("from_currency", sa.String(length=3), nullable=False),
        sa.Column("to_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("rate_type", sa.String(length=16), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_fx_rates_pair_effective_type",
        "fx_rates",
        ["from_currency", "to_currency", "effective_date", "rate_type"],
    )
    op.create_index(
        "ix_fx_rates_tenant_pair_effective_type",
        "fx_rates",
        ["tenant_id", "from_currency", "to_currency", "effective_date", "rate_type"],
    )

    op.add_column(
        "accounting_jv_lines",
        sa.Column("transaction_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "accounting_jv_lines",
        sa.Column("functional_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "accounting_jv_lines",
        sa.Column("base_amount", sa.Numeric(20, 4), nullable=True),
    )
    op.create_index(
        "ix_accounting_jv_lines_transaction_currency",
        "accounting_jv_lines",
        ["transaction_currency"],
    )

    op.execute(
        """
        UPDATE accounting_jv_lines
        SET transaction_currency = COALESCE(transaction_currency, currency)
        """
    )
    op.execute(
        """
        UPDATE accounting_jv_lines line
        SET functional_currency = COALESCE(
            line.functional_currency,
            entity.base_currency,
            line.currency,
            'INR'
        )
        FROM cp_entities entity
        WHERE line.entity_id = entity.id
        """
    )
    op.execute(
        """
        UPDATE accounting_jv_lines
        SET base_amount = COALESCE(base_amount, amount_inr, amount)
        """
    )

    op.create_table(
        "accounting_fx_revaluation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closing_rate_source", sa.String(length=32), nullable=True),
        sa.Column(
            "initiated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "adjustment_jv_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounting_jv_aggregates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_accounting_fx_revaluation_runs_tenant",
        "accounting_fx_revaluation_runs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_accounting_fx_revaluation_runs_entity_date",
        "accounting_fx_revaluation_runs",
        ["tenant_id", "entity_id", "as_of_date"],
    )

    op.create_table(
        "accounting_fx_revaluation_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounting_fx_revaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(length=50), nullable=False),
        sa.Column("account_name", sa.String(length=300), nullable=False),
        sa.Column("transaction_currency", sa.String(length=3), nullable=False),
        sa.Column("functional_currency", sa.String(length=3), nullable=False),
        sa.Column("foreign_balance", sa.Numeric(20, 8), nullable=False),
        sa.Column("historical_base_balance", sa.Numeric(20, 8), nullable=False),
        sa.Column("closing_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("revalued_base_balance", sa.Numeric(20, 8), nullable=False),
        sa.Column("fx_difference", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_accounting_fx_revaluation_lines_tenant",
        "accounting_fx_revaluation_lines",
        ["tenant_id"],
    )
    op.create_index(
        "ix_accounting_fx_revaluation_lines_run_id",
        "accounting_fx_revaluation_lines",
        ["run_id"],
    )

    op.create_table(
        "consolidation_translation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "org_group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("org_groups.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("presentation_currency", sa.String(length=3), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "initiated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_consolidation_translation_runs_tenant",
        "consolidation_translation_runs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_consolidation_translation_runs_group_date",
        "consolidation_translation_runs",
        ["tenant_id", "org_group_id", "as_of_date"],
    )

    op.create_table(
        "consolidation_translation_entity_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("consolidation_translation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("org_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("functional_currency", sa.String(length=3), nullable=False),
        sa.Column("presentation_currency", sa.String(length=3), nullable=False),
        sa.Column("closing_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("average_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("translated_assets", sa.Numeric(20, 8), nullable=False),
        sa.Column("translated_liabilities", sa.Numeric(20, 8), nullable=False),
        sa.Column("translated_equity", sa.Numeric(20, 8), nullable=False),
        sa.Column("translated_net_profit", sa.Numeric(20, 8), nullable=False),
        sa.Column("cta_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_consolidation_translation_entity_results_tenant",
        "consolidation_translation_entity_results",
        ["tenant_id"],
    )
    op.create_index(
        "ix_consolidation_translation_entity_results_run_entity",
        "consolidation_translation_entity_results",
        ["run_id", "org_entity_id"],
    )

    # Seed CTA/FCTR reserve account per template (idempotent).
    op.execute(
        """
        INSERT INTO coa_ledger_accounts (
            id,
            account_subgroup_id,
            industry_template_id,
            tenant_id,
            code,
            name,
            description,
            source_type,
            version,
            created_by,
            normal_balance,
            cash_flow_tag,
            cash_flow_method,
            bs_pl_flag,
            asset_liability_class,
            is_monetary,
            is_related_party,
            is_tax_deductible,
            is_control_account,
            notes_reference,
            is_active,
            sort_order,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            subgroup.id,
            template.id,
            NULL,
            'CTA_FCTR',
            'Foreign Currency Translation Reserve',
            'IAS 21 cumulative translation adjustment reserve',
            'SYSTEM'::coa_source_type_enum,
            1,
            NULL,
            'CREDIT',
            NULL,
            NULL,
            'EQUITY',
            'EQUITY',
            false,
            false,
            true,
            false,
            'CTA',
            true,
            9999,
            now(),
            now()
        FROM coa_industry_templates template
        JOIN LATERAL (
            SELECT subgroup.id
            FROM coa_account_subgroups subgroup
            JOIN coa_account_groups grp ON grp.id = subgroup.account_group_id
            WHERE grp.industry_template_id = template.id
            ORDER BY
                CASE
                    WHEN upper(grp.name) LIKE '%EQUITY%'
                      OR upper(grp.code) LIKE '%EQUITY%'
                      OR upper(grp.name) LIKE '%CAPITAL%'
                    THEN 0
                    ELSE 1
                END,
                subgroup.sort_order ASC,
                subgroup.created_at ASC
            LIMIT 1
        ) subgroup ON true
        WHERE NOT EXISTS (
            SELECT 1
            FROM coa_ledger_accounts existing
            WHERE existing.industry_template_id = template.id
              AND existing.tenant_id IS NULL
              AND existing.code = 'CTA_FCTR'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM coa_ledger_accounts
        WHERE tenant_id IS NULL
          AND code = 'CTA_FCTR'
        """
    )

    op.drop_index(
        "ix_consolidation_translation_entity_results_run_entity",
        table_name="consolidation_translation_entity_results",
    )
    op.drop_index(
        "ix_consolidation_translation_entity_results_tenant",
        table_name="consolidation_translation_entity_results",
    )
    op.drop_table("consolidation_translation_entity_results")

    op.drop_index(
        "ix_consolidation_translation_runs_group_date",
        table_name="consolidation_translation_runs",
    )
    op.drop_index(
        "ix_consolidation_translation_runs_tenant",
        table_name="consolidation_translation_runs",
    )
    op.drop_table("consolidation_translation_runs")

    op.drop_index(
        "ix_accounting_fx_revaluation_lines_run_id",
        table_name="accounting_fx_revaluation_lines",
    )
    op.drop_index(
        "ix_accounting_fx_revaluation_lines_tenant",
        table_name="accounting_fx_revaluation_lines",
    )
    op.drop_table("accounting_fx_revaluation_lines")

    op.drop_index(
        "ix_accounting_fx_revaluation_runs_entity_date",
        table_name="accounting_fx_revaluation_runs",
    )
    op.drop_index(
        "ix_accounting_fx_revaluation_runs_tenant",
        table_name="accounting_fx_revaluation_runs",
    )
    op.drop_table("accounting_fx_revaluation_runs")

    op.drop_index(
        "ix_accounting_jv_lines_transaction_currency",
        table_name="accounting_jv_lines",
    )
    op.drop_column("accounting_jv_lines", "base_amount")
    op.drop_column("accounting_jv_lines", "functional_currency")
    op.drop_column("accounting_jv_lines", "transaction_currency")

    op.drop_index("ix_fx_rates_tenant_pair_effective_type", table_name="fx_rates")
    op.drop_index("ix_fx_rates_pair_effective_type", table_name="fx_rates")
    op.drop_table("fx_rates")
