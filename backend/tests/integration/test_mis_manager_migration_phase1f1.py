from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.mis_phase1f1_helpers import MIS_TABLES

EXPECTED_RLS_TABLES: tuple[str, ...] = (
    "mis_templates",
    "mis_uploads",
    "mis_template_versions",
    "mis_template_sections",
    "mis_template_columns",
    "mis_template_row_mappings",
    "mis_data_snapshots",
    "mis_normalized_lines",
    "mis_ingestion_exceptions",
    "mis_drift_events",
    "mis_canonical_metric_dictionary",
    "mis_canonical_dimension_dictionary",
)

EXPECTED_CONSTRAINTS: tuple[str, ...] = (
    "uq_mis_templates_tenant_template_code",
    "ck_mis_templates_status",
    "uq_mis_template_versions_template_version_no",
    "uq_mis_template_versions_template_version_token",
    "ck_mis_template_versions_status",
    "uq_mis_template_sections_code",
    "uq_mis_template_sections_order",
    "uq_mis_template_columns_ordinal",
    "ck_mis_template_columns_role",
    "ck_mis_template_columns_data_type",
    "ck_mis_template_row_mappings_confidence",
    "uq_mis_data_snapshots_version_token",
    "ck_mis_data_snapshots_status",
    "uq_mis_normalized_lines_snapshot_line_no",
    "ck_mis_normalized_lines_validation_status",
    "ck_mis_ingestion_exceptions_severity",
    "ck_mis_ingestion_exceptions_resolution_status",
    "ck_mis_drift_events_type",
    "ck_mis_drift_events_decision_status",
)

EXPECTED_INDEXES: tuple[str, ...] = (
    "idx_mis_templates_template_code",
    "idx_mis_template_versions_template_created",
    "uq_mis_template_versions_one_active",
    "idx_mis_template_sections_version",
    "idx_mis_template_columns_version",
    "idx_mis_template_row_mappings_version",
    "idx_mis_data_snapshots_period",
    "idx_mis_normalized_lines_snapshot",
    "idx_mis_ingestion_exceptions_snapshot",
    "idx_mis_drift_events_template",
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0012_applies_cleanly_on_fresh_db(
    mis_phase1f1_session: AsyncSession,
) -> None:
    version = (
        await mis_phase1f1_session.execute(text("SELECT version_num FROM alembic_version"))
    ).scalar_one()
    # Phase 1F.1 is expected to remain present while newer migrations are allowed.
    assert version == "0022_phase2_5_ownership_consol"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0012_creates_all_expected_mis_tables(
    mis_phase1f1_session: AsyncSession,
) -> None:
    all_tables = (*MIS_TABLES, "mis_templates")
    for table_name in all_tables:
        regclass = (
            await mis_phase1f1_session.execute(
                text("SELECT to_regclass(:qualified_name)"),
                {"qualified_name": f"public.{table_name}"},
            )
        ).scalar_one()
        assert regclass == table_name


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0012_creates_expected_constraints_and_indexes(
    mis_phase1f1_session: AsyncSession,
) -> None:
    constraints = set(
        (
            await mis_phase1f1_session.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE conname LIKE 'ck_mis_%'
                       OR conname LIKE 'uq_mis_%'
                    """
                )
            )
        ).scalars().all()
    )
    for name in EXPECTED_CONSTRAINTS:
        assert name in constraints

    indexes = set(
        (
            await mis_phase1f1_session.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            )
        ).scalars().all()
    )
    for name in EXPECTED_INDEXES:
        assert name in indexes

    triggers = set(
        (
            await mis_phase1f1_session.execute(
                text(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE NOT tgisinternal
                    """
                )
            )
        ).scalars().all()
    )
    assert "trg_mis_template_versions_validate_supersession" in triggers
    for table_name in (
        "mis_templates",
        "mis_uploads",
        "mis_template_versions",
        "mis_template_sections",
        "mis_template_columns",
        "mis_template_row_mappings",
        "mis_data_snapshots",
        "mis_normalized_lines",
        "mis_ingestion_exceptions",
        "mis_drift_events",
    ):
        assert f"trg_append_only_{table_name}" in triggers


@pytest.mark.asyncio
@pytest.mark.integration
async def test_migration_0012_enables_and_forces_rls_on_all_mis_tables(
    mis_phase1f1_session: AsyncSession,
) -> None:
    for table_name in EXPECTED_RLS_TABLES:
        row = (
            await mis_phase1f1_session.execute(
                text(
                    """
                    SELECT c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = :table_name
                    """
                ),
                {"table_name": table_name},
            )
        ).one()
        assert row.relrowsecurity is True
        assert row.relforcerowsecurity is True

        policy_count = (
            await mis_phase1f1_session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_policies
                    WHERE schemaname = 'public'
                      AND tablename = :table_name
                      AND policyname = :policy_name
                    """
                ),
                {
                    "table_name": table_name,
                    "policy_name": f"{table_name}_tenant_isolation",
                },
            )
        ).scalar_one()
        assert policy_count == 1
