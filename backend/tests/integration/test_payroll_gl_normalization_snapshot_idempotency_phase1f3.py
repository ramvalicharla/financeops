from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.normalization_phase1f3_helpers import (
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
)


async def _commit_payroll_source_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_code: str,
) -> dict:
    service = build_normalization_service(session)
    return await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="payroll",
        source_code=source_code,
        source_name="Payroll Source",
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={
            "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
        },
        activate=True,
        created_by=tenant_id,
    )


async def _commit_gl_source_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_code: str,
) -> dict:
    service = build_normalization_service(session)
    return await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_family="gl",
        source_code=source_code,
        source_name="GL Source",
        structure_hash="d" * 64,
        header_hash="e" * 64,
        row_signature_hash="f" * 64,
        source_detection_summary_json={
            "headers": ["Account Code", "Debit", "Credit", "Currency", "Posting Date"]
        },
        activate=True,
        created_by=tenant_id,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_identical_upload_produces_identical_run_token(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    committed = await _commit_payroll_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_code=f"payroll_idem_{uuid.uuid4().hex[:8]}",
    )
    service = build_normalization_service(normalization_phase1f3_session)
    upload_kwargs = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "source_id": uuid.UUID(committed["source_id"]),
        "source_version_id": uuid.UUID(committed["source_version_id"]),
        "run_type": "payroll_normalization",
        "reporting_period": date(2026, 1, 31),
        "source_artifact_id": uuid.uuid4(),
        "file_name": "payroll.csv",
        "file_content_base64": csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
        ),
        "sheet_name": "csv",
        "created_by": tenant_id,
    }
    first = await service.upload_run(**upload_kwargs)
    second = await service.upload_run(**upload_kwargs)
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_upload_does_not_create_invalid_duplicate_normalized_lines(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    committed = await _commit_payroll_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_code=f"payroll_dup_{uuid.uuid4().hex[:8]}",
    )
    service = build_normalization_service(normalization_phase1f3_session)
    payload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "source_id": uuid.UUID(committed["source_id"]),
        "source_version_id": uuid.UUID(committed["source_version_id"]),
        "run_type": "payroll_normalization",
        "reporting_period": date(2026, 2, 28),
        "source_artifact_id": uuid.uuid4(),
        "file_name": "payroll.csv",
        "file_content_base64": csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\nE002,Bob,1200,USD\n"
        ),
        "sheet_name": "csv",
        "created_by": tenant_id,
    }
    first = await service.upload_run(**payload)
    second = await service.upload_run(**payload)
    assert second["idempotent"] is True
    row_count = (
        await normalization_phase1f3_session.execute(
            text("SELECT COUNT(*) FROM payroll_normalized_lines WHERE run_id = :run_id"),
            {"run_id": first["run_id"]},
        )
    ).scalar_one()
    assert row_count == first["payroll_line_count"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_changed_file_hash_changes_run_token_when_expected(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    committed = await _commit_payroll_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_code=f"payroll_filehash_{uuid.uuid4().hex[:8]}",
    )
    service = build_normalization_service(normalization_phase1f3_session)
    base_payload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "source_id": uuid.UUID(committed["source_id"]),
        "source_version_id": uuid.UUID(committed["source_version_id"]),
        "run_type": "payroll_normalization",
        "reporting_period": date(2026, 1, 31),
        "source_artifact_id": uuid.uuid4(),
        "file_name": "payroll.csv",
        "sheet_name": "csv",
        "created_by": tenant_id,
    }
    first = await service.upload_run(
        **base_payload,
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
        ),
    )
    second = await service.upload_run(
        **base_payload,
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1100,USD\n"
        ),
    )
    assert first["run_token"] != second["run_token"]
    assert first["run_id"] != second["run_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_same_file_different_reporting_period_changes_run_token_when_expected(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    committed = await _commit_payroll_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_code=f"payroll_period_{uuid.uuid4().hex[:8]}",
    )
    service = build_normalization_service(normalization_phase1f3_session)
    csv_payload = csv_b64(
        "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
    )
    first = await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_payload,
        sheet_name="csv",
        created_by=tenant_id,
    )
    second = await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 2, 28),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_payload,
        sheet_name="csv",
        created_by=tenant_id,
    )
    assert first["run_token"] != second["run_token"]
    assert first["run_id"] != second["run_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_gl_identical_upload_produces_identical_run_token(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    committed = await _commit_gl_source_version(
        normalization_phase1f3_session,
        tenant_id=tenant_id,
        source_code=f"gl_idem_{uuid.uuid4().hex[:8]}",
    )
    service = build_normalization_service(normalization_phase1f3_session)
    payload = {
        "tenant_id": tenant_id,
        "organisation_id": tenant_id,
        "source_id": uuid.UUID(committed["source_id"]),
        "source_version_id": uuid.UUID(committed["source_version_id"]),
        "run_type": "gl_normalization",
        "reporting_period": date(2026, 1, 31),
        "source_artifact_id": uuid.uuid4(),
        "file_name": "gl.csv",
        "file_content_base64": csv_b64(
            "Account Code,Debit,Credit,Currency,Posting Date\n4000,1000,0,USD,2026-01-31\n"
        ),
        "sheet_name": "csv",
        "created_by": tenant_id,
    }
    first = await service.upload_run(**payload)
    second = await service.upload_run(**payload)
    assert first["run_token"] == second["run_token"]
    assert first["run_id"] == second["run_id"]
    assert second["idempotent"] is True
