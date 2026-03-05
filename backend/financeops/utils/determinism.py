from __future__ import annotations

import hashlib
import json
from typing import Any

DETERMINISM_SCHEMA_VERSION = "workbench.phase2.determinism.v1"

DEFAULT_POLICY_VERSION = "phase2-policy-placeholder"
DEFAULT_RULEPACK_VERSION = "phase2-rulepack-placeholder"
DEFAULT_ENGINE_VERSION = "phase2-engine-placeholder"
DEFAULT_MODEL_VERSION = "phase2-model-placeholder"

DETERMINISTIC_ARTIFACT_INPUT = "request.json"
DETERMINISTIC_ARTIFACT_OUTPUT = "response.json"
DETERMINISTIC_ARTIFACT_PAYLOAD = "deterministic_payload.json"
DETERMINISTIC_ARTIFACT_SHA = "determinism_sha256.txt"
DETERMINISTIC_ARTIFACT_VERSIONS = "versions.json"
WORKSPACE_SNAPSHOT_ARTIFACT = "workspace_snapshot.json"
WORKSPACE_SNAPSHOT_SHA_ARTIFACT = "workspace_snapshot_sha256.txt"
NON_DETERMINISTIC_ARTIFACT_METADATA = "non_deterministic_metadata.json"

_NON_DETERMINISTIC_KEY_PARTS = (
    "job_id",
    "session_id",
    "conversation_id",
    "request_id",
    "run_id",
    "timestamp",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "written_at",
    "pid",
    "nonce",
    "random",
    "uuid",
    "auth_secret",
    "api_base",
    "port",
    "path",
)
_NON_DETERMINISTIC_EXACT_KEYS = {"ts", "pid", "port"}


def canonical_json_dumps(value: Any) -> str:
    normalized = _canonicalize(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json_dumps(value).encode("utf-8")


def sha256_hex_bytes(value: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(value)
    return digest.hexdigest()


def sha256_hex_text(value: str) -> str:
    return sha256_hex_bytes(value.encode("utf-8"))


def stable_finding_id(
    *,
    input_hash: str,
    rule_id: str,
    location: str,
    normalized_evidence: Any,
) -> str:
    evidence_text = canonical_json_dumps(_canonicalize(normalized_evidence))
    token = "||".join(
        (
            str(input_hash).strip(),
            str(rule_id).strip(),
            str(location).strip(),
            evidence_text,
        )
    )
    return sha256_hex_text(token)


def normalize_versions(job: dict[str, Any]) -> dict[str, str]:
    return {
        "engine_version": _version_or_default(job.get("engine_version"), DEFAULT_ENGINE_VERSION),
        "policy_version": _version_or_default(job.get("policy_version"), DEFAULT_POLICY_VERSION),
        "rulepack_version": _version_or_default(job.get("rulepack_version"), DEFAULT_RULEPACK_VERSION),
        "model_version": _version_or_default(job.get("model_version"), DEFAULT_MODEL_VERSION),
    }


def build_job_determinism_bundle(
    *,
    job: dict[str, Any],
    events: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    workspace_snapshot_hash: str | None = None,
) -> dict[str, Any]:
    versions = normalize_versions(job)
    deterministic_events = _deterministic_event_projection(events)
    deterministic_artifact_hashes = _deterministic_artifact_hashes(artifacts)
    snapshot_hash = str(workspace_snapshot_hash or "").strip()

    job_projection = {
        "job_type": str(job.get("job_type") or ""),
        "status": str(job.get("status") or ""),
        "input_hash": str(job.get("input_hash") or ""),
        "error_code": str(job.get("error_code") or ""),
    }
    if snapshot_hash:
        job_projection["workspace_snapshot_hash"] = snapshot_hash
    deterministic_payload = {
        "schema_version": DETERMINISM_SCHEMA_VERSION,
        "job": job_projection,
        "versions": versions,
        "events": deterministic_events,
        "artifact_hashes": deterministic_artifact_hashes,
    }
    canonical_payload = canonical_json_dumps(deterministic_payload)
    determinism_sha256 = sha256_hex_text(canonical_payload)
    non_deterministic_metadata = _non_deterministic_metadata(job, events, artifacts)
    return {
        "versions": versions,
        "deterministic_payload": deterministic_payload,
        "deterministic_payload_canonical": canonical_payload,
        "determinism_sha256": determinism_sha256,
        "non_deterministic_metadata": non_deterministic_metadata,
    }


def payload_contains_nondeterministic_markers(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if _is_non_deterministic_key(lowered):
                return True
            if payload_contains_nondeterministic_markers(value):
                return True
        return False
    if isinstance(payload, list):
        return any(payload_contains_nondeterministic_markers(item) for item in payload)
    return False


def _version_or_default(raw: Any, default: str) -> str:
    text = str(raw).strip() if raw is not None else ""
    return text or default


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    return value


def _is_non_deterministic_key(lowered_key: str) -> bool:
    if lowered_key in _NON_DETERMINISTIC_EXACT_KEYS:
        return True
    for part in _NON_DETERMINISTIC_KEY_PARTS:
        if part in lowered_key:
            return True
    return False


def _deterministic_event_projection(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: int(item.get("seq") or 0)):
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload")
        projected.append(
            {
                "event_type": event_type,
                "payload": _project_event_payload(
                    event_type=event_type,
                    payload=payload if isinstance(payload, dict) else {},
                ),
            }
        )
    return projected


def _project_event_payload(*, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_type = str(event_type).strip().upper()
    if normalized_type in {"QUEUED", "RUNNING", "DONE"}:
        status = str(payload.get("status") or "").strip()
        return {"status": status} if status else {}

    if normalized_type == "PROGRESS":
        projected: dict[str, Any] = {}
        phase = str(payload.get("phase") or "").strip()
        message = str(payload.get("message") or "").strip()
        percent = payload.get("percent")
        if phase:
            projected["phase"] = phase
        if message:
            projected["message"] = message
        if isinstance(percent, (int, float)) and not isinstance(percent, bool):
            projected["percent"] = int(percent)
        counts = payload.get("counts")
        if isinstance(counts, dict):
            projected_counts: dict[str, Any] = {}
            for key in (
                "closed_period",
                "edges",
                "finding_count",
                "findings",
                "impact_nodes",
                "nodes",
                "rows",
                "threshold_amount",
            ):
                if key not in counts:
                    continue
                value = counts.get(key)
                if value is None or isinstance(value, (str, int, float, bool)):
                    projected_counts[key] = value
            if projected_counts:
                projected["counts"] = projected_counts
        artifact_hashes = payload.get("artifact_hashes")
        if isinstance(artifact_hashes, dict):
            projected_hashes: dict[str, str] = {}
            for key in ("findings", "impact_radius", "import_graph"):
                value = artifact_hashes.get(key)
                text = str(value).strip() if value is not None else ""
                if text:
                    projected_hashes[key] = text
            if projected_hashes:
                projected["artifact_hashes"] = projected_hashes
        return projected

    if normalized_type == "RESULT":
        projected = {}
        for key in ("artifact_name", "artifact_kind", "artifact_sha256"):
            value = str(payload.get(key) or "").strip()
            if value:
                projected[key] = value
        return projected

    if normalized_type == "ERROR":
        code = str(payload.get("code") or "").strip()
        return {"code": code} if code else {}

    if normalized_type in {"WARNING", "LOG"}:
        projected = {}
        code = str(payload.get("code") or "").strip()
        phase = str(payload.get("phase") or "").strip()
        status = str(payload.get("status") or "").strip()
        if code:
            projected["code"] = code
        if phase:
            projected["phase"] = phase
        if status:
            projected["status"] = status
        if isinstance(payload.get("cancel_requested"), bool):
            projected["cancel_requested"] = bool(payload.get("cancel_requested"))
        return projected

    return {}


def _deterministic_artifact_hashes(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    allowed = {
        DETERMINISTIC_ARTIFACT_INPUT,
        DETERMINISTIC_ARTIFACT_OUTPUT,
        WORKSPACE_SNAPSHOT_ARTIFACT,
        WORKSPACE_SNAPSHOT_SHA_ARTIFACT,
        "import_graph.json",
        "impact_radius.json",
        "findings.json",
    }
    for artifact in artifacts:
        name = str(artifact.get("name") or "")
        if name not in allowed:
            continue
        rows.append(
            {
                "name": name,
                "kind": str(artifact.get("kind") or ""),
                "sha256": str(artifact.get("sha256") or ""),
            }
        )
    rows.sort(key=lambda item: (item["kind"], item["name"]))
    return rows


def _non_deterministic_metadata(
    job: dict[str, Any],
    events: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    event_envelopes = [
        {
            "seq": int(event.get("seq") or 0),
            "ts": str(event.get("ts") or ""),
            "event_type": str(event.get("event_type") or ""),
        }
        for event in sorted(events, key=lambda item: int(item.get("seq") or 0))
    ]
    artifact_rows = [
        {
            "name": str(item.get("name") or ""),
            "kind": str(item.get("kind") or ""),
            "path": str(item.get("path") or ""),
            "created_at": str(item.get("created_at") or ""),
        }
        for item in sorted(
            artifacts,
            key=lambda item: (
                str(item.get("kind") or ""),
                str(item.get("name") or ""),
                str(item.get("created_at") or ""),
            ),
        )
    ]
    return {
        "job_id": str(job.get("job_id") or ""),
        "timestamps": {
            "created_at": str(job.get("created_at") or ""),
            "started_at": str(job.get("started_at") or ""),
            "finished_at": str(job.get("finished_at") or ""),
        },
        "event_envelopes": event_envelopes,
        "artifacts": artifact_rows,
    }
