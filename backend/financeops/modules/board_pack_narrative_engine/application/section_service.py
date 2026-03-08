from __future__ import annotations

from decimal import Decimal
from typing import Any

from financeops.modules.board_pack_narrative_engine.domain.entities import ComputedSection


class SectionService:
    def build_sections(
        self,
        *,
        section_rows: list[Any],
        metric_rows: list[Any],
        risk_rows: list[Any],
        anomaly_rows: list[Any],
        top_limit: int,
    ) -> list[ComputedSection]:
        metric_sorted = sorted(
            metric_rows,
            key=lambda item: (item.metric_code, str(item.id)),
        )[:top_limit]
        high_risks = [
            row for row in risk_rows if row.severity in ("high", "critical")
        ]
        elevated_anomalies = [
            row
            for row in anomaly_rows
            if row.severity in ("high", "critical")
            or row.persistence_classification in ("sustained", "escalating")
        ]

        sections: list[ComputedSection] = []
        for row in sorted(
            section_rows,
            key=lambda item: (item.section_order_default, item.section_code, item.id),
        ):
            summary = self._summary_for_section(
                section_code=row.section_code,
                metric_sorted=metric_sorted,
                high_risks=high_risks,
                elevated_anomalies=elevated_anomalies,
            )
            payload = {
                "metric_count": len(metric_sorted),
                "high_risk_count": len(high_risks),
                "elevated_anomaly_count": len(elevated_anomalies),
            }
            sections.append(
                ComputedSection(
                    section_code=row.section_code,
                    section_order=row.section_order_default,
                    section_title=row.section_name,
                    section_summary_text=summary,
                    section_payload_json=payload,
                )
            )
        return sections

    def _summary_for_section(
        self,
        *,
        section_code: str,
        metric_sorted: list[Any],
        high_risks: list[Any],
        elevated_anomalies: list[Any],
    ) -> str:
        if section_code == "executive_summary":
            return (
                f"Material metrics reviewed: {len(metric_sorted)}. "
                f"High/critical risks: {len(high_risks)}. "
                f"Elevated anomalies: {len(elevated_anomalies)}."
            )
        if section_code == "key_risks":
            top_codes = ", ".join(
                sorted({row.risk_code for row in high_risks})[:3]
            ) or "none"
            return f"Risk focus items: {top_codes}."
        if section_code == "anomaly_watchlist":
            top_codes = ", ".join(
                sorted({row.anomaly_code for row in elevated_anomalies})[:3]
            ) or "none"
            return f"Anomaly watchlist items: {top_codes}."
        total_metric_value = sum(
            [Decimal(str(getattr(row, "metric_value", 0))) for row in metric_sorted],
            start=Decimal("0"),
        )
        return (
            f"Section {section_code} built from {len(metric_sorted)} metrics "
            f"(aggregate value {total_metric_value:.6f})."
        )
