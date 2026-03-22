from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import INVALID_EVENT_SEQUENCE, VERSION_CHAIN_BROKEN


@dataclass(frozen=True)
class SupersessionNode:
    id: UUID
    tenant_id: UUID
    created_at: datetime
    supersedes_id: UUID | None


def validate_linear_chain(
    *,
    nodes: Iterable[SupersessionNode],
    tenant_id: UUID,
) -> list[SupersessionNode]:
    ordered = sorted(nodes, key=lambda row: (row.created_at, row.id))
    if not ordered:
        return []

    for row in ordered:
        if row.tenant_id != tenant_id:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Supersession chain contains cross-tenant node",
            )

    by_id = {row.id: row for row in ordered}
    child_count: dict[UUID, int] = {}
    roots = 0
    for row in ordered:
        if row.supersedes_id is None:
            roots += 1
            continue
        if row.supersedes_id not in by_id:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Supersession chain has orphaned predecessor reference",
            )
        child_count[row.supersedes_id] = child_count.get(row.supersedes_id, 0) + 1
        if child_count[row.supersedes_id] > 1:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Supersession chain branching detected",
            )

    if roots != 1:
        raise AccountingValidationError(
            error_code=VERSION_CHAIN_BROKEN,
            message="Supersession chain must have exactly one root",
        )

    # Cycle detection
    state: dict[UUID, int] = {row.id: 0 for row in ordered}  # 0=unseen,1=visiting,2=done

    def _visit(node: SupersessionNode) -> None:
        current = state[node.id]
        if current == 1:
            raise AccountingValidationError(
                error_code=VERSION_CHAIN_BROKEN,
                message="Supersession cycle detected",
            )
        if current == 2:
            return
        state[node.id] = 1
        if node.supersedes_id is not None:
            _visit(by_id[node.supersedes_id])
        state[node.id] = 2

    for row in ordered:
        _visit(row)

    return ordered


def resolve_terminal_node(
    *,
    nodes: Iterable[SupersessionNode],
    tenant_id: UUID,
) -> SupersessionNode | None:
    ordered = validate_linear_chain(nodes=nodes, tenant_id=tenant_id)
    if not ordered:
        return None
    by_id = {row.id: row for row in ordered}
    superseded_ids = {row.supersedes_id for row in ordered if row.supersedes_id is not None}
    terminals = [row for row in ordered if row.id not in superseded_ids]
    if len(terminals) != 1:
        raise AccountingValidationError(
            error_code=VERSION_CHAIN_BROKEN,
            message="Supersession chain terminal node is ambiguous",
        )
    return terminals[0]


def ensure_append_targets_terminal(
    *,
    nodes: Iterable[SupersessionNode],
    tenant_id: UUID,
    supersedes_id: UUID | None,
) -> None:
    terminal = resolve_terminal_node(nodes=nodes, tenant_id=tenant_id)
    if terminal is None:
        if supersedes_id is not None:
            raise AccountingValidationError(
                error_code=INVALID_EVENT_SEQUENCE,
                message="Cannot supersede a non-existent terminal node",
            )
        return
    if supersedes_id != terminal.id:
        raise AccountingValidationError(
            error_code=INVALID_EVENT_SEQUENCE,
            message="New supersession row must point to current terminal node",
        )


