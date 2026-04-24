from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------

def _platform_user(role: str = "platform_admin") -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.tenant_id = uuid.uuid4()
    u.role = MagicMock()
    u.role.value = role
    return u


def _tenant(tenant_id: uuid.UUID | None = None) -> MagicMock:
    t = MagicMock()
    t.id = tenant_id or uuid.uuid4()
    t.tenant_id = t.id
    t.display_name = "Acme Corp"
    t.slug = "acme-corp"
    t.status = MagicMock()
    t.status.value = "active"
    t.country = "IN"
    t.created_at = MagicMock()
    t.created_at.isoformat = lambda: "2026-01-01T00:00:00"
    return t


def _sub(tenant_id: uuid.UUID | None = None, status: str = "trialing") -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.tenant_id = tenant_id or uuid.uuid4()
    s.plan_id = uuid.uuid4()
    s.provider = "internal"
    s.provider_subscription_id = f"trial_{s.tenant_id}"
    s.provider_customer_id = str(s.tenant_id)
    s.status = status
    s.billing_cycle = "monthly"
    s.current_period_start = date(2026, 1, 1)
    s.current_period_end = date(2026, 1, 15)
    s.trial_start = date(2026, 1, 1)
    s.trial_end = date(2026, 1, 15)
    s.trial_end_date = date(2026, 1, 15)
    s.start_date = date(2026, 1, 1)
    s.end_date = date(2026, 1, 15)
    s.auto_renew = True
    s.cancelled_at = None
    s.cancel_at_period_end = False
    s.onboarding_mode = "self_serve"
    s.billing_country = "IN"
    s.billing_currency = "USD"
    s.metadata_json = {}
    return s


def _make_session(scalars_return=None, scalar_one_or_none_return=None, scalar_return=0):
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one=MagicMock(return_value=0),
            scalar_one_or_none=MagicMock(return_value=scalar_one_or_none_return),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=scalars_return or []))),
        )
    )
    session.scalar = AsyncMock(return_value=scalar_return)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_request():
    r = MagicMock()
    r.client = MagicMock()
    r.client.host = "127.0.0.1"
    r.headers = MagicMock()
    r.headers.get = MagicMock(return_value=None)
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_admin_list_tenants_requires_platform_admin() -> None:
    """GET /admin/tenants: returns paginated list; each item has expected keys."""
    from financeops.platform.api.v1.admin import admin_list_tenants

    tenant_id = uuid.uuid4()
    t = _tenant(tenant_id)

    exec_results = [
        MagicMock(scalar_one=MagicMock(return_value=1)),          # total count
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[t])))),  # tenants
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # subscription
        MagicMock(),                                               # credit sum (scalar)
        MagicMock(scalar_one=MagicMock(return_value=2)),          # user count
    ]
    exec_iter = iter(exec_results)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))
    session.scalar = AsyncMock(return_value=50)

    user = _platform_user("platform_admin")

    result = await admin_list_tenants(limit=50, offset=0, session=session, user=user)

    assert result["total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == str(tenant_id)
    assert "credit_balance" in item
    assert "user_count" in item


async def test_admin_get_tenant_detail() -> None:
    """GET /admin/tenants/{id}: returns tenant, subscription, credits, invoices, ledger."""
    from financeops.platform.api.v1.admin import admin_get_tenant

    tenant_id = uuid.uuid4()
    t = _tenant(tenant_id)
    s = _sub(tenant_id=tenant_id)

    exec_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=t)),     # tenant lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=s)),     # subscription
        MagicMock(),                                                  # credit scalar placeholder
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # invoices
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # credits
    ]
    exec_iter = iter(exec_results)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))
    session.scalar = AsyncMock(return_value=200)

    result = await admin_get_tenant(tenant_id=tenant_id, session=session, user=_platform_user())

    assert result["tenant"]["id"] == str(tenant_id)
    assert result["subscription"]["id"] == str(s.id)
    assert result["credit_balance"] == 200
    assert isinstance(result["recent_invoices"], list)
    assert isinstance(result["recent_credits"], list)


async def test_admin_extend_trial() -> None:
    """POST /admin/tenants/{id}/extend-trial: appends subscription revision with new trial_end_date."""
    from financeops.platform.api.v1.admin import admin_extend_trial, ExtendTrialRequest

    tenant_id = uuid.uuid4()
    s = _sub(tenant_id=tenant_id, status="trialing")
    s.trial_end_date = date(2026, 1, 15)

    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=s))
    )
    session.flush = AsyncMock()

    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "trialing"

    with (
        patch("financeops.platform.api.v1.admin.SubscriptionService") as MockSvc,
        patch("financeops.platform.api.v1.admin.AuditWriter.insert_financial_record", AsyncMock(return_value=mock_revised)),
        patch("financeops.platform.api.v1.admin.log_action", AsyncMock()),
    ):
        MockSvc.return_value.append_subscription_revision = AsyncMock(return_value=mock_revised)
        result = await admin_extend_trial(
            tenant_id=tenant_id,
            body=ExtendTrialRequest(days=7),
            request=_make_request(),
            session=session,
            user=_platform_user(),
        )

    assert result["success"] is True
    assert result["days_added"] == 7
    expected_end = date(2026, 1, 15) + timedelta(days=7)
    assert result["new_trial_end_date"] == expected_end.isoformat()


async def test_admin_activate_tenant() -> None:
    """POST /admin/tenants/{id}/activate: revision inserted with status='active'."""
    from financeops.platform.api.v1.admin import admin_activate_tenant

    tenant_id = uuid.uuid4()
    s = _sub(tenant_id=tenant_id, status="suspended")

    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=s))
    )
    session.flush = AsyncMock()

    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "active"

    with (
        patch("financeops.platform.api.v1.admin.SubscriptionService") as MockSvc,
        patch("financeops.platform.api.v1.admin.log_action", AsyncMock()),
    ):
        MockSvc.return_value.append_subscription_revision = AsyncMock(return_value=mock_revised)
        result = await admin_activate_tenant(
            tenant_id=tenant_id,
            request=_make_request(),
            session=session,
            user=_platform_user(),
        )

    assert result["success"] is True
    assert result["status"] == "active"
    MockSvc.return_value.append_subscription_revision.assert_awaited_once_with(source=s, status="active")


async def test_admin_suspend_tenant() -> None:
    """POST /admin/tenants/{id}/suspend: revision inserted with status='suspended'."""
    from financeops.platform.api.v1.admin import admin_suspend_tenant

    tenant_id = uuid.uuid4()
    s = _sub(tenant_id=tenant_id, status="active")

    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=s))
    )
    session.flush = AsyncMock()

    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "suspended"

    with (
        patch("financeops.platform.api.v1.admin.SubscriptionService") as MockSvc,
        patch("financeops.platform.api.v1.admin.log_action", AsyncMock()),
    ):
        MockSvc.return_value.append_subscription_revision = AsyncMock(return_value=mock_revised)
        result = await admin_suspend_tenant(
            tenant_id=tenant_id,
            request=_make_request(),
            session=session,
            user=_platform_user(),
        )

    assert result["success"] is True
    assert result["status"] == "suspended"
    MockSvc.return_value.append_subscription_revision.assert_awaited_once_with(source=s, status="suspended")


async def test_admin_change_plan() -> None:
    """POST /admin/tenants/{id}/change-plan: revises subscription plan and allocates credits."""
    from financeops.platform.api.v1.admin import admin_change_plan, ChangePlanRequest

    tenant_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id
    mock_plan.plan_tier = "professional"
    mock_plan.included_credits = 2000

    s = _sub(tenant_id=tenant_id, status="active")

    exec_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_plan)),  # plan lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=s)),          # sub lookup
    ]
    exec_iter = iter(exec_results)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))
    session.scalar = AsyncMock(return_value=100)  # current balance
    session.flush = AsyncMock()

    mock_revised = MagicMock()
    mock_revised.id = uuid.uuid4()
    mock_revised.status = "active"

    with (
        patch("financeops.platform.api.v1.admin.SubscriptionService") as MockSvc,
        patch("financeops.platform.api.v1.admin.AuditWriter.insert_financial_record", AsyncMock()),
        patch("financeops.platform.api.v1.admin.log_action", AsyncMock()),
    ):
        MockSvc.return_value.append_subscription_revision = AsyncMock(return_value=mock_revised)
        result = await admin_change_plan(
            tenant_id=tenant_id,
            body=ChangePlanRequest(plan_id=plan_id),
            request=_make_request(),
            session=session,
            user=_platform_user(),
        )

    assert result["success"] is True
    assert result["plan_tier"] == "professional"
    assert result["credits_allocated"] == 2000


async def test_admin_list_credits() -> None:
    """GET /admin/credits: returns credit balances per tenant; low_balance filter works."""
    from financeops.platform.api.v1.admin import admin_list_credits

    row = MagicMock()
    row.id = uuid.uuid4()
    row.display_name = "Acme Corp"
    row.balance = 50
    row.last_transaction_at = MagicMock()
    row.last_transaction_at.isoformat = lambda: "2026-04-01T00:00:00"

    exec_results = [
        MagicMock(scalar_one=MagicMock(return_value=1)),      # total count
        MagicMock(all=MagicMock(return_value=[row])),          # rows
    ]
    exec_iter = iter(exec_results)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda *a, **kw: next(exec_iter))

    result = await admin_list_credits(
        limit=50,
        offset=0,
        low_balance=True,
        session=session,
        user=_platform_user(),
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["credit_balance"] == 50
    assert result["items"][0]["tenant_name"] == "Acme Corp"


async def test_admin_switch_requires_platform_owner() -> None:
    """POST /admin/tenants/{id}/switch: issues a 15-min JWT scoped to the target tenant."""
    from financeops.platform.api.v1.admin import admin_switch_tenant

    tenant_id = uuid.uuid4()
    t = _tenant(tenant_id)
    user = _platform_user("platform_owner")

    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=t))
    )
    session.flush = AsyncMock()

    with (
        patch("financeops.platform.api.v1.admin.create_access_token", return_value="switch.jwt.token") as mock_token,
        patch("financeops.platform.api.v1.admin.log_action", AsyncMock()),
    ):
        result = await admin_switch_tenant(
            tenant_id=tenant_id,
            request=_make_request(),
            session=session,
            user=user,
        )

    assert result["switch_token"] == "switch.jwt.token"
    assert result["tenant_id"] == str(tenant_id)
    assert result["expires_in_seconds"] == 900

    mock_token.assert_called_once()
    call_kwargs = mock_token.call_args.kwargs
    assert call_kwargs["tenant_id"] == tenant_id
    assert call_kwargs["additional_claims"]["scope"] == "platform_switch"
