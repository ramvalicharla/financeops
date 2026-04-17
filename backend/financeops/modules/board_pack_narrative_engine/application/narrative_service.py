from __future__ import annotations

from typing import Any

from financeops.config import settings
from financeops.modules.ai_cfo_layer.domain.exceptions import AIProviderUnavailableError
from financeops.modules.ai_cfo_layer.infrastructure.ai_client import AIClient
from financeops.modules.board_pack_narrative_engine.domain.entities import (
    ComputedNarrativeBlock,
)
from financeops.modules.board_pack_narrative_engine.domain.exceptions import (
    NarrativeSummaryGenerationError,
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

    async def executive_summary(
        self,
        *,
        sections: list[Any],
        reporting_period: str,
        metric_count: int,
        high_risk_count: int,
        medium_risk_count: int,
        anomaly_count: int,
        elevated_anomaly_count: int,
    ) -> str:
        section_count = len(sections)
        key_metrics = self._key_metrics(sections)
        fallback = self._deterministic_summary(
            reporting_period=reporting_period,
            section_count=section_count,
            metric_count=metric_count,
            high_risk_count=high_risk_count,
            medium_risk_count=medium_risk_count,
            anomaly_count=anomaly_count,
        )

        try:
            response = await AIClient(settings).complete(
                system=(
                    "Write a concise executive summary for a finance board pack. "
                    "Use only the provided facts. Do not invent metrics."
                ),
                user=(
                    f"Reporting period: {reporting_period}\n"
                    f"Section count: {section_count}\n"
                    f"Metric count: {metric_count}\n"
                    f"High risk count: {high_risk_count}\n"
                    f"Medium risk count: {medium_risk_count}\n"
                    f"Anomaly count: {anomaly_count}\n"
                    f"Elevated anomaly count: {elevated_anomaly_count}\n"
                    f"Key metrics: {key_metrics or 'none'}"
                ),
                max_tokens=180,
            )
        except AIProviderUnavailableError:
            return fallback
        except Exception as exc:
            raise NarrativeSummaryGenerationError(str(exc)) from exc

        text = str(response.text or "").strip()
        if not text:
            raise NarrativeSummaryGenerationError("AI provider returned an empty summary")
        return text

    def _deterministic_summary(
        self,
        *,
        reporting_period: str,
        section_count: int,
        metric_count: int,
        high_risk_count: int,
        medium_risk_count: int,
        anomaly_count: int,
    ) -> str:
        return (
            f"Board pack for {reporting_period}: {section_count} sections, "
            f"{metric_count} KPIs reviewed. "
            f"Risk items: {high_risk_count} high, {medium_risk_count} medium. "
            f"Anomalies detected: {anomaly_count}."
        )

    def _key_metrics(self, sections: list[Any]) -> str:
        codes: list[str] = []
        for section in sections:
            payload = getattr(section, "section_payload_json", {}) or {}
            for key in ("top_metric_codes", "metric_codes"):
                values = payload.get(key)
                if isinstance(values, list):
                    codes.extend([str(value) for value in values if str(value).strip()])
            title = getattr(section, "section_title", None)
            if title and title not in codes:
                codes.append(str(title))
        ordered = []
        seen: set[str] = set()
        for code in codes:
            if code in seen:
                continue
            seen.add(code)
            ordered.append(code)
        return ", ".join(ordered[:5])

    def _safe_format(self, template: str, payload: dict[str, Any]) -> str:
        try:
            return template.format(**payload)
        except KeyError:
            return template
