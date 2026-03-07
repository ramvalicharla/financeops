from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import VERSION_CHAIN_BROKEN
from financeops.services.accounting_common.supersession_validator import SupersessionNode, validate_linear_chain


def _node(
    *,
    tenant_id,
    supersedes_id=None,
    minute: int,
):
    return SupersessionNode(
        id=uuid4(),
        tenant_id=tenant_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
        supersedes_id=supersedes_id,
    )


def test_validate_linear_chain_rejects_branching() -> None:
    tenant_id = uuid4()
    root = _node(tenant_id=tenant_id, supersedes_id=None, minute=0)
    child_1 = _node(tenant_id=tenant_id, supersedes_id=root.id, minute=1)
    child_2 = _node(tenant_id=tenant_id, supersedes_id=root.id, minute=2)

    with pytest.raises(AccountingValidationError) as exc:
        validate_linear_chain(nodes=[root, child_1, child_2], tenant_id=tenant_id)

    assert exc.value.error_code == VERSION_CHAIN_BROKEN


def test_validate_linear_chain_rejects_cycle() -> None:
    tenant_id = uuid4()
    root = _node(tenant_id=tenant_id, supersedes_id=None, minute=0)
    child = _node(tenant_id=tenant_id, supersedes_id=root.id, minute=1)
    # Create cycle by linking root back to child.
    cyc_root = SupersessionNode(
        id=root.id,
        tenant_id=root.tenant_id,
        created_at=root.created_at,
        supersedes_id=child.id,
    )

    with pytest.raises(AccountingValidationError) as exc:
        validate_linear_chain(nodes=[cyc_root, child], tenant_id=tenant_id)

    assert exc.value.error_code == VERSION_CHAIN_BROKEN


def test_validate_linear_chain_rejects_cross_tenant_node() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    root = _node(tenant_id=tenant_id, supersedes_id=None, minute=0)
    foreign = _node(tenant_id=other_tenant_id, supersedes_id=root.id, minute=1)

    with pytest.raises(AccountingValidationError) as exc:
        validate_linear_chain(nodes=[root, foreign], tenant_id=tenant_id)

    assert exc.value.error_code == VERSION_CHAIN_BROKEN
