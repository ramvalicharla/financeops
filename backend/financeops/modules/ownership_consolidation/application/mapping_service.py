from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from financeops.modules.ownership_consolidation.domain.invariants import q6


class MappingService:
    def extract_entity_id_from_scope(self, scope_json: dict[str, Any]) -> uuid.UUID | None:
        raw_entity = scope_json.get("entity_id")
        if raw_entity:
            try:
                return uuid.UUID(str(raw_entity))
            except ValueError:
                return None
        raw_entities = scope_json.get("entity_ids")
        if isinstance(raw_entities, list):
            entity_ids = sorted(str(v) for v in raw_entities if str(v).strip())
            if entity_ids:
                try:
                    return uuid.UUID(entity_ids[0])
                except ValueError:
                    return None
        return None

    def derive_scope_code(self, scope_json: dict[str, Any]) -> str:
        scope_code = str(scope_json.get("scope_code", "")).strip()
        return scope_code or "default_scope"

    def derive_weight(
        self,
        *,
        relationship: Any | None,
    ) -> Decimal:
        if relationship is None:
            return Decimal("1.000000")
        percentage = Decimal(str(relationship.ownership_percentage))
        if bool(getattr(relationship, "proportionate_consolidation_indicator", False)):
            return q6(percentage / Decimal("100"))
        return Decimal("1.000000")

    def derive_minority_value(
        self,
        *,
        source_value: Decimal,
        relationship: Any | None,
    ) -> Decimal | None:
        if relationship is None:
            return None
        if not bool(getattr(relationship, "minority_interest_indicator", False)):
            return None
        percentage = Decimal(str(relationship.ownership_percentage))
        minority_share = Decimal("1") - (percentage / Decimal("100"))
        if minority_share <= Decimal("0"):
            return Decimal("0.000000")
        return q6(source_value * minority_share)
