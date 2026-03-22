from __future__ import annotations

from typing import Any, Literal

from workbench.backend import db as _db
from workbench.backend import determinism

CandidateType = Literal["accrual", "reclass", "capex"]

_TYPE_TO_TABLE: dict[str, str] = {
    "accrual": "e3_accrual_proposals",
    "reclass": "e3_reclass_proposals",
    "capex": "e3_capex_proposals",
}

_TYPE_TO_LIST_FN = {
    "accrual": _db.list_engine3_accrual_proposals,
    "reclass": _db.list_engine3_reclass_proposals,
    "capex": _db.list_engine3_capex_proposals,
}

_STATE_MAP: dict[str, str] = {
    "PROPOSED": "detected",
    "REJECTED": "rejected",
    "CONVERTED_TO_JE": "converted",
}


def normalize_candidate_type(value: str) -> CandidateType:
    normalized = _db._normalize_required_text(value, field_name="candidate_type").strip().lower()
    if normalized not in _TYPE_TO_TABLE:
        raise ValueError("candidate_type must be one of: accrual, reclass, capex")
    return normalized  # type: ignore[return-value]


def _canonical_candidate_fingerprint(
    *,
    candidate_type: CandidateType,
    output_fingerprint_sha256: str,
    config_hash_sha256: str | None,
) -> str:
    payload = {
        "candidate_type": candidate_type,
        "output_fingerprint_sha256": _db._normalize_engine1_hash(
            output_fingerprint_sha256,
            field_name="output_fingerprint_sha256",
        ),
        "config_hash_sha256": (
            _db._normalize_engine1_hash(config_hash_sha256, field_name="config_hash_sha256")
            if str(config_hash_sha256 or "").strip()
            else None
        ),
    }
    return determinism.sha256_hex_bytes(determinism.canonical_json_bytes(payload))


def map_to_canonical(
    candidate_row: dict[str, Any],
    candidate_type: str,
    *,
    config_hash_sha256: str | None = None,
) -> dict[str, Any]:
    normalized_type = normalize_candidate_type(candidate_type)
    status = _db._normalize_required_text(candidate_row.get("status"), field_name="status").upper()
    state = _STATE_MAP.get(status)
    if state is None:
        raise ValueError("Unsupported proposal status for canonical mapping")

    summary = {
        "amount": str(candidate_row.get("calculated_amount") or ""),
        "currency": str(candidate_row.get("currency") or ""),
        "status": status,
    }
    source_refs = dict(candidate_row.get("source_reference_json") or {})
    details_payload = dict(candidate_row.get("proposed_je_payload_json") or {})

    rule_hits: list[str] = []
    direct_rule = str(candidate_row.get("detection_rule_id") or "").strip()
    if direct_rule:
        rule_hits.append(direct_rule)
    source_rule = str(source_refs.get("rule_code") or "").strip()
    if source_rule and source_rule not in rule_hits:
        rule_hits.append(source_rule)

    output_fingerprint_sha256 = _db._normalize_engine1_hash(
        candidate_row.get("output_fingerprint_sha256"),
        field_name="output_fingerprint_sha256",
    )

    return {
        "candidate_id": str(candidate_row.get("id") or ""),
        "execution_run_id": str(candidate_row.get("execution_run_id") or ""),
        "candidate_type": normalized_type,
        "summary": summary,
        "details_payload": details_payload,
        "state": state,
        "source_refs": source_refs,
        "rule_hits": rule_hits,
        "created_at": str(candidate_row.get("created_at") or ""),
        "output_fingerprint_sha256": output_fingerprint_sha256,
        "canonical_fingerprint_sha256": _canonical_candidate_fingerprint(
            candidate_type=normalized_type,
            output_fingerprint_sha256=output_fingerprint_sha256,
            config_hash_sha256=config_hash_sha256,
        ),
    }


def list_candidates(
    *,
    tenant_id: str,
    workspace_id: str,
    execution_run_id: str,
    candidate_type: str,
    config_hash_sha256: str | None = None,
) -> list[dict[str, Any]]:
    normalized_type = normalize_candidate_type(candidate_type)
    list_fn = _TYPE_TO_LIST_FN[normalized_type]
    rows = list_fn(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        execution_run_id=execution_run_id,
    )
    return [
        map_to_canonical(row, normalized_type, config_hash_sha256=config_hash_sha256)
        for row in rows
    ]


def get_candidate(
    *,
    tenant_id: str,
    workspace_id: str,
    candidate_id: str,
    candidate_type: str,
    config_hash_sha256: str | None = None,
) -> dict[str, Any] | None:
    normalized_type = normalize_candidate_type(candidate_type)
    table_name = _TYPE_TO_TABLE[normalized_type]
    normalized_candidate_id = _db._normalize_required_text(candidate_id, field_name="candidate_id")
    normalized_tenant = _db._normalize_required_text(tenant_id, field_name="tenant_id")
    normalized_workspace = _db._normalize_required_text(workspace_id, field_name="workspace_id")

    if not _db.list_table_columns(table_name):
        raise RuntimeError(f"{table_name} schema is not available.")

    with _db.get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT *
            FROM {table_name}
            WHERE id = ?
            LIMIT 1
            """,
            (normalized_candidate_id,),
        ).fetchone()
    if not row:
        return None

    row_payload = dict(row)
    row_tenant = _db._normalize_required_text(row_payload.get("tenant_id"), field_name="tenant_id")
    row_workspace = _db._normalize_required_text(row_payload.get("workspace_id"), field_name="workspace_id")
    if row_tenant != normalized_tenant or row_workspace != normalized_workspace:
        raise PermissionError("candidate_id is outside tenant/workspace scope.")

    # Normalize typed JSON fields consistently with existing list APIs.
    execution_run_id = _db._normalize_required_text(row_payload.get("execution_run_id"), field_name="execution_run_id")
    typed_rows = _TYPE_TO_LIST_FN[normalized_type](
        tenant_id=normalized_tenant,
        workspace_id=normalized_workspace,
        execution_run_id=execution_run_id,
    )
    target = next((item for item in typed_rows if str(item.get("id") or "") == normalized_candidate_id), None)
    if target is None:
        return None
    return map_to_canonical(target, normalized_type, config_hash_sha256=config_hash_sha256)

