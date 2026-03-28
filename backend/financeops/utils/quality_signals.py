from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financeops.utils.erp_compat import db, determinism

QUALITY_SIGNAL_VERSION = "v1"
ANALYZER_JOB_TYPES = {"code.analysis.v1", "finance.analysis.v1"}
REQUIRED_ANALYZER_ARTIFACTS_BY_JOB_TYPE: dict[str, set[str]] = {
    "code.analysis.v1": {"findings.json", "import_graph.json", "impact_radius.json"},
    "finance.analysis.v1": {"findings.json"},
}


def is_analyzer_job_type(job_type: str) -> bool:
    return str(job_type).strip() in ANALYZER_JOB_TYPES


def build_quality_signal(*, job: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    job_id = str(job.get("job_id") or "").strip()
    job_type = str(job.get("job_type") or "").strip()
    if not job_id:
        raise ValueError("quality signal requires job_id.")
    if not is_analyzer_job_type(job_type):
        raise ValueError("quality signal only supports analyzer jobs.")

    by_name = _artifact_index(artifacts)
    versions = _resolve_versions(job=job, versions_artifact=by_name.get(determinism.DETERMINISTIC_ARTIFACT_VERSIONS))
    required_names = REQUIRED_ANALYZER_ARTIFACTS_BY_JOB_TYPE.get(job_type, set())
    present = sorted([name for name in required_names if name in by_name])
    missing = sorted([name for name in required_names if name not in by_name])

    signal = {
        "job_id": job_id,
        "job_type": job_type,
        "analyzer_type": job_type,
        "job_status": "SUCCEEDED" if str(job.get("status") or "").strip().upper() == "SUCCEEDED" else "FAILED",
        "determinism_sha256": _read_text_artifact(by_name.get(determinism.DETERMINISTIC_ARTIFACT_SHA)),
        "workspace_snapshot_hash": _read_workspace_snapshot_hash(by_name),
        "versions": versions,
        "quality_metrics": {
            "findings_count": _findings_count(by_name.get("findings.json")),
            "analyzer_artifacts_present": present,
            "analyzer_artifacts_missing": missing,
            "analyzer_duration_ms": _duration_ms(
                started_at=str(job.get("started_at") or "").strip(),
                finished_at=str(job.get("finished_at") or "").strip(),
            ),
            "analyzer_failed": str(job.get("status") or "").strip().upper() != "SUCCEEDED",
        },
        "quality_version": QUALITY_SIGNAL_VERSION,
        "recorded_at": db.utc_now_iso(),
    }
    return _normalize_signal(signal)


def record_quality_signal(signal: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_signal(signal)
    payload = determinism.canonical_json_dumps(normalized)
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO quality_signals (
                job_id,
                job_type,
                analyzer_type,
                job_status,
                determinism_sha256,
                workspace_snapshot_hash,
                quality_version,
                recorded_at,
                signal_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["job_id"],
                normalized["job_type"],
                normalized["analyzer_type"],
                normalized["job_status"],
                normalized["determinism_sha256"],
                normalized["workspace_snapshot_hash"],
                normalized["quality_version"],
                normalized["recorded_at"],
                payload,
            ),
        )
    return normalized


def list_quality_signals(job_id: str) -> list[dict[str, Any]]:
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        return []
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT signal_json
            FROM quality_signals
            WHERE job_id = ?
            ORDER BY signal_id ASC
            """,
            (normalized_job_id,),
        ).fetchall()
    signals: list[dict[str, Any]] = []
    for row in rows:
        try:
            decoded = json.loads(str(row["signal_json"]))
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            signals.append(decoded)
    return signals


def get_quality_signal_for_job(job_id: str) -> dict[str, Any] | None:
    signals = list_quality_signals(job_id)
    if not signals:
        return None
    return signals[-1]


def _artifact_index(artifacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        name = str(artifact.get("name") or "").strip()
        if name:
            indexed[name] = artifact
    return indexed


def _artifact_path(artifact: dict[str, Any] | None) -> Path | None:
    if not isinstance(artifact, dict):
        return None
    raw_path = str(artifact.get("path") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path).expanduser().resolve(strict=False)
    if not path.exists() or not path.is_file():
        return None
    return path


def _read_text_artifact(artifact: dict[str, Any] | None) -> str:
    path = _artifact_path(artifact)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_json_artifact(artifact: dict[str, Any] | None) -> dict[str, Any]:
    path = _artifact_path(artifact)
    if path is None:
        return {}
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _findings_count(artifact: dict[str, Any] | None) -> int:
    decoded = _read_json_artifact(artifact)
    findings = decoded.get("findings")
    if not isinstance(findings, list):
        return 0
    return len([item for item in findings if isinstance(item, dict)])


def _read_workspace_snapshot_hash(artifact_index: dict[str, dict[str, Any]]) -> str:
    from_snapshot_sha = _read_text_artifact(artifact_index.get(determinism.WORKSPACE_SNAPSHOT_SHA_ARTIFACT))
    if from_snapshot_sha:
        return from_snapshot_sha
    payload = _read_json_artifact(artifact_index.get(determinism.DETERMINISTIC_ARTIFACT_PAYLOAD))
    job = payload.get("job")
    if isinstance(job, dict):
        return str(job.get("workspace_snapshot_hash") or "").strip()
    return ""


def _resolve_versions(*, job: dict[str, Any], versions_artifact: dict[str, Any] | None) -> dict[str, str]:
    decoded = _read_json_artifact(versions_artifact)
    normalized = determinism.normalize_versions(job)
    return {
        "policy_version": str(decoded.get("policy_version") or normalized["policy_version"]).strip(),
        "rulepack_version": str(decoded.get("rulepack_version") or normalized["rulepack_version"]).strip(),
        "engine_version": str(decoded.get("engine_version") or normalized["engine_version"]).strip(),
        "model_version": str(decoded.get("model_version") or normalized["model_version"]).strip(),
    }


def _duration_ms(*, started_at: str, finished_at: str) -> int | None:
    started = _parse_iso_utc(started_at)
    finished = _parse_iso_utc(finished_at)
    if started is None or finished is None:
        return None
    delta_ms = int((finished - started).total_seconds() * 1000)
    return max(delta_ms, 0)


def _parse_iso_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    quality_metrics = signal.get("quality_metrics")
    if not isinstance(quality_metrics, dict):
        quality_metrics = {}
    versions = signal.get("versions")
    if not isinstance(versions, dict):
        versions = {}
    return {
        "job_id": str(signal.get("job_id") or "").strip(),
        "job_type": str(signal.get("job_type") or "").strip(),
        "analyzer_type": str(signal.get("analyzer_type") or "").strip(),
        "job_status": str(signal.get("job_status") or "FAILED").strip().upper(),
        "determinism_sha256": str(signal.get("determinism_sha256") or "").strip(),
        "workspace_snapshot_hash": str(signal.get("workspace_snapshot_hash") or "").strip(),
        "versions": {
            "policy_version": str(versions.get("policy_version") or "").strip(),
            "rulepack_version": str(versions.get("rulepack_version") or "").strip(),
            "engine_version": str(versions.get("engine_version") or "").strip(),
            "model_version": str(versions.get("model_version") or "").strip(),
        },
        "quality_metrics": {
            "findings_count": int(quality_metrics.get("findings_count") or 0),
            "analyzer_artifacts_present": sorted(
                [str(item).strip() for item in quality_metrics.get("analyzer_artifacts_present", []) if str(item).strip()]
            ),
            "analyzer_artifacts_missing": sorted(
                [str(item).strip() for item in quality_metrics.get("analyzer_artifacts_missing", []) if str(item).strip()]
            ),
            "analyzer_duration_ms": (
                int(quality_metrics.get("analyzer_duration_ms"))
                if quality_metrics.get("analyzer_duration_ms") is not None
                else None
            ),
            "analyzer_failed": bool(quality_metrics.get("analyzer_failed") is True),
        },
        "quality_version": str(signal.get("quality_version") or QUALITY_SIGNAL_VERSION).strip() or QUALITY_SIGNAL_VERSION,
        "recorded_at": str(signal.get("recorded_at") or db.utc_now_iso()).strip() or db.utc_now_iso(),
    }
