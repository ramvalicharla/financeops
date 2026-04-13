from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from financeops.accounting_policy_engine import AccountingPolicyService, Policy
from financeops.modules.multi_entity_consolidation.application.adjustment_service import (
    AdjustmentService,
)
from financeops.modules.multi_entity_consolidation.application.aggregation_service import (
    AggregationService,
)
from financeops.modules.multi_entity_consolidation.application.hierarchy_service import (
    HierarchyService,
)
from financeops.modules.multi_entity_consolidation.application.intercompany_service import (
    IntercompanyService,
)
from financeops.modules.multi_entity_consolidation.application.run_service import (
    RunService,
)
from financeops.modules.multi_entity_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.services.consolidation.ic_matcher import (
    IntercompanyMatchDecision,
    IntercompanyToleranceConfig,
    MatchCandidateLine,
)


def _metric_row(
    *,
    row_id: uuid.UUID,
    metric_code: str,
    metric_value: str,
    entity_id: str | None,
    source_summary_json: dict | None = None,
    account_code: str | None = None,
) -> SimpleNamespace:
    dimension_json: dict[str, object] = {}
    if entity_id is not None:
        dimension_json["entity_id"] = entity_id
        dimension_json["legal_entity"] = entity_id
    if account_code is not None:
        dimension_json["account_code"] = account_code
    return SimpleNamespace(
        id=row_id,
        metric_code=metric_code,
        metric_value=Decimal(metric_value),
        dimension_json=dimension_json,
        source_summary_json=source_summary_json or {},
    )


class _FakeRepo:
    def __init__(
        self,
        *,
        run: SimpleNamespace,
        nodes: list[SimpleNamespace],
        metric_runs: list[SimpleNamespace],
        metric_rows: list[SimpleNamespace],
        variance_rows: list[SimpleNamespace] | None = None,
        intercompany_rules: list[SimpleNamespace] | None = None,
        adjustment_rows: list[SimpleNamespace] | None = None,
    ) -> None:
        self._session = object()
        self._run = run
        self._nodes = nodes
        self._metric_runs = metric_runs
        self._metric_rows = metric_rows
        self._variance_rows = variance_rows or []
        self._intercompany_rules = intercompany_rules or []
        self._adjustment_rows = adjustment_rows or []
        self.metric_results: list[SimpleNamespace] = []
        self.variance_results: list[SimpleNamespace] = []
        self.evidence_links: list[SimpleNamespace] = []

    async def get_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> SimpleNamespace | None:
        del tenant_id
        return self._run if self._run.id == run_id else None

    async def list_metric_results(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> list[SimpleNamespace]:
        del tenant_id, run_id
        return list(self.metric_results)

    async def summarize_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, int]:
        del tenant_id, run_id
        return {
            "metric_count": len(self.metric_results),
            "variance_count": len(self.variance_results),
            "evidence_count": len(self.evidence_links),
        }

    async def active_hierarchy_nodes(
        self, *, tenant_id: uuid.UUID, hierarchy_id: uuid.UUID
    ) -> list[SimpleNamespace]:
        del tenant_id, hierarchy_id
        return list(self._nodes)

    async def list_metric_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[SimpleNamespace]:
        del tenant_id
        return [row for row in self._metric_runs if row.id in set(run_ids)]

    async def list_metric_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[SimpleNamespace]:
        del tenant_id
        valid = set(run_ids)
        return [row for row in self._metric_rows if row.run_id in valid]

    async def list_variance_results_for_runs(
        self, *, tenant_id: uuid.UUID, run_ids: list[uuid.UUID]
    ) -> list[SimpleNamespace]:
        del tenant_id
        valid = set(run_ids)
        return [row for row in self._variance_rows if row.run_id in valid]

    async def create_metric_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict],
        created_by: uuid.UUID,
    ) -> list[SimpleNamespace]:
        del tenant_id, run_id, created_by
        created: list[SimpleNamespace] = []
        for payload in rows:
            row = SimpleNamespace(id=uuid.uuid4(), **payload)
            created.append(row)
        self.metric_results.extend(created)
        return created

    async def create_variance_results(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict],
        created_by: uuid.UUID,
    ) -> list[SimpleNamespace]:
        del tenant_id, run_id, created_by
        created: list[SimpleNamespace] = []
        for payload in rows:
            row = SimpleNamespace(id=uuid.uuid4(), **payload)
            created.append(row)
        self.variance_results.extend(created)
        return created

    async def create_evidence_links(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        rows: list[dict],
        created_by: uuid.UUID,
    ) -> list[SimpleNamespace]:
        del tenant_id, run_id, created_by
        created: list[SimpleNamespace] = []
        for payload in rows:
            row = SimpleNamespace(id=uuid.uuid4(), **payload)
            created.append(row)
        self.evidence_links.extend(created)
        return created

    async def active_intercompany_rules(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[SimpleNamespace]:
        del tenant_id, organisation_id, reporting_period
        return list(self._intercompany_rules)

    async def active_adjustment_definitions(
        self,
        *,
        tenant_id: uuid.UUID,
        organisation_id: uuid.UUID,
        reporting_period: date,
    ) -> list[SimpleNamespace]:
        del tenant_id, organisation_id, reporting_period
        return list(self._adjustment_rows)


class _FakeOwnershipRepo:
    def __init__(self, session: object, *, structures: list[SimpleNamespace], relationships: list[SimpleNamespace]) -> None:
        del session
        self._structures = structures
        self._relationships = relationships

    async def active_structure_definitions(
        self, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, reporting_period: date
    ) -> list[SimpleNamespace]:
        del tenant_id, organisation_id, reporting_period
        return list(self._structures)

    async def active_relationships(
        self,
        *,
        tenant_id: uuid.UUID,
        ownership_structure_id: uuid.UUID,
        reporting_period: date,
    ) -> list[SimpleNamespace]:
        del tenant_id, ownership_structure_id, reporting_period
        return list(self._relationships)


class _TupleResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarRows:
        return _ScalarRows(self._rows)


class _RunProcessingSession:
    def __init__(self, *, execute_results: list[object], scalar_results: list[int]) -> None:
        self._execute_results = list(execute_results)
        self._scalar_results = list(scalar_results)

    async def scalar(self, *_: object, **__: object) -> int:
        return self._scalar_results.pop(0)

    async def execute(self, *_: object, **__: object) -> object:
        return self._execute_results.pop(0)


def test_intercompany_service_wrapper_calls_legacy_matcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    candidate = MatchCandidateLine(
        snapshot_line_id=uuid.uuid4(),
        entity_id=entity_a,
        account_code="4000",
        local_amount=Decimal("100.000000"),
        expected_rate=Decimal("1.000000"),
        parent_amount=Decimal("100.000000"),
        ic_reference="IC-REF-1",
        ic_counterparty_entity=entity_b,
        transaction_date=date(2026, 1, 31),
        ic_account_class="IC_REVENUE",
    )
    tolerance = IntercompanyToleranceConfig(
        amount_tolerance_parent=Decimal("0.010000"),
        fx_explained_tolerance_parent=Decimal("0.500000"),
        timing_tolerance_days=3,
    )
    match_calls: list[tuple[list[MatchCandidateLine], IntercompanyToleranceConfig]] = []
    elimination_calls: list[dict[str, object]] = []
    decision = IntercompanyMatchDecision(
        match_key_hash="match-1",
        entity_from=entity_a,
        entity_to=entity_b,
        account_code="4000",
        ic_reference="IC-REF-1",
        amount_local_from=Decimal("100.000000"),
        amount_local_to=Decimal("-100.000000"),
        amount_parent_from=Decimal("100.000000"),
        amount_parent_to=Decimal("-100.000000"),
        expected_difference=Decimal("0.000000"),
        actual_difference=Decimal("0.000000"),
        fx_explained=Decimal("0.000000"),
        unexplained_difference=Decimal("0.000000"),
        classification="matched",
        transaction_date_from=date(2026, 1, 31),
        transaction_date_to=date(2026, 1, 31),
    )

    def _fake_match_intercompany_lines(
        *, lines: list[MatchCandidateLine], tolerance: IntercompanyToleranceConfig
    ) -> list[IntercompanyMatchDecision]:
        match_calls.append((lines, tolerance))
        return [decision]

    def _fake_build_elimination_decisions(*, pair_ids: dict[str, uuid.UUID], pairs: list[object]) -> list[SimpleNamespace]:
        elimination_calls.append({"pair_ids": pair_ids, "pairs": pairs})
        return [
            SimpleNamespace(
                intercompany_pair_id=pair_ids["match-1"],
                entity_from=entity_a,
                entity_to=entity_b,
                account_code="4000",
                classification_at_time="matched",
                elimination_status="applied",
                eliminated_amount_parent=Decimal("0.000000"),
                fx_component_impact_parent=Decimal("0.000000"),
                residual_difference_parent=Decimal("0.000000"),
                rule_code="ELIM.APPLY.MATCHED",
                reason="Applied elimination per deterministic IC classification",
            )
        ]

    monkeypatch.setattr(
        "financeops.modules.multi_entity_consolidation.application.intercompany_service.match_intercompany_lines",
        _fake_match_intercompany_lines,
    )
    monkeypatch.setattr(
        "financeops.modules.multi_entity_consolidation.application.intercompany_service.build_elimination_decisions",
        _fake_build_elimination_decisions,
    )

    summary = IntercompanyService().match_candidates(candidates=[candidate], tolerance=tolerance)

    assert len(match_calls) == 1
    assert len(elimination_calls) == 1
    assert set(summary) >= {
        "matched_pairs",
        "unmatched_items",
        "elimination_entries",
        "validation_report",
    }


def test_intercompany_service_no_data_passes_with_empty_contract() -> None:
    summary = IntercompanyService().classify_source_refs(
        source_run_refs=[{"source_type": "metric_run", "run_id": str(uuid.uuid4())}],
        metric_rows=[
            _metric_row(
                row_id=uuid.uuid4(),
                metric_code="revenue",
                metric_value="250.000000",
                entity_id=str(uuid.uuid4()),
                account_code="4000",
                source_summary_json={},
            )
        ],
        intercompany_rules=[],
    )

    assert summary["validation_report"] == {
        "status": "PASS",
        "reason": "no intercompany transactions",
    }
    assert summary["matched_pairs"] == []
    assert summary["unmatched_items"] == []
    assert summary["elimination_entries"] == []


def test_intercompany_service_produces_non_empty_results() -> None:
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    service = IntercompanyService()
    metric_rows = [
        _metric_row(
            row_id=uuid.uuid4(),
            metric_code="ic_sales",
            metric_value="100.000000",
            entity_id=str(entity_a),
            account_code="4000",
            source_summary_json={
                "ic_reference": "IC-REF-1",
                "ic_counterparty_entity": str(entity_b),
                "ic_account_class": "IC_REVENUE",
                "local_amount": "100.000000",
                "parent_amount": "100.000000",
                "expected_rate": "1.000000",
            },
        ),
        _metric_row(
            row_id=uuid.uuid4(),
            metric_code="ic_sales",
            metric_value="-100.000000",
            entity_id=str(entity_b),
            account_code="4000",
            source_summary_json={
                "ic_reference": "IC-REF-1",
                "ic_counterparty_entity": str(entity_a),
                "ic_account_class": "IC_EXPENSE",
                "local_amount": "-100.000000",
                "parent_amount": "-100.000000",
                "expected_rate": "1.000000",
            },
        ),
    ]
    rules = [SimpleNamespace(id=uuid.uuid4(), rule_code="IC_STD", treatment_rule_json={})]

    summary = service.classify_source_refs(
        source_run_refs=[{"source_type": "metric_run", "run_id": str(uuid.uuid4())}],
        metric_rows=metric_rows,
        intercompany_rules=rules,
    )

    assert summary["validation_report"]["status"] == "PASS"
    assert len(summary["matched_pairs"]) == 1
    assert len(summary["elimination_entries"]) == 1


def test_adjustment_service_produces_entries() -> None:
    service = AdjustmentService()
    adjustment_rows = [
        SimpleNamespace(id=uuid.uuid4(), adjustment_code="ADJ_IC", adjustment_type="analytic_adjustment"),
        SimpleNamespace(id=uuid.uuid4(), adjustment_code="RECLASS_IC", adjustment_type="presentation_reclass"),
    ]

    summary = service.summarize_adjustments(
        intercompany_summary={
            "unmatched_items": [
                {
                    "classification": "unexplained",
                    "entity_from": str(uuid.uuid4()),
                    "entity_to": str(uuid.uuid4()),
                    "account_code": "4000",
                    "unexplained_difference": "25.000000",
                    "transaction_reference": "IC-UNMATCHED-1",
                },
                {
                    "classification": "timing_difference",
                    "entity_from": str(uuid.uuid4()),
                    "entity_to": str(uuid.uuid4()),
                    "account_code": "4100",
                    "residual_difference_parent": "12.500000",
                    "transaction_reference": "IC-TIMING-1",
                },
            ]
        },
        adjustment_rows=adjustment_rows,
    )

    assert summary["validation_report"]["status"] == "PASS"
    assert len(summary["adjustment_entries"]) == 1
    assert len(summary["reclassification_entries"]) == 1


@pytest.mark.asyncio
async def test_execute_run_cross_check_produces_eliminations_and_minority_interest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.application import run_service as run_service_module
    from financeops.platform.services.control_plane import phase4_service as phase4_service_module

    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    hierarchy_id = uuid.uuid4()
    run_id = uuid.uuid4()
    metric_run_id = uuid.uuid4()
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    entity_c = uuid.uuid4()

    run = SimpleNamespace(
        id=run_id,
        run_token="run-token",
        run_status="created",
        hierarchy_id=hierarchy_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_run_refs_json=[{"source_type": "metric_run", "run_id": str(metric_run_id)}],
    )
    nodes = [
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_a, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_b, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_c, parent_node_id=None, node_level=0),
    ]
    metric_rows = [
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="100.000000",
                entity_id=str(entity_a),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_b),
                    "ic_account_class": "IC_REVENUE",
                    "local_amount": "100.000000",
                    "parent_amount": "100.000000",
                    "expected_rate": "1.000000",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="-100.000000",
                entity_id=str(entity_b),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_a),
                    "ic_account_class": "IC_EXPENSE",
                    "local_amount": "-100.000000",
                    "parent_amount": "-100.000000",
                    "expected_rate": "1.000000",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="nci_balance",
                metric_value="100.000000",
                entity_id=str(entity_c),
                source_summary_json={"nci_balance": "100.000000"},
            ).__dict__,
        ),
    ]
    repo = _FakeRepo(
        run=run,
        nodes=nodes,
        metric_runs=[SimpleNamespace(id=metric_run_id)],
        metric_rows=metric_rows,
        intercompany_rules=[SimpleNamespace(id=uuid.uuid4(), rule_code="IC_STD", treatment_rule_json={})],
        adjustment_rows=[SimpleNamespace(id=uuid.uuid4(), adjustment_code="ADJ_IC", adjustment_type="analytic_adjustment")],
    )

    structures = [SimpleNamespace(id=uuid.uuid4(), ownership_structure_code="GROUP_MAIN")]
    relationships = [
        SimpleNamespace(
            id=uuid.uuid4(),
            child_entity_id=entity_c,
            ownership_percentage=Decimal("80.000000"),
            minority_interest_indicator=True,
        )
    ]

    monkeypatch.setattr(
        run_service_module,
        "OwnershipConsolidationRepository",
        lambda session: _FakeOwnershipRepo(session, structures=structures, relationships=relationships),
    )

    class _SnapshotService:
        def __init__(self, session: object) -> None:
            del session

        async def ensure_snapshot_for_subject(self, **_: object) -> None:
            return None

    monkeypatch.setattr(phase4_service_module, "Phase4ControlPlaneService", _SnapshotService)

    service = RunService(
        repository=repo,
        validation_service=ValidationService(),
        hierarchy_service=HierarchyService(),
        aggregation_service=AggregationService(),
        intercompany_service=IntercompanyService(),
        adjustment_service=AdjustmentService(),
    )

    result = await service.execute_run(tenant_id=tenant_id, run_id=run_id, created_by=uuid.uuid4())

    assert result["elimination_entry_count"] > 0
    assert result["minority_interest_total"] == "20.000000"
    assert result["validation_report"]["status"] == "PASS"
    assert any(
        row.evidence_ref == "minority-interest:summary" for row in repo.evidence_links
    )


@pytest.mark.asyncio
async def test_execute_run_applies_accounting_policies_deterministically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.application import run_service as run_service_module
    from financeops.platform.services.control_plane import phase4_service as phase4_service_module

    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    hierarchy_id = uuid.uuid4()
    run_id = uuid.uuid4()
    metric_run_id = uuid.uuid4()
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    entity_c = uuid.uuid4()

    run = SimpleNamespace(
        id=run_id,
        run_token="run-token",
        run_status="created",
        hierarchy_id=hierarchy_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_run_refs_json=[{"source_type": "metric_run", "run_id": str(metric_run_id)}],
    )
    nodes = [
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_a, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_b, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_c, parent_node_id=None, node_level=0),
    ]
    metric_rows = [
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="100.000000",
                entity_id=str(entity_a),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_b),
                    "ic_account_class": "IC_REVENUE",
                    "local_amount": "100.000000",
                    "parent_amount": "100.000000",
                    "expected_rate": "1.000000",
                    "currency_code": "USD",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="-100.000000",
                entity_id=str(entity_b),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_a),
                    "ic_account_class": "IC_EXPENSE",
                    "local_amount": "-100.000000",
                    "parent_amount": "-100.000000",
                    "expected_rate": "1.000000",
                    "currency_code": "USD",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="revenue",
                metric_value="250.000000",
                entity_id=str(entity_a),
                account_code="4100",
                source_summary_json={"currency_code": "USD"},
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="nci_balance",
                metric_value="100.000000",
                entity_id=str(entity_c),
                source_summary_json={"nci_balance": "100.000000", "currency_code": "USD"},
            ).__dict__,
        ),
    ]
    repo = _FakeRepo(
        run=run,
        nodes=nodes,
        metric_runs=[SimpleNamespace(id=metric_run_id)],
        metric_rows=metric_rows,
        intercompany_rules=[SimpleNamespace(id=uuid.uuid4(), rule_code="IC_STD", treatment_rule_json={})],
        adjustment_rows=[SimpleNamespace(id=uuid.uuid4(), adjustment_code="ADJ_IC", adjustment_type="analytic_adjustment")],
    )

    structures = [SimpleNamespace(id=uuid.uuid4(), ownership_structure_code="GROUP_MAIN")]
    relationships = [
        SimpleNamespace(
            id=uuid.uuid4(),
            child_entity_id=entity_c,
            ownership_percentage=Decimal("80.000000"),
            minority_interest_indicator=True,
        )
    ]

    monkeypatch.setattr(
        run_service_module,
        "OwnershipConsolidationRepository",
        lambda session: _FakeOwnershipRepo(session, structures=structures, relationships=relationships),
    )

    class _SnapshotService:
        def __init__(self, session: object) -> None:
            del session

        async def ensure_snapshot_for_subject(self, **_: object) -> None:
            return None

    monkeypatch.setattr(phase4_service_module, "Phase4ControlPlaneService", _SnapshotService)

    policy_service = AccountingPolicyService(
        policies=[
            Policy(
                policy_id="policy.ic.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="intercompany_profit_elimination",
                parameters={"unrealized_profit_rate": "0.250000", "policy_effect": "adjustment"},
            ),
            Policy(
                policy_id="policy.nci.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="minority_interest_adjustment",
                parameters={
                    "basis": "full_goodwill",
                    "adjustment_multiplier": "1.500000",
                    "policy_effect": "adjustment",
                },
            ),
            Policy(
                policy_id="policy.revenue.v2",
                policy_version_id=2,
                effective_date=date(2025, 1, 1),
                rule_type="revenue_reclassification",
                parameters={
                    "metric_codes": ["revenue"],
                    "reclassification_rate": "0.100000",
                    "policy_effect": "adjustment",
                },
            ),
        ]
    )

    service = RunService(
        repository=repo,
        validation_service=ValidationService(),
        hierarchy_service=HierarchyService(),
        aggregation_service=AggregationService(),
        intercompany_service=IntercompanyService(),
        adjustment_service=AdjustmentService(),
        policy_service=policy_service,
    )

    result = await service.execute_run(tenant_id=tenant_id, run_id=run_id, created_by=uuid.uuid4())

    assert result["minority_interest_total"] == "30.000000"
    revenue_rows = [row for row in repo.metric_results if row.metric_code == "revenue"]
    assert len(revenue_rows) == 1
    assert revenue_rows[0].aggregated_value == Decimal("225.000000")
    policy_rows = [row for row in repo.evidence_links if row.evidence_ref == "accounting-policy:summary"]
    assert len(policy_rows) == 1
    assert (
        policy_rows[0].evidence_payload_json["intercompany_profit_elimination"]["policy_version_id"]
        == 2
    )
    assert (
        policy_rows[0].evidence_payload_json["minority_interest_adjustment"]["audit_trace"][
            "rule_type"
        ]
        == "minority_interest_adjustment"
    )


@pytest.mark.asyncio
async def test_execute_run_missing_data_triggers_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.application import run_service as run_service_module
    from financeops.platform.services.control_plane import phase4_service as phase4_service_module

    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    hierarchy_id = uuid.uuid4()
    run_id = uuid.uuid4()
    metric_run_id = uuid.uuid4()
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    entity_c = uuid.uuid4()

    run = SimpleNamespace(
        id=run_id,
        run_token="run-token",
        run_status="created",
        hierarchy_id=hierarchy_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_run_refs_json=[{"source_type": "metric_run", "run_id": str(metric_run_id)}],
    )
    nodes = [
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_a, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_b, parent_node_id=None, node_level=0),
        SimpleNamespace(id=uuid.uuid4(), entity_id=entity_c, parent_node_id=None, node_level=0),
    ]
    metric_rows = [
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="100.000000",
                entity_id=str(entity_a),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_b),
                    "ic_account_class": "IC_REVENUE",
                    "local_amount": "100.000000",
                    "parent_amount": "100.000000",
                    "expected_rate": "1.000000",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="ic_sales",
                metric_value="-100.000000",
                entity_id=str(entity_b),
                account_code="4000",
                source_summary_json={
                    "ic_reference": "IC-REF-1",
                    "ic_counterparty_entity": str(entity_a),
                    "ic_account_class": "IC_EXPENSE",
                    "local_amount": "-100.000000",
                    "parent_amount": "-100.000000",
                    "expected_rate": "1.000000",
                },
            ).__dict__,
        ),
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="nci_balance",
                metric_value="100.000000",
                entity_id=None,
                source_summary_json={"nci_balance": "100.000000"},
            ).__dict__,
        ),
    ]
    repo = _FakeRepo(
        run=run,
        nodes=nodes,
        metric_runs=[SimpleNamespace(id=metric_run_id)],
        metric_rows=metric_rows,
        intercompany_rules=[SimpleNamespace(id=uuid.uuid4(), rule_code="IC_STD", treatment_rule_json={})],
        adjustment_rows=[SimpleNamespace(id=uuid.uuid4(), adjustment_code="ADJ_IC", adjustment_type="analytic_adjustment")],
    )

    structures = [SimpleNamespace(id=uuid.uuid4(), ownership_structure_code="GROUP_MAIN")]
    relationships = [
        SimpleNamespace(
            id=uuid.uuid4(),
            child_entity_id=entity_c,
            ownership_percentage=Decimal("80.000000"),
            minority_interest_indicator=True,
        )
    ]

    monkeypatch.setattr(
        run_service_module,
        "OwnershipConsolidationRepository",
        lambda session: _FakeOwnershipRepo(session, structures=structures, relationships=relationships),
    )

    class _SnapshotService:
        def __init__(self, session: object) -> None:
            del session

        async def ensure_snapshot_for_subject(self, **_: object) -> None:
            return None

    monkeypatch.setattr(phase4_service_module, "Phase4ControlPlaneService", _SnapshotService)

    service = RunService(
        repository=repo,
        validation_service=ValidationService(),
        hierarchy_service=HierarchyService(),
        aggregation_service=AggregationService(),
        intercompany_service=IntercompanyService(),
        adjustment_service=AdjustmentService(),
    )

    with pytest.raises(ValueError, match="validation_report.status=FAIL: missing minority-interest source rows"):
        await service.execute_run(tenant_id=tenant_id, run_id=run_id, created_by=uuid.uuid4())


@pytest.mark.asyncio
async def test_execute_run_without_intercompany_data_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.multi_entity_consolidation.application import run_service as run_service_module
    from financeops.platform.services.control_plane import phase4_service as phase4_service_module

    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    hierarchy_id = uuid.uuid4()
    run_id = uuid.uuid4()
    metric_run_id = uuid.uuid4()
    entity_a = uuid.uuid4()

    run = SimpleNamespace(
        id=run_id,
        run_token="run-token",
        run_status="created",
        hierarchy_id=hierarchy_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_run_refs_json=[{"source_type": "metric_run", "run_id": str(metric_run_id)}],
    )
    nodes = [SimpleNamespace(id=uuid.uuid4(), entity_id=entity_a, parent_node_id=None, node_level=0)]
    metric_rows = [
        SimpleNamespace(
            run_id=metric_run_id,
            **_metric_row(
                row_id=uuid.uuid4(),
                metric_code="revenue",
                metric_value="250.000000",
                entity_id=str(entity_a),
                account_code="4000",
                source_summary_json={},
            ).__dict__,
        )
    ]
    repo = _FakeRepo(
        run=run,
        nodes=nodes,
        metric_runs=[SimpleNamespace(id=metric_run_id)],
        metric_rows=metric_rows,
    )

    monkeypatch.setattr(
        run_service_module,
        "OwnershipConsolidationRepository",
        lambda session: _FakeOwnershipRepo(session, structures=[], relationships=[]),
    )

    class _SnapshotService:
        def __init__(self, session: object) -> None:
            del session

        async def ensure_snapshot_for_subject(self, **_: object) -> None:
            return None

    monkeypatch.setattr(phase4_service_module, "Phase4ControlPlaneService", _SnapshotService)

    service = RunService(
        repository=repo,
        validation_service=ValidationService(),
        hierarchy_service=HierarchyService(),
        aggregation_service=AggregationService(),
        intercompany_service=IntercompanyService(),
        adjustment_service=AdjustmentService(),
    )

    result = await service.execute_run(tenant_id=tenant_id, run_id=run_id, created_by=uuid.uuid4())

    assert result["validation_report"] == {
        "status": "PASS",
        "reason": "no intercompany transactions",
    }
    assert result["elimination_entry_count"] == 0
    assert result["adjustment_entry_count"] == 0


@pytest.mark.asyncio
async def test_legacy_run_processing_routes_through_intercompany_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.services.consolidation import run_processing as run_processing_module

    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    pair_id = uuid.uuid4()
    wrapper_calls = {"match": 0, "eliminate": 0}
    inserted_pairs: list[dict[str, object]] = []
    inserted_eliminations: list[dict[str, object]] = []

    class _FakeIntercompanyService:
        def match_candidates(self, *, candidates: list[MatchCandidateLine], tolerance: object) -> dict[str, object]:
            del tolerance
            wrapper_calls["match"] += 1
            assert candidates
            return {
                "validation_report": {"status": "PASS", "reason": "legacy wrapper"},
                "matched_pairs": [
                    {
                        "match_key_hash": "match-1",
                        "entity_from": str(entity_a),
                        "entity_to": str(entity_b),
                        "account_code": "4000",
                        "ic_reference": "IC-REF-1",
                        "amount_local_from": "100.000000",
                        "amount_local_to": "-100.000000",
                        "amount_parent_from": "100.000000",
                        "amount_parent_to": "-100.000000",
                        "classification": "matched",
                        "expected_difference": "0.000000",
                        "actual_difference": "0.000000",
                        "fx_explained": "0.000000",
                        "unexplained_difference": "0.000000",
                        "transaction_reference": "IC-REF-1",
                    }
                ],
                "unmatched_items": [],
                "elimination_entries": [],
            }

        def build_eliminations_from_pairs(self, *, pair_rows: list[object], tolerance: object) -> dict[str, object]:
            del tolerance
            wrapper_calls["eliminate"] += 1
            assert len(pair_rows) == 1
            return {
                "validation_report": {"status": "PASS", "reason": "legacy wrapper"},
                "matched_pairs": [],
                "unmatched_items": [],
                "elimination_entries": [
                    {
                        "intercompany_pair_id": str(pair_rows[0].id),
                        "entity_from": str(pair_rows[0].entity_from),
                        "entity_to": str(pair_rows[0].entity_to),
                        "account_code": pair_rows[0].account_code,
                        "classification_at_time": pair_rows[0].classification,
                        "elimination_status": "applied",
                        "eliminated_amount_parent": "0.000000",
                        "fx_component_impact_parent": "0.000000",
                        "residual_difference_parent": "0.000000",
                        "rule_code": "ELIM.APPLY.MATCHED",
                        "reason": "Applied elimination per deterministic IC classification",
                        "transaction_reference": "IC-REF-1",
                        "matching_rationale": "legacy_matcher:matched",
                        "tolerance_applied": {
                            "amount_tolerance_parent": "0.010000",
                            "fx_explained_tolerance_parent": "0.500000",
                            "timing_tolerance_days": 3,
                        },
                    }
                ],
            }

    async def _fake_insert_financial_record(
        session: object,
        *,
        model_class: object,
        tenant_id: uuid.UUID,
        record_data: dict[str, object],
        values: dict[str, object],
        audit: object,
    ) -> None:
        del session, tenant_id, audit
        payload = {"record_data": record_data, "values": values}
        if model_class is run_processing_module.IntercompanyPair:
            inserted_pairs.append(payload)
            return None
        if model_class is run_processing_module.ConsolidationElimination:
            inserted_eliminations.append(payload)
            return None
        raise AssertionError("unexpected model insert")

    line_item = SimpleNamespace(
        snapshot_line_id=uuid.uuid4(),
        entity_id=entity_a,
        account_code="4000",
        local_amount=Decimal("100.000000"),
        expected_rate=Decimal("1.000000"),
        parent_amount=Decimal("100.000000"),
        ic_reference="IC-REF-1",
        ic_counterparty_entity=entity_b,
        transaction_date=date(2026, 1, 31),
    )
    pair_row = SimpleNamespace(
        id=pair_id,
        match_key_hash="match-1",
        entity_from=entity_a,
        entity_to=entity_b,
        account_code="4000",
        ic_reference="IC-REF-1",
        amount_local_from=Decimal("100.000000"),
        amount_local_to=Decimal("-100.000000"),
        amount_parent_from=Decimal("100.000000"),
        amount_parent_to=Decimal("-100.000000"),
        expected_difference=Decimal("0.000000"),
        actual_difference=Decimal("0.000000"),
        fx_explained=Decimal("0.000000"),
        unexplained_difference=Decimal("0.000000"),
        classification="matched",
    )
    session = _RunProcessingSession(
        execute_results=[
            _TupleResult([(line_item, "IC_REVENUE")]),
            _ScalarResult([pair_row]),
        ],
        scalar_results=[0, 0],
    )

    async def _fake_get_run_or_raise(*args: object, **kwargs: object) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(
            configuration_json={
                "tolerances": {
                    "amount_tolerance_parent": "0.010000",
                    "fx_explained_tolerance_parent": "0.500000",
                    "timing_tolerance_days": 3,
                }
            }
        )

    monkeypatch.setattr(run_processing_module.AuditWriter, "insert_financial_record", _fake_insert_financial_record)
    monkeypatch.setattr(run_processing_module, "get_run_or_raise", _fake_get_run_or_raise)
    monkeypatch.setattr(
        "financeops.modules.multi_entity_consolidation.application.intercompany_service.IntercompanyService",
        _FakeIntercompanyService,
    )

    assert not hasattr(run_processing_module, "match_intercompany_lines")
    assert not hasattr(run_processing_module, "build_elimination_decisions")

    pair_count = await run_processing_module.match_intercompany_for_run(
        session,
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        correlation_id="corr-1",
    )
    elimination_count = await run_processing_module.compute_eliminations_for_run(
        session,
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        correlation_id="corr-1",
    )

    assert pair_count == 1
    assert elimination_count == 1
    assert wrapper_calls == {"match": 1, "eliminate": 1}
    assert len(inserted_pairs) == 1
    assert len(inserted_eliminations) == 1
