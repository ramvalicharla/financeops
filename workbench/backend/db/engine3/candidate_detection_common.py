from __future__ import annotations

from typing import Any

from workbench.backend import db as _db
from workbench.backend import determinism

_LOCK_EVENT_TYPE = "CUSTOM_NOTE"
_LOCK_PAYLOAD_KEY = "candidate_detection_lock"

_CONFIG_TABLES_BY_TYPE: dict[str, tuple[str, ...]] = {
    "accrual": ("e3_account_mappings",),
    "reclass": (
        "e3_account_mappings",
        "e3_reclass_allocation_rules",
        "e3_entity_relationships",
    ),
    "capex": ("e3_account_mappings", "e3_capex_rules"),
}


def config_tables_for_candidate_type(candidate_type: str) -> tuple[str, ...]:
    normalized_type = str(candidate_type or "").strip().lower()
    if normalized_type not in _CONFIG_TABLES_BY_TYPE:
        raise ValueError("candidate_type must be one of: accrual, reclass, capex")
    return _CONFIG_TABLES_BY_TYPE[normalized_type]


def compute_scoped_config_hash(
    *,
    tenant_id: str,
    workspace_id: str,
    candidate_type: str,
) -> str:
    normalized_tenant = _db._normalize_required_text(tenant_id, field_name="tenant_id")
    normalized_workspace = _db._normalize_required_text(workspace_id, field_name="workspace_id")
    tables = config_tables_for_candidate_type(candidate_type)

    payload_tables: list[dict[str, Any]] = []
    with _db.get_conn() as conn:
        for table_name in tables:
            columns = _db.list_table_columns(table_name)
            if not columns:
                payload_tables.append({"table_name": table_name, "missing": True, "rows": []})
                continue
            select_columns = ", ".join(columns)
            order_by_columns = ", ".join(columns)
            rows = conn.execute(
                f"""
                SELECT {select_columns}
                FROM {table_name}
                WHERE tenant_id = ?
                  AND workspace_id = ?
                ORDER BY {order_by_columns}
                """,
                (normalized_tenant, normalized_workspace),
            ).fetchall()
            normalized_rows = [{key: row[key] for key in columns} for row in rows]
            payload_tables.append(
                {
                    "table_name": table_name,
                    "missing": False,
                    "rows": normalized_rows,
                }
            )

    payload = {
        "candidate_type": str(candidate_type or "").strip().lower(),
        "tenant_id": normalized_tenant,
        "workspace_id": normalized_workspace,
        "tables": payload_tables,
    }
    return determinism.sha256_hex_bytes(determinism.canonical_json_bytes(payload))


def _extract_locked_hash_from_payload(payload: dict[str, Any], *, candidate_type: str) -> str | None:
    lock_payload = payload.get(_LOCK_PAYLOAD_KEY)
    if not isinstance(lock_payload, dict):
        return None
    payload_type = str(lock_payload.get("candidate_type") or "").strip().lower()
    if payload_type != str(candidate_type or "").strip().lower():
        return None
    hash_value = str(lock_payload.get("config_hash_sha256") or "").strip().lower()
    if not hash_value:
        return None
    try:
        return _db._normalize_engine1_hash(hash_value, field_name="config_hash_sha256")
    except Exception:  # noqa: BLE001
        return None


def read_locked_config_hash(
    *,
    tenant_id: str,
    workspace_id: str,
    execution_run_id: str,
    candidate_type: str,
) -> str | None:
    normalized_tenant = _db._normalize_required_text(tenant_id, field_name="tenant_id")
    normalized_workspace = _db._normalize_required_text(workspace_id, field_name="workspace_id")
    normalized_run_id = _db._normalize_required_text(execution_run_id, field_name="execution_run_id")
    normalized_type = str(candidate_type or "").strip().lower()

    with _db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT event_payload_json
            FROM e3_execution_events
            WHERE execution_run_id = ?
              AND tenant_id = ?
              AND workspace_id = ?
              AND event_type = ?
            ORDER BY event_seq ASC
            """,
            (normalized_run_id, normalized_tenant, normalized_workspace, _LOCK_EVENT_TYPE),
        ).fetchall()
    for row in rows:
        raw_payload = str(row["event_payload_json"] or "").strip()
        if not raw_payload:
            continue
        try:
            payload = _db.json.loads(raw_payload)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(payload, dict):
            continue
        locked_hash = _extract_locked_hash_from_payload(payload, candidate_type=normalized_type)
        if locked_hash:
            return locked_hash
    return None


def lock_or_validate_detection_config(
    *,
    tenant_id: str,
    workspace_id: str,
    execution_run_id: str,
    candidate_type: str,
) -> tuple[str, bool]:
    """
    Returns (locked_hash, drifted).
    drifted=True means current config hash no longer matches the run lock.
    """
    normalized_type = str(candidate_type or "").strip().lower()
    current_hash = compute_scoped_config_hash(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        candidate_type=normalized_type,
    )
    locked_hash = read_locked_config_hash(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        execution_run_id=execution_run_id,
        candidate_type=normalized_type,
    )
    if locked_hash is None:
        payload = {
            _LOCK_PAYLOAD_KEY: {
                "candidate_type": normalized_type,
                "config_hash_sha256": current_hash,
                "config_tables": list(config_tables_for_candidate_type(normalized_type)),
            }
        }
        _db.append_engine3_execution_event(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            execution_run_id=execution_run_id,
            event_type=_LOCK_EVENT_TYPE,
            event_payload_json=payload,
            actor_type="SYSTEM",
            actor_id="engine3_system",
        )
        return current_hash, False
    return locked_hash, locked_hash != current_hash

