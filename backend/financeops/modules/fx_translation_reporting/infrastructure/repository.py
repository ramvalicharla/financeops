from __future__ import annotations

import calendar
import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fx_rates import FxManualMonthlyRate, FxRateQuote
from financeops.db.models.fx_translation_reporting import (
    FxRateSelectionPolicy,
    FxTranslatedMetricResult,
    FxTranslatedVarianceResult,
    FxTranslationEvidenceLink,
    FxTranslationRun,
    FxTranslationRuleDefinition,
    ReportingCurrencyDefinition,
)
from financeops.db.models.multi_entity_consolidation import (
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationVarianceResult,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


class FxTranslationReportingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_reporting_currency_definition(self, **values: Any) -> ReportingCurrencyDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=ReportingCurrencyDefinition,
            tenant_id=values["tenant_id"],
            record_data={
                "reporting_currency_code": values["reporting_currency_code"],
                "reporting_scope_type": values["reporting_scope_type"],
                "reporting_scope_ref": values["reporting_scope_ref"],
            },
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="fx_translation.reporting_currency_definition.created",
                resource_type="reporting_currency_definition",
                resource_name=values["reporting_currency_code"],
            ),
        )

    async def list_reporting_currency_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
    ) -> list[ReportingCurrencyDefinition]:
        stmt = select(ReportingCurrencyDefinition).where(ReportingCurrencyDefinition.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(ReportingCurrencyDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                ReportingCurrencyDefinition.reporting_currency_code.asc(),
                ReportingCurrencyDefinition.effective_from.desc(),
                ReportingCurrencyDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_reporting_currency_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> ReportingCurrencyDefinition | None:
        result = await self._session.execute(
            select(ReportingCurrencyDefinition).where(
                ReportingCurrencyDefinition.tenant_id == tenant_id,
                ReportingCurrencyDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_reporting_currency_versions(
        self,
        *,
        tenant_id: uuid.UUID,
        definition_id: uuid.UUID,
    ) -> list[ReportingCurrencyDefinition]:
        current = await self.get_reporting_currency_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(ReportingCurrencyDefinition)
            .where(
                ReportingCurrencyDefinition.tenant_id == tenant_id,
                ReportingCurrencyDefinition.organisation_id == current.organisation_id,
                ReportingCurrencyDefinition.reporting_currency_code == current.reporting_currency_code,
                ReportingCurrencyDefinition.reporting_scope_type == current.reporting_scope_type,
                ReportingCurrencyDefinition.reporting_scope_ref == current.reporting_scope_ref,
            )
            .order_by(
                ReportingCurrencyDefinition.effective_from.desc(),
                ReportingCurrencyDefinition.created_at.desc(),
                ReportingCurrencyDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_reporting_currency_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        reporting_currency_code: str | None = None,
    ) -> list[ReportingCurrencyDefinition]:
        stmt = select(ReportingCurrencyDefinition).where(
            ReportingCurrencyDefinition.tenant_id == tenant_id,
            ReportingCurrencyDefinition.organisation_id == organisation_id,
            ReportingCurrencyDefinition.status == "active",
            ReportingCurrencyDefinition.effective_from <= reporting_period,
            or_(
                ReportingCurrencyDefinition.effective_to.is_(None),
                ReportingCurrencyDefinition.effective_to >= reporting_period,
            ),
        )
        if reporting_currency_code is not None:
            stmt = stmt.where(
                ReportingCurrencyDefinition.reporting_currency_code == reporting_currency_code.upper()
            )
        result = await self._session.execute(
            stmt.order_by(
                ReportingCurrencyDefinition.reporting_currency_code.asc(),
                ReportingCurrencyDefinition.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_translation_rule_definition(self, **values: Any) -> FxTranslationRuleDefinition:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=FxTranslationRuleDefinition,
            tenant_id=values["tenant_id"],
            record_data={"rule_code": values["rule_code"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="fx_translation.translation_rule_definition.created",
                resource_type="fx_translation_rule_definition",
                resource_name=values["rule_code"],
            ),
        )

    async def list_translation_rule_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
    ) -> list[FxTranslationRuleDefinition]:
        stmt = select(FxTranslationRuleDefinition).where(
            FxTranslationRuleDefinition.tenant_id == tenant_id
        )
        if organisation_id is not None:
            stmt = stmt.where(FxTranslationRuleDefinition.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                FxTranslationRuleDefinition.rule_code.asc(),
                FxTranslationRuleDefinition.effective_from.desc(),
                FxTranslationRuleDefinition.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_translation_rule_definition(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> FxTranslationRuleDefinition | None:
        result = await self._session.execute(
            select(FxTranslationRuleDefinition).where(
                FxTranslationRuleDefinition.tenant_id == tenant_id,
                FxTranslationRuleDefinition.id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_translation_rule_versions(
        self, *, tenant_id: uuid.UUID, definition_id: uuid.UUID
    ) -> list[FxTranslationRuleDefinition]:
        current = await self.get_translation_rule_definition(
            tenant_id=tenant_id, definition_id=definition_id
        )
        if current is None:
            return []
        result = await self._session.execute(
            select(FxTranslationRuleDefinition)
            .where(
                FxTranslationRuleDefinition.tenant_id == tenant_id,
                FxTranslationRuleDefinition.organisation_id == current.organisation_id,
                FxTranslationRuleDefinition.rule_code == current.rule_code,
            )
            .order_by(
                FxTranslationRuleDefinition.effective_from.desc(),
                FxTranslationRuleDefinition.created_at.desc(),
                FxTranslationRuleDefinition.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_translation_rule_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        reporting_currency_code: str | None = None,
    ) -> list[FxTranslationRuleDefinition]:
        stmt = select(FxTranslationRuleDefinition).where(
            FxTranslationRuleDefinition.tenant_id == tenant_id,
            FxTranslationRuleDefinition.organisation_id == organisation_id,
            FxTranslationRuleDefinition.status == "active",
            FxTranslationRuleDefinition.effective_from <= reporting_period,
            or_(
                FxTranslationRuleDefinition.effective_to.is_(None),
                FxTranslationRuleDefinition.effective_to >= reporting_period,
            ),
        )
        if reporting_currency_code is not None:
            stmt = stmt.where(
                FxTranslationRuleDefinition.target_reporting_currency_code
                == reporting_currency_code.upper()
            )
        result = await self._session.execute(
            stmt.order_by(FxTranslationRuleDefinition.rule_code.asc(), FxTranslationRuleDefinition.id.asc())
        )
        return list(result.scalars().all())

    async def create_rate_selection_policy(self, **values: Any) -> FxRateSelectionPolicy:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=FxRateSelectionPolicy,
            tenant_id=values["tenant_id"],
            record_data={"policy_code": values["policy_code"], "rate_type": values["rate_type"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="fx_translation.rate_selection_policy.created",
                resource_type="fx_rate_selection_policy",
                resource_name=values["policy_code"],
            ),
        )

    async def list_rate_selection_policies(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID | None = None,
    ) -> list[FxRateSelectionPolicy]:
        stmt = select(FxRateSelectionPolicy).where(FxRateSelectionPolicy.tenant_id == tenant_id)
        if organisation_id is not None:
            stmt = stmt.where(FxRateSelectionPolicy.organisation_id == organisation_id)
        result = await self._session.execute(
            stmt.order_by(
                FxRateSelectionPolicy.policy_code.asc(),
                FxRateSelectionPolicy.effective_from.desc(),
                FxRateSelectionPolicy.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def get_rate_selection_policy(
        self, *, tenant_id: uuid.UUID, policy_id: uuid.UUID
    ) -> FxRateSelectionPolicy | None:
        result = await self._session.execute(
            select(FxRateSelectionPolicy).where(
                FxRateSelectionPolicy.tenant_id == tenant_id,
                FxRateSelectionPolicy.id == policy_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_rate_selection_policy_versions(
        self, *, tenant_id: uuid.UUID, policy_id: uuid.UUID
    ) -> list[FxRateSelectionPolicy]:
        current = await self.get_rate_selection_policy(tenant_id=tenant_id, policy_id=policy_id)
        if current is None:
            return []
        result = await self._session.execute(
            select(FxRateSelectionPolicy)
            .where(
                FxRateSelectionPolicy.tenant_id == tenant_id,
                FxRateSelectionPolicy.organisation_id == current.organisation_id,
                FxRateSelectionPolicy.policy_code == current.policy_code,
            )
            .order_by(
                FxRateSelectionPolicy.effective_from.desc(),
                FxRateSelectionPolicy.created_at.desc(),
                FxRateSelectionPolicy.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def active_rate_selection_policies(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[FxRateSelectionPolicy]:
        result = await self._session.execute(
            select(FxRateSelectionPolicy)
            .where(
                FxRateSelectionPolicy.tenant_id == tenant_id,
                FxRateSelectionPolicy.organisation_id == organisation_id,
                FxRateSelectionPolicy.status == "active",
                FxRateSelectionPolicy.effective_from <= reporting_period,
                or_(
                    FxRateSelectionPolicy.effective_to.is_(None),
                    FxRateSelectionPolicy.effective_to >= reporting_period,
                ),
            )
            .order_by(FxRateSelectionPolicy.policy_code.asc(), FxRateSelectionPolicy.id.asc())
        )
        return list(result.scalars().all())

    async def create_run(self, **values: Any) -> FxTranslationRun:
        return await AuditWriter.insert_financial_record(
            self._session,
            model_class=FxTranslationRun,
            tenant_id=values["tenant_id"],
            record_data={"run_token": values["run_token"]},
            values=values,
            audit=AuditEvent(
                tenant_id=values["tenant_id"],
                user_id=values["created_by"],
                action="fx_translation.run.created",
                resource_type="fx_translation_run",
                resource_name=values["run_token"],
            ),
        )

    async def get_run_by_token(self, *, tenant_id: uuid.UUID, run_token: str) -> FxTranslationRun | None:
        result = await self._session.execute(
            select(FxTranslationRun).where(
                FxTranslationRun.tenant_id == tenant_id,
                FxTranslationRun.run_token == run_token,
            )
        )
        return result.scalar_one_or_none()

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> FxTranslationRun | None:
        result = await self._session.execute(
            select(FxTranslationRun).where(
                FxTranslationRun.tenant_id == tenant_id,
                FxTranslationRun.id == run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_source_metric_results_for_runs(
        self,
        *,
        tenant_id: uuid.UUID,
        run_ids: Iterable[uuid.UUID],
    ) -> list[MultiEntityConsolidationMetricResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MultiEntityConsolidationMetricResult)
            .where(
                MultiEntityConsolidationMetricResult.tenant_id == tenant_id,
                MultiEntityConsolidationMetricResult.run_id.in_(ids),
            )
            .order_by(
                MultiEntityConsolidationMetricResult.run_id.asc(),
                MultiEntityConsolidationMetricResult.line_no.asc(),
                MultiEntityConsolidationMetricResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def list_source_variance_results_for_runs(
        self,
        *,
        tenant_id: uuid.UUID,
        run_ids: Iterable[uuid.UUID],
    ) -> list[MultiEntityConsolidationVarianceResult]:
        ids = list(run_ids)
        if not ids:
            return []
        result = await self._session.execute(
            select(MultiEntityConsolidationVarianceResult)
            .where(
                MultiEntityConsolidationVarianceResult.tenant_id == tenant_id,
                MultiEntityConsolidationVarianceResult.run_id.in_(ids),
            )
            .order_by(
                MultiEntityConsolidationVarianceResult.run_id.asc(),
                MultiEntityConsolidationVarianceResult.line_no.asc(),
                MultiEntityConsolidationVarianceResult.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def create_translated_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[FxTranslatedMetricResult]:
        created: list[FxTranslatedMetricResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=FxTranslatedMetricResult,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "line_no": payload["line_no"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="fx_translation.metric_result.created",
                    resource_type="fx_translated_metric_result",
                    resource_name=payload["metric_code"],
                ),
            )
            created.append(row)
        return created

    async def create_translated_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[FxTranslatedVarianceResult]:
        created: list[FxTranslatedVarianceResult] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=FxTranslatedVarianceResult,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "line_no": payload["line_no"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="fx_translation.variance_result.created",
                    resource_type="fx_translated_variance_result",
                    resource_name=payload["metric_code"],
                ),
            )
            created.append(row)
        return created

    async def create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: Iterable[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> list[FxTranslationEvidenceLink]:
        created: list[FxTranslationEvidenceLink] = []
        for payload in rows:
            row = await AuditWriter.insert_financial_record(
                self._session,
                model_class=FxTranslationEvidenceLink,
                tenant_id=tenant_id,
                record_data={"run_id": str(run_id), "evidence_type": payload["evidence_type"]},
                values={**payload, "run_id": run_id, "created_by": created_by},
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=created_by,
                    action="fx_translation.evidence_link.created",
                    resource_type="fx_translation_evidence_link",
                    resource_name=payload["evidence_type"],
                ),
            )
            created.append(row)
        return created

    async def list_translated_metric_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[FxTranslatedMetricResult]:
        result = await self._session.execute(
            select(FxTranslatedMetricResult)
            .where(
                FxTranslatedMetricResult.tenant_id == tenant_id,
                FxTranslatedMetricResult.run_id == run_id,
            )
            .order_by(FxTranslatedMetricResult.line_no.asc(), FxTranslatedMetricResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_translated_variance_results(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[FxTranslatedVarianceResult]:
        result = await self._session.execute(
            select(FxTranslatedVarianceResult)
            .where(
                FxTranslatedVarianceResult.tenant_id == tenant_id,
                FxTranslatedVarianceResult.run_id == run_id,
            )
            .order_by(FxTranslatedVarianceResult.line_no.asc(), FxTranslatedVarianceResult.id.asc())
        )
        return list(result.scalars().all())

    async def list_evidence_links(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[FxTranslationEvidenceLink]:
        result = await self._session.execute(
            select(FxTranslationEvidenceLink)
            .where(
                FxTranslationEvidenceLink.tenant_id == tenant_id,
                FxTranslationEvidenceLink.run_id == run_id,
            )
            .order_by(FxTranslationEvidenceLink.created_at.asc(), FxTranslationEvidenceLink.id.asc())
        )
        return list(result.scalars().all())

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        metric_count = await self._session.scalar(
            select(func.count())
            .select_from(FxTranslatedMetricResult)
            .where(
                FxTranslatedMetricResult.tenant_id == tenant_id,
                FxTranslatedMetricResult.run_id == run_id,
            )
        )
        variance_count = await self._session.scalar(
            select(func.count())
            .select_from(FxTranslatedVarianceResult)
            .where(
                FxTranslatedVarianceResult.tenant_id == tenant_id,
                FxTranslatedVarianceResult.run_id == run_id,
            )
        )
        evidence_count = await self._session.scalar(
            select(func.count())
            .select_from(FxTranslationEvidenceLink)
            .where(
                FxTranslationEvidenceLink.tenant_id == tenant_id,
                FxTranslationEvidenceLink.run_id == run_id,
            )
        )
        return {
            "metric_count": int(metric_count or 0),
            "variance_count": int(variance_count or 0),
            "evidence_count": int(evidence_count or 0),
        }

    async def get_latest_locked_manual_rate(
        self,
        *,
        tenant_id: uuid.UUID,
        period_year: int,
        period_month: int,
        base_currency: str,
        quote_currency: str,
    ) -> FxManualMonthlyRate | None:
        result = await self._session.execute(
            select(FxManualMonthlyRate)
            .where(
                FxManualMonthlyRate.tenant_id == tenant_id,
                FxManualMonthlyRate.period_year == period_year,
                FxManualMonthlyRate.period_month == period_month,
                FxManualMonthlyRate.base_currency == base_currency,
                FxManualMonthlyRate.quote_currency == quote_currency,
                FxManualMonthlyRate.is_month_end_locked.is_(True),
            )
            .order_by(FxManualMonthlyRate.created_at.desc(), FxManualMonthlyRate.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_manual_rate(
        self,
        *,
        tenant_id: uuid.UUID,
        period_year: int,
        period_month: int,
        base_currency: str,
        quote_currency: str,
    ) -> FxManualMonthlyRate | None:
        result = await self._session.execute(
            select(FxManualMonthlyRate)
            .where(
                FxManualMonthlyRate.tenant_id == tenant_id,
                FxManualMonthlyRate.period_year == period_year,
                FxManualMonthlyRate.period_month == period_month,
                FxManualMonthlyRate.base_currency == base_currency,
                FxManualMonthlyRate.quote_currency == quote_currency,
            )
            .order_by(FxManualMonthlyRate.created_at.desc(), FxManualMonthlyRate.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_quote_on_or_before(
        self,
        *,
        tenant_id: uuid.UUID,
        base_currency: str,
        quote_currency: str,
        as_of_date: date,
    ) -> FxRateQuote | None:
        result = await self._session.execute(
            select(FxRateQuote)
            .where(
                FxRateQuote.tenant_id == tenant_id,
                FxRateQuote.base_currency == base_currency,
                FxRateQuote.quote_currency == quote_currency,
                FxRateQuote.rate_date <= as_of_date,
            )
            .order_by(FxRateQuote.rate_date.desc(), FxRateQuote.created_at.desc(), FxRateQuote.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_average_quote_for_month(
        self,
        *,
        tenant_id: uuid.UUID,
        period_year: int,
        period_month: int,
        base_currency: str,
        quote_currency: str,
    ) -> Decimal | None:
        last_day = calendar.monthrange(period_year, period_month)[1]
        start = date(period_year, period_month, 1)
        end = date(period_year, period_month, last_day)
        result = await self._session.scalar(
            select(func.avg(FxRateQuote.rate))
            .where(
                FxRateQuote.tenant_id == tenant_id,
                FxRateQuote.base_currency == base_currency,
                FxRateQuote.quote_currency == quote_currency,
                and_(FxRateQuote.rate_date >= start, FxRateQuote.rate_date <= end),
            )
        )
        return Decimal(str(result)) if result is not None else None

