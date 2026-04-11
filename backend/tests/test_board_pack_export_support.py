from __future__ import annotations

import sys
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from financeops.modules.board_pack_generator.application import export_service
from financeops.modules.board_pack_generator.application.export_service import (
    BoardPackExportService,
    assert_weasyprint_available,
    get_weasyprint_mode,
)
from financeops.modules.board_pack_generator.domain.enums import SectionType
from financeops.modules.board_pack_generator.domain.pack_definition import (
    AssembledPack,
    RenderedSection,
)
from scripts.smoke_pdf import main as smoke_pdf_main


def _make_pack() -> AssembledPack:
    section = RenderedSection(
        section_type=SectionType.PROFIT_AND_LOSS,
        section_order=1,
        title="P&L",
        data_snapshot={"revenue": "1000000"},
        section_hash="hash-1",
    )
    return AssembledPack(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        sections=[section],
        chain_hash="chain-hash",
    )


def test_get_weasyprint_mode_returns_string() -> None:
    mode = get_weasyprint_mode()
    assert mode in {"real", "stub", "broken"}


def test_weasyprint_mode_real_when_render_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str, base_url: str | None = None) -> None:
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            return b"%PDF-fake"

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))
    assert get_weasyprint_mode() == "real"


def test_weasyprint_mode_broken_when_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str, base_url: str | None = None) -> None:
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            raise OSError("missing libgobject")

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))
    assert get_weasyprint_mode() == "broken"


def test_assert_weasyprint_available_passes_in_real_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(export_service, "get_weasyprint_mode", lambda: "real")
    assert_weasyprint_available()


def test_assert_weasyprint_available_passes_in_stub_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(export_service, "get_weasyprint_mode", lambda: "stub")
    assert_weasyprint_available()


def test_assert_weasyprint_available_raises_in_broken_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(export_service, "get_weasyprint_mode", lambda: "broken")
    with pytest.raises(RuntimeError, match="libgobject"):
        assert_weasyprint_available()


def test_pdf_generation_calls_assert_weasyprint(monkeypatch: pytest.MonkeyPatch) -> None:
    assert_mock = Mock()

    class FakeHTML:
        def __init__(self, string: str, base_url: str | None = None) -> None:
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            return b"%PDF-test"

    monkeypatch.setattr(export_service, "assert_weasyprint_available", assert_mock)
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))

    service = BoardPackExportService()
    pdf_bytes, _ = service.export_pdf(_make_pack(), "Pack", datetime.now(UTC))

    assert_mock.assert_called_once()
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_generation_propagates_broken_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        export_service,
        "assert_weasyprint_available",
        Mock(side_effect=RuntimeError("broken mode")),
    )

    service = BoardPackExportService()
    with pytest.raises(RuntimeError, match="broken mode"):
        service.export_pdf(_make_pack(), "Pack", datetime.now(UTC))


def test_pdf_generation_returns_bytes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str, base_url: str | None = None) -> None:
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            return b"%PDF-test-content"

    monkeypatch.setattr(export_service, "assert_weasyprint_available", lambda: None)
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))

    service = BoardPackExportService()
    pdf_bytes, _ = service.export_pdf(_make_pack(), "Pack", datetime.now(UTC))
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_generation_fails_on_empty_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str, base_url: str | None = None) -> None:
            self.string = string
            self.base_url = base_url

        def write_pdf(self) -> bytes:
            return b""

    monkeypatch.setattr(export_service, "assert_weasyprint_available", lambda: None)
    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))

    service = BoardPackExportService()
    with pytest.raises(RuntimeError, match="empty PDF output"):
        service.export_pdf(_make_pack(), "Pack", datetime.now(UTC))


def test_smoke_script_exits_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self) -> bytes:
            return b"%PDF-1.4 fake"

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))
    assert smoke_pdf_main() == 0


def test_smoke_script_exits_one_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeHTML:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self) -> bytes:
            raise OSError("no gobject")

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))
    assert smoke_pdf_main() == 1
