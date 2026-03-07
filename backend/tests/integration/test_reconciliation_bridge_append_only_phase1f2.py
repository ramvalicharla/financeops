from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.reconciliation_bridge import (
    ReconciliationEvidenceLink,
    ReconciliationResolutionEvent,
)
from financeops.services.audit_writer import AuditWriter
from tests.integration.reconciliation_phase1f2_helpers import (
    ensure_tenant_context,
    seed_recon_line,
    seed_recon_session,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_reconciliation_lines(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    session_row = await seed_recon_session(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        token_seed="append_only_line",
    )
    line = await seed_recon_line(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        session_id=session_row.id,
        created_by=tenant_id,
        line_key="line_a",
    )
    with pytest.raises(DBAPIError):
        await recon_phase1f2_session.execute(
            text("UPDATE reconciliation_lines SET explanation_hint = 'changed' WHERE id = :id"),
            {"id": str(line.id)},
        )
        await recon_phase1f2_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_reconciliation_resolution_events(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    session_row = await seed_recon_session(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        token_seed="append_only_event",
    )
    line = await seed_recon_line(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        session_id=session_row.id,
        created_by=tenant_id,
        line_key="line_b",
    )
    event = await AuditWriter.insert_financial_record(
        recon_phase1f2_session,
        model_class=ReconciliationResolutionEvent,
        tenant_id=tenant_id,
        record_data={"line_id": str(line.id), "event_type": "explanation_added"},
        values={
            "session_id": session_row.id,
            "line_id": line.id,
            "exception_id": None,
            "event_type": "explanation_added",
            "event_payload_json": {"message": "x"},
            "actor_user_id": tenant_id,
        },
    )
    with pytest.raises(DBAPIError):
        await recon_phase1f2_session.execute(
            text(
                "UPDATE reconciliation_resolution_events "
                "SET event_payload_json = '{\"message\":\"y\"}'::jsonb WHERE id = :id"
            ),
            {"id": str(event.id)},
        )
        await recon_phase1f2_session.flush()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_append_only_rejects_update_on_reconciliation_evidence_links(
    recon_phase1f2_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(recon_phase1f2_session, tenant_id)
    session_row = await seed_recon_session(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        created_by=tenant_id,
        token_seed="append_only_evidence",
    )
    line = await seed_recon_line(
        recon_phase1f2_session,
        tenant_id=tenant_id,
        session_id=session_row.id,
        created_by=tenant_id,
        line_key="line_c",
    )
    evidence = await AuditWriter.insert_financial_record(
        recon_phase1f2_session,
        model_class=ReconciliationEvidenceLink,
        tenant_id=tenant_id,
        record_data={"line_id": str(line.id), "evidence_ref": "tb:row:1"},
        values={
            "session_id": session_row.id,
            "line_id": line.id,
            "evidence_type": "tb_line",
            "evidence_ref": "tb:row:1",
            "evidence_label": "TB row 1",
            "created_by": tenant_id,
        },
    )
    with pytest.raises(DBAPIError):
        await recon_phase1f2_session.execute(
            text(
                "UPDATE reconciliation_evidence_links "
                "SET evidence_label = 'changed' WHERE id = :id"
            ),
            {"id": str(evidence.id)},
        )
        await recon_phase1f2_session.flush()
