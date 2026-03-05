from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from workbench.backend import determinism


@dataclass(frozen=True)
class Finding:
    rule_id: str
    location: str
    evidence: dict[str, Any]
    severity: str
    finding_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "location": self.location,
            "evidence": self.evidence,
            "severity": self.severity,
            "finding_id": self.finding_id,
        }


def make_finding(
    *,
    input_hash: str,
    rule_id: str,
    location: str,
    evidence: Any,
    severity: str = "MEDIUM",
) -> Finding:
    normalized_rule_id = str(rule_id).strip()
    normalized_location = str(location).strip()
    normalized_severity = str(severity).strip().upper() or "MEDIUM"
    normalized_evidence = _normalize_evidence(evidence)
    finding_id = determinism.stable_finding_id(
        input_hash=str(input_hash).strip(),
        rule_id=normalized_rule_id,
        location=normalized_location,
        normalized_evidence=normalized_evidence,
    )
    return Finding(
        rule_id=normalized_rule_id,
        location=normalized_location,
        evidence=normalized_evidence,
        severity=normalized_severity,
        finding_id=finding_id,
    )


def canonicalize_findings(findings: Iterable[Finding | dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in findings:
        if isinstance(item, Finding):
            rows.append(item.to_dict())
            continue
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rule_id": str(item.get("rule_id") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "evidence": _normalize_evidence(item.get("evidence")),
                "severity": str(item.get("severity") or "MEDIUM").strip().upper(),
                "finding_id": str(item.get("finding_id") or "").strip(),
            }
        )

    rows = [row for row in rows if row["rule_id"] and row["location"] and row["finding_id"]]
    rows.sort(
        key=lambda row: (
            str(row["severity"]),
            str(row["rule_id"]),
            str(row["location"]),
            str(row["finding_id"]),
        )
    )
    return rows


def _normalize_evidence(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        canonical = determinism.canonical_json_dumps(value)
        decoded = json.loads(canonical)
        return decoded if isinstance(decoded, dict) else {"value": decoded}
    if isinstance(value, list):
        canonical = determinism.canonical_json_dumps(value)
        decoded = json.loads(canonical)
        return {"items": decoded}
    return {"value": value}
