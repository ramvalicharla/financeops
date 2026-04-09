from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor, IntentService
from financeops.modules.fixed_assets.models import FaAssetClass
from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService
from financeops.modules.invoice_classifier.application.ai_classifier import classify_with_ai
from financeops.modules.invoice_classifier.application.rule_engine import (
    CONFIDENCE_THRESHOLD,
    InvoiceInput,
    RuleResult,
    apply_rules,
)
from financeops.modules.invoice_classifier.models import ClassificationRule, InvoiceClassification
from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService

log = logging.getLogger(__name__)


class ClassifierService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._fa_service = FixedAssetService(session)
        self._prepaid_service = PrepaidService(session)

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(limit, 1000))

    async def _get_classification_or_404(
        self,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
    ) -> InvoiceClassification:
        row = (
            await self._session.execute(
                select(InvoiceClassification).where(
                    InvoiceClassification.id == classification_id,
                    InvoiceClassification.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Invoice classification not found")
        return row

    async def get_classification(
        self,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
    ) -> InvoiceClassification:
        return await self._get_classification_or_404(tenant_id, classification_id)

    async def classify_invoice(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        invoice_data: InvoiceInput,
    ) -> InvoiceClassification:
        rules = (
            await self._session.execute(
                select(ClassificationRule)
                .where(ClassificationRule.tenant_id == tenant_id, ClassificationRule.is_active.is_(True))
                .order_by(ClassificationRule.priority.asc(), ClassificationRule.created_at.asc())
            )
        ).scalars().all()

        chosen_rule: RuleResult | None = apply_rules(invoice_data, list(rules))
        classification = "UNCERTAIN"
        confidence = Decimal("0.0000")
        method = "AI_GATEWAY"
        rule_matched = None
        ai_reasoning = None

        if chosen_rule is not None and chosen_rule.confidence >= CONFIDENCE_THRESHOLD:
            classification = chosen_rule.classification
            confidence = Decimal(str(chosen_rule.confidence))
            method = chosen_rule.method
            rule_matched = chosen_rule.rule_matched
        else:
            ai_result = await classify_with_ai(invoice_data, tenant_id)
            classification = ai_result.classification
            confidence = Decimal(str(ai_result.confidence))
            method = ai_result.method
            ai_reasoning = ai_result.ai_reasoning
            if chosen_rule is not None:
                rule_matched = chosen_rule.rule_matched

        requires_review = confidence < CONFIDENCE_THRESHOLD

        row = InvoiceClassification(
            tenant_id=tenant_id,
            entity_id=entity_id,
            invoice_number=invoice_data.invoice_number,
            vendor_name=invoice_data.vendor_name or None,
            invoice_date=date.fromisoformat(invoice_data.invoice_date) if invoice_data.invoice_date else None,
            invoice_amount=Decimal(str(invoice_data.invoice_amount)),
            line_description=invoice_data.line_description or None,
            classification=classification,
            confidence=confidence,
            classification_method=method,
            rule_matched=rule_matched,
            ai_reasoning=ai_reasoning,
            requires_human_review=requires_review,
            routing_action="PENDING" if requires_review else None,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def review_and_confirm(
        self,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
        confirmed_classification: str,
        reviewed_by: uuid.UUID,
    ) -> InvoiceClassification:
        row = await self._get_classification_or_404(tenant_id, classification_id)
        confirmed = str(confirmed_classification).upper()
        row.human_override = confirmed
        row.human_reviewed_by = reviewed_by
        row.human_reviewed_at = datetime.now(UTC)
        row.requires_human_review = False

        if confirmed == "FIXED_ASSET":
            row.routing_action = "ROUTED_TO_FA"
        elif confirmed == "PREPAID_EXPENSE":
            row.routing_action = "ROUTED_TO_PREPAID"
        elif confirmed in {"DIRECT_EXPENSE", "OPEX", "CAPEX"}:
            row.routing_action = "ROUTED_TO_EXPENSE"
        else:
            row.routing_action = "PENDING"

        await self._session.flush()
        return row

    async def _ensure_default_asset_class(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> FaAssetClass | None:
        row = (
            await self._session.execute(
                select(FaAssetClass)
                .where(
                    FaAssetClass.tenant_id == tenant_id,
                    FaAssetClass.entity_id == entity_id,
                    FaAssetClass.is_active.is_(True),
                )
                .order_by(FaAssetClass.created_at.asc())
        )
        ).scalars().first()
        if row is not None:
            return row

        return None

    @staticmethod
    def _intent_idempotency_key(
        *,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
        intent_type: IntentType,
        payload: dict[str, Any],
    ) -> str:
        fingerprint = {
            "tenant_id": str(tenant_id),
            "classification_id": str(classification_id),
            "intent_type": intent_type.value,
            "payload": payload,
        }
        raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _submit_governed_route_intent(
        self,
        *,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_role: str,
        intent_type: IntentType,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        result = await IntentService(self._session).submit_intent(
            intent_type=intent_type,
            actor=IntentActor(
                user_id=actor_user_id,
                tenant_id=tenant_id,
                role=actor_role,
                source_channel=IntentSourceChannel.API.value,
            ),
            payload=payload,
            idempotency_key=self._intent_idempotency_key(
                tenant_id=tenant_id,
                classification_id=classification_id,
                intent_type=intent_type,
                payload=payload,
            ),
        )
        if not result.record_refs:
            raise ValidationError(
                f"{intent_type.value} completed without governed record references."
            )
        return result.record_refs

    async def route_to_module(
        self,
        tenant_id: uuid.UUID,
        classification_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        actor_role: str,
    ) -> uuid.UUID:
        row = await self._get_classification_or_404(tenant_id, classification_id)

        if row.requires_human_review and row.human_reviewed_at is None:
            raise ValidationError("Classification requires human review before routing")

        final_classification = (row.human_override or row.classification or "UNCERTAIN").upper()
        routed_record_id: uuid.UUID | None = None
        invoice_date = row.invoice_date or date.today()

        if final_classification == "FIXED_ASSET":
            asset_class = await self._ensure_default_asset_class(tenant_id, row.entity_id)
            if asset_class is None:
                asset_class_refs = await self._submit_governed_route_intent(
                    tenant_id=tenant_id,
                    classification_id=classification_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                intent_type=IntentType.CREATE_FIXED_ASSET_CLASS,
                payload={
                    "entity_id": str(row.entity_id),
                    "period_year": invoice_date.year,
                    "period_number": invoice_date.month,
                    "name": "Unclassified Asset",
                    "asset_type": "TANGIBLE",
                    "default_method": "SLM",
                    "default_useful_life_years": 5,
                    "default_residual_pct": "0.0500",
                        "is_active": True,
                    },
                )
                asset_class_id = asset_class_refs.get("asset_class_id")
                if asset_class_id in {None, ""}:
                    raise ValidationError(
                        "CREATE_FIXED_ASSET_CLASS intent did not return asset_class_id."
                    )
                asset_class = await self._session.get(FaAssetClass, uuid.UUID(str(asset_class_id)))
                if asset_class is None:
                    raise ValidationError("Governed asset class creation did not persist.")
            asset_refs = await self._submit_governed_route_intent(
                tenant_id=tenant_id,
                classification_id=classification_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                intent_type=IntentType.CREATE_FIXED_ASSET,
                payload={
                    "entity_id": str(row.entity_id),
                    "period_year": invoice_date.year,
                    "period_number": invoice_date.month,
                    "asset_class_id": str(asset_class.id),
                    "asset_code": f"INV-{row.invoice_number}",
                    "asset_name": row.line_description or row.vendor_name or f"Invoice {row.invoice_number}",
                    "description": row.line_description,
                    "location": None,
                    "serial_number": None,
                    "purchase_date": invoice_date.isoformat(),
                    "capitalisation_date": invoice_date.isoformat(),
                    "original_cost": str(Decimal(str(row.invoice_amount))),
                    "residual_value": "0",
                    "useful_life_years": "5",
                    "depreciation_method": "SLM",
                    "status": "UNDER_INSTALLATION",
                    "gaap_overrides": None,
                },
            )
            asset_id = asset_refs.get("asset_id")
            if asset_id in {None, ""}:
                raise ValidationError("CREATE_FIXED_ASSET intent did not return asset_id.")
            routed_record_id = uuid.UUID(str(asset_id))
            row.routing_action = "ROUTED_TO_FA"
        elif final_classification == "PREPAID_EXPENSE":
            schedule_refs = await self._submit_governed_route_intent(
                tenant_id=tenant_id,
                classification_id=classification_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                intent_type=IntentType.CREATE_PREPAID_SCHEDULE,
                payload={
                    "entity_id": str(row.entity_id),
                    "period_year": invoice_date.year,
                    "period_number": invoice_date.month,
                    "reference_number": f"INV-{row.invoice_number}",
                    "description": row.line_description or row.vendor_name or f"Invoice {row.invoice_number}",
                    "prepaid_type": "OTHER",
                    "vendor_name": row.vendor_name,
                    "invoice_number": row.invoice_number,
                    "total_amount": str(Decimal(str(row.invoice_amount))),
                    "coverage_start": invoice_date.isoformat(),
                    "coverage_end": (invoice_date + timedelta(days=30)).isoformat(),
                    "amortisation_method": "SLM",
                },
            )
            schedule_id = schedule_refs.get("schedule_id")
            if schedule_id in {None, ""}:
                raise ValidationError(
                    "CREATE_PREPAID_SCHEDULE intent did not return schedule_id."
                )
            routed_record_id = uuid.UUID(str(schedule_id))
            row.routing_action = "ROUTED_TO_PREPAID"
        else:
            row.routing_action = "ROUTED_TO_EXPENSE"

        row.routed_record_id = routed_record_id
        await self._session.flush()
        return routed_record_id or row.id

    async def get_review_queue(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        stmt = select(InvoiceClassification).where(
            InvoiceClassification.tenant_id == tenant_id,
            InvoiceClassification.entity_id == entity_id,
            InvoiceClassification.requires_human_review.is_(True),
            InvoiceClassification.human_reviewed_at.is_(None),
        )
        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
        rows = (
            await self._session.execute(
                stmt.order_by(InvoiceClassification.created_at.desc())
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def get_classifications(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        skip: int,
        limit: int,
        classification: str | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        effective_limit = self._limit(limit)
        stmt = select(InvoiceClassification).where(
            InvoiceClassification.tenant_id == tenant_id,
            InvoiceClassification.entity_id == entity_id,
        )
        if classification:
            stmt = stmt.where(InvoiceClassification.classification == classification)
        if method:
            stmt = stmt.where(InvoiceClassification.classification_method == method)

        total = int((await self._session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
        rows = (
            await self._session.execute(
                stmt.order_by(InvoiceClassification.created_at.desc())
                .offset(skip)
                .limit(effective_limit)
            )
        ).scalars().all()
        return {
            "items": list(rows),
            "total": total,
            "skip": skip,
            "limit": effective_limit,
            "has_more": (skip + len(rows)) < total,
        }

    async def create_rule(
        self,
        tenant_id: uuid.UUID,
        data: dict[str, Any],
    ) -> ClassificationRule:
        row = ClassificationRule(
            tenant_id=tenant_id,
            rule_name=str(data["rule_name"]),
            description=data.get("description"),
            pattern_type=str(data["pattern_type"]).upper(),
            pattern_value=str(data["pattern_value"]),
            amount_min=data.get("amount_min"),
            amount_max=data.get("amount_max"),
            classification=str(data["classification"]).upper(),
            confidence=Decimal(str(data["confidence"])),
            priority=int(data.get("priority", 100)),
            is_active=bool(data.get("is_active", True)),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_rules(self, tenant_id: uuid.UUID) -> list[ClassificationRule]:
        rows = (
            await self._session.execute(
                select(ClassificationRule)
                .where(ClassificationRule.tenant_id == tenant_id)
                .order_by(ClassificationRule.priority.asc(), ClassificationRule.created_at.asc())
            )
        ).scalars().all()
        return list(rows)

    async def update_rule(
        self,
        tenant_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: dict[str, Any],
    ) -> ClassificationRule:
        row = (
            await self._session.execute(
                select(ClassificationRule).where(
                    ClassificationRule.id == rule_id,
                    ClassificationRule.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Classification rule not found")

        for key in [
            "rule_name",
            "description",
            "pattern_type",
            "pattern_value",
            "amount_min",
            "amount_max",
            "classification",
            "confidence",
            "priority",
            "is_active",
        ]:
            if key in data:
                setattr(row, key, data[key])

        await self._session.flush()
        return row

    async def soft_delete_rule(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> ClassificationRule:
        row = await self.update_rule(tenant_id, rule_id, {"is_active": False})
        return row

    def learn_from_confirmation(
        self,
        rule: ClassificationRule | None,
        confirmed_classification: str,
        invoice: InvoiceInput,
    ) -> None:
        log.info(
            "invoice_classifier_learning_stub rule=%s classification=%s invoice_number=%s vendor=%s amount=%s",
            rule.rule_name if rule else None,
            confirmed_classification,
            invoice.invoice_number,
            invoice.vendor_name,
            invoice.invoice_amount,
        )


__all__ = ["ClassifierService", "CONFIDENCE_THRESHOLD"]
