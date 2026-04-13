from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ComputedBoardPack:
    board_pack_code: str
    executive_summary_text: str
    overall_health_classification: str
    status: str


@dataclass(frozen=True)
class ComputedSection:
    section_code: str
    section_order: int
    section_title: str
    section_summary_text: str
    section_payload_json: dict[str, Any]


@dataclass(frozen=True)
class ComputedNarrativeBlock:
    narrative_template_code: str
    narrative_text: str
    narrative_payload_json: dict[str, Any]
    block_order: int
    generation_method: str = "template"


@dataclass(frozen=True)
class ComputedEvidenceLink:
    section_result_id: str | None
    narrative_block_id: str | None
    evidence_type: str
    evidence_ref: str
    evidence_label: str
    evidence_payload_json: dict[str, Any]
    board_attention_flag: bool
    severity_rank: Decimal
