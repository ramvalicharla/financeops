from __future__ import annotations

from typing import Any

REPLAY_STATUS_SUCCESS = "SUCCESS"
REPLAY_STATUS_FAILED = "FAILED"

DRIFT_NO_DRIFT = "NO_DRIFT"
DRIFT_BYTE = "BYTE_DRIFT"
DRIFT_SEMANTIC = "SEMANTIC_DRIFT"
DRIFT_VERSION = "VERSION_DRIFT"
DRIFT_SNAPSHOT = "SNAPSHOT_MISMATCH"
DRIFT_MISSING_INPUT = "MISSING_INPUT"

DRIFT_TYPES = {
    DRIFT_NO_DRIFT,
    DRIFT_BYTE,
    DRIFT_SEMANTIC,
    DRIFT_VERSION,
    DRIFT_SNAPSHOT,
    DRIFT_MISSING_INPUT,
}


def build_replay_result(
    *,
    job_id: str,
    replay_status: str,
    drift_type: str,
    original_sha: str,
    replay_sha: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = str(replay_status).strip().upper()
    if normalized_status not in {REPLAY_STATUS_SUCCESS, REPLAY_STATUS_FAILED}:
        normalized_status = REPLAY_STATUS_FAILED
    normalized_drift = str(drift_type).strip().upper()
    if normalized_drift not in DRIFT_TYPES:
        normalized_drift = DRIFT_MISSING_INPUT
    payload = details if isinstance(details, dict) else {}
    return {
        "job_id": str(job_id).strip(),
        "replay_status": normalized_status,
        "drift_type": normalized_drift,
        "original_sha": str(original_sha).strip(),
        "replay_sha": str(replay_sha).strip(),
        "details": payload,
    }
