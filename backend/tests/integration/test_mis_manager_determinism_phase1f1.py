from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.mis_manager.application.canonical_dictionary_service import (
    CanonicalDictionaryService,
)
from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.application.validation_service import ValidationService
from financeops.modules.mis_manager.domain.value_objects import (
    SnapshotTokenInput,
    VersionTokenInput,
)
from financeops.modules.mis_manager.infrastructure.signature_builder import (
    build_signature_bundle,
)
from financeops.modules.mis_manager.infrastructure.token_builder import (
    build_snapshot_token,
    build_version_token,
)
from tests.integration.mis_phase1f1_helpers import (
    build_ingest_service,
    csv_b64,
    ensure_tenant_context,
    hash64,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signature_builder_is_stable_across_runs() -> None:
    args = {
        "headers": ["Metric", "Period_2026_01"],
        "row_labels": ["Revenue Net", "Marketing Expense"],
        "column_order": ["Metric", "Period_2026_01"],
        "section_breaks": ["revenue", "expenses"],
        "blank_row_density": Decimal("0.0000"),
        "formula_density": Decimal("0.0000"),
    }
    first = build_signature_bundle(**args)
    second = build_signature_bundle(**args)
    assert first == second


@pytest.mark.asyncio
@pytest.mark.integration
async def test_token_builder_is_stable_across_runs() -> None:
    template_id = uuid.uuid4()
    version_token_input = VersionTokenInput(
        template_id=template_id,
        structure_hash=hash64("token:structure"),
        header_hash=hash64("token:header"),
        row_signature_hash=hash64("token:row"),
        column_signature_hash=hash64("token:column"),
        detection_summary_json={"sheet": "Sheet1", "header_row_index": 1},
    )
    snapshot_token_input = SnapshotTokenInput(
        source_file_hash=hash64("token:file"),
        sheet_name="Sheet1",
        structure_hash=hash64("token:structure"),
        mapping_set_identity=hash64("token:mapping"),
        validation_rule_set_identity="mis_validation_v1",
        reporting_period=date(2026, 1, 31),
        template_version_id=template_id,
        status="pending",
    )
    assert build_version_token(version_token_input) == build_version_token(
        version_token_input
    )
    assert build_snapshot_token(snapshot_token_input) == build_snapshot_token(
        snapshot_token_input
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detection_pipeline_is_stable_for_fixed_fixture(
    mis_phase1f1_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(mis_phase1f1_session, tenant_id)
    service = build_ingest_service(mis_phase1f1_session)
    payload = {
        "tenant_id": tenant_id,
        "template_code": "deterministic_fixture",
        "file_name": "fixture.csv",
        "file_content_base64": csv_b64(
            "Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n"
        ),
        "sheet_name": "csv",
    }
    first = await service.detect_template(**payload)
    second = await service.detect_template(**payload)
    assert first == second


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validation_output_is_stable_for_fixed_fixture(
    mis_phase1f1_session: AsyncSession,
) -> None:
    mapping_service = MappingService(CanonicalDictionaryService())
    snapshot_service = SnapshotService(mapping_service)
    validation_service = ValidationService()

    rows = [["Revenue Net", "1000"], ["Marketing Expense", "200"]]
    headers = ["Metric", "Period_2026_01"]
    first_build = snapshot_service.normalize_sheet(
        sheet_name="Sheet1",
        headers=headers,
        rows=rows,
        currency_code="USD",
    )
    second_build = snapshot_service.normalize_sheet(
        sheet_name="Sheet1",
        headers=headers,
        rows=rows,
        currency_code="USD",
    )
    assert first_build.normalized_lines == second_build.normalized_lines
    assert first_build.exceptions == second_build.exceptions

    first_validation = validation_service.validate_snapshot(
        template_type="pnl_monthly",
        headers=headers,
        lines=first_build.normalized_lines,
        currency_codes=["USD"],
    )
    second_validation = validation_service.validate_snapshot(
        template_type="pnl_monthly",
        headers=headers,
        lines=second_build.normalized_lines,
        currency_codes=["USD"],
    )
    assert first_validation == second_validation
