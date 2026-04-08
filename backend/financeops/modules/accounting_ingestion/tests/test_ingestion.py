from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financeops.db.models.accounting_ingestion import (
    EmailProcessingStatus,
    PortalSubmissionStatus,
)
from financeops.modules.accounting_ingestion.application.email_ingestion_service import (
    _is_sender_whitelisted,
    ingest_email,
)
from financeops.modules.accounting_ingestion.application.ocr_pipeline_service import (
    TextractProvider,
)
from financeops.modules.accounting_ingestion.application.vendor_portal_service import (
    _generate_reference_id,
    create_submission,
)
from financeops.modules.accounting_ingestion.domain.schemas import (
    EntityDetectionResult,
    EntityDetectionSignal,
    NormalisedExtractionResult,
)


class TestToDecimal:
    def setup_method(self) -> None:
        self.provider = TextractProvider()

    def test_plain_decimal_string(self) -> None:
        assert self.provider._to_decimal("1000.50") == Decimal("1000.50")

    def test_comma_separated(self) -> None:
        assert self.provider._to_decimal("1,00,000.00") == Decimal("100000.00")

    def test_rupee_symbol(self) -> None:
        assert self.provider._to_decimal("\u20b95000.00") == Decimal("5000.00")

    def test_none_returns_none(self) -> None:
        assert self.provider._to_decimal(None) is None

    def test_invalid_returns_none(self) -> None:
        assert self.provider._to_decimal("not-a-number") is None

    def test_returns_decimal_not_float(self) -> None:
        value = self.provider._to_decimal("100.00")
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)


class TestParseDate:
    def setup_method(self) -> None:
        self.provider = TextractProvider()

    def test_dd_mm_yyyy_slash(self) -> None:
        assert self.provider._parse_date("01/03/2026") == date(2026, 3, 1)

    def test_yyyy_mm_dd(self) -> None:
        assert self.provider._parse_date("2026-03-01") == date(2026, 3, 1)

    def test_invalid_returns_none(self) -> None:
        assert self.provider._parse_date("not-a-date") is None


class TestExtractField:
    def setup_method(self) -> None:
        self.provider = TextractProvider()

    def _make_field(self, type_text: str, value: str, confidence_percent: float) -> dict:
        return {
            "Type": {"Text": type_text},
            "ValueDetection": {"Text": value, "Confidence": confidence_percent},
        }

    def test_field_found(self) -> None:
        fields = [
            self._make_field("VENDOR_NAME", "Acme Corp", 95.0),
            self._make_field("TOTAL", "5000.00", 90.0),
        ]
        value, confidence = self.provider._extract_field(fields, "VENDOR_NAME")
        assert value == "Acme Corp"
        assert abs(confidence - 0.95) < 0.001

    def test_field_not_found(self) -> None:
        value, confidence = self.provider._extract_field([], "VENDOR_NAME")
        assert value is None
        assert confidence == 0.0


class TestTextractExtract:
    @pytest.mark.asyncio
    async def test_low_quality_when_no_documents(self) -> None:
        provider = TextractProvider()
        with patch.object(
            provider,
            "_get_client",
            return_value=MagicMock(analyze_expense=MagicMock(return_value={"ExpenseDocuments": []})),
        ):
            result = await provider.extract(b"pdf", "inv.pdf", "application/pdf")
        assert result.low_quality is True
        assert result.requires_manual_review is True

    @pytest.mark.asyncio
    async def test_multi_invoice_detected(self) -> None:
        provider = TextractProvider()
        response = {
            "ExpenseDocuments": [
                {"SummaryFields": [], "LineItemGroups": []},
                {"SummaryFields": [], "LineItemGroups": []},
            ]
        }
        with patch.object(
            provider,
            "_get_client",
            return_value=MagicMock(analyze_expense=MagicMock(return_value=response)),
        ):
            result = await provider.extract(b"pdf", "inv.pdf", "application/pdf")
        assert result.multi_invoice_detected is True

    @pytest.mark.asyncio
    async def test_no_float_in_extracted_amounts(self) -> None:
        provider = TextractProvider()
        response = {
            "ExpenseDocuments": [
                {
                    "SummaryFields": [
                        {"Type": {"Text": "VENDOR_NAME"}, "ValueDetection": {"Text": "Acme", "Confidence": 95.0}},
                        {"Type": {"Text": "INVOICE_RECEIPT_ID"}, "ValueDetection": {"Text": "INV-001", "Confidence": 92.0}},
                        {"Type": {"Text": "TOTAL"}, "ValueDetection": {"Text": "5000.00", "Confidence": 93.0}},
                        {"Type": {"Text": "SUBTOTAL"}, "ValueDetection": {"Text": "4500.00", "Confidence": 90.0}},
                        {"Type": {"Text": "TAX"}, "ValueDetection": {"Text": "500.00", "Confidence": 89.0}},
                    ],
                    "LineItemGroups": [],
                }
            ]
        }
        with patch.object(
            provider,
            "_get_client",
            return_value=MagicMock(analyze_expense=MagicMock(return_value=response)),
        ):
            result = await provider.extract(b"pdf", "inv.pdf", "application/pdf")
        if result.total is not None:
            assert isinstance(result.total, Decimal)
        if result.subtotal is not None:
            assert isinstance(result.subtotal, Decimal)
        if result.tax_amount is not None:
            assert isinstance(result.tax_amount, Decimal)


class TestIsSenderWhitelisted:
    def test_full_email_match(self) -> None:
        assert _is_sender_whitelisted("vendor@acme.com", ["vendor@acme.com"]) is True

    def test_domain_match(self) -> None:
        assert _is_sender_whitelisted("billing@acme.com", ["@acme.com"]) is True

    def test_not_in_whitelist(self) -> None:
        assert _is_sender_whitelisted("unknown@evil.com", ["@acme.com"]) is False


class TestGenerateReferenceId:
    def test_length_16(self) -> None:
        assert len(_generate_reference_id()) == 16

    def test_unique(self) -> None:
        refs = {_generate_reference_id() for _ in range(100)}
        assert len(refs) == 100


class TestPortalSubmissionStatus:
    def test_only_constrained_states(self) -> None:
        expected = {
            PortalSubmissionStatus.RECEIVED,
            PortalSubmissionStatus.UNDER_REVIEW,
            PortalSubmissionStatus.ACCEPTED,
            PortalSubmissionStatus.REJECTED,
        }
        assert PortalSubmissionStatus.ALL == expected

    def test_no_jv_states_exposed(self) -> None:
        forbidden = {"DRAFT", "SUBMITTED", "APPROVED", "PUSHED", "VOIDED"}
        assert not forbidden.intersection(PortalSubmissionStatus.ALL)


class TestEmailProcessingStatus:
    def test_all_states_defined(self) -> None:
        assert len(EmailProcessingStatus.ALL) == 5
        assert EmailProcessingStatus.PENDING in EmailProcessingStatus.ALL
        assert EmailProcessingStatus.REJECTED in EmailProcessingStatus.ALL


class TestNormalisedExtractionResult:
    def test_decimal_amounts(self) -> None:
        result = NormalisedExtractionResult(
            total=Decimal("5000.00"),
            subtotal=Decimal("4500.00"),
            tax_amount=Decimal("500.00"),
        )
        assert isinstance(result.total, Decimal)
        assert isinstance(result.subtotal, Decimal)
        assert isinstance(result.tax_amount, Decimal)

    def test_default_currency_inr(self) -> None:
        assert NormalisedExtractionResult().currency == "INR"


class TestEntityDetectionResult:
    def test_confidence_range(self) -> None:
        result = EntityDetectionResult(detected_entity_id=uuid.uuid4(), confidence=0.95)
        assert 0.0 <= result.confidence <= 1.0

    def test_signal_schema(self) -> None:
        signal = EntityDetectionSignal(
            signal_type="ROUTING_RULE",
            entity_id=uuid.uuid4(),
            confidence=1.0,
            reason="routing",
        )
        assert signal.confidence == 1.0


class TestUniversalAirlockEnforcement:
    @pytest.mark.asyncio
    async def test_vendor_portal_submission_uses_airlock_admission_service(self) -> None:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
        fake_submission = SimpleNamespace(
            id=uuid.uuid4(),
            reference_id="REF1234567890123",
            status=PortalSubmissionStatus.RECEIVED,
        )
        fake_item = SimpleNamespace(
            mime_type="application/pdf",
            size_bytes=4,
            checksum_sha256="abc123",
            status="ADMITTED",
        )

        with (
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.resolve_airlock_actor",
                new=AsyncMock(return_value=SimpleNamespace(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="finance_leader")),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.AirlockAdmissionService.submit_external_input",
                new=AsyncMock(return_value=SimpleNamespace(item_id=uuid.uuid4())),
            ) as submit_mock,
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.AirlockAdmissionService.admit_airlock_item",
                new=AsyncMock(return_value=SimpleNamespace(item_id=uuid.uuid4(), status="ADMITTED")),
            ) as admit_mock,
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.AirlockAdmissionService.get_item",
                new=AsyncMock(return_value=fake_item),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.AuditWriter.insert_financial_record",
                new=AsyncMock(return_value=fake_submission),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.vendor_portal_service.get_storage",
                return_value=MagicMock(upload_file=MagicMock()),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.ocr_task.run_ocr_pipeline_task.apply_async",
                new=MagicMock(),
            ),
        ):
            row = await create_submission(
                db,
                tenant_id=uuid.uuid4(),
                submitter_email="vendor@example.com",
                submitter_name="Vendor",
                file_bytes=b"data",
                filename="invoice.pdf",
                mime_type="application/pdf",
            )

        assert submit_mock.await_count == 1
        assert admit_mock.await_count == 1
        assert row.reference_id == fake_submission.reference_id

    @pytest.mark.asyncio
    async def test_email_ingestion_uses_airlock_admission_service(self) -> None:
        tenant_id = uuid.uuid4()
        message_id = uuid.uuid4()
        message_row = SimpleNamespace(
            id=message_id,
            processing_status=EmailProcessingStatus.PENDING,
            sender_whitelisted=True,
            attachment_count=1,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: None),
            ]
        )

        with (
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.resolve_airlock_actor",
                new=AsyncMock(return_value=SimpleNamespace(user_id=uuid.uuid4(), tenant_id=tenant_id, role="finance_leader")),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.AuditWriter.insert_financial_record",
                new=AsyncMock(return_value=message_row),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.AirlockAdmissionService.submit_external_input",
                new=AsyncMock(return_value=SimpleNamespace(item_id=uuid.uuid4())),
            ) as submit_mock,
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.AirlockAdmissionService.admit_airlock_item",
                new=AsyncMock(return_value=SimpleNamespace(item_id=uuid.uuid4(), status="ADMITTED")),
            ) as admit_mock,
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.AirlockAdmissionService.get_item",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        checksum_sha256="abc123",
                        mime_type="application/pdf",
                    )
                ),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service.get_storage",
                return_value=MagicMock(upload_file=MagicMock()),
            ),
            patch(
                "financeops.modules.accounting_ingestion.application.email_ingestion_service._enqueue_ocr",
                new=MagicMock(),
            ),
        ):
            row = await ingest_email(
                db,
                tenant_id=tenant_id,
                message_id="mail-1",
                sender_email="vendor@example.com",
                sender_name="Vendor",
                subject="Invoice",
                attachment_bytes_list=[("invoice.pdf", b"data", "application/pdf")],
                sender_whitelist=["vendor@example.com"],
            )

        assert submit_mock.await_count == 1
        assert admit_mock.await_count == 1
        assert row.id == message_id
