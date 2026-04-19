from __future__ import annotations

from types import SimpleNamespace

import pytest

from financeops.config import settings
from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
    NarrativeService,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_narrative_exec_summary_uses_real_data_not_hardcoded_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_CFO_ENABLED", False)

    service = NarrativeService()
    sections = [
        SimpleNamespace(
            section_code="executive_summary",
            section_title="Executive Summary",
            section_payload_json={"metric_count": 3, "metric_codes": ["revenue", "ebitda"]},
        ),
        SimpleNamespace(
            section_code="key_risks",
            section_title="Key Risks",
            section_payload_json={"high_risk_count": 2},
        ),
        SimpleNamespace(
            section_code="anomaly_watchlist",
            section_title="Anomaly Watchlist",
            section_payload_json={"elevated_anomaly_count": 1},
        ),
    ]

    summary = await service.executive_summary(
        sections=sections,
        reporting_period="2026-03-31",
        metric_count=3,
        high_risk_count=2,
        medium_risk_count=0,
        anomaly_count=1,
        elevated_anomaly_count=1,
    )

    assert "2026-03-31" in summary
    assert "3 sections" in summary
    assert "3 KPIs reviewed" in summary
    assert "2 high" in summary
    assert "1." in summary
    assert "Anomalies detected: 1" in summary
    assert (
        summary
        != "Board pack assembled with 3 sections. High/critical risks: 2. Elevated anomalies: 1."
    )
