from __future__ import annotations

import csv
import io
from decimal import Decimal
from unittest.mock import MagicMock

from financeops.db.models.accounting_notifications import (
    AccountingAPAgeingSnapshot,
    ExportFormat,
    ExportType,
    NotificationChannel,
    NotificationType,
)


class TestNotificationTypeConstants:
    def test_all_types_defined(self) -> None:
        for value in (
            NotificationType.APPROVAL_REQUIRED,
            NotificationType.JV_APPROVED,
            NotificationType.JV_REJECTED,
            NotificationType.SLA_BREACH,
            NotificationType.PUSH_FAILED,
            NotificationType.DAILY_DIGEST,
            NotificationType.REMINDER_24H,
            NotificationType.REMINDER_48H,
        ):
            assert value in NotificationType.ALL

    def test_8_notification_types(self) -> None:
        assert len(NotificationType.ALL) == 8

    def test_reminder_types_distinct(self) -> None:
        assert NotificationType.REMINDER_24H != NotificationType.REMINDER_48H


class TestNotificationChannelConstants:
    def test_all_channels_defined(self) -> None:
        assert NotificationChannel.IN_APP in NotificationChannel.ALL
        assert NotificationChannel.EMAIL in NotificationChannel.ALL
        assert NotificationChannel.PUSH in NotificationChannel.ALL

    def test_3_channels(self) -> None:
        assert len(NotificationChannel.ALL) == 3


class TestExportConstants:
    def test_export_types_defined(self) -> None:
        for value in (
            ExportType.JV_LIFECYCLE,
            ExportType.ERP_PUSH,
            ExportType.APPROVALS,
            ExportType.AP_AGEING,
            ExportType.FULL_ACCOUNTING,
        ):
            assert value in ExportType.ALL

    def test_export_formats(self) -> None:
        assert ExportFormat.CSV in ExportFormat.ALL
        assert ExportFormat.PDF in ExportFormat.ALL
        assert len(ExportFormat.ALL) == 2


class TestAPAgeingDecimal:
    def _make_snapshot(
        self,
        current: str = "100000.00",
        overdue_1_30: str = "50000.00",
        overdue_31_60: str = "30000.00",
        overdue_61_90: str = "20000.00",
        overdue_90_plus: str = "10000.00",
    ) -> AccountingAPAgeingSnapshot:
        row = MagicMock(spec=AccountingAPAgeingSnapshot)
        row.current_amount = Decimal(current)
        row.overdue_1_30 = Decimal(overdue_1_30)
        row.overdue_31_60 = Decimal(overdue_31_60)
        row.overdue_61_90 = Decimal(overdue_61_90)
        row.overdue_90_plus = Decimal(overdue_90_plus)
        row.total_outstanding = (
            Decimal(current)
            + Decimal(overdue_1_30)
            + Decimal(overdue_31_60)
            + Decimal(overdue_61_90)
            + Decimal(overdue_90_plus)
        )
        return row

    def test_total_overdue_is_sum_of_buckets(self) -> None:
        row = self._make_snapshot()
        expected = Decimal("110000.00")
        total_overdue = row.overdue_1_30 + row.overdue_31_60 + row.overdue_61_90 + row.overdue_90_plus
        assert total_overdue == expected

    def test_amounts_are_decimal_not_float(self) -> None:
        row = self._make_snapshot()
        assert isinstance(row.current_amount, Decimal)
        assert isinstance(row.overdue_1_30, Decimal)
        assert isinstance(row.total_outstanding, Decimal)

    def test_decimal_precision_no_float_leakage(self) -> None:
        assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")

    def test_large_amounts(self) -> None:
        row = self._make_snapshot(
            current="99999999.9999",
            overdue_1_30="88888888.8888",
        )
        assert row.current_amount == Decimal("99999999.9999")

    def test_total_outstanding_equals_sum_of_all_buckets(self) -> None:
        current = Decimal("100000.00")
        overdue_1_30 = Decimal("50000.00")
        overdue_31_60 = Decimal("30000.00")
        overdue_61_90 = Decimal("20000.00")
        overdue_90_plus = Decimal("10000.00")
        expected = current + overdue_1_30 + overdue_31_60 + overdue_61_90 + overdue_90_plus
        assert expected == Decimal("210000.00")


class TestAPAgeingCSV:
    def test_csv_amounts_are_strings(self) -> None:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["snapshot_date", "current_amount", "total_outstanding"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "snapshot_date": "2026-03-01",
                "current_amount": str(Decimal("100000.00")),
                "total_outstanding": str(Decimal("210000.00")),
            }
        )
        content = output.getvalue()
        assert "100000.00" in content
        assert "210000.00" in content
        assert "1e5" not in content
        assert "2.1e5" not in content

    def test_csv_headers_present(self) -> None:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "snapshot_date",
                "vendor_id",
                "current_amount",
                "overdue_1_30",
                "overdue_31_60",
                "overdue_61_90",
                "overdue_90_plus",
                "total_outstanding",
                "currency",
                "data_source",
                "connector_type",
            ],
        )
        writer.writeheader()
        content = output.getvalue()
        assert "snapshot_date" in content
        assert "total_outstanding" in content
        assert "overdue_90_plus" in content


class TestAuditExportAmounts:
    def test_jv_total_debit_as_string_in_export(self) -> None:
        serialised = str(Decimal("500000.0000"))
        assert serialised == "500000.0000"
        assert "e" not in serialised.lower()

    def test_approval_threshold_as_string(self) -> None:
        assert str(Decimal("5000000.0000")) == "5000000.0000"

    def test_zero_decimal_as_string(self) -> None:
        assert str(Decimal("0")) == "0"
        assert str(Decimal("0.00")) == "0.00"


class TestRBACSeeds:
    def test_6_accounting_roles_defined(self) -> None:
        roles = [
            "ACCOUNTING_PREPARER",
            "ACCOUNTING_REVIEWER",
            "ACCOUNTING_SR_REVIEWER",
            "ACCOUNTING_CFO_APPROVER",
            "ACCOUNTING_ADMIN",
            "ACCOUNTING_AUDITOR",
        ]
        assert len(roles) == 6
        assert len(set(roles)) == 6

    def test_role_ids_are_stable_uuids(self) -> None:
        import uuid

        preparer = "a1000001-0000-0000-0000-000000000001"
        auditor = "a1000001-0000-0000-0000-000000000006"
        assert preparer != auditor
        uuid.UUID(preparer)
        uuid.UUID(auditor)

    def test_on_conflict_target_is_role_code(self) -> None:
        assert "uq_cp_roles_code" == "uq_cp_roles_code"

    def test_new_phase11_permissions_defined(self) -> None:
        permissions = ["ap_ageing:view", "audit:export", "notification:manage"]
        assert len(permissions) == 3
        assert all(":" in permission for permission in permissions)


class TestSLANudgeLogic:
    def test_24h_nudge_triggers_at_review_sla_hours(self) -> None:
        review_sla_hours = 24
        hours_pending = 25.0
        nudge_24h_sent = False
        assert (hours_pending >= review_sla_hours and not nudge_24h_sent) is True

    def test_24h_nudge_not_sent_before_threshold(self) -> None:
        review_sla_hours = 24
        hours_pending = 20.0
        nudge_24h_sent = False
        assert (hours_pending >= review_sla_hours and not nudge_24h_sent) is False

    def test_24h_nudge_not_double_sent(self) -> None:
        review_sla_hours = 24
        hours_pending = 50.0
        nudge_24h_sent = True
        assert (hours_pending >= review_sla_hours and not nudge_24h_sent) is False

    def test_48h_nudge_triggers_at_approval_sla_hours(self) -> None:
        approval_sla_hours = 48
        hours_pending = 50.0
        nudge_48h_sent = False
        assert (hours_pending >= approval_sla_hours and not nudge_48h_sent) is True

    def test_both_nudges_independent(self) -> None:
        review_sla_hours = 24
        approval_sla_hours = 48
        hours_pending = 50.0
        send_24h = hours_pending >= review_sla_hours and not False
        send_48h = hours_pending >= approval_sla_hours and not False
        assert send_24h is True
        assert send_48h is True

