from __future__ import annotations

import uuid
from time import perf_counter
from typing import Any

from financeops.modules.observability_engine.application.diff_service import DiffService
from financeops.modules.observability_engine.application.graph_service import GraphService
from financeops.modules.observability_engine.application.replay_service import ReplayService
from financeops.modules.observability_engine.application.validation_service import ValidationService
from financeops.modules.observability_engine.domain.enums import OperationStatus, OperationType
from financeops.modules.observability_engine.domain.value_objects import (
    DiffTokenInput,
    ObservabilityOperationTokenInput,
)
from financeops.modules.observability_engine.infrastructure.repository import ObservabilityRepository
from financeops.modules.observability_engine.infrastructure.token_builder import (
    build_diff_chain_hash,
    build_operation_token,
)
from financeops.shared_kernel.tokens import build_token


class RunService:
    def __init__(
        self,
        *,
        repository: ObservabilityRepository,
        validation_service: ValidationService,
        diff_service: DiffService,
        replay_service: ReplayService,
        graph_service: GraphService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._diff = diff_service
        self._replay = replay_service
        self._graph = graph_service

    async def list_registry_runs(self, *, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_registry(tenant_id=tenant_id)
        return [self._registry_row_to_dict(row) for row in rows]

    async def get_registry_run(self, *, tenant_id: uuid.UUID, registry_or_run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_registry(tenant_id=tenant_id, registry_id=registry_or_run_id)
        if row is None:
            row = await self._repository.get_latest_registry_by_run_id(
                tenant_id=tenant_id, run_id=registry_or_run_id
            )
        if row is None:
            return None
        return self._registry_row_to_dict(row)

    async def discover_and_sync_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        snapshot = self._validation.require_snapshot(
            await self._repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=run_id),
            run_id=str(run_id),
        )
        existing = await self._repository.get_registry_by_run(
            tenant_id=tenant_id,
            module_code=snapshot["module_code"],
            run_id=snapshot["run_id"],
            run_token=snapshot["run_token"],
        )
        if existing is not None:
            return self._registry_row_to_dict(existing)

        row = await self._repository.create_registry_entry(
            tenant_id=tenant_id,
            module_code=snapshot["module_code"],
            run_id=snapshot["run_id"],
            run_token=snapshot["run_token"],
            version_token_snapshot_json=snapshot["version_tokens"],
            upstream_dependencies_json=snapshot["dependencies"],
            execution_time_ms=int(snapshot.get("execution_time_ms", 0)),
            status="discovered",
            created_by=created_by,
        )
        await self._repository.create_governance_event(
            tenant_id=tenant_id,
            module_code=snapshot["module_code"],
            run_id=snapshot["run_id"],
            event_type="version_resolution_trace",
            event_payload_json={"version_tokens": snapshot["version_tokens"]},
            created_by=created_by,
        )
        return self._registry_row_to_dict(row)

    async def run_diff(
        self,
        *,
        tenant_id: uuid.UUID,
        base_run_id: uuid.UUID,
        compare_run_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        started = perf_counter()
        base = self._validation.require_snapshot(
            await self._repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=base_run_id),
            run_id=str(base_run_id),
        )
        compare = self._validation.require_snapshot(
            await self._repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=compare_run_id),
            run_id=str(compare_run_id),
        )
        self._validation.validate_diff_inputs(base=base, compare=compare)

        diff_summary = self._diff.compare(base=base, compare=compare)
        chain_hash = build_diff_chain_hash(
            DiffTokenInput(
                tenant_id=tenant_id,
                base_run_id=base_run_id,
                compare_run_id=compare_run_id,
                base_run_token=base["run_token"],
                compare_run_token=compare["run_token"],
            )
        )
        op_token = build_operation_token(
            ObservabilityOperationTokenInput(
                tenant_id=tenant_id,
                operation_type=OperationType.DIFF.value,
                input_ref_json={
                    "base_run_id": str(base_run_id),
                    "compare_run_id": str(compare_run_id),
                    "base_run_token": base["run_token"],
                    "compare_run_token": compare["run_token"],
                },
            )
        )
        existing_op = await self._repository.get_observability_run_by_token(
            tenant_id=tenant_id,
            operation_token=op_token,
        )
        if existing_op is not None:
            existing_result = await self._repository.get_observability_result_for_run(
                tenant_id=tenant_id,
                observability_run_id=existing_op.id,
            )
            if existing_result is not None:
                payload = dict(existing_result.result_payload_json)
                payload["idempotent"] = True
                return payload

        operation = await self._repository.create_observability_run(
            tenant_id=tenant_id,
            operation_type=OperationType.DIFF.value,
            input_ref_json={
                "base_run_id": str(base_run_id),
                "compare_run_id": str(compare_run_id),
            },
            operation_token=op_token,
            status=OperationStatus.COMPLETED.value,
            created_by=created_by,
        )
        diff_row = await self._repository.create_diff_result(
            tenant_id=tenant_id,
            base_run_id=base_run_id,
            compare_run_id=compare_run_id,
            diff_summary_json=diff_summary,
            drift_flag=bool(diff_summary["drift_flag"]),
            chain_hash=chain_hash,
            previous_hash="0" * 64,
            created_by=created_by,
        )
        perf = await self._repository.create_performance_metric(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            query_count=4,
            execution_time_ms=max(int((perf_counter() - started) * 1000), 0),
            dependency_depth=0,
            created_by=created_by,
        )
        event = await self._repository.create_governance_event(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            event_type="diff_computed",
            event_payload_json=diff_summary,
            created_by=created_by,
        )
        payload = {
            "diff_id": str(diff_row.id),
            "base_run_id": str(base_run_id),
            "compare_run_id": str(compare_run_id),
            "drift_flag": bool(diff_row.drift_flag),
            "summary": diff_summary,
            "idempotent": False,
        }
        result = await self._repository.create_observability_result(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            result_payload_json=payload,
            created_by=created_by,
        )
        await self._repository.create_observability_evidence_links(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            created_by=created_by,
            rows=[
                {
                    "result_id": result.id,
                    "evidence_type": "upstream_run",
                    "evidence_ref": str(base_run_id),
                    "evidence_label": "Base run",
                    "evidence_payload_json": {"module_code": base["module_code"]},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "upstream_run",
                    "evidence_ref": str(compare_run_id),
                    "evidence_label": "Compare run",
                    "evidence_payload_json": {"module_code": compare["module_code"]},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "diff_result",
                    "evidence_ref": str(diff_row.id),
                    "evidence_label": "Diff result",
                    "evidence_payload_json": {},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "performance_metric",
                    "evidence_ref": str(perf.id),
                    "evidence_label": "Performance metric",
                    "evidence_payload_json": {},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "governance_event",
                    "evidence_ref": str(event.id),
                    "evidence_label": "Governance event",
                    "evidence_payload_json": {},
                },
            ],
        )
        return payload

    async def get_diff(self, *, tenant_id: uuid.UUID, diff_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_diff_result(tenant_id=tenant_id, diff_id=diff_id)
        if row is None:
            return None
        return {
            "diff_id": str(row.id),
            "base_run_id": str(row.base_run_id),
            "compare_run_id": str(row.compare_run_id),
            "drift_flag": bool(row.drift_flag),
            "summary": row.diff_summary_json,
        }

    async def replay_validate(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        started = perf_counter()
        snapshot = self._validation.require_snapshot(
            await self._repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=run_id),
            run_id=str(run_id),
        )
        self._validation.validate_replay_support(module_code=str(snapshot["module_code"]))

        recomputed = self._replay.recompute_run_token(
            module_code=str(snapshot["module_code"]), row=snapshot["row"]
        )
        matches = recomputed == str(snapshot["run_token"])

        op_token = build_operation_token(
            ObservabilityOperationTokenInput(
                tenant_id=tenant_id,
                operation_type=OperationType.REPLAY_VALIDATE.value,
                input_ref_json={
                    "run_id": str(run_id),
                    "module_code": str(snapshot["module_code"]),
                    "stored_run_token": str(snapshot["run_token"]),
                },
            )
        )
        operation = await self._repository.create_observability_run(
            tenant_id=tenant_id,
            operation_type=OperationType.REPLAY_VALIDATE.value,
            input_ref_json={"run_id": str(run_id), "module_code": str(snapshot["module_code"])},
            operation_token=op_token,
            status=OperationStatus.COMPLETED.value if matches else OperationStatus.FAILED.value,
            created_by=created_by,
        )

        perf = await self._repository.create_performance_metric(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            query_count=2,
            execution_time_ms=max(int((perf_counter() - started) * 1000), 0),
            dependency_depth=0,
            created_by=created_by,
        )
        event = await self._repository.create_governance_event(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            event_type="replay_validated",
            event_payload_json={
                "module_code": snapshot["module_code"],
                "run_id": str(run_id),
                "stored_run_token": snapshot["run_token"],
                "recomputed_run_token": recomputed,
                "matches": matches,
            },
            created_by=created_by,
        )
        payload = {
            "run_id": str(run_id),
            "module_code": snapshot["module_code"],
            "stored_run_token": snapshot["run_token"],
            "recomputed_run_token": recomputed,
            "matches": matches,
        }
        result = await self._repository.create_observability_result(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            result_payload_json=payload,
            created_by=created_by,
        )
        await self._repository.create_observability_evidence_links(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            created_by=created_by,
            rows=[
                {
                    "result_id": result.id,
                    "evidence_type": "upstream_run",
                    "evidence_ref": str(run_id),
                    "evidence_label": "Replay target run",
                    "evidence_payload_json": {"module_code": snapshot["module_code"]},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "performance_metric",
                    "evidence_ref": str(perf.id),
                    "evidence_label": "Performance metric",
                    "evidence_payload_json": {},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "governance_event",
                    "evidence_ref": str(event.id),
                    "evidence_label": "Governance event",
                    "evidence_payload_json": {},
                },
            ],
        )
        return payload

    async def build_graph_snapshot(
        self, *, tenant_id: uuid.UUID, root_run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        started = perf_counter()
        graph_payload = await self._graph.build_graph(tenant_id=tenant_id, root_run_id=root_run_id)
        deterministic_hash = build_token(graph_payload)
        op_token = build_operation_token(
            ObservabilityOperationTokenInput(
                tenant_id=tenant_id,
                operation_type=OperationType.GRAPH_SNAPSHOT.value,
                input_ref_json={
                    "root_run_id": str(root_run_id),
                    "deterministic_hash": deterministic_hash,
                },
            )
        )
        operation = await self._repository.create_observability_run(
            tenant_id=tenant_id,
            operation_type=OperationType.GRAPH_SNAPSHOT.value,
            input_ref_json={"root_run_id": str(root_run_id)},
            operation_token=op_token,
            status=OperationStatus.COMPLETED.value,
            created_by=created_by,
        )
        snapshot = await self._repository.create_graph_snapshot(
            tenant_id=tenant_id,
            root_run_id=root_run_id,
            graph_payload_json=graph_payload,
            deterministic_hash=deterministic_hash,
            created_by=created_by,
        )
        depth = 0
        if graph_payload.get("edges"):
            depth = 1 + max(graph_payload["edges"].count(edge) for edge in graph_payload["edges"])
        perf = await self._repository.create_performance_metric(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            query_count=max(len(graph_payload.get("nodes", [])), 1),
            execution_time_ms=max(int((perf_counter() - started) * 1000), 0),
            dependency_depth=depth,
            created_by=created_by,
        )
        event = await self._repository.create_governance_event(
            tenant_id=tenant_id,
            module_code="observability_engine",
            run_id=operation.id,
            event_type="graph_snapshot_created",
            event_payload_json={"root_run_id": str(root_run_id), "deterministic_hash": deterministic_hash},
            created_by=created_by,
        )
        payload = {
            "graph_snapshot_id": str(snapshot.id),
            "root_run_id": str(root_run_id),
            "deterministic_hash": deterministic_hash,
            "graph": graph_payload,
        }
        result = await self._repository.create_observability_result(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            result_payload_json=payload,
            created_by=created_by,
        )
        await self._repository.create_observability_evidence_links(
            tenant_id=tenant_id,
            observability_run_id=operation.id,
            created_by=created_by,
            rows=[
                {
                    "result_id": result.id,
                    "evidence_type": "graph_snapshot",
                    "evidence_ref": str(snapshot.id),
                    "evidence_label": "Graph snapshot",
                    "evidence_payload_json": {},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "performance_metric",
                    "evidence_ref": str(perf.id),
                    "evidence_label": "Performance metric",
                    "evidence_payload_json": {},
                },
                {
                    "result_id": result.id,
                    "evidence_type": "governance_event",
                    "evidence_ref": str(event.id),
                    "evidence_label": "Governance event",
                    "evidence_payload_json": {},
                },
            ],
        )
        return payload

    async def latest_graph(self, *, tenant_id: uuid.UUID, root_run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_latest_graph_snapshot(
            tenant_id=tenant_id,
            root_run_id=root_run_id,
        )
        if row is None:
            return None
        return {
            "graph_snapshot_id": str(row.id),
            "root_run_id": str(row.root_run_id),
            "deterministic_hash": row.deterministic_hash,
            "graph": row.graph_payload_json,
        }

    async def list_events(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_governance_events(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "module_code": row.module_code,
                "run_id": str(row.run_id),
                "event_type": row.event_type,
                "event_payload_json": row.event_payload_json,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def latest_performance(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.latest_performance_metric(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "module_code": row.module_code,
            "run_id": str(row.run_id),
            "query_count": int(row.query_count),
            "execution_time_ms": int(row.execution_time_ms),
            "dependency_depth": int(row.dependency_depth),
            "created_at": row.created_at.isoformat(),
        }

    @staticmethod
    def _registry_row_to_dict(row: Any) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "module_code": row.module_code,
            "run_id": str(row.run_id),
            "run_token": row.run_token,
            "version_token_snapshot_json": row.version_token_snapshot_json,
            "upstream_dependencies_json": row.upstream_dependencies_json,
            "execution_time_ms": int(row.execution_time_ms),
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
