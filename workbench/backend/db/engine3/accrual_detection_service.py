from __future__ import annotations

import time
from typing import Any

from workbench.backend import db as _db
from workbench.backend.db.engine3 import candidate_repository
from workbench.backend.db.engine3 import candidate_detection_common
from workbench.backend.utils.observability import incr, observe_time


def detect_accrual_candidates(
    *,
    tenant_id: str,
    workspace_id: str,
    execution_run_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        config_hash, drifted = candidate_detection_common.lock_or_validate_detection_config(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            execution_run_id=execution_run_id,
            candidate_type="accrual",
        )
        if drifted:
            proposals = _db.list_engine3_accrual_proposals(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                execution_run_id=execution_run_id,
            )
            if not proposals:
                raise RuntimeError("DETECTION_CONFIG_DRIFT")
            candidates = [
                candidate_repository.map_to_canonical(
                    row,
                    "accrual",
                    config_hash_sha256=config_hash,
                )
                for row in proposals
            ]
            return {
                "execution_run_id": str(execution_run_id).strip(),
                "created_count": 0,
                "proposals": proposals,
                "candidates": candidates,
                "config_hash_sha256": config_hash,
            }

        detected = _db.detect_engine3_accrual_proposals(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            execution_run_id=execution_run_id,
        )
        proposals = list(detected.get("proposals") or [])
        candidates = [
            candidate_repository.map_to_canonical(
                row,
                "accrual",
                config_hash_sha256=config_hash,
            )
            for row in proposals
        ]
        incr("engine3.candidate.detected.count", value=len(candidates))
        return {
            "execution_run_id": str(execution_run_id).strip(),
            "created_count": int(detected.get("created_count") or 0),
            "proposals": proposals,
            "candidates": candidates,
            "config_hash_sha256": config_hash,
        }
    finally:
        observe_time("engine3.candidate.detection.time", time.perf_counter() - started)

