from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.llm.fallback import AIResult as GatewayAIResult
from financeops.modules.fixed_assets.models import FaAsset
from financeops.modules.invoice_classifier.application.ai_classifier import classify_with_ai
from financeops.modules.invoice_classifier.application.classifier_service import (
    CONFIDENCE_THRESHOLD,
    ClassifierService,
)
from financeops.modules.invoice_classifier.application.rule_engine import (
    InvoiceInput,
    apply_rules,
)
from financeops.modules.invoice_classifier.models import ClassificationRule
from financeops.modules.prepaid_expenses.models import PrepaidSchedule
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_entity(async_session: AsyncSession, *, tenant_id: uuid.UUID, suffix: str) -> CpEntity:
    org = CpOrganisation(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash({"organisation_code": f"ORG_{suffix}"}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        organisation_code=f"ORG_{suffix}",
        organisation_name=f"Org {suffix}",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
    )
    async_session.add(org)
    await async_session.flush()

    entity = CpEntity(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash({"entity_code": f"ENT_{suffix}"}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        entity_code=f"ENT_{suffix}",
        entity_name=f"Entity {suffix}",
        organisation_id=org.id,
        group_id=None,
        base_currency="INR",
        country_code="IN",
        status="active",
    )
    async_session.add(entity)
    await async_session.flush()
    return entity


async def _create_scoped_finance_team_user(
    async_client,
    async_session: AsyncSession,
    owner_user: IamUser,
    *,
    entity_id: str,
) -> IamUser:
    scoped_user = IamUser(
        tenant_id=owner_user.tenant_id,
        email=f"scoped-inv-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Scoped Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(scoped_user)
    await async_session.flush()

    assign_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(owner_user),
        json={
            "user_id": str(scoped_user.id),
            "entity_id": entity_id,
            "effective_from": datetime.utcnow().isoformat(),
            "effective_to": None,
        },
    )
    assert assign_resp.status_code == 200
    return scoped_user


def _rule(
    *,
    tenant_id: uuid.UUID,
    rule_name: str,
    pattern_type: str,
    pattern_value: str,
    classification: str,
    confidence: Decimal,
    priority: int = 100,
) -> ClassificationRule:
    return ClassificationRule(
        tenant_id=tenant_id,
        rule_name=rule_name,
        description=None,
        pattern_type=pattern_type,
        pattern_value=pattern_value,
        amount_min=None,
        amount_max=None,
        classification=classification,
        confidence=confidence,
        priority=priority,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_rule_engine_vendor_name_match(test_user: IamUser) -> None:
    invoice = InvoiceInput(
        invoice_number="INV-1",
        vendor_name="ACME SOFTWARE PVT LTD",
        line_description="Annual license",
        invoice_amount=Decimal("5000.0000"),
    )
    rule = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="Vendor rule",
        pattern_type="VENDOR_NAME",
        pattern_value="acme software",
        classification="PREPAID_EXPENSE",
        confidence=Decimal("0.9500"),
    )
    result = apply_rules(invoice, [rule])
    assert result is not None
    assert result.classification == "PREPAID_EXPENSE"


@pytest.mark.asyncio
async def test_rule_engine_description_keyword_match(test_user: IamUser) -> None:
    invoice = InvoiceInput("INV-2", "Vendor", "purchase of laptop", Decimal("75000.0000"))
    rule = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="Keyword",
        pattern_type="DESCRIPTION_KEYWORD",
        pattern_value="laptop",
        classification="FIXED_ASSET",
        confidence=Decimal("0.9700"),
    )
    result = apply_rules(invoice, [rule])
    assert result is not None
    assert result.classification == "FIXED_ASSET"


@pytest.mark.asyncio
async def test_rule_engine_amount_range_match(test_user: IamUser) -> None:
    invoice = InvoiceInput("INV-3", "Vendor", "services", Decimal("1500.0000"))
    rule = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="Range",
        pattern_type="AMOUNT_RANGE",
        pattern_value="",
        classification="DIRECT_EXPENSE",
        confidence=Decimal("0.9000"),
    )
    rule.amount_min = Decimal("1000.0000")
    rule.amount_max = Decimal("2000.0000")
    result = apply_rules(invoice, [rule])
    assert result is not None
    assert result.classification == "DIRECT_EXPENSE"


@pytest.mark.asyncio
async def test_rule_engine_no_match_returns_none(test_user: IamUser) -> None:
    invoice = InvoiceInput("INV-4", "Unknown", "misc", Decimal("100.0000"))
    rule = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="No match",
        pattern_type="VENDOR_NAME",
        pattern_value="acme",
        classification="PREPAID_EXPENSE",
        confidence=Decimal("0.9000"),
    )
    assert apply_rules(invoice, [rule]) is None


@pytest.mark.asyncio
async def test_rule_engine_priority_order_respected(test_user: IamUser) -> None:
    invoice = InvoiceInput("INV-5", "Acme", "License", Decimal("1200.0000"))
    low_priority = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="Low",
        pattern_type="VENDOR_NAME",
        pattern_value="acme",
        classification="DIRECT_EXPENSE",
        confidence=Decimal("0.9000"),
        priority=200,
    )
    high_priority = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="High",
        pattern_type="VENDOR_NAME",
        pattern_value="acme",
        classification="PREPAID_EXPENSE",
        confidence=Decimal("0.9200"),
        priority=10,
    )
    result = apply_rules(invoice, [low_priority, high_priority])
    assert result is not None
    assert result.rule_matched == "High"


@pytest.mark.asyncio
async def test_rule_confidence_is_decimal_not_float(test_user: IamUser) -> None:
    invoice = InvoiceInput("INV-6", "Acme", "License", Decimal("1200.0000"))
    rule = _rule(
        tenant_id=test_user.tenant_id,
        rule_name="Confidence",
        pattern_type="VENDOR_NAME",
        pattern_value="acme",
        classification="PREPAID_EXPENSE",
        confidence=Decimal("0.9500"),
    )
    result = apply_rules(invoice, [rule])
    assert result is not None
    assert isinstance(result.confidence, Decimal)


@pytest.mark.asyncio
async def test_threshold_is_decimal() -> None:
    assert CONFIDENCE_THRESHOLD == Decimal("0.8500")
    assert isinstance(CONFIDENCE_THRESHOLD, Decimal)


@pytest.mark.asyncio
async def test_high_confidence_skips_human_review(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC01")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "High confidence",
            "pattern_type": "VENDOR_NAME",
            "pattern_value": "acme",
            "classification": "PREPAID_EXPENSE",
            "confidence": Decimal("0.9000"),
            "priority": 1,
        },
    )
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-7", "Acme Corp", "Annual license", Decimal("1000.0000")),
    )
    assert row.requires_human_review is False


@pytest.mark.asyncio
async def test_low_confidence_requires_review(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC02")

    async def _fake_ai(_invoice: InvoiceInput, _tenant_id: uuid.UUID):
        from financeops.modules.invoice_classifier.application.ai_classifier import AIResult

        return AIResult(
            classification="OPEX",
            confidence=Decimal("0.8400"),
            ai_reasoning="Low confidence",
        )

    monkeypatch.setattr(
        "financeops.modules.invoice_classifier.application.classifier_service.classify_with_ai",
        _fake_ai,
    )

    service = ClassifierService(async_session)
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-8", "Unknown", "unknown", Decimal("100.0000")),
    )
    assert row.requires_human_review is True


@pytest.mark.asyncio
async def test_boundary_exact_0_8500_no_review(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC03")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "Boundary",
            "pattern_type": "VENDOR_NAME",
            "pattern_value": "boundary vendor",
            "classification": "DIRECT_EXPENSE",
            "confidence": Decimal("0.8500"),
            "priority": 1,
        },
    )
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-9", "Boundary Vendor", "description", Decimal("500.0000")),
    )
    assert row.requires_human_review is False


@pytest.mark.asyncio
async def test_ai_classifier_called_when_no_rule_match(
    async_session: AsyncSession,
    test_user: IamUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC04")
    called = {"value": False}

    async def _fake_ai(_invoice: InvoiceInput, _tenant_id: uuid.UUID):
        from financeops.modules.invoice_classifier.application.ai_classifier import AIResult

        called["value"] = True
        return AIResult(
            classification="DIRECT_EXPENSE",
            confidence=Decimal("0.9100"),
            ai_reasoning="AI fallback",
        )

    monkeypatch.setattr(
        "financeops.modules.invoice_classifier.application.classifier_service.classify_with_ai",
        _fake_ai,
    )

    service = ClassifierService(async_session)
    await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-10", "No Rule Vendor", "none", Decimal("10.0000")),
    )
    assert called["value"] is True


@pytest.mark.asyncio
async def test_ai_confidence_converted_to_decimal(monkeypatch: pytest.MonkeyPatch, test_user: IamUser) -> None:
    async def _fake_gateway_generate(**_kwargs):
        return GatewayAIResult(
            content='{"classification":"PREPAID_EXPENSE","confidence":0.92,"reasoning":"match"}',
            model_used="test-model",
            provider="test-provider",
            was_fallback=False,
            attempt_number=1,
            duration_ms=1.0,
            tokens_used=10,
        )

    monkeypatch.setattr(
        "financeops.modules.invoice_classifier.application.ai_classifier.gateway_generate",
        _fake_gateway_generate,
    )

    result = await classify_with_ai(
        InvoiceInput("INV-11", "Vendor", "description", Decimal("10.0000")),
        test_user.tenant_id,
    )
    assert isinstance(result.confidence, Decimal)
    assert result.confidence == Decimal("0.9200")


@pytest.mark.asyncio
async def test_classify_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC05")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "create-record",
            "pattern_type": "VENDOR_NAME",
            "pattern_value": "acme",
            "classification": "PREPAID_EXPENSE",
            "confidence": Decimal("0.9500"),
            "priority": 1,
        },
    )
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-12", "Acme", "license", Decimal("300.0000")),
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_review_sets_human_fields(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC06")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "review",
            "pattern_type": "VENDOR_NAME",
            "pattern_value": "acme",
            "classification": "PREPAID_EXPENSE",
            "confidence": Decimal("0.6000"),
            "priority": 1,
        },
    )

    async def _fake_ai(_invoice: InvoiceInput, _tenant_id: uuid.UUID):
        from financeops.modules.invoice_classifier.application.ai_classifier import AIResult

        return AIResult("UNCERTAIN", Decimal("0.7000"), "uncertain")

    # Force low confidence classification.
    from financeops.modules.invoice_classifier.application import classifier_service as classifier_service_module

    original_ai = classifier_service_module.classify_with_ai
    classifier_service_module.classify_with_ai = _fake_ai
    try:
        row = await service.classify_invoice(
            test_user.tenant_id,
            entity.id,
            InvoiceInput("INV-13", "No Match", "something", Decimal("90.0000")),
        )
    finally:
        classifier_service_module.classify_with_ai = original_ai

    reviewed = await service.review_and_confirm(
        test_user.tenant_id,
        row.id,
        "PREPAID_EXPENSE",
        test_user.id,
    )
    assert reviewed.human_reviewed_at is not None
    assert reviewed.human_override == "PREPAID_EXPENSE"


@pytest.mark.asyncio
async def test_route_to_fa_creates_stub_asset(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC07")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "fa-route",
            "pattern_type": "DESCRIPTION_KEYWORD",
            "pattern_value": "laptop",
            "classification": "FIXED_ASSET",
            "confidence": Decimal("0.9700"),
            "priority": 1,
        },
    )
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-14", "Hardware Vendor", "Laptop purchase", Decimal("80000.0000")),
    )
    routed_id = await service.route_to_module(
        test_user.tenant_id,
        row.id,
        actor_user_id=test_user.id,
        actor_role=test_user.role.value,
    )
    asset = await async_session.get(FaAsset, routed_id)
    assert asset is not None


@pytest.mark.asyncio
async def test_route_to_prepaid_creates_stub_schedule(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC08")
    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "prepaid-route",
            "pattern_type": "DESCRIPTION_KEYWORD",
            "pattern_value": "annual subscription",
            "classification": "PREPAID_EXPENSE",
            "confidence": Decimal("0.9600"),
            "priority": 1,
        },
    )
    row = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-15", "SaaS Vendor", "Annual subscription plan", Decimal("12000.0000")),
    )
    routed_id = await service.route_to_module(
        test_user.tenant_id,
        row.id,
        actor_user_id=test_user.id,
        actor_role=test_user.role.value,
    )
    schedule = await async_session.get(PrepaidSchedule, routed_id)
    assert schedule is not None


@pytest.mark.asyncio
async def test_review_queue_returns_only_unreviewed(async_session: AsyncSession, test_user: IamUser, monkeypatch: pytest.MonkeyPatch) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC09")

    async def _fake_ai(_invoice: InvoiceInput, _tenant_id: uuid.UUID):
        from financeops.modules.invoice_classifier.application.ai_classifier import AIResult

        return AIResult("UNCERTAIN", Decimal("0.7000"), "needs review")

    monkeypatch.setattr(
        "financeops.modules.invoice_classifier.application.classifier_service.classify_with_ai",
        _fake_ai,
    )

    service = ClassifierService(async_session)
    one = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-16", "Vendor A", "desc", Decimal("10.0000")),
    )
    two = await service.classify_invoice(
        test_user.tenant_id,
        entity.id,
        InvoiceInput("INV-17", "Vendor B", "desc", Decimal("20.0000")),
    )
    await service.review_and_confirm(test_user.tenant_id, one.id, "DIRECT_EXPENSE", test_user.id)

    queue = await service.get_review_queue(test_user.tenant_id, entity.id, skip=0, limit=50)
    ids = {row.id for row in queue["items"]}
    assert two.id in ids
    assert one.id not in ids


@pytest.mark.asyncio
async def test_entity_isolation_invoice_classifier(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC10")
    entity_b = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="IC11")

    scoped_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=str(entity_b.id),
    )

    service = ClassifierService(async_session)
    await service.create_rule(
        test_user.tenant_id,
        {
            "rule_name": "isolation",
            "pattern_type": "VENDOR_NAME",
            "pattern_value": "acme",
            "classification": "PREPAID_EXPENSE",
            "confidence": Decimal("0.9600"),
            "priority": 1,
        },
    )
    await service.classify_invoice(
        test_user.tenant_id,
        entity_a.id,
        InvoiceInput("INV-18", "Acme", "desc", Decimal("300.0000")),
    )

    denied = await async_client.get(
        f"/api/v1/invoice-classifier?entity_id={entity_a.id}",
        headers=_auth_headers(scoped_user),
    )
    assert denied.status_code == 403
