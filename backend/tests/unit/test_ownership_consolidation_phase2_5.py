from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from financeops.modules.ownership_consolidation.application.mapping_service import MappingService
from financeops.modules.ownership_consolidation.domain.value_objects import OwnershipRunTokenInput
from financeops.modules.ownership_consolidation.infrastructure.token_builder import (
    build_ownership_run_token,
)


@dataclass
class _Relationship:
    ownership_percentage: Decimal
    minority_interest_indicator: bool
    proportionate_consolidation_indicator: bool


def test_ownership_run_token_is_stable_for_same_inputs() -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    payload = OwnershipRunTokenInput(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        hierarchy_version_token="h1",
        scope_version_token="s1",
        ownership_structure_version_token="os1",
        ownership_rule_version_token="or1",
        minority_interest_rule_version_token="mr1",
        fx_translation_run_ref_nullable=None,
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": "00000000-0000-0000-0000-000000000001"}
        ],
        run_status="created",
    )
    assert build_ownership_run_token(payload) == build_ownership_run_token(payload)


def test_mapping_service_applies_proportionate_and_minority_deterministically() -> None:
    service = MappingService()
    relationship = _Relationship(
        ownership_percentage=Decimal("60.000000"),
        minority_interest_indicator=True,
        proportionate_consolidation_indicator=True,
    )
    weight = service.derive_weight(relationship=relationship)
    minority = service.derive_minority_value(
        source_value=Decimal("100.000000"),
        relationship=relationship,
    )
    assert weight == Decimal("0.600000")
    assert minority == Decimal("40.000000")


def test_mapping_service_extracts_entity_id_stably() -> None:
    service = MappingService()
    scope = {"entity_ids": ["00000000-0000-0000-0000-0000000000b1"]}
    entity_id = service.extract_entity_id_from_scope(scope)
    assert str(entity_id) == "00000000-0000-0000-0000-0000000000b1"
