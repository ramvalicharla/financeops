from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.financial_risk_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.financial_risk_engine.application.scoring_service import ScoringService
from financeops.modules.financial_risk_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.financial_risk_engine.domain.entities import (
    ComputedRisk,
    RiskRollforward,
    RiskSignal,
)
from financeops.modules.financial_risk_engine.domain.enums import (
    PersistenceState,
    RunStatus,
)
from financeops.modules.financial_risk_engine.domain.invariants import (
    SEVERITY_RANK,
    q6,
)
from financeops.modules.financial_risk_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
    RiskRunTokenInput,
)
from financeops.modules.financial_risk_engine.infrastructure.repository import (
    FinancialRiskRepository,
)
from financeops.modules.financial_risk_engine.infrastructure.token_builder import (
    build_definition_version_token,
    build_risk_run_token,
)


class RunService:
    def __init__(
        self,
        *,
        repository: FinancialRiskRepository,
        validation_service: ValidationService,
        scoring_service: ScoringService,
        materiality_service: MaterialityService,
    ) -> None:
        self._repository = repository
        self._validation_service = validation_service
        self._scoring_service = scoring_service
        self._materiality_service = materiality_service

    async def create_run(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
        source_metric_run_ids: list[uuid.UUID],
        source_variance_run_ids: list[uuid.UUID],
        source_trend_run_ids: list[uuid.UUID],
        source_reconciliation_session_ids: list[uuid.UUID],
        created_by: uuid.UUID,
    ) -> dict[str, Any]:
        self._validation_service.validate_run_inputs(
            source_metric_run_ids=source_metric_run_ids,
            source_variance_run_ids=source_variance_run_ids,
            source_trend_run_ids=source_trend_run_ids,
            source_reconciliation_session_ids=source_reconciliation_session_ids,
        )
        metric_runs = await self._repository.list_metric_runs(
            tenant_id=tenant_id,
            run_ids=sorted(
                set(source_metric_run_ids + source_variance_run_ids + source_trend_run_ids),
                key=lambda value: str(value),
            ),
        )
        metric_runs_by_id = {row.id: row for row in metric_runs}
        for run_id in source_metric_run_ids:
            run = metric_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed metric run: {run_id}")
        for run_id in source_variance_run_ids:
            run = metric_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed variance run: {run_id}")
        for run_id in source_trend_run_ids:
            run = metric_runs_by_id.get(run_id)
            if run is None or run.status != "completed":
                raise ValueError(f"Missing or non-completed trend run: {run_id}")

        sessions = await self._repository.list_reconciliation_sessions(
            tenant_id=tenant_id,
            session_ids=sorted(source_reconciliation_session_ids, key=lambda value: str(value)),
        )
        sessions_by_id = {row.id: row for row in sessions}
        for session_id in source_reconciliation_session_ids:
            if sessions_by_id.get(session_id) is None:
                raise ValueError(f"Missing reconciliation session: {session_id}")

        definitions = await self._repository.active_risk_definitions(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        weights = await self._repository.active_weight_configurations(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        materiality_rules = await self._repository.active_materiality_rules(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
        )
        self._validation_service.validate_definition_sets(
            definitions=definitions,
            weights=weights,
            materiality_rules=materiality_rules,
        )

        dependencies = await self._repository.list_dependencies(
            tenant_id=tenant_id,
            definition_ids=[row.id for row in definitions],
        )
        self._validation_service.validate_dependency_rows(dependency_rows=dependencies)

        risk_definition_version_token = self._definitions_version_token(definitions)
        propagation_version_token = self._dependencies_version_token(dependencies)
        weight_version_token = self._weights_version_token(weights)
        materiality_version_token = self._materiality_version_token(materiality_rules)

        run_token = build_risk_run_token(
            RiskRunTokenInput(
                tenant_id=tenant_id,
                organisation_id=organisation_id,
                reporting_period=reporting_period,
                risk_definition_version_token=risk_definition_version_token,
                propagation_version_token=propagation_version_token,
                weight_version_token=weight_version_token,
                materiality_version_token=materiality_version_token,
                source_metric_run_ids=[str(value) for value in source_metric_run_ids],
                source_variance_run_ids=[str(value) for value in source_variance_run_ids],
                source_trend_run_ids=[str(value) for value in source_trend_run_ids],
                source_reconciliation_session_ids=[
                    str(value) for value in source_reconciliation_session_ids
                ],
                status=RunStatus.CREATED.value,
            )
        )
        existing = await self._repository.get_risk_run_by_token(
            tenant_id=tenant_id,
            run_token=run_token,
        )
        if existing is not None:
            return {
                "run_id": str(existing.id),
                "run_token": existing.run_token,
                "status": existing.status,
                "idempotent": True,
            }

        created = await self._repository.create_risk_run(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            reporting_period=reporting_period,
            risk_definition_version_token=risk_definition_version_token,
            propagation_version_token=propagation_version_token,
            weight_version_token=weight_version_token,
            materiality_version_token=materiality_version_token,
            source_metric_run_ids_json=[str(value) for value in source_metric_run_ids],
            source_variance_run_ids_json=[str(value) for value in source_variance_run_ids],
            source_trend_run_ids_json=[str(value) for value in source_trend_run_ids],
            source_reconciliation_session_ids_json=[
                str(value) for value in source_reconciliation_session_ids
            ],
            run_token=run_token,
            status=RunStatus.CREATED.value,
            validation_summary_json={
                "definitions": len(definitions),
                "dependencies": len(dependencies),
                "weights": len(weights),
                "materiality_rules": len(materiality_rules),
            },
            created_by=created_by,
        )
        return {
            "run_id": str(created.id),
            "run_token": created.run_token,
            "status": created.status,
            "idempotent": False,
        }

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._repository.get_risk_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "reporting_period": row.reporting_period.isoformat(),
            "run_token": row.run_token,
            "status": row.status,
            "risk_definition_version_token": row.risk_definition_version_token,
            "propagation_version_token": row.propagation_version_token,
            "weight_version_token": row.weight_version_token,
            "materiality_version_token": row.materiality_version_token,
            "source_metric_run_ids": row.source_metric_run_ids_json,
            "source_variance_run_ids": row.source_variance_run_ids_json,
            "source_trend_run_ids": row.source_trend_run_ids_json,
            "source_reconciliation_session_ids": row.source_reconciliation_session_ids_json,
            "validation_summary_json": row.validation_summary_json,
            "created_at": row.created_at.isoformat(),
        }

    async def summary(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        row = await self._repository.get_risk_run(tenant_id=tenant_id, run_id=run_id)
        if row is None:
            raise ValueError("Risk run not found")
        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=run_id)
        return {
            "run_id": str(row.id),
            "run_token": row.run_token,
            "status": row.status,
            **summary,
        }

    async def list_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_risk_results(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "risk_code": row.risk_code,
                "risk_name": row.risk_name,
                "risk_domain": row.risk_domain,
                "risk_score": str(row.risk_score),
                "severity": row.severity,
                "confidence_score": str(row.confidence_score),
                "materiality_flag": bool(row.materiality_flag),
                "board_attention_flag": bool(row.board_attention_flag),
                "persistence_state": row.persistence_state,
                "unresolved_dependency_flag": bool(row.unresolved_dependency_flag),
                "source_summary_json": row.source_summary_json,
            }
            for row in rows
        ]

    async def list_signals(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_risk_signals(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "risk_result_id": str(row.risk_result_id),
                "signal_type": row.signal_type,
                "signal_ref": row.signal_ref,
                "contribution_weight": str(row.contribution_weight),
                "contribution_score": str(row.contribution_score),
                "signal_payload_json": row.signal_payload_json,
            }
            for row in rows
        ]

    async def list_rollforwards(
        self, *, tenant_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = await self._repository.list_rollforward_events(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "risk_result_id": str(row.risk_result_id),
                "event_type": row.event_type,
                "event_payload_json": row.event_payload_json,
                "actor_user_id": str(row.actor_user_id),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def list_evidence(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._repository.list_evidence_links(tenant_id=tenant_id, run_id=run_id)
        return [
            {
                "id": str(row.id),
                "risk_result_id": str(row.risk_result_id),
                "evidence_type": row.evidence_type,
                "evidence_ref": row.evidence_ref,
                "evidence_label": row.evidence_label,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def execute_run(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict[str, Any]:
        run = await self._repository.get_risk_run(tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("Risk run not found")

        completed = await self._ensure_status_row(
            tenant_id=tenant_id,
            run=run,
            status=RunStatus.COMPLETED,
            created_by=actor_user_id,
        )
        existing = await self._repository.list_risk_results(
            tenant_id=tenant_id,
            run_id=completed.id,
        )
        if existing:
            summary = await self._repository.summarize_run(
                tenant_id=tenant_id,
                run_id=completed.id,
            )
            return {
                "run_id": str(completed.id),
                "run_token": completed.run_token,
                "status": completed.status,
                "idempotent": True,
                **summary,
            }

        definitions = await self._repository.active_risk_definitions(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        weights = await self._repository.active_weight_configurations(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        materiality_rules = await self._repository.active_materiality_rules(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            reporting_period=completed.reporting_period,
        )
        self._validation_service.validate_definition_sets(
            definitions=definitions,
            weights=weights,
            materiality_rules=materiality_rules,
        )
        dependencies = await self._repository.list_dependencies(
            tenant_id=tenant_id,
            definition_ids=[row.id for row in definitions],
        )
        self._validation_service.validate_dependency_rows(dependency_rows=dependencies)

        if self._definitions_version_token(definitions) != completed.risk_definition_version_token:
            raise ValueError("Risk definition drift detected")
        if self._dependencies_version_token(dependencies) != completed.propagation_version_token:
            raise ValueError("Risk dependency drift detected")
        if self._weights_version_token(weights) != completed.weight_version_token:
            raise ValueError("Risk weight drift detected")
        if self._materiality_version_token(materiality_rules) != completed.materiality_version_token:
            raise ValueError("Risk materiality drift detected")

        metric_run_ids = [uuid.UUID(value) for value in completed.source_metric_run_ids_json]
        variance_run_ids = [uuid.UUID(value) for value in completed.source_variance_run_ids_json]
        trend_run_ids = [uuid.UUID(value) for value in completed.source_trend_run_ids_json]
        reconciliation_session_ids = [
            uuid.UUID(value) for value in completed.source_reconciliation_session_ids_json
        ]

        metric_rows = await self._repository.list_metric_results_for_runs(
            tenant_id=tenant_id,
            run_ids=metric_run_ids,
        )
        variance_rows = await self._repository.list_variance_results_for_runs(
            tenant_id=tenant_id,
            run_ids=variance_run_ids,
        )
        trend_rows = await self._repository.list_trend_results_for_runs(
            tenant_id=tenant_id,
            run_ids=trend_run_ids,
        )
        recon_exceptions = await self._repository.list_reconciliation_exceptions_for_sessions(
            tenant_id=tenant_id,
            session_ids=reconciliation_session_ids,
        )
        open_recon_count = len(
            [row for row in recon_exceptions if row.resolution_status == "open"]
        )

        metric_by_code: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in metric_rows:
            metric_by_code[row.metric_code] += Decimal(str(row.metric_value))
        variance_by_code: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in variance_rows:
            variance_by_code[row.metric_code] += abs(Decimal(str(row.variance_abs)))
        trend_by_code: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in trend_rows:
            trend_by_code[row.metric_code] += abs(Decimal(str(row.trend_value)))

        dependencies_by_definition: dict[uuid.UUID, list[Any]] = defaultdict(list)
        for row in dependencies:
            dependencies_by_definition[row.risk_definition_id].append(row)

        ordered = self._stable_topological_order(
            definitions=definitions,
            dependencies=dependencies,
        )
        materiality_rule_json = self._materiality_service.merged_rule_json(materiality_rules)

        computed_rows: list[ComputedRisk] = []
        signals_by_risk_code: dict[str, list[RiskSignal]] = {}
        rollforward_by_risk_code: dict[str, list[RiskRollforward]] = {}
        evidence_by_risk_code: dict[str, list[dict[str, Any]]] = {}
        computed_by_definition_id: dict[uuid.UUID, ComputedRisk] = {}

        prior_by_code = await self._repository.latest_prior_risk_results_by_codes(
            tenant_id=tenant_id,
            organisation_id=completed.organisation_id,
            risk_codes=[row.risk_code for row in ordered],
            before_reporting_period=completed.reporting_period,
        )

        for definition in ordered:
            selector = definition.signal_selector_json or {}
            metric_codes = sorted(set(selector.get("metric_codes", [])))
            variance_codes = sorted(set(selector.get("variance_codes", [])))
            trend_codes = sorted(set(selector.get("trend_codes", [])))
            include_reconciliation = bool(
                selector.get("include_reconciliation", False)
                or definition.risk_domain == "reconciliation_dependency"
            )

            weight_multiplier = self._scoring_service.base_weight_for_definition(
                risk_code=definition.risk_code,
                risk_domain=definition.risk_domain,
                rows=weights,
            )
            signal_rows: list[RiskSignal] = []
            score_parts: list[Decimal] = []

            for metric_code in metric_codes:
                contribution = self._scoring_service.metric_signal(
                    metric_by_code.get(metric_code, Decimal("0")),
                    weight=weight_multiplier,
                )
                score_parts.append(contribution)
                signal_rows.append(
                    RiskSignal(
                        signal_type="metric_result",
                        signal_ref=f"metric:{metric_code}",
                        contribution_weight=weight_multiplier,
                        contribution_score=contribution,
                        signal_payload_json={"metric_code": metric_code},
                    )
                )
            for metric_code in variance_codes:
                contribution = self._scoring_service.variance_signal(
                    variance_by_code.get(metric_code, Decimal("0")),
                    weight=weight_multiplier,
                )
                score_parts.append(contribution)
                signal_rows.append(
                    RiskSignal(
                        signal_type="variance_result",
                        signal_ref=f"variance:{metric_code}",
                        contribution_weight=weight_multiplier,
                        contribution_score=contribution,
                        signal_payload_json={"metric_code": metric_code},
                    )
                )
            for metric_code in trend_codes:
                contribution = self._scoring_service.trend_signal(
                    trend_by_code.get(metric_code, Decimal("0")),
                    weight=weight_multiplier,
                )
                score_parts.append(contribution)
                signal_rows.append(
                    RiskSignal(
                        signal_type="trend_result",
                        signal_ref=f"trend:{metric_code}",
                        contribution_weight=weight_multiplier,
                        contribution_score=contribution,
                        signal_payload_json={"metric_code": metric_code},
                    )
                )
            if include_reconciliation:
                recon_contribution = self._scoring_service.reconciliation_signal(
                    open_recon_count,
                    weight=weight_multiplier,
                )
                score_parts.append(recon_contribution)
                signal_rows.append(
                    RiskSignal(
                        signal_type="reconciliation_exception",
                        signal_ref=f"open:{open_recon_count}",
                        contribution_weight=weight_multiplier,
                        contribution_score=recon_contribution,
                        signal_payload_json={"open_exception_count": open_recon_count},
                    )
                )

            unresolved_dependency = False
            for dependency in sorted(
                dependencies_by_definition.get(definition.id, []),
                key=lambda row: (row.dependency_type, str(row.depends_on_risk_definition_id), str(row.id)),
            ):
                if dependency.dependency_type != "risk_result":
                    continue
                parent = computed_by_definition_id.get(dependency.depends_on_risk_definition_id)
                if parent is None:
                    unresolved_dependency = True
                    continue
                dep_score = self._scoring_service.dependency_signal(
                    parent_score=parent.risk_score,
                    propagation_factor=dependency.propagation_factor,
                    cap_limit=dependency.cap_limit,
                )
                score_parts.append(dep_score)
                signal_rows.append(
                    RiskSignal(
                        signal_type="parent_risk_result",
                        signal_ref=f"risk:{parent.risk_code}",
                        contribution_weight=q6(dependency.propagation_factor),
                        contribution_score=dep_score,
                        signal_payload_json={
                            "parent_risk_code": parent.risk_code,
                            "cap_limit": str(dependency.cap_limit),
                        },
                    )
                )

            risk_score = self._scoring_service.combine(score_parts)
            severity = self._materiality_service.severity_for_score(
                score=risk_score,
                rule_json=materiality_rule_json,
            )
            materiality_flag = self._materiality_service.materiality_flag(
                score=risk_score,
                rule_json=materiality_rule_json,
            )
            confidence_score = self._scoring_service.confidence(
                has_signals=bool(signal_rows),
                unresolved_dependency=unresolved_dependency,
                has_open_reconciliation=open_recon_count > 0,
            )

            board_override = any(
                row.board_critical_override
                for row in weights
                if row.risk_code in ("*", definition.risk_code)
            )
            board_attention_flag = self._scoring_service.board_attention(
                severity=severity.value,
                risk_domain=definition.risk_domain,
                board_override=board_override,
            )

            prior = prior_by_code.get(definition.risk_code)
            persistence = self._persistence_state(
                current_severity=severity.value,
                prior_severity=prior.severity if prior else None,
            )

            computed = ComputedRisk(
                risk_code=definition.risk_code,
                risk_name=definition.risk_name,
                risk_domain=definition.risk_domain,
                risk_score=risk_score,
                severity=severity,
                confidence_score=confidence_score,
                materiality_flag=materiality_flag,
                board_attention_flag=board_attention_flag,
                persistence_state=persistence,
                unresolved_dependency_flag=unresolved_dependency,
                source_summary_json={
                    "metric_codes": metric_codes,
                    "variance_codes": variance_codes,
                    "trend_codes": trend_codes,
                    "open_reconciliation_exceptions": open_recon_count,
                },
            )
            computed_rows.append(computed)
            computed_by_definition_id[definition.id] = computed
            signals_by_risk_code[definition.risk_code] = signal_rows
            rollforward_by_risk_code[definition.risk_code] = self._rollforward_events_for(
                persistence_state=persistence,
                confidence_score=confidence_score,
            )
            evidence_by_risk_code[definition.risk_code] = self._evidence_for_run_inputs(
                completed=completed,
                definition=definition,
            )

        inserted = await self._repository.insert_risk_results(
            tenant_id=tenant_id,
            run_id=completed.id,
            rows=computed_rows,
            created_by=actor_user_id,
        )
        by_code = {row.risk_code: row for row in inserted}
        for risk_code, row in by_code.items():
            await self._repository.insert_risk_signals(
                tenant_id=tenant_id,
                run_id=completed.id,
                risk_result_id=row.id,
                rows=signals_by_risk_code.get(risk_code, []),
                created_by=actor_user_id,
            )
            await self._repository.insert_rollforward_events(
                tenant_id=tenant_id,
                run_id=completed.id,
                risk_result_id=row.id,
                rows=rollforward_by_risk_code.get(risk_code, []),
                actor_user_id=actor_user_id,
                created_by=actor_user_id,
            )
            await self._repository.insert_evidence_links(
                tenant_id=tenant_id,
                run_id=completed.id,
                risk_result_id=row.id,
                rows=evidence_by_risk_code.get(risk_code, []),
                created_by=actor_user_id,
            )

        summary = await self._repository.summarize_run(tenant_id=tenant_id, run_id=completed.id)
        return {
            "run_id": str(completed.id),
            "run_token": completed.run_token,
            "status": completed.status,
            "idempotent": False,
            **summary,
        }

    def _definitions_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "risk_code": row.risk_code,
                        "risk_domain": row.risk_domain,
                        "version_token": row.version_token,
                    }
                    for row in sorted(rows, key=lambda item: (item.risk_code, item.id))
                ]
            )
        )

    def _dependencies_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "risk_definition_id": str(row.risk_definition_id),
                        "dependency_type": row.dependency_type,
                        "depends_on_risk_definition_id": (
                            str(row.depends_on_risk_definition_id)
                            if row.depends_on_risk_definition_id
                            else None
                        ),
                        "signal_reference_code": row.signal_reference_code,
                        "propagation_factor": str(row.propagation_factor),
                        "cap_limit": str(row.cap_limit),
                    }
                    for row in sorted(rows, key=lambda item: (item.risk_definition_id, item.id))
                ]
            )
        )

    def _weights_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "weight_code": row.weight_code,
                        "risk_code": row.risk_code,
                        "scope_type": row.scope_type,
                        "scope_value": row.scope_value,
                        "weight_value": str(row.weight_value),
                        "version_token": row.version_token,
                    }
                    for row in sorted(rows, key=lambda item: (item.weight_code, item.id))
                ]
            )
        )

    def _materiality_version_token(self, rows: list[Any]) -> str:
        return build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "rule_code": row.rule_code,
                        "version_token": row.version_token,
                    }
                    for row in sorted(rows, key=lambda item: (item.rule_code, item.id))
                ]
            )
        )

    def _run_token(self, *, run: Any, status: RunStatus) -> str:
        return build_risk_run_token(
            RiskRunTokenInput(
                tenant_id=run.tenant_id,
                organisation_id=run.organisation_id,
                reporting_period=run.reporting_period,
                risk_definition_version_token=run.risk_definition_version_token,
                propagation_version_token=run.propagation_version_token,
                weight_version_token=run.weight_version_token,
                materiality_version_token=run.materiality_version_token,
                source_metric_run_ids=list(run.source_metric_run_ids_json),
                source_variance_run_ids=list(run.source_variance_run_ids_json),
                source_trend_run_ids=list(run.source_trend_run_ids_json),
                source_reconciliation_session_ids=list(
                    run.source_reconciliation_session_ids_json
                ),
                status=status.value,
            )
        )

    async def _ensure_status_row(
        self,
        *,
        tenant_id: uuid.UUID,
        run: Any,
        status: RunStatus,
        created_by: uuid.UUID,
    ) -> Any:
        token = self._run_token(run=run, status=status)
        existing = await self._repository.get_risk_run_by_token(
            tenant_id=tenant_id,
            run_token=token,
        )
        if existing is not None:
            return existing
        return await self._repository.create_risk_run(
            tenant_id=tenant_id,
            organisation_id=run.organisation_id,
            reporting_period=run.reporting_period,
            risk_definition_version_token=run.risk_definition_version_token,
            propagation_version_token=run.propagation_version_token,
            weight_version_token=run.weight_version_token,
            materiality_version_token=run.materiality_version_token,
            source_metric_run_ids_json=list(run.source_metric_run_ids_json),
            source_variance_run_ids_json=list(run.source_variance_run_ids_json),
            source_trend_run_ids_json=list(run.source_trend_run_ids_json),
            source_reconciliation_session_ids_json=list(run.source_reconciliation_session_ids_json),
            run_token=token,
            status=status.value,
            validation_summary_json=run.validation_summary_json,
            created_by=created_by,
        )

    def _stable_topological_order(self, *, definitions: list[Any], dependencies: list[Any]) -> list[Any]:
        by_id = {row.id: row for row in definitions}
        children: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        indegree: dict[uuid.UUID, int] = {row.id: 0 for row in definitions}
        for row in dependencies:
            if row.dependency_type != "risk_result" or not row.depends_on_risk_definition_id:
                continue
            if row.depends_on_risk_definition_id not in by_id:
                continue
            children[row.depends_on_risk_definition_id].append(row.risk_definition_id)
            indegree[row.risk_definition_id] += 1

        queue = sorted(
            [row.id for row in definitions if indegree[row.id] == 0],
            key=lambda value: by_id[value].risk_code,
        )
        ordered_ids: list[uuid.UUID] = []
        while queue:
            current = queue.pop(0)
            ordered_ids.append(current)
            for child in sorted(children.get(current, []), key=lambda value: by_id[value].risk_code):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort(key=lambda value: by_id[value].risk_code)

        if len(ordered_ids) != len(definitions):
            raise ValueError("Risk dependency graph cycle detected during execution")
        return [by_id[row_id] for row_id in ordered_ids]

    def _persistence_state(
        self, *, current_severity: str, prior_severity: str | None
    ) -> PersistenceState:
        if prior_severity is None:
            return PersistenceState.NEW
        current_rank = SEVERITY_RANK.get(current_severity, 0)
        prior_rank = SEVERITY_RANK.get(prior_severity, 0)
        if prior_rank == 0 and current_rank > 0:
            return PersistenceState.REOPENED
        if current_rank == 0 and prior_rank > 0:
            return PersistenceState.RESOLVED
        if current_rank > prior_rank:
            return PersistenceState.ESCALATING
        if current_rank < prior_rank:
            return PersistenceState.DEESCALATING
        return PersistenceState.REPEATED

    def _rollforward_events_for(
        self,
        *,
        persistence_state: PersistenceState,
        confidence_score: Decimal,
    ) -> list[RiskRollforward]:
        mapping = {
            PersistenceState.NEW: "rolled_forward",
            PersistenceState.REPEATED: "rolled_forward",
            PersistenceState.ESCALATING: "escalated",
            PersistenceState.DEESCALATING: "deescalated",
            PersistenceState.RESOLVED: "resolved",
            PersistenceState.REOPENED: "reopened",
        }
        events = [
            RiskRollforward(
                event_type=mapping[persistence_state],
                event_payload_json={"persistence_state": persistence_state.value},
            )
        ]
        if q6(confidence_score) < Decimal("0.700000"):
            events.append(
                RiskRollforward(
                    event_type="confidence_degraded",
                    event_payload_json={"confidence_score": str(confidence_score)},
                )
            )
        else:
            events.append(
                RiskRollforward(
                    event_type="confidence_restored",
                    event_payload_json={"confidence_score": str(confidence_score)},
                )
            )
        return events

    def _evidence_for_run_inputs(self, *, completed: Any, definition: Any) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = [
            {
                "evidence_type": "definition_token",
                "evidence_ref": f"risk_definition_token:{completed.risk_definition_version_token}",
                "evidence_label": f"Definition {definition.risk_code}",
            },
            {
                "evidence_type": "definition_token",
                "evidence_ref": f"propagation_token:{completed.propagation_version_token}",
                "evidence_label": "Propagation rule set",
            },
            {
                "evidence_type": "definition_token",
                "evidence_ref": f"weight_token:{completed.weight_version_token}",
                "evidence_label": "Weight configuration set",
            },
            {
                "evidence_type": "definition_token",
                "evidence_ref": f"materiality_token:{completed.materiality_version_token}",
                "evidence_label": "Materiality rule set",
            },
        ]
        for value in completed.source_metric_run_ids_json:
            links.append(
                {
                    "evidence_type": "run_input",
                    "evidence_ref": f"metric_run:{value}",
                    "evidence_label": "Metric run input",
                }
            )
        for value in completed.source_variance_run_ids_json:
            links.append(
                {
                    "evidence_type": "run_input",
                    "evidence_ref": f"variance_run:{value}",
                    "evidence_label": "Variance run input",
                }
            )
        for value in completed.source_trend_run_ids_json:
            links.append(
                {
                    "evidence_type": "run_input",
                    "evidence_ref": f"trend_run:{value}",
                    "evidence_label": "Trend run input",
                }
            )
        for value in completed.source_reconciliation_session_ids_json:
            links.append(
                {
                    "evidence_type": "reconciliation_session",
                    "evidence_ref": f"reconciliation_session:{value}",
                    "evidence_label": "Reconciliation session input",
                }
            )
        return links
