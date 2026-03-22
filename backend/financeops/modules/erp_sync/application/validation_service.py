from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Any

from financeops.modules.erp_sync.domain.enums import SyncRunStatus


VALIDATION_CATEGORIES: tuple[str, ...] = (
    "REQUIRED_FIELD_PRESENCE",
    "DUPLICATE_SYNC_DETECTION",
    "CURRENCY_CONSISTENCY",
    "ENTITY_SCOPE_CONSISTENCY",
    "PERIOD_CONSISTENCY",
    "BALANCE_CHECK",
    "SNAPSHOT_INTEGRITY",
    "DELTA_BOUNDARY",
    "CAPABILITY_MISMATCH",
    "MAPPING_COMPLETENESS",
    "AGEING_BUCKET_INTEGRITY",
    "REGISTER_LINE_INTEGRITY",
    "BANK_BALANCE_INTEGRITY",
    "BANK_MULTICURRENCY_INTEGRITY",
    "INVENTORY_VALUE_INTEGRITY",
    "MASTER_DATA_REFERENTIAL",
    "PII_CONSENT_CHECK",
    "IRN_FORMAT_VALIDITY",
    "GSTR_PERIOD_CONSISTENCY",
    "BACKDATED_MODIFICATION_CHECK",
)


@dataclass(frozen=True)
class ValidationOutcome:
    category: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "passed": self.passed,
            "message": self.message,
        }


class ValidationService:
    def validate(
        self,
        *,
        dataset_type: str,
        canonical_payload: Mapping[str, Any],
        raw_payload: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_values = dict(context or {})
        outcomes: list[ValidationOutcome] = []

        for category in VALIDATION_CATEGORIES:
            passed, message = self._evaluate_category(
                category=category,
                dataset_type=dataset_type,
                canonical_payload=canonical_payload,
                raw_payload=raw_payload,
                context=context_values,
            )
            outcomes.append(ValidationOutcome(category=category, passed=passed, message=message))

        all_passed = all(outcome.passed for outcome in outcomes)
        return {
            "dataset_type": dataset_type,
            "passed": all_passed,
            "run_status": SyncRunStatus.COMPLETED.value if all_passed else SyncRunStatus.HALTED.value,
            "categories": [outcome.to_dict() for outcome in outcomes],
        }

    def _evaluate_category(
        self,
        *,
        category: str,
        dataset_type: str,
        canonical_payload: Mapping[str, Any],
        raw_payload: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> tuple[bool, str]:
        override_key = f"{category.lower()}_pass"
        if override_key in context:
            passed = bool(context[override_key])
            return passed, "override"

        forced_failures = context.get("force_fail_categories")
        if isinstance(forced_failures, list) and category in forced_failures:
            return False, "forced_fail"

        if category == "REQUIRED_FIELD_PRESENCE":
            required_fields = ("dataset_token",)
            missing = [field for field in required_fields if not canonical_payload.get(field)]
            return (len(missing) == 0, "ok" if not missing else f"missing: {','.join(missing)}")

        if category == "DUPLICATE_SYNC_DETECTION":
            duplicate = bool(context.get("duplicate_sync_token", False))
            return (not duplicate, "ok" if not duplicate else "duplicate sync token detected")

        if category == "CURRENCY_CONSISTENCY":
            currency = str(canonical_payload.get("currency", "") or "")
            valid = len(currency) == 3 and currency.upper() == currency
            return valid, "ok" if valid else "currency must be uppercase ISO-4217 code"

        if category == "ENTITY_SCOPE_CONSISTENCY":
            expected_entity = str(context.get("entity_id", "") or "")
            payload_entity = str(canonical_payload.get("entity_id", "") or "")
            if not expected_entity:
                return bool(payload_entity), "ok" if payload_entity else "entity missing"
            return payload_entity == expected_entity, "ok" if payload_entity == expected_entity else "entity mismatch"

        if category == "PERIOD_CONSISTENCY":
            start = canonical_payload.get("from_date")
            end = canonical_payload.get("to_date")
            as_at = canonical_payload.get("as_at_date")
            if isinstance(start, date) and isinstance(end, date):
                return start <= end, "ok" if start <= end else "from_date > to_date"
            if as_at is not None:
                return True, "ok"
            return True, "ok"

        if category == "BALANCE_CHECK":
            total_debit = self._to_decimal(canonical_payload.get("total_debits")) or self._to_decimal(
                canonical_payload.get("total_closing_debit")
            )
            total_credit = self._to_decimal(canonical_payload.get("total_credits")) or self._to_decimal(
                canonical_payload.get("total_closing_credit")
            )
            if total_debit is None or total_credit is None:
                return True, "not_applicable"
            return total_debit == total_credit, "ok" if total_debit == total_credit else "debit/credit mismatch"

        if category == "SNAPSHOT_INTEGRITY":
            expected_hash = str(context.get("expected_raw_snapshot_hash", "") or "")
            payload_hash = str(raw_payload.get("payload_hash", "") or context.get("raw_snapshot_payload_hash", ""))
            if not expected_hash:
                return True, "not_configured"
            return expected_hash == payload_hash, "ok" if expected_hash == payload_hash else "hash mismatch"

        if category == "DELTA_BOUNDARY":
            overlap_detected = bool(context.get("delta_overlap_detected", False))
            return (not overlap_detected, "ok" if not overlap_detected else "incremental overlap detected")

        if category == "CAPABILITY_MISMATCH":
            supported = bool(context.get("capability_supported", True))
            return supported, "ok" if supported else "dataset not supported by connector"

        if category == "MAPPING_COMPLETENESS":
            if dataset_type == "gst_return_gstr9c":
                variance = self._to_decimal(canonical_payload.get("variance")) or Decimal("0")
                reason = str(canonical_payload.get("reason_for_variance", "") or "").strip()
                if variance != Decimal("0") and not reason:
                    return False, "variance reason required when variance is non-zero"
            complete = bool(context.get("mapping_complete", True))
            return complete, "ok" if complete else "mapping incomplete"

        if category == "AGEING_BUCKET_INTEGRITY":
            consistent = bool(context.get("ageing_bucket_consistent", True))
            return consistent, "ok" if consistent else "ageing bucket totals mismatch"

        if category == "REGISTER_LINE_INTEGRITY":
            consistent = bool(context.get("register_line_integrity", True))
            return consistent, "ok" if consistent else "register line mismatch"

        if category == "BANK_BALANCE_INTEGRITY":
            consistent = bool(context.get("bank_balance_integrity", True))
            return consistent, "ok" if consistent else "bank opening/movement/closing mismatch"

        if category == "BANK_MULTICURRENCY_INTEGRITY":
            consistent = bool(context.get("bank_multicurrency_integrity", True))
            return consistent, "ok" if consistent else "missing exchange_rate_applied"

        if category == "INVENTORY_VALUE_INTEGRITY":
            consistent = bool(context.get("inventory_value_integrity", True))
            return consistent, "ok" if consistent else "inventory rollforward mismatch"

        if category == "MASTER_DATA_REFERENTIAL":
            valid = bool(context.get("master_data_referential", True))
            return valid, "ok" if valid else "master data reference missing"

        if category == "PII_CONSENT_CHECK":
            if dataset_type == "form_26as":
                return self._validate_form_26as_masking(canonical_payload)
            if dataset_type == "ais_register":
                return self._validate_ais_masking(canonical_payload)
            valid = bool(context.get("pii_consent_valid", True))
            return valid, "ok" if valid else "pii consent/masking missing"

        if category == "IRN_FORMAT_VALIDITY":
            valid = bool(context.get("irn_format_valid", True))
            return valid, "ok" if valid else "irn format invalid"

        if category == "GSTR_PERIOD_CONSISTENCY":
            if dataset_type in {"gst_return_gstr9", "gst_return_gstr9c"}:
                financial_year = str(canonical_payload.get("financial_year", "") or "")
                if not re.fullmatch(r"\d{4}-\d{2}", financial_year):
                    return False, "financial_year must match YYYY-YY"
            valid = bool(context.get("gstr_period_consistent", True))
            return valid, "ok" if valid else "gstr period mismatch"

        if category == "BACKDATED_MODIFICATION_CHECK":
            valid = bool(context.get("backdated_modification_clear", True))
            return valid, "ok" if valid else "backdated modification detected"

        return True, "ok"

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _validate_form_26as_masking(canonical_payload: Mapping[str, Any]) -> tuple[bool, str]:
        pan_number = canonical_payload.get("pan_number")
        if pan_number is not None and not ValidationService._is_masked_pan(str(pan_number)):
            return False, "pan_number must be masked with at most last 4 characters visible"
        if not bool(canonical_payload.get("pii_masked", False)):
            return False, "pii_masked must be true for form_26as"
        return True, "ok"

    @staticmethod
    def _validate_ais_masking(canonical_payload: Mapping[str, Any]) -> tuple[bool, str]:
        if not bool(canonical_payload.get("pii_masked", False)):
            return False, "pii_masked must be true for ais_register"
        entries = canonical_payload.get("entries", [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, Mapping) and not bool(entry.get("pii_masked", False)):
                    return False, "all ais entries must be pii masked"
        return True, "ok"

    @staticmethod
    def _is_masked_pan(value: str) -> bool:
        visible_chars = [ch for ch in value if ch.isalnum() and ch not in {"X", "x", "*"}]
        return len(visible_chars) <= 4

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        dataset_type = str(kwargs.get("dataset_type", "")).strip()
        canonical_payload = kwargs.get("canonical_payload", {})
        raw_payload = kwargs.get("raw_payload", {})
        context = kwargs.get("context", {})
        if not isinstance(canonical_payload, Mapping):
            raise ValueError("canonical_payload must be a mapping")
        if not isinstance(raw_payload, Mapping):
            raise ValueError("raw_payload must be a mapping")
        if not isinstance(context, Mapping):
            raise ValueError("context must be a mapping")
        return self.validate(
            dataset_type=dataset_type,
            canonical_payload=canonical_payload,
            raw_payload=raw_payload,
            context=context,
        )
