from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_normalization.domain.entities import (
    NormalizationExceptionEntry,
)
from financeops.modules.payroll_gl_normalization.domain.enums import ExceptionSeverity
from financeops.modules.payroll_gl_normalization.domain.value_objects import (
    RunTokenInput,
    SourceVersionTokenInput,
)
from financeops.modules.payroll_gl_normalization.infrastructure.structure_signature_builder import (
    build_structure_signature,
)
from financeops.modules.payroll_gl_normalization.infrastructure.token_builder import (
    build_run_token,
    build_source_version_token,
)
from tests.integration.normalization_phase1f3_helpers import (
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_signature_builder_is_stable_across_runs() -> None:
    first = build_structure_signature(
        headers=["Employee ID", "Employee Name", "Gross Pay", "Currency"],
        row_labels=["E001", "E002"],
        source_family="payroll",
        blank_row_density=Decimal("0"),
        formula_density=Decimal("0"),
    )
    second = build_structure_signature(
        headers=["Employee ID", "Employee Name", "Gross Pay", "Currency"],
        row_labels=["E001", "E002"],
        source_family="payroll",
        blank_row_density=Decimal("0"),
        formula_density=Decimal("0"),
    )
    assert first == second


@pytest.mark.asyncio
@pytest.mark.integration
async def test_token_builder_is_stable_across_runs() -> None:
    source_id = uuid.uuid4()
    version_id = uuid.uuid4()
    source_input = SourceVersionTokenInput(
        source_id=source_id,
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={"headers": ["x", "y"]},
    )
    run_input = RunTokenInput(
        source_id=source_id,
        source_version_id=version_id,
        mapping_version_token="d" * 64,
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_file_hash="e" * 64,
        run_status="pending",
    )
    assert build_source_version_token(source_input) == build_source_version_token(source_input)
    assert build_run_token(run_input) == build_run_token(run_input)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detection_pipeline_is_stable_for_fixed_fixture(
    normalization_phase1f3_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await ensure_tenant_context(normalization_phase1f3_session, tenant_id)
    service = build_normalization_service(normalization_phase1f3_session)
    payload = {
        "tenant_id": tenant_id,
        "source_code": f"det_src_{uuid.uuid4().hex[:8]}",
        "file_name": "payroll.csv",
        "file_content_base64": csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\nE002,Bob,1200,USD\n"
        ),
        "source_family_hint": "payroll",
        "sheet_name": "csv",
    }
    first = await service.detect_source(**payload)
    second = await service.detect_source(**payload)
    assert first["source_family"] == second["source_family"]
    assert first["signature"] == second["signature"]
    assert first["proposed_mappings"] == second["proposed_mappings"]
    assert first["unmapped_headers"] == second["unmapped_headers"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_validation_output_is_stable_for_fixed_fixture() -> None:
    validation = ValidationService()
    exceptions = [
        NormalizationExceptionEntry(
            exception_code="UNMAPPED_PAY_COMPONENT",
            severity=ExceptionSeverity.WARNING,
            source_ref="row:1,col:bonus",
            message="Numeric payroll component was not mapped",
        ),
        NormalizationExceptionEntry(
            exception_code="REQUIRED_FIELD_MISSING",
            severity=ExceptionSeverity.ERROR,
            source_ref="headers",
            message="Payroll upload requires employee anchor column",
        ),
    ]
    first = validation.summarize(exceptions=exceptions)
    second = validation.summarize(exceptions=exceptions)
    assert first == second
