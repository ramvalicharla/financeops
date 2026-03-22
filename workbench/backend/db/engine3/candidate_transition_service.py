from __future__ import annotations

from typing import Any

from workbench.backend import db as _db
from workbench.backend.db.engine3 import candidate_repository
from workbench.backend.utils.observability import incr

_ACTION_TO_STATUS: dict[str, str] = {
    "reject": "REJECTED",
    "convert": "CONVERTED_TO_JE",
}

_ACTION_TO_TERMINAL_STATE: dict[str, str] = {
    "reject": "rejected",
    "convert": "converted",
}


def _normalize_action(value: str) -> str:
    normalized = _db._normalize_required_text(value, field_name="action").strip().lower()
    if normalized not in _ACTION_TO_STATUS:
        raise ValueError("action must be one of: reject, convert")
    return normalized


def transition_candidate(
    *,
    tenant_id: str,
    workspace_id: str,
    candidate_id: str,
    candidate_type: str,
    action: str,
    actor_type: str = "SYSTEM",
    actor_id: str = "engine3_system",
) -> dict[str, Any]:
    normalized_type = candidate_repository.normalize_candidate_type(candidate_type)
    normalized_action = _normalize_action(action)
    expected_terminal_state = _ACTION_TO_TERMINAL_STATE[normalized_action]

    current = candidate_repository.get_candidate(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        candidate_id=candidate_id,
        candidate_type=normalized_type,
    )
    if current is None:
        raise LookupError("candidate_id was not found.")

    current_state = str(current.get("state") or "").strip().lower()
    if current_state in {"converted", "rejected"}:
        if current_state == expected_terminal_state:
            return {
                "candidate_type": normalized_type,
                "candidate": current,
                "idempotent": True,
            }
        raise RuntimeError("candidate state does not allow transition.")

    to_status = _ACTION_TO_STATUS[normalized_action]
    transition_fn = {
        "accrual": _db.transition_engine3_accrual_status,
        "reclass": _db.transition_engine3_reclass_status,
        "capex": _db.transition_engine3_capex_status,
    }[normalized_type]

    transitioned_row, transitioned = transition_fn(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        accrual_id=candidate_id if normalized_type == "accrual" else None,  # type: ignore[arg-type]
        reclass_id=candidate_id if normalized_type == "reclass" else None,  # type: ignore[arg-type]
        capex_id=candidate_id if normalized_type == "capex" else None,  # type: ignore[arg-type]
        to_status=to_status,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    # The underlying typed transition functions ensure execution_run ownership/status enforcement.
    canonical = candidate_repository.map_to_canonical(transitioned_row, normalized_type)
    if transitioned:
        incr("engine3.candidate.transition.count")
        if normalized_action == "reject":
            incr("engine3.candidate.rejected.count")
    return {
        "candidate_type": normalized_type,
        "candidate": canonical,
        "idempotent": not transitioned,
    }

