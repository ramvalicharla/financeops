from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import sys
import types
from uuid import uuid4

import pytest

from financeops.modules.board_pack_generator.application.export_service import (
    BoardPackExportService,
    _format_decimal,
)
from financeops.modules.board_pack_generator.domain.enums import SectionType
from financeops.modules.board_pack_generator.domain.pack_definition import AssembledPack, RenderedSection


def _contains_float(value):
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


def _build_pack(*, long_titles: bool = False) -> AssembledPack:
    titles = [
        "Profit and Loss Summary",
        "Balance Sheet Summary",
    ]
    if long_titles:
        titles = [
            "This is a very long board pack section title that exceeds Excel limit one",
            "This is a very long board pack section title that exceeds Excel limit two",
        ]

    section1_snapshot = {
        "items": [
            {"metric": "Revenue", "amount": Decimal("1234567.89")},
            {"metric": "COGS", "amount": Decimal("234567.89")},
        ]
    }
    section2_snapshot = {
        "assets": {"cash": Decimal("100.00"), "inventory": Decimal("250.50")},
        "liabilities": {"payables": Decimal("50.25")},
    }

    section1 = RenderedSection(
        section_type=SectionType.PROFIT_AND_LOSS,
        section_order=1,
        title=titles[0],
        data_snapshot=section1_snapshot,
        section_hash=RenderedSection.compute_hash(section1_snapshot),
    )
    section2 = RenderedSection(
        section_type=SectionType.BALANCE_SHEET,
        section_order=2,
        title=titles[1],
        data_snapshot=section2_snapshot,
        section_hash=RenderedSection.compute_hash(section2_snapshot),
    )

    return AssembledPack(
        run_id=uuid4(),
        tenant_id=uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        sections=[section1, section2],
        chain_hash=AssembledPack.compute_chain_hash([section1, section2]),
    )


def _install_fake_weasyprint(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeHTML:
        def __init__(self, *, string: str, base_url: str | None = None) -> None:
            self._string = string
            self._base_url = base_url

        def write_pdf(self) -> bytes:
            body = self._string.encode("utf-8")
            return b"%PDF-1.7\n%FinanceOps\n" + body

    fake_module = types.SimpleNamespace(HTML=_FakeHTML)
    monkeypatch.setitem(sys.modules, "weasyprint", fake_module)


@pytest.mark.unit
def test_t_021_export_pdf_has_pdf_header(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_weasyprint(monkeypatch)
    service = BoardPackExportService()
    pdf_bytes, filename = service.export_pdf(
        pack=_build_pack(),
        pack_name="Monthly Board Pack",
        generated_at=datetime(2026, 2, 1, 0, 0, 0),
    )
    assert filename.endswith(".pdf")
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.unit
def test_t_022_export_excel_is_loadable_and_has_cover_sheet() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    service = BoardPackExportService()
    excel_bytes, filename = service.export_excel(
        pack=_build_pack(),
        pack_name="Monthly Board Pack",
        generated_at=datetime(2026, 2, 1, 0, 0, 0),
    )
    workbook = openpyxl.load_workbook(BytesIO(excel_bytes))
    assert filename.endswith(".xlsx")
    assert "Cover" in workbook.sheetnames


@pytest.mark.unit
def test_t_023_export_excel_sheet_count_equals_sections_plus_cover() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pack = _build_pack()
    service = BoardPackExportService()
    excel_bytes, _ = service.export_excel(
        pack=pack,
        pack_name="Monthly Board Pack",
        generated_at=datetime(2026, 2, 1, 0, 0, 0),
    )
    workbook = openpyxl.load_workbook(BytesIO(excel_bytes))
    assert len(workbook.sheetnames) == len(pack.sections) + 1


@pytest.mark.unit
def test_t_024_format_decimal_recursive_contains_no_float() -> None:
    value = {
        "a": Decimal("1.10"),
        "nested": [Decimal("2.20"), {"b": Decimal("3.30")}],
    }
    formatted = _format_decimal(value)
    assert not _contains_float(formatted)


@pytest.mark.unit
def test_t_025_format_decimal_negative_value() -> None:
    assert _format_decimal(Decimal("-1234567.89")) == "-1,234,567.89"


@pytest.mark.unit
def test_t_026_export_excel_truncates_long_sheet_names_and_keeps_unique() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    service = BoardPackExportService()
    excel_bytes, _ = service.export_excel(
        pack=_build_pack(long_titles=True),
        pack_name="Monthly Board Pack",
        generated_at=datetime(2026, 2, 1, 0, 0, 0),
    )
    workbook = openpyxl.load_workbook(BytesIO(excel_bytes))
    sheet_names = workbook.sheetnames
    assert len(sheet_names) == len(set(sheet_names))
    assert all(len(name) <= 31 for name in sheet_names)


@pytest.mark.unit
def test_t_027_export_pdf_is_identical_for_same_input_and_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_weasyprint(monkeypatch)
    service = BoardPackExportService()
    pack = _build_pack()
    generated_at = datetime(2026, 2, 1, 0, 0, 0)

    first_bytes, _ = service.export_pdf(pack=pack, pack_name="Monthly Board Pack", generated_at=generated_at)
    second_bytes, _ = service.export_pdf(pack=pack, pack_name="Monthly Board Pack", generated_at=generated_at)

    assert first_bytes == second_bytes
