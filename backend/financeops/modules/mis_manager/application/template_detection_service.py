from __future__ import annotations

from financeops.modules.mis_manager.application.drift_detection_service import (
    DriftDetectionService,
)
from financeops.modules.mis_manager.domain.entities import (
    SheetProfile,
    TemplateDetectionResult,
)
from financeops.modules.mis_manager.infrastructure.signature_builder import (
    build_signature_bundle,
)


class TemplateDetectionService:
    def __init__(self, drift_detection_service: DriftDetectionService) -> None:
        self._drift_detection_service = drift_detection_service

    def detect(
        self,
        *,
        profile: SheetProfile,
        prior_template_version_id,
        prior_header_hash: str | None,
        prior_row_signature_hash: str | None,
        prior_column_signature_hash: str | None,
        prior_structure_hash: str | None,
    ) -> tuple[TemplateDetectionResult, dict]:
        signature = build_signature_bundle(
            headers=profile.headers,
            row_labels=profile.row_labels,
            column_order=profile.column_order,
            section_breaks=profile.section_breaks,
            blank_row_density=profile.blank_row_density,
            formula_density=profile.formula_density,
        )

        drift = self._drift_detection_service.classify(
            prior_header_hash=prior_header_hash,
            prior_row_signature_hash=prior_row_signature_hash,
            prior_column_signature_hash=prior_column_signature_hash,
            prior_structure_hash=prior_structure_hash,
            candidate_header_hash=signature.header_hash,
            candidate_row_signature_hash=signature.row_signature_hash,
            candidate_column_signature_hash=signature.column_signature_hash,
            candidate_structure_hash=signature.structure_hash,
        )

        if prior_structure_hash and prior_structure_hash == signature.structure_hash:
            outcome = "exact_match"
        elif drift.is_material:
            outcome = "no_match"
        else:
            outcome = "tolerable_drift"

        detection_summary = {
            "sheet_name": profile.sheet_name,
            "header_row_index": profile.header_row_index,
            "data_start_row_index": profile.data_start_row_index,
            "blank_row_density": str(profile.blank_row_density),
            "formula_density": str(profile.formula_density),
            "text_to_numeric_ratio": str(profile.text_to_numeric_ratio),
            "merged_cell_count": profile.merged_cell_count,
            "detected_sections": profile.section_breaks,
        }

        result = TemplateDetectionResult(
            signature=signature,
            detection_summary=detection_summary,
            template_match_outcome=outcome,
            prior_template_version_id=prior_template_version_id,
        )
        return result, {
            "drift_type": drift.drift_type.value,
            "is_material": drift.is_material,
            "details": drift.details,
        }
