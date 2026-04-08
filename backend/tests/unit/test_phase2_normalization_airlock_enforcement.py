from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from financeops.core.exceptions import ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import MappingService
from financeops.modules.payroll_gl_normalization.application.payroll_normalization_service import (
    PayrollNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.run_service import (
    NormalizationRunService,
)
from financeops.modules.payroll_gl_normalization.application.source_detection_service import (
    SourceDetectionService,
)
from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService,
)


@pytest.mark.asyncio
async def test_normalization_upload_run_requires_admitted_airlock_reference() -> None:
    repository = MagicMock()
    repository._session = MagicMock()
    service = NormalizationRunService(
        repository=repository,
        source_detection_service=SourceDetectionService(),
        mapping_service=MappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=ValidationService(),
    )

    with pytest.raises(ValidationError, match="cannot run without an active intent/job context"):
        await service.upload_run(
            tenant_id=uuid.uuid4(),
            organisation_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            source_version_id=uuid.uuid4(),
            run_type="payroll_normalization",
            reporting_period=__import__("datetime").date(2026, 3, 31),
            source_artifact_id=uuid.uuid4(),
            file_name="payroll.csv",
            file_content_base64="aWQsdmFsdWUKMSwy",
            sheet_name=None,
            created_by=uuid.uuid4(),
            admitted_airlock_item_id=None,
        )


@pytest.mark.asyncio
async def test_normalization_upload_run_requires_admitted_airlock_reference_after_context() -> None:
    repository = MagicMock()
    repository._session = MagicMock()
    service = NormalizationRunService(
        repository=repository,
        source_detection_service=SourceDetectionService(),
        mapping_service=MappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=ValidationService(),
    )

    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=uuid.uuid4(),
            actor_role="finance_leader",
            intent_type="TEST_NORMALIZATION_UPLOAD",
        )
    ):
        with pytest.raises(ValidationError, match="admitted_airlock_item_id is required"):
            await service.upload_run(
                tenant_id=uuid.uuid4(),
                organisation_id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                source_version_id=uuid.uuid4(),
                run_type="payroll_normalization",
                reporting_period=__import__("datetime").date(2026, 3, 31),
                source_artifact_id=uuid.uuid4(),
                file_name="payroll.csv",
                file_content_base64="aWQsdmFsdWUKMSwy",
                sheet_name=None,
                created_by=uuid.uuid4(),
                admitted_airlock_item_id=None,
            )
