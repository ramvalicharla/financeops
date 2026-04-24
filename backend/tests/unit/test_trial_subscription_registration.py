from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def _make_body():
    from financeops.api.v1.auth import RegisterRequest
    from financeops.db.models.tenants import TenantType

    return RegisterRequest(
        email="test@example.com",
        password="Str0ng!Pass",
        full_name="Test User",
        tenant_name="Test Co",
        tenant_type=TenantType.company,
        country="IN",
        terms_accepted=True,
    )


def _mock_request():
    r = MagicMock()
    r.headers.get = MagicMock(return_value="pytest/unit")
    r.state.request_id = "req-unit"
    return r


def _common_patches(mock_tenant, mock_user, mock_sub_svc, mock_add_credits):
    return [
        patch("financeops.api.v1.auth.create_tenant", AsyncMock(return_value=mock_tenant)),
        patch("financeops.api.v1.auth.set_tenant_context", AsyncMock()),
        patch("financeops.api.v1.auth.create_default_workspace", AsyncMock()),
        patch("financeops.api.v1.auth.create_user", AsyncMock(return_value=mock_user)),
        patch("financeops.api.v1.auth.SubscriptionService", return_value=mock_sub_svc),
        patch("financeops.api.v1.auth.add_credits", mock_add_credits),
        patch("financeops.api.v1.auth.log_action", AsyncMock()),
        patch("financeops.api.v1.auth.send_direct", AsyncMock()),
        patch("financeops.api.v1.auth.welcome_email", return_value=("subj", "<h/>")),
        patch("financeops.api.v1.auth.commit_session", AsyncMock()),
        patch("financeops.api.v1.auth.generate_mfa_setup_token", return_value="setup-tok"),
        patch("financeops.api.v1.auth.get_real_ip", return_value="127.0.0.1"),
    ]


async def test_registration_creates_trial_subscription() -> None:
    """register: SubscriptionService.create_subscription_record called with Trial plan when plan exists."""
    from financeops.api.v1.auth import register

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id

    mock_tenant = MagicMock()
    mock_tenant.id = tenant_id
    mock_tenant.display_name = "Test Co"
    mock_tenant.country = "IN"

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_plan))
    )
    mock_session.flush = AsyncMock()

    mock_sub_svc = MagicMock()
    mock_sub_svc.create_subscription_record = AsyncMock(return_value=MagicMock())
    mock_add_credits = AsyncMock()

    patches = _common_patches(mock_tenant, mock_user, mock_sub_svc, mock_add_credits)
    body = _make_body()

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6], patches[7], patches[8], patches[9], patches[10], patches[11]:
        result = await register(body=body, request=_mock_request(), session=mock_session)

    mock_sub_svc.create_subscription_record.assert_awaited_once()
    kwargs = mock_sub_svc.create_subscription_record.call_args.kwargs
    assert kwargs["plan_id"] == plan_id
    assert kwargs["provider"] == "internal"
    assert kwargs["billing_cycle"] == "monthly"
    assert result.tenant_id == str(tenant_id)


async def test_registration_sets_trial_end_date_14_days() -> None:
    """register: trial_end and period_end passed to SubscriptionService are today + 14 days."""
    from financeops.api.v1.auth import register

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id

    mock_tenant = MagicMock()
    mock_tenant.id = tenant_id
    mock_tenant.display_name = "Test Co"
    mock_tenant.country = "US"

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_plan))
    )
    mock_session.flush = AsyncMock()

    mock_sub_svc = MagicMock()
    mock_sub_svc.create_subscription_record = AsyncMock(return_value=MagicMock())
    mock_add_credits = AsyncMock()

    patches = _common_patches(mock_tenant, mock_user, mock_sub_svc, mock_add_credits)
    body = _make_body()

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6], patches[7], patches[8], patches[9], patches[10], patches[11]:
        await register(body=body, request=_mock_request(), session=mock_session)

    kwargs = mock_sub_svc.create_subscription_record.call_args.kwargs
    today = date.today()
    assert kwargs["trial_start"] == today
    assert kwargs["trial_end"] == today + timedelta(days=14)
    assert kwargs["period_end"] == today + timedelta(days=14)


async def test_registration_seeds_trial_credits() -> None:
    """register: add_credits called with reason='trial_credit' and amount=Decimal('100')."""
    from financeops.api.v1.auth import register

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id

    mock_tenant = MagicMock()
    mock_tenant.id = tenant_id
    mock_tenant.display_name = "Test Co"
    mock_tenant.country = "US"

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_plan))
    )
    mock_session.flush = AsyncMock()

    mock_sub_svc = MagicMock()
    mock_sub_svc.create_subscription_record = AsyncMock(return_value=MagicMock())
    mock_add_credits = AsyncMock()

    patches = _common_patches(mock_tenant, mock_user, mock_sub_svc, mock_add_credits)
    body = _make_body()

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
         patches[6], patches[7], patches[8], patches[9], patches[10], patches[11]:
        await register(body=body, request=_mock_request(), session=mock_session)

    mock_add_credits.assert_awaited_once()
    ck = mock_add_credits.call_args
    assert ck.kwargs.get("amount") == Decimal("100")
    assert ck.kwargs.get("reason") == "trial_credit"
