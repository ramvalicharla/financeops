from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from financeops.db.models.consolidation import ConsolidationLineItem, IntercompanyPair


@dataclass(frozen=True)
class PairLineItemLink:
    line_item_from_id: UUID | None
    line_item_to_id: UUID | None


def _candidate_key(
    *,
    entity_id: UUID,
    account_code: str,
    ic_reference: str | None,
) -> tuple[UUID, str, str | None]:
    return (entity_id, account_code, ic_reference)


def _build_line_item_buckets(
    line_items: list[ConsolidationLineItem],
) -> dict[tuple[UUID, str, str | None], list[ConsolidationLineItem]]:
    buckets: dict[tuple[UUID, str, str | None], list[ConsolidationLineItem]] = {}
    for row in line_items:
        key = _candidate_key(
            entity_id=row.entity_id,
            account_code=row.account_code,
            ic_reference=row.ic_reference,
        )
        buckets.setdefault(key, []).append(row)
        fallback_key = _candidate_key(
            entity_id=row.entity_id,
            account_code=row.account_code,
            ic_reference=None,
        )
        if fallback_key != key:
            buckets.setdefault(fallback_key, []).append(row)
    for key in buckets:
        buckets[key] = sorted(
            buckets[key],
            key=lambda item: (str(item.id), str(item.snapshot_line_id)),
        )
    return buckets


def _find_line_item_match(
    *,
    buckets: dict[tuple[UUID, str, str | None], list[ConsolidationLineItem]],
    entity_id: UUID,
    account_code: str,
    ic_reference: str | None,
    parent_amount: Decimal,
) -> UUID | None:
    key = _candidate_key(
        entity_id=entity_id,
        account_code=account_code,
        ic_reference=ic_reference,
    )
    candidates = buckets.get(key, [])
    if not candidates:
        return None
    for row in candidates:
        if row.parent_amount == parent_amount:
            return row.id
    return candidates[0].id


def resolve_pair_line_item_links(
    *,
    pairs: list[IntercompanyPair],
    line_items: list[ConsolidationLineItem],
) -> dict[UUID, PairLineItemLink]:
    buckets = _build_line_item_buckets(line_items)
    links: dict[UUID, PairLineItemLink] = {}
    for pair in sorted(pairs, key=lambda row: str(row.id)):
        from_id = _find_line_item_match(
            buckets=buckets,
            entity_id=pair.entity_from,
            account_code=pair.account_code,
            ic_reference=pair.ic_reference,
            parent_amount=pair.amount_parent_from,
        )
        to_id = _find_line_item_match(
            buckets=buckets,
            entity_id=pair.entity_to,
            account_code=pair.account_code,
            ic_reference=pair.ic_reference,
            parent_amount=pair.amount_parent_to,
        )
        links[pair.id] = PairLineItemLink(
            line_item_from_id=from_id,
            line_item_to_id=to_id,
        )
    return links

