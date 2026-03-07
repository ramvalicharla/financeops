from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.mis_phase1f1_helpers import (
    build_ingest_service,
    csv_b64,
    ensure_tenant_context,
    hash64,
)


async def _commit_template_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_code: str,
    structure_seed: str,
    activate: bool = True,
) -> dict:
    service = build_ingest_service(session)
    return await service.commit_template_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_code=template_code,
        template_name="Snapshot Idempotency Template",
        template_type="pnl_monthly",
        created_by=tenant_id,
        structure_hash=hash64(f"{structure_seed}:structure"),
        header_hash=hash64(f"{structure_seed}:header"),
        row_signature_hash=hash64(f"{structure_seed}:row"),
        column_signature_hash=hash64(f"{structure_seed}:column"),
        detection_summary_json={"seed": structure_seed},
        drift_reason=None,
        activate=activate,
        effective_from=None,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_upload_produces_identical_snapshot_token(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    committed = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"idem_template_{uuid.uuid4().hex[:8]}",
        structure_seed="idem_structure",
    )
    payload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "template_id": uuid.UUID(committed["template_id"]),
        "template_version_id": uuid.UUID(committed["template_version_id"]),
        "reporting_period": date(2026, 1, 31),
        "upload_artifact_id": uuid.UUID("00000000-0000-0000-0000-000000000101"),
        "file_name": "snapshot.csv",
        "file_content_base64": csv_b64(
            "Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n"
        ),
        "sheet_name": "csv",
        "currency_code": "USD",
        "created_by": tenant_id,
    }
    first = await service.upload_snapshot(**payload)
    second = await service.upload_snapshot(**payload)
    assert first["snapshot_token"] == second["snapshot_token"]
    assert first["snapshot_id"] == second["snapshot_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_upload_does_not_create_invalid_duplicate_normalized_lines(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    committed = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"idem_lines_{uuid.uuid4().hex[:8]}",
        structure_seed="idem_lines",
    )
    upload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "template_id": uuid.UUID(committed["template_id"]),
        "template_version_id": uuid.UUID(committed["template_version_id"]),
        "reporting_period": date(2026, 1, 31),
        "upload_artifact_id": uuid.UUID("00000000-0000-0000-0000-000000000202"),
        "file_name": "snapshot.csv",
        "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
        "sheet_name": "csv",
        "currency_code": "USD",
        "created_by": tenant_id,
    }
    first = await service.upload_snapshot(**upload)
    line_count_before = (
        await mis_phase1f1_session.execute(
            text("SELECT COUNT(*) FROM mis_normalized_lines WHERE snapshot_id = :snapshot_id"),
            {"snapshot_id": first["snapshot_id"]},
        )
    ).scalar_one()

    second = await service.upload_snapshot(**upload)
    line_count_after = (
        await mis_phase1f1_session.execute(
            text("SELECT COUNT(*) FROM mis_normalized_lines WHERE snapshot_id = :snapshot_id"),
            {"snapshot_id": second["snapshot_id"]},
        )
    ).scalar_one()
    assert line_count_after == line_count_before
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_file_hash_changes_snapshot_token_when_expected(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    committed = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"idem_file_{uuid.uuid4().hex[:8]}",
        structure_seed="idem_file",
    )

    upload_common = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "template_id": uuid.UUID(committed["template_id"]),
        "template_version_id": uuid.UUID(committed["template_version_id"]),
        "reporting_period": date(2026, 1, 31),
        "sheet_name": "csv",
        "currency_code": "USD",
        "created_by": tenant_id,
    }
    first = await service.upload_snapshot(
        **upload_common,
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000303"),
        file_name="snapshot_a.csv",
        file_content_base64=csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
    )
    second = await service.upload_snapshot(
        **upload_common,
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000304"),
        file_name="snapshot_b.csv",
        file_content_base64=csv_b64("Metric,Period_2026_01\nRevenue Net,1001\n"),
    )
    assert first["snapshot_token"] != second["snapshot_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_same_file_different_reporting_period_changes_snapshot_token_when_expected(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    committed = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=f"idem_period_{uuid.uuid4().hex[:8]}",
        structure_seed="idem_period",
    )

    payload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "template_id": uuid.UUID(committed["template_id"]),
        "template_version_id": uuid.UUID(committed["template_version_id"]),
        "file_name": "snapshot.csv",
        "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
        "sheet_name": "csv",
        "currency_code": "USD",
        "created_by": tenant_id,
    }
    jan = await service.upload_snapshot(
        **payload,
        reporting_period=date(2026, 1, 31),
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000401"),
    )
    feb = await service.upload_snapshot(
        **payload,
        reporting_period=date(2026, 2, 28),
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000402"),
    )
    assert jan["snapshot_token"] != feb["snapshot_token"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_template_version_changes_snapshot_token_when_expected(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    stable_code = f"idem_version_target_{uuid.uuid4().hex[:8]}"
    first_commit = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=stable_code,
        structure_seed="idem_version_target_v1",
    )
    second_commit = await _commit_template_version(
        mis_phase1f1_session,
        tenant_id=tenant_id,
        template_code=stable_code,
        structure_seed="idem_version_target_v2",
        activate=False,
    )
    upload_common = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "template_id": uuid.UUID(first_commit["template_id"]),
        "reporting_period": date(2026, 1, 31),
        "file_name": "snapshot.csv",
        "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
        "sheet_name": "csv",
        "currency_code": "USD",
        "created_by": tenant_id,
    }
    s1 = await service.upload_snapshot(
        **upload_common,
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000501"),
        template_version_id=uuid.UUID(first_commit["template_version_id"]),
    )
    s2 = await service.upload_snapshot(
        **upload_common,
        upload_artifact_id=uuid.UUID("00000000-0000-0000-0000-000000000502"),
        template_version_id=uuid.UUID(second_commit["template_version_id"]),
    )
    assert s1["snapshot_token"] != s2["snapshot_token"]
