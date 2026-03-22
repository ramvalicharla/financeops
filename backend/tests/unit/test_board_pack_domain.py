from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType
from financeops.modules.board_pack_generator.domain.pack_assembler import PackAssembler
from financeops.modules.board_pack_generator.domain.pack_definition import (
    AssembledPack,
    PackDefinitionSchema,
    PackRunContext,
    RenderedSection,
    SectionConfig,
)
from financeops.modules.board_pack_generator.domain.section_renderer import (
    RENDERER_REGISTRY,
    get_renderer,
)


def _make_definition(*, section_configs: list[SectionConfig] | None = None) -> PackDefinitionSchema:
    return PackDefinitionSchema(
        name="Board Pack",
        description="Test definition",
        section_configs=section_configs
        or [
            SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1),
            SectionConfig(section_type=SectionType.BALANCE_SHEET, order=2),
        ],
        entity_ids=[uuid.uuid4()],
        period_type=PeriodType.MONTHLY,
        config={},
    )


def _make_context(definition: PackDefinitionSchema | None = None) -> PackRunContext:
    return PackRunContext(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        definition=definition or _make_definition(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        triggered_by=uuid.uuid4(),
    )


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


@pytest.mark.unit
def test_t_007_pack_definition_requires_non_empty_sections() -> None:
    with pytest.raises(ValidationError):
        PackDefinitionSchema(
            name="Bad",
            section_configs=[],
            entity_ids=[uuid.uuid4()],
            period_type=PeriodType.MONTHLY,
        )


@pytest.mark.unit
def test_t_008_pack_definition_rejects_duplicate_section_order() -> None:
    with pytest.raises(ValidationError):
        _make_definition(
            section_configs=[
                SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1),
                SectionConfig(section_type=SectionType.BALANCE_SHEET, order=1),
            ]
        )


@pytest.mark.unit
def test_t_009_pack_definition_requires_non_empty_entity_ids() -> None:
    with pytest.raises(ValidationError):
        PackDefinitionSchema(
            name="Bad",
            section_configs=[SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1)],
            entity_ids=[],
            period_type=PeriodType.MONTHLY,
        )


@pytest.mark.unit
def test_t_010_pack_run_context_rejects_period_end_before_start() -> None:
    with pytest.raises(ValidationError):
        PackRunContext(
            run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            definition=_make_definition(),
            period_start=date(2026, 1, 31),
            period_end=date(2026, 1, 1),
            triggered_by=uuid.uuid4(),
        )


@pytest.mark.unit
def test_t_011_compute_hash_is_deterministic_for_same_dict() -> None:
    payload = {
        "a": "value",
        "b": 2,
        "nested": {"x": "1", "y": ["2", "3"]},
    }
    hashes = {RenderedSection.compute_hash(payload) for _ in range(100)}
    assert len(hashes) == 1


@pytest.mark.unit
def test_t_012_decimal_is_canonicalized_as_string_for_hashing() -> None:
    payload = {"amount": Decimal("123.45")}
    canonical = RenderedSection._canonicalize_value(payload)
    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert '"123.45"' in canonical_json
    assert "123.45" in canonical_json

    first = RenderedSection.compute_hash(payload)
    second = RenderedSection.compute_hash(payload)
    assert first == second


@pytest.mark.unit
def test_t_013_chain_hash_same_even_when_input_order_differs() -> None:
    s1 = RenderedSection(
        section_type=SectionType.PROFIT_AND_LOSS,
        section_order=1,
        title="P&L",
        data_snapshot={"v": "1"},
        section_hash=RenderedSection.compute_hash({"v": "1"}),
    )
    s2 = RenderedSection(
        section_type=SectionType.BALANCE_SHEET,
        section_order=2,
        title="BS",
        data_snapshot={"v": "2"},
        section_hash=RenderedSection.compute_hash({"v": "2"}),
    )
    assert AssembledPack.compute_chain_hash([s1, s2]) == AssembledPack.compute_chain_hash([s2, s1])


@pytest.mark.unit
def test_t_014_all_renderers_produce_non_empty_hash() -> None:
    for section_type in SectionType:
        renderer = get_renderer(section_type)
        context = _make_context(
            _make_definition(section_configs=[SectionConfig(section_type=section_type, order=1)])
        )
        rendered = renderer.render(
            context=context,
            section_config=SectionConfig(section_type=section_type, order=1, title="Section"),
            source_data={"amount": Decimal("10.50")},
        )
        assert rendered.section_hash
        assert isinstance(rendered.section_hash, str)


@pytest.mark.unit
def test_t_015_decimal_safe_recursive_conversion_has_no_float() -> None:
    renderer = get_renderer(SectionType.KPI_SUMMARY)
    nested = {
        "amount": Decimal("1.20"),
        "id": uuid.uuid4(),
        "dt": date(2026, 1, 1),
        "enum": SectionType.FX_SUMMARY,
        "items": [Decimal("2.34"), {"deep": Decimal("9.99")}],
    }
    safe = renderer._decimal_safe(nested)
    assert not _contains_float(safe)


@pytest.mark.unit
def test_t_016_get_renderer_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        get_renderer("UNKNOWN" )  # type: ignore[arg-type]


@pytest.mark.unit
def test_t_017_pack_assembler_rejects_duplicate_section_order() -> None:
    assembler = PackAssembler()
    context = _make_context()
    duplicated = [
        RenderedSection(
            section_type=SectionType.PROFIT_AND_LOSS,
            section_order=1,
            title="A",
            data_snapshot={"x": "1"},
            section_hash=RenderedSection.compute_hash({"x": "1"}),
        ),
        RenderedSection(
            section_type=SectionType.BALANCE_SHEET,
            section_order=1,
            title="B",
            data_snapshot={"y": "2"},
            section_hash=RenderedSection.compute_hash({"y": "2"}),
        ),
    ]
    with pytest.raises(ValueError):
        assembler.assemble(context=context, rendered_sections=duplicated)


@pytest.mark.unit
def test_t_018_pack_assembler_chain_hash_matches_manual_hash() -> None:
    assembler = PackAssembler()
    context = _make_context()
    sections = [
        RenderedSection(
            section_type=SectionType.PROFIT_AND_LOSS,
            section_order=2,
            title="P&L",
            data_snapshot={"a": "1"},
            section_hash="b" * 64,
        ),
        RenderedSection(
            section_type=SectionType.BALANCE_SHEET,
            section_order=1,
            title="BS",
            data_snapshot={"a": "2"},
            section_hash="a" * 64,
        ),
    ]
    assembled = assembler.assemble(context=context, rendered_sections=sections)
    manual = hashlib.sha256((("a" * 64) + ("b" * 64)).encode("utf-8")).hexdigest()
    assert assembled.chain_hash == manual


@pytest.mark.unit
def test_t_019_different_snapshots_yield_different_section_hashes() -> None:
    first = RenderedSection.compute_hash({"value": "1"})
    second = RenderedSection.compute_hash({"value": "2"})
    assert first != second


@pytest.mark.unit
def test_t_020_renderer_registry_has_all_section_types() -> None:
    assert set(RENDERER_REGISTRY.keys()) == set(SectionType)
