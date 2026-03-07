from __future__ import annotations

from financeops.modules.mis_manager.domain.entities import DriftAssessment
from financeops.modules.mis_manager.domain.enums import DriftType


class DriftDetectionService:
    def classify(
        self,
        *,
        prior_header_hash: str | None,
        prior_row_signature_hash: str | None,
        prior_column_signature_hash: str | None,
        prior_structure_hash: str | None,
        candidate_header_hash: str,
        candidate_row_signature_hash: str,
        candidate_column_signature_hash: str,
        candidate_structure_hash: str,
    ) -> DriftAssessment:
        if prior_structure_hash is None:
            return DriftAssessment(
                drift_type=DriftType.MAJOR_LAYOUT_CHANGE,
                is_material=True,
                details={"reason": "first_version"},
            )

        if prior_structure_hash == candidate_structure_hash:
            return DriftAssessment(
                drift_type=DriftType.HEADER_CHANGE,
                is_material=False,
                details={"reason": "exact_match"},
            )

        if (
            prior_row_signature_hash == candidate_row_signature_hash
            and prior_column_signature_hash == candidate_column_signature_hash
            and prior_header_hash != candidate_header_hash
        ):
            return DriftAssessment(
                drift_type=DriftType.HEADER_CHANGE,
                is_material=False,
                details={"reason": "header_only_change"},
            )

        if prior_column_signature_hash != candidate_column_signature_hash:
            return DriftAssessment(
                drift_type=DriftType.PERIOD_AXIS_CHANGE,
                is_material=True,
                details={"reason": "column_axis_changed"},
            )

        if prior_row_signature_hash != candidate_row_signature_hash:
            return DriftAssessment(
                drift_type=DriftType.ROW_PATTERN_CHANGE,
                is_material=True,
                details={"reason": "row_pattern_changed"},
            )

        return DriftAssessment(
            drift_type=DriftType.MAJOR_LAYOUT_CHANGE,
            is_material=True,
            details={"reason": "structure_hash_mismatch"},
        )
