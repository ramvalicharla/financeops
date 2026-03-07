from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import IntercompanyPair
from financeops.services.audit_writer import AuditWriter
from financeops.services.consolidation.lineage_validation import validate_lineage_completeness
from tests.utils.consolidation_seed import seed_consolidation_drill_dataset


@pytest.mark.asyncio
async def test_lineage_validation_passes_for_complete_seeded_run(
    async_session: AsyncSession,
    test_tenant,
    test_user,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-lineage-valid",
    )
    result = await validate_lineage_completeness(
        async_session,
        tenant_id=test_tenant.id,
        run_id=seeded["run_id"],
    )
    assert result.is_complete is True
    assert result.missing_intercompany_line_links == 0


@pytest.mark.asyncio
async def test_lineage_validation_detects_missing_intercompany_line_links(
    async_session: AsyncSession,
    test_tenant,
    test_user,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-lineage-invalid",
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=IntercompanyPair,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(seeded["run_id"]),
            "match_key_hash": f"orphan-{uuid.uuid4().hex}",
            "entity_from": str(uuid.uuid4()),
            "entity_to": str(uuid.uuid4()),
            "account_code": "ORPHAN",
            "classification": "unexplained",
        },
        values={
            "run_id": seeded["run_id"],
            "match_key_hash": f"orphan-{uuid.uuid4().hex}",
            "entity_from": uuid.uuid4(),
            "entity_to": uuid.uuid4(),
            "account_code": "ORPHAN",
            "ic_reference": "IC-ORPHAN",
            "amount_local_from": Decimal("1.000000"),
            "amount_local_to": Decimal("-1.000000"),
            "amount_parent_from": Decimal("1.000000"),
            "amount_parent_to": Decimal("-1.000000"),
            "expected_difference": Decimal("0.000000"),
            "actual_difference": Decimal("0.000000"),
            "fx_explained": Decimal("0.000000"),
            "unexplained_difference": Decimal("0.000000"),
            "classification": "unexplained",
            "correlation_id": "corr-lineage-orphan",
        },
    )

    result = await validate_lineage_completeness(
        async_session,
        tenant_id=test_tenant.id,
        run_id=seeded["run_id"],
    )
    assert result.is_complete is False
    assert result.missing_intercompany_line_links >= 1
