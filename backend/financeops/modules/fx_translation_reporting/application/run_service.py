from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.fx_translation_reporting.application.rate_selection_service import (
    RateSelectionService,
)
from financeops.modules.fx_translation_reporting.application.validation_service import (
    ValidationService,
)
from financeops.modules.fx_translation_reporting.domain.enums import RunStatus
from financeops.modules.fx_translation_reporting.domain.invariants import q6
from financeops.modules.fx_translation_reporting.domain.value_objects import (
    DefinitionVersionTokenInput,
    FxTranslationRunTokenInput,
)
from financeops.modules.fx_translation_reporting.infrastructure.repository import (
    FxTranslationReportingRepository,
)
from financeops.modules.fx_translation_reporting.infrastructure.token_builder import (
    build_definition_version_token,
    build_fx_translation_run_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: FxTranslationReportingRepository,
        validation_service: ValidationService,
        rate_selection_service: RateSelectionService,
    ) -> None:
        self._repository = repository
        self._validation = validation_service
        self._rate_selection = rate_selection_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        reporting_currency_code: str,
        source_consolidation_run_refs: list[dict[str, Any]],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation.validate_source_run_refs(source_run_refs=source_consolidation_run_refs)
        normalized_reporting_currency = reporting_currency_code.upper()
        reporting_currency_rows = await self._repository.active_reporting_currency_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            reporting_currency_code=normalized_reporting_currency,
        )
        translation_rule_rows = await self._repository.active_translation_rule_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            reporting_currency_code=normalized_reporting_currency,
        )
        rate_policy_rows = await self._repository.active_rate_selection_policies(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_active_definition_sets(
            reporting_currency_rows=reporting_currency_rows,
            translation_rule_rows=translation_rule_rows,
            rate_policy_rows=rate_policy_rows,
            reporting_period=reporting_period,
        )

        reporting_currency_version_token = self._definition_token(
            rows=reporting_currency_rows,
            code_field="reporting_currency_code",
        )
        translation_rule_version_token = self._definition_token(
            rows=translation_rule_rows,
            code_field="rule_code",
        )
        rate_policy_version_token = self._definition_token(
            rows=rate_policy_rows,
            code_field="policy_code",
        )
        rate_source_version_token = "fx_rate_tables_v1"
        source_refs_sorted = sorted(
            [
                {
                    "source_type": str(row.get("source_type")),
                    "run_id": str(row.get("run_id")),
                }
                for row in source_consolidation_run_refs
            ],
            key=lambda row: (row["source_type"], row["run_id"]),
        )
        run_token = build_fx_translation_run_token(
            FxTranslationRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                reporting_currency_code=normalized_reporting_currency,
                reporting_currency_version_token=reporting_currency_version_token,
                translation_rule_version_token=translation_rule_version_token,
                rate_policy_version_token=rate_policy_version_token,
                rate_source_version_token=rate_source_version_token,
                source_consolidation_run_refs=source_refs_sorted,
                run_status=RunStatus.CREATED.value,
            )
        )

        existing = await self._repository.get_run_by_token(tenant_id=tenant_id, run_token=run_token)
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "status": existing.run_status,
                "idempotent": True,
            }

        row = await self._repository.create_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            reporting_currency_code=normalized_reporting_currency,
            reporting_currency_version_token=reporting_currency_version_token,
            translation_rule_version_token=translation_rule_version_token,
            rate_policy_version_token=rate_policy_version_token,
            rate_source_version_token=rate_source_version_token,
            source_consolidation_run_refs_json=source_refs_sorted,
            run_token=run_token,
            run_status=RunStatus.CREATED.value,
            validation_summary_json={
                "reporting_currency_definition_count": len(reporting_currency_rows),
                "translation_rule_count": len(translation_rule_rows),
                "rate_policy_count": len(rate_policy_rows),
            },
            created_by=created_by,
        )
        return {
            "run_id": str(row.id),
            "run_token": row.run_token,
            "status": row.run_status,
            "idempotent": False,
        }

    async def execute_run(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID, created_by: uuid.UUID
    ) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("FX translation run not found")

        existing_metrics = await self._repository.list_translated_metric_results(
            tenant_id=tenant_id, run_id=run_id
        )
        if existing_metrics:
            summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
            return {
                "run_id": str(run.id),
                "run_token": run.run_token,
                "status": run.run_status,
                "idempotent": True,
                **summary,
            }

        reporting_currency_rows, translation_rule_rows, rate_policy_rows = (
            await self._load_definition_snapshot_for_run(
                tenant_id=tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
                reporting_currency_code=run.reporting_currency_code,
                reporting_currency_version_token=run.reporting_currency_version_token,
                translation_rule_version_token=run.translation_rule_version_token,
                rate_policy_version_token=run.rate_policy_version_token,
            )
        )
        policy = self._select_primary_policy(rate_policy_rows=rate_policy_rows)
        rule = self._select_primary_rule(translation_rule_rows=translation_rule_rows)
        selected_policy = next(
            (row for row in rate_policy_rows if row.policy_code == rule.rate_policy_ref),
            policy,
        )

        source_run_ids = [
            uuid.UUID(str(row["run_id"]))
            for row in sorted(
                list(run.source_consolidation_run_refs_json),
                key=lambda item: (str(item.get("source_type", "")), str(item.get("run_id", ""))),
            )
        ]
        source_metric_rows = await self._repository.list_source_metric_results_for_runs(
            tenant_id=tenant_id,
            run_ids=source_run_ids,
        )
        source_variance_rows = await self._repository.list_source_variance_results_for_runs(
            tenant_id=tenant_id,
            run_ids=source_run_ids,
        )
        if not source_metric_rows and not source_variance_rows:
            raise ValueError("No source consolidation metric/variance rows found for run refs")

        metric_currency_by_code: dict[str, str] = {}
        for row in source_metric_rows:
            metric_currency_by_code.setdefault(row.metric_code, row.currency_code.upper())

        rate_cache: dict[str, dict[str, str | Decimal]] = {}

        translated_metric_payloads: list[dict[str, Any]] = []
        for line_no, row in enumerate(source_metric_rows, start=1):
            source_currency = row.currency_code.upper()
            selected_rate = await self._resolve_rate(
                tenant_id=tenant_id,
                reporting_period=run.reporting_period,
                source_currency=source_currency,
                reporting_currency=run.reporting_currency_code.upper(),
                policy=selected_policy,
                cache=rate_cache,
            )
            source_value = Decimal(str(row.aggregated_value))
            translated_metric_payloads.append(
                {
                    "line_no": line_no,
                    "source_metric_result_id": row.id,
                    "metric_code": row.metric_code,
                    "source_currency_code": source_currency,
                    "reporting_currency_code": run.reporting_currency_code.upper(),
                    "applied_rate_type": str(selected_rate["rate_type"]),
                    "applied_rate_ref": str(selected_rate["rate_ref"]),
                    "applied_rate_value": Decimal(str(selected_rate["multiplier"])),
                    "source_value": q6(source_value),
                    "translated_value": q6(source_value * Decimal(str(selected_rate["multiplier"]))),
                    "lineage_json": {
                        "source_metric_result_id": str(row.id),
                        "source_run_id": str(row.run_id),
                        "reporting_currency_version_token": reporting_currency_rows[0].version_token,
                        "translation_rule_version_token": rule.version_token,
                        "rate_policy_version_token": selected_policy.version_token,
                    },
                }
            )

        translated_variance_payloads: list[dict[str, Any]] = []
        for line_no, row in enumerate(source_variance_rows, start=1):
            source_currency = metric_currency_by_code.get(
                row.metric_code, run.reporting_currency_code.upper()
            )
            selected_rate = await self._resolve_rate(
                tenant_id=tenant_id,
                reporting_period=run.reporting_period,
                source_currency=source_currency,
                reporting_currency=run.reporting_currency_code.upper(),
                policy=selected_policy,
                cache=rate_cache,
            )
            multiplier = Decimal(str(selected_rate["multiplier"]))
            source_base_value = Decimal(str(row.base_value))
            source_current_value = Decimal(str(row.current_value))
            source_variance_value = Decimal(str(row.variance_value))
            translated_variance_payloads.append(
                {
                    "line_no": line_no,
                    "source_variance_result_id": row.id,
                    "metric_code": row.metric_code,
                    "comparison_type": row.comparison_type,
                    "source_currency_code": source_currency,
                    "reporting_currency_code": run.reporting_currency_code.upper(),
                    "applied_rate_type": str(selected_rate["rate_type"]),
                    "applied_rate_ref": str(selected_rate["rate_ref"]),
                    "applied_rate_value": multiplier,
                    "source_base_value": q6(source_base_value),
                    "source_current_value": q6(source_current_value),
                    "source_variance_value": q6(source_variance_value),
                    "translated_base_value": q6(source_base_value * multiplier),
                    "translated_current_value": q6(source_current_value * multiplier),
                    "translated_variance_value": q6(source_variance_value * multiplier),
                    "variance_pct": row.variance_pct,
                    "lineage_json": {
                        "source_variance_result_id": str(row.id),
                        "source_run_id": str(row.run_id),
                        "reporting_currency_version_token": reporting_currency_rows[0].version_token,
                        "translation_rule_version_token": rule.version_token,
                        "rate_policy_version_token": selected_policy.version_token,
                    },
                }
            )

        created_metrics = await self._repository.create_translated_metric_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=translated_metric_payloads,
            created_by=created_by,
        )
        created_variances = await self._repository.create_translated_variance_results(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=translated_variance_payloads,
            created_by=created_by,
        )

        evidence_rows: list[dict[str, Any]] = []
        for row in created_metrics:
            evidence_rows.append(
                {
                    "translated_metric_result_id": row.id,
                    "translated_variance_result_id": None,
                    "evidence_type": "source_result",
                    "evidence_ref": str(row.source_metric_result_id),
                    "evidence_label": f"Source metric result {row.metric_code}",
                    "evidence_payload_json": {
                        "source_currency_code": row.source_currency_code,
                        "reporting_currency_code": row.reporting_currency_code,
                        "applied_rate_ref": row.applied_rate_ref,
                    },
                }
            )
            evidence_rows.append(
                {
                    "translated_metric_result_id": row.id,
                    "translated_variance_result_id": None,
                    "evidence_type": "applied_rate",
                    "evidence_ref": row.applied_rate_ref,
                    "evidence_label": f"Applied rate for metric {row.metric_code}",
                    "evidence_payload_json": {
                        "applied_rate_type": row.applied_rate_type,
                        "applied_rate_value": str(row.applied_rate_value),
                    },
                }
            )
        for row in created_variances:
            evidence_rows.append(
                {
                    "translated_metric_result_id": None,
                    "translated_variance_result_id": row.id,
                    "evidence_type": "source_result",
                    "evidence_ref": str(row.source_variance_result_id),
                    "evidence_label": f"Source variance result {row.metric_code}",
                    "evidence_payload_json": {
                        "source_currency_code": row.source_currency_code,
                        "reporting_currency_code": row.reporting_currency_code,
                        "applied_rate_ref": row.applied_rate_ref,
                    },
                }
            )
            evidence_rows.append(
                {
                    "translated_metric_result_id": None,
                    "translated_variance_result_id": row.id,
                    "evidence_type": "applied_rate",
                    "evidence_ref": row.applied_rate_ref,
                    "evidence_label": f"Applied rate for variance {row.metric_code}",
                    "evidence_payload_json": {
                        "applied_rate_type": row.applied_rate_type,
                        "applied_rate_value": str(row.applied_rate_value),
                    },
                }
            )
        await self._repository.create_evidence_links(
            tenant_id=tenant_id,
            run_id=run_id,
            rows=evidence_rows,
            created_by=created_by,
        )
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "status": run.run_status,
            "idempotent": False,
            **summary,
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "reporting_period": row.reporting_period.isoformat(),
            "reporting_currency_code": row.reporting_currency_code,
            "reporting_currency_version_token": row.reporting_currency_version_token,
            "translation_rule_version_token": row.translation_rule_version_token,
            "rate_policy_version_token": row.rate_policy_version_token,
            "rate_source_version_token": row.rate_source_version_token,
            "source_consolidation_run_refs": list(row.source_consolidation_run_refs_json),
            "run_token": row.run_token,
            "run_status": row.run_status,
            "validation_summary_json": dict(row.validation_summary_json),
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        run = await self._repository.get_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("FX translation run not found")
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(run.id),
            "run_token": run.run_token,
            "run_status": run.run_status,
            **summary,
        }

    async def list_metrics(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_translated_metric_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "source_metric_result_id": str(row.source_metric_result_id),
                "metric_code": row.metric_code,
                "source_currency_code": row.source_currency_code,
                "reporting_currency_code": row.reporting_currency_code,
                "applied_rate_type": row.applied_rate_type,
                "applied_rate_ref": row.applied_rate_ref,
                "applied_rate_value": str(row.applied_rate_value),
                "source_value": str(row.source_value),
                "translated_value": str(row.translated_value),
                "lineage_json": dict(row.lineage_json),
            }
            for row in rows
        ]

    async def list_variances(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_translated_variance_results(
            tenant_id=tenant_id, run_id=run_id
        )
        return [
            {
                "id": str(row.id),
                "line_no": row.line_no,
                "source_variance_result_id": str(row.source_variance_result_id),
                "metric_code": row.metric_code,
                "comparison_type": row.comparison_type,
                "source_currency_code": row.source_currency_code,
                "reporting_currency_code": row.reporting_currency_code,
                "applied_rate_type": row.applied_rate_type,
                "applied_rate_ref": row.applied_rate_ref,
                "applied_rate_value": str(row.applied_rate_value),
                "source_base_value": str(row.source_base_value),
                "source_current_value": str(row.source_current_value),
                "source_variance_value": str(row.source_variance_value),
                "translated_base_value": str(row.translated_base_value),
                "translated_current_value": str(row.translated_current_value),
                "translated_variance_value": str(row.translated_variance_value),
                "variance_pct": None if row.variance_pct is None else str(row.variance_pct),
                "lineage_json": dict(row.lineage_json),
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "translated_metric_result_id": None
                if row.translated_metric_result_id is None
                else str(row.translated_metric_result_id),
                "translated_variance_result_id": None
                if row.translated_variance_result_id is None
                else str(row.translated_variance_result_id),
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "evidence_payload_json": dict(row.evidence_payload_json),
            }
            for row in rows
        ]

    async def _load_definition_snapshot_for_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        reporting_currency_code: str,
        reporting_currency_version_token: str,
        translation_rule_version_token: str,
        rate_policy_version_token: str,
    ) -> tuple[list[Any], list[Any], list[Any]]:
        reporting_currency_rows = await self._repository.active_reporting_currency_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            reporting_currency_code=reporting_currency_code,
        )
        translation_rule_rows = await self._repository.active_translation_rule_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            reporting_currency_code=reporting_currency_code,
        )
        rate_policy_rows = await self._repository.active_rate_selection_policies(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation.validate_active_definition_sets(
            reporting_currency_rows=reporting_currency_rows,
            translation_rule_rows=translation_rule_rows,
            rate_policy_rows=rate_policy_rows,
            reporting_period=reporting_period,
        )
        if (
            self._definition_token(
                rows=reporting_currency_rows, code_field="reporting_currency_code"
            )
            != reporting_currency_version_token
        ):
            raise ValueError("Reporting currency definition snapshot mismatch for run")
        if (
            self._definition_token(rows=translation_rule_rows, code_field="rule_code")
            != translation_rule_version_token
        ):
            raise ValueError("Translation rule definition snapshot mismatch for run")
        if (
            self._definition_token(rows=rate_policy_rows, code_field="policy_code")
            != rate_policy_version_token
        ):
            raise ValueError("Rate policy definition snapshot mismatch for run")
        return reporting_currency_rows, translation_rule_rows, rate_policy_rows

    async def _resolve_rate(
        self,
        *,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
        policy: Any,
        cache: dict[str, dict[str, str | Decimal]],
    ) -> dict[str, str | Decimal]:
        cache_key = f"{source_currency}:{reporting_currency}:{policy.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        selected = await self._rate_selection.resolve_selected_rate(
            repository=self._repository,
            tenant_id=tenant_id,
            source_currency=source_currency,
            reporting_currency=reporting_currency,
            reporting_period=reporting_period,
            rate_type=policy.rate_type,
            locked_rate_required=bool(policy.locked_rate_requirement_flag),
            fallback_behavior_json=dict(policy.fallback_behavior_json),
        )
        value = {
            "multiplier": selected.multiplier,
            "rate_type": selected.rate_type,
            "rate_ref": selected.rate_ref,
        }
        cache[cache_key] = value
        return value

    def _definition_token(self, *, rows: list[Any], code_field: str) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "id": str(row.id),
                        "code": str(getattr(row, code_field)),
                        "version_token": str(row.version_token),
                        "effective_from": row.effective_from.isoformat(),
                    }
                    for row in sorted(
                        rows,
                        key=lambda value: (str(getattr(value, code_field)), str(value.id)),
                    )
                ]
            )
        )

    def _select_primary_policy(self, *, rate_policy_rows: list[Any]) -> Any:
        return sorted(rate_policy_rows, key=lambda row: (row.policy_code, str(row.id)))[0]

    def _select_primary_rule(self, *, translation_rule_rows: list[Any]) -> Any:
        return sorted(translation_rule_rows, key=lambda row: (row.rule_code, str(row.id)))[0]

