from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


async def test_vendor_portal_upload_fails_gracefully() -> None:
    """vendor_portal_service: R2 upload failure raises ServiceUnavailableError (503), not raw botocore error."""
    from financeops.core.exceptions import ServiceUnavailableError
    from financeops.modules.accounting_ingestion.application.vendor_portal_service import create_submission

    tenant_id = uuid.uuid4()
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()

    # Vendor email lookup → no vendor found (still runs upload path via airlock admit)
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    mock_airlock_item = MagicMock()
    mock_airlock_item.status = "ADMITTED"
    mock_airlock_item.checksum_sha256 = "abc123"
    mock_airlock_item.mime_type = "text/csv"
    mock_airlock_item.size_bytes = 128
    mock_airlock_item.item_id = uuid.uuid4()

    mock_airlock_service = MagicMock()
    mock_airlock_service.submit_external_input = AsyncMock(
        return_value=MagicMock(item_id=mock_airlock_item.item_id)
    )
    mock_airlock_service.admit_airlock_item = AsyncMock()
    mock_airlock_service.get_item = AsyncMock(return_value=mock_airlock_item)

    mock_storage = MagicMock()
    mock_storage.upload_file = MagicMock(side_effect=Exception("NoCredentialsError: no credentials"))

    with (
        patch(
            "financeops.modules.accounting_ingestion.application.vendor_portal_service.AirlockAdmissionService",
            return_value=mock_airlock_service,
        ),
        patch(
            "financeops.modules.accounting_ingestion.application.vendor_portal_service.resolve_airlock_actor",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "financeops.modules.accounting_ingestion.application.vendor_portal_service.get_storage",
            return_value=mock_storage,
        ),
    ):
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await create_submission(
                mock_db,
                tenant_id=tenant_id,
                submitter_email="vendor@example.com",
                submitter_name="Vendor Co",
                file_bytes=b"col1,col2\n1,2",
                filename="invoice.csv",
                mime_type="text/csv",
            )

    assert exc_info.value.status_code == 503
    assert "storage" in str(exc_info.value).lower()


async def test_board_pack_presigned_url_fails_with_503() -> None:
    """board_pack routes: generate_signed_url failure returns HTTP 503, not an unhandled 500."""
    from financeops.modules.board_pack_generator.api.routes import download_artifact

    run_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id

    mock_run = MagicMock()
    mock_run.id = run_id

    mock_artifact = MagicMock()
    mock_artifact.id = artifact_id
    mock_artifact.run_id = run_id
    mock_artifact.format = "PDF"
    mock_artifact.storage_path = f"artifacts/board_packs/{tenant_id}/{run_id}/{artifact_id}/pack.pdf"

    mock_repo = MagicMock()
    mock_repo.get_run = AsyncMock(return_value=mock_run)
    mock_repo.list_artifacts_for_run = AsyncMock(return_value=[mock_artifact])

    mock_storage = MagicMock()
    mock_storage.generate_signed_url = MagicMock(
        side_effect=Exception("NoCredentialsError: no credentials configured")
    )

    mock_db = MagicMock()

    with (
        patch(
            "financeops.modules.board_pack_generator.api.routes.BoardPackRepository",
            return_value=mock_repo,
        ),
        patch(
            "financeops.modules.board_pack_generator.api.routes.get_storage",
            return_value=mock_storage,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_artifact(
                run_id=run_id,
                format="PDF",
                db=mock_db,
                user=mock_user,
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "File storage unavailable"
