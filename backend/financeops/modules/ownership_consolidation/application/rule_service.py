from __future__ import annotations

from collections.abc import Sequence


class RuleService:
    def select_primary_structure(self, *, rows: Sequence[object]) -> object:
        return sorted(rows, key=lambda row: (row.ownership_structure_code, row.id))[0]

    def select_primary_ownership_rule(self, *, rows: Sequence[object]) -> object:
        return sorted(rows, key=lambda row: (row.rule_code, row.id))[0]

    def select_primary_minority_rule(self, *, rows: Sequence[object]) -> object:
        return sorted(rows, key=lambda row: (row.rule_code, row.id))[0]
