from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.db.models.consolidation import ConsolidationRunEvent, IntercompanyPair
from financeops.services.audit_writer import AuditWriter
from financeops.services.consolidation import finalize_run
from tests.utils.consolidation_seed import seed_consolidation_drill_dataset


@pytest.mark.asyncio
async def test_lineage_completeness_enforced_before_completed_terminal_event(
    async_session: AsyncSession,
    test_tenant,
    test_user,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-lineage-enforced",
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=IntercompanyPair,
        tenant_id=test_tenant.id,
        record_data={
            "run_id": str(seeded["run_id"]),
            "match_key_hash": f"broken-{uuid.uuid4().hex}",
            "entity_from": str(uuid.uuid4()),
            "entity_to": str(uuid.uuid4()),
            "account_code": "BROKEN",
            "classification": "unexplained",
        },
        values={
            "run_id": seeded["run_id"],
            "match_key_hash": f"broken-{uuid.uuid4().hex}",
            "entity_from": uuid.uuid4(),
            "entity_to": uuid.uuid4(),
            "account_code": "BROKEN",
            "ic_reference": "IC-BROKEN",
            "amount_local_from": Decimal("1.000000"),
            "amount_local_to": Decimal("-1.000000"),
            "amount_parent_from": Decimal("1.000000"),
            "amount_parent_to": Decimal("-1.000000"),
            "expected_difference": Decimal("0.000000"),
            "actual_difference": Decimal("0.000000"),
            "fx_explained": Decimal("0.000000"),
            "unexplained_difference": Decimal("0.000000"),
            "classification": "unexplained",
            "correlation_id": "corr-broken",
        },
    )

    with pytest.raises(ValidationError, match="LINEAGE_INCOMPLETE"):
        await finalize_run(
            async_session,
            tenant_id=test_tenant.id,
            run_id=seeded["run_id"],
            user_id=test_user.id,
            correlation_id="corr-lineage-enforced",
            event_type="completed",
            metadata_json={"attempted": True},
        )

    events = (
        await async_session.execute(
            select(ConsolidationRunEvent)
            .where(
                ConsolidationRunEvent.tenant_id == test_tenant.id,
                ConsolidationRunEvent.run_id == seeded["run_id"],
            )
            .order_by(ConsolidationRunEvent.event_seq)
        )
    ).scalars().all()
    assert events[-1].event_type == "failed"
    assert events[-1].metadata_json is not None
    assert events[-1].metadata_json["error_code"] == "LINEAGE_INCOMPLETE"
