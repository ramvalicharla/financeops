from __future__ import annotations

from typing import Any


class ValidationService:
    def require_snapshot(self, snapshot: dict[str, Any] | None, *, run_id: str) -> dict[str, Any]:
        if snapshot is None:
            raise ValueError(f"run {run_id} is not discoverable for tenant")
        return snapshot

    def validate_diff_inputs(self, *, base: dict[str, Any], compare: dict[str, Any]) -> None:
        if base["run_id"] == compare["run_id"]:
            raise ValueError("base and compare runs must be different")
        if not base["run_token"] or not compare["run_token"]:
            raise ValueError("run tokens are required for diff")

    def validate_replay_support(self, *, module_code: str) -> None:
        if module_code not in {"equity_engine", "cash_flow_engine"}:
            raise ValueError(f"replay validation is not supported for module {module_code}")
