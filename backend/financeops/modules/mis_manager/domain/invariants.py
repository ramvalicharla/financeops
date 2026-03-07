from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SupersessionNode:
    id: UUID
    template_id: UUID
    supersedes_id: UUID | None


def enforce_linear_supersession(nodes: list[SupersessionNode]) -> None:
    """Raise ValueError when the supersession chain is cyclic or branched."""
    by_id = {node.id: node for node in nodes}
    child_counts: dict[UUID, int] = {}

    for node in nodes:
        if node.supersedes_id is None:
            continue
        if node.supersedes_id == node.id:
            raise ValueError("Self-supersession is not allowed")
        parent = by_id.get(node.supersedes_id)
        if parent is None:
            raise ValueError("Supersession points to a missing parent")
        if parent.template_id != node.template_id:
            raise ValueError("Supersession across templates is not allowed")
        child_counts[node.supersedes_id] = child_counts.get(node.supersedes_id, 0) + 1
        if child_counts[node.supersedes_id] > 1:
            raise ValueError("Supersession branching detected")

    state: dict[UUID, int] = {
        node.id: 0 for node in nodes
    }  # 0 unseen, 1 visiting, 2 done

    def _visit(node: SupersessionNode) -> None:
        status = state[node.id]
        if status == 1:
            raise ValueError("Supersession cycle detected")
        if status == 2:
            return
        state[node.id] = 1
        if node.supersedes_id is not None:
            _visit(by_id[node.supersedes_id])
        state[node.id] = 2

    for node in nodes:
        _visit(node)


def enforce_engine_isolation(target_table: str) -> None:
    lowered = target_table.lower()
    forbidden_prefixes = (
        "revenue_",
        "lease_",
        "prepaid_",
        "asset_",
        "far_",
    )
    if lowered.startswith(forbidden_prefixes):
        raise ValueError("MIS manager cannot write to accounting engine tables")
