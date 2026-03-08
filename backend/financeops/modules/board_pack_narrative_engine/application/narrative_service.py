from __future__ import annotations

from typing import Any

from financeops.modules.board_pack_narrative_engine.domain.entities import (
    ComputedNarrativeBlock,
)


class NarrativeService:
    def render_blocks(
        self,
        *,
        sections: list[Any],
        templates: list[Any],
        reporting_period: str,
    ) -> list[ComputedNarrativeBlock]:
        template_lookup = {
            row.template_code: row
            for row in sorted(templates, key=lambda item: (item.template_code, item.id))
        }
        default_template = next(iter(template_lookup.values()), None)
        blocks: list[ComputedNarrativeBlock] = []
        for idx, section in enumerate(
            sorted(sections, key=lambda item: (item.section_order, item.section_code)),
            start=1,
        ):
            template = template_lookup.get(section.section_code) or default_template
            template_code = template.template_code if template is not None else "default"
            template_text = (
                template.template_text
                if template is not None
                else "{section_title}: {section_summary_text}"
            )
            payload = {
                "reporting_period": reporting_period,
                "section_code": section.section_code,
                "section_title": section.section_title,
                "section_summary_text": section.section_summary_text,
                "metric_count": section.section_payload_json.get("metric_count", 0),
                "high_risk_count": section.section_payload_json.get("high_risk_count", 0),
                "elevated_anomaly_count": section.section_payload_json.get(
                    "elevated_anomaly_count", 0
                ),
            }
            text = self._safe_format(template_text, payload)
            blocks.append(
                ComputedNarrativeBlock(
                    narrative_template_code=template_code,
                    narrative_text=text,
                    narrative_payload_json=payload,
                    block_order=idx,
                )
            )
        return blocks

    def executive_summary(
        self,
        *,
        sections: list[Any],
        high_risk_count: int,
        elevated_anomaly_count: int,
    ) -> str:
        section_count = len(sections)
        return (
            f"Board pack assembled with {section_count} sections. "
            f"High/critical risks: {high_risk_count}. "
            f"Elevated anomalies: {elevated_anomaly_count}."
        )

    def _safe_format(self, template: str, payload: dict[str, Any]) -> str:
        try:
            return template.format(**payload)
        except KeyError:
            return template
