from __future__ import annotations

import uuid
from typing import Any

from financeops.modules.observability_engine.infrastructure.repository import ObservabilityRepository


class GraphService:
    def __init__(self, repository: ObservabilityRepository) -> None:
        self._repository = repository

    async def build_graph(self, *, tenant_id: uuid.UUID, root_run_id: uuid.UUID) -> dict[str, Any]:
        visited: set[str] = set()
        queue: list[uuid.UUID] = [root_run_id]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        while queue:
            current = queue.pop(0)
            current_key = str(current)
            if current_key in visited:
                continue
            visited.add(current_key)
            snapshot = await self._repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=current)
            if snapshot is None:
                continue
            nodes.append(
                {
                    "run_id": str(snapshot["run_id"]),
                    "module_code": snapshot["module_code"],
                    "run_token": snapshot["run_token"],
                    "status": snapshot["status"],
                }
            )
            for dep in snapshot.get("dependencies", []):
                dep_id = dep.get("run_id")
                if not dep_id:
                    continue
                edges.append(
                    {
                        "from_run_id": str(snapshot["run_id"]),
                        "to_run_id": str(dep_id),
                        "kind": dep.get("kind", "run_ref"),
                    }
                )
                try:
                    dep_uuid = uuid.UUID(str(dep_id))
                except ValueError:
                    continue
                if str(dep_uuid) not in visited:
                    queue.append(dep_uuid)

        nodes.sort(key=lambda item: (item["module_code"], item["run_id"]))
        edges.sort(key=lambda item: (item["from_run_id"], item["kind"], item["to_run_id"]))
        return {
            "root_run_id": str(root_run_id),
            "nodes": nodes,
            "edges": edges,
        }
