from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.invoice_classifier.api.schemas import (
    ClassificationRuleCreateRequest,
    ClassificationRuleResponse,
    ClassificationRuleUpdateRequest,
    InvoiceClassificationResponse,
    InvoiceClassifyRequest,
    InvoiceReviewRequest,
    InvoiceRouteResponse,
)
from financeops.modules.invoice_classifier.application.classifier_service import ClassifierService
from financeops.modules.invoice_classifier.application.rule_engine import InvoiceInput
from financeops.platform.services.tenancy.entity_access import assert_entity_access
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/invoice-classifier", tags=["invoice-classifier"])


@router.post("/classify", response_model=InvoiceClassificationResponse)
async def classify_invoice(
    body: InvoiceClassifyRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> InvoiceClassificationResponse:
    await assert_entity_access(session, user.tenant_id, body.entity_id, user.id, user.role)
    service = ClassifierService(session)
    row = await service.classify_invoice(
        tenant_id=user.tenant_id,
        entity_id=body.entity_id,
        invoice_data=InvoiceInput(
            invoice_number=body.invoice_number,
            vendor_name=body.vendor_name,
            line_description=body.line_description,
            invoice_amount=body.invoice_amount,
            invoice_date=body.invoice_date.isoformat() if body.invoice_date else None,
        ),
    )
    return InvoiceClassificationResponse.model_validate(row, from_attributes=True)


@router.get("/queue", response_model=Paginated[InvoiceClassificationResponse])
async def get_review_queue(
    entity_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[InvoiceClassificationResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = ClassifierService(session)
    payload = await service.get_review_queue(user.tenant_id, entity_id, skip, limit)
    return Paginated[InvoiceClassificationResponse](
        items=[InvoiceClassificationResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.post("/{classification_id}/review", response_model=InvoiceClassificationResponse)
async def review_classification(
    classification_id: uuid.UUID,
    body: InvoiceReviewRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> InvoiceClassificationResponse:
    service = ClassifierService(session)
    row = await service.review_and_confirm(
        tenant_id=user.tenant_id,
        classification_id=classification_id,
        confirmed_classification=body.confirmed_classification,
        reviewed_by=user.id,
    )
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    return InvoiceClassificationResponse.model_validate(row, from_attributes=True)


@router.post("/{classification_id}/route", response_model=InvoiceRouteResponse)
async def route_classification(
    classification_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> InvoiceRouteResponse:
    service = ClassifierService(session)
    row = await service.get_classification(user.tenant_id, classification_id)
    await assert_entity_access(session, user.tenant_id, row.entity_id, user.id, user.role)
    routed_record_id = await service.route_to_module(
        user.tenant_id,
        classification_id,
        actor_user_id=user.id,
        actor_role=user.role.value,
    )
    refreshed = await service.get_classification(user.tenant_id, classification_id)
    return InvoiceRouteResponse(routed_record_id=routed_record_id, routing_action=str(refreshed.routing_action or "PENDING"))


@router.get("", response_model=Paginated[InvoiceClassificationResponse])
async def get_classifications(
    entity_id: uuid.UUID,
    classification: str | None = Query(default=None),
    method: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[InvoiceClassificationResponse]:
    await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
    service = ClassifierService(session)
    payload = await service.get_classifications(
        tenant_id=user.tenant_id,
        entity_id=entity_id,
        skip=skip,
        limit=limit,
        classification=classification,
        method=method,
    )
    return Paginated[InvoiceClassificationResponse](
        items=[InvoiceClassificationResponse.model_validate(item, from_attributes=True) for item in payload["items"]],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
    )


@router.get("/rules", response_model=list[ClassificationRuleResponse])
async def get_rules(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[ClassificationRuleResponse]:
    service = ClassifierService(session)
    rows = await service.list_rules(user.tenant_id)
    return [ClassificationRuleResponse.model_validate(item, from_attributes=True) for item in rows]


@router.post("/rules", response_model=ClassificationRuleResponse)
async def create_rule(
    body: ClassificationRuleCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ClassificationRuleResponse:
    service = ClassifierService(session)
    row = await service.create_rule(user.tenant_id, body.model_dump())
    return ClassificationRuleResponse.model_validate(row, from_attributes=True)


@router.patch("/rules/{rule_id}", response_model=ClassificationRuleResponse)
async def patch_rule(
    rule_id: uuid.UUID,
    body: ClassificationRuleUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ClassificationRuleResponse:
    service = ClassifierService(session)
    row = await service.update_rule(
        tenant_id=user.tenant_id,
        rule_id=rule_id,
        data=body.model_dump(exclude_unset=True),
    )
    return ClassificationRuleResponse.model_validate(row, from_attributes=True)


@router.delete("/rules/{rule_id}", response_model=ClassificationRuleResponse)
async def delete_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ClassificationRuleResponse:
    service = ClassifierService(session)
    row = await service.soft_delete_rule(user.tenant_id, rule_id)
    return ClassificationRuleResponse.model_validate(row, from_attributes=True)


__all__ = ["router"]
