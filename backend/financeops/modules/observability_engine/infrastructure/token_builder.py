from __future__ import annotations

from financeops.modules.observability_engine.domain.value_objects import (
    DiffTokenInput,
    ObservabilityOperationTokenInput,
)
from financeops.shared_kernel.tokens import build_token


def build_operation_token(payload: ObservabilityOperationTokenInput) -> str:
    return build_token(
        {
            "tenant_id": str(payload.tenant_id),
            "operation_type": payload.operation_type,
            "input_ref_json": payload.input_ref_json,
        }
    )


def build_diff_chain_hash(payload: DiffTokenInput) -> str:
    return build_token(
        {
            "tenant_id": str(payload.tenant_id),
            "base_run_id": str(payload.base_run_id),
            "compare_run_id": str(payload.compare_run_id),
            "base_run_token": payload.base_run_token,
            "compare_run_token": payload.compare_run_token,
        }
    )
