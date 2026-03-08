from __future__ import annotations

import uuid

import pytest

from financeops.modules.observability_engine.application.diff_service import DiffService
from financeops.modules.observability_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.observability_engine.domain.enums import OperationType
from financeops.modules.observability_engine.domain.value_objects import (
    DiffTokenInput,
    ObservabilityOperationTokenInput,
)
from financeops.modules.observability_engine.infrastructure.token_builder import (
    build_diff_chain_hash,
    build_operation_token,
)


def test_operation_token_generation_is_deterministic() -> None:
    tenant_id = uuid.uuid4()
    payload = ObservabilityOperationTokenInput(
        tenant_id=tenant_id,
        operation_type=OperationType.DIFF.value,
        input_ref_json={"a": "1", "b": "2"},
    )
    assert build_operation_token(payload) == build_operation_token(payload)


def test_diff_chain_hash_changes_when_run_order_changes() -> None:
    tenant_id = uuid.uuid4()
    run_a = uuid.uuid4()
    run_b = uuid.uuid4()
    forward = build_diff_chain_hash(
        DiffTokenInput(
            tenant_id=tenant_id,
            base_run_id=run_a,
            compare_run_id=run_b,
            base_run_token="a",
            compare_run_token="b",
        )
    )
    reverse = build_diff_chain_hash(
        DiffTokenInput(
            tenant_id=tenant_id,
            base_run_id=run_b,
            compare_run_id=run_a,
            base_run_token="b",
            compare_run_token="a",
        )
    )
    assert forward != reverse


def test_diff_service_output_is_stable() -> None:
    service = DiffService()
    base = {
        "module_code": "equity_engine",
        "run_id": uuid.uuid4(),
        "run_token": "tok1",
        "version_tokens": {"a_version_token": "a", "b_version_token": "b"},
        "dependencies": [{"kind": "x", "run_id": "1"}],
    }
    compare = {
        "module_code": "equity_engine",
        "run_id": uuid.uuid4(),
        "run_token": "tok2",
        "version_tokens": {"a_version_token": "a", "b_version_token": "c"},
        "dependencies": [{"kind": "x", "run_id": "2"}],
    }
    result_a = service.compare(base=base, compare=compare)
    result_b = service.compare(base=base, compare=compare)
    assert result_a == result_b
    assert result_a["drift_flag"] is True
    assert result_a["version_token_diffs"][0]["key"] == "b_version_token"


def test_validation_service_rejects_unsupported_replay_module() -> None:
    with pytest.raises(ValueError, match="replay validation is not supported"):
        ValidationService().validate_replay_support(module_code="ratio_variance_engine")

