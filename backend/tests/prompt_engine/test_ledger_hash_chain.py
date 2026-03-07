from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from financeops.prompt_engine import ExecutionRecord, PromptStatus
from financeops.prompt_engine.ledger_updater import PromptLedgerUpdater


def _append_sample_rows(ledger_path: Path) -> PromptLedgerUpdater:
    updater = PromptLedgerUpdater(ledger_path)
    updater.append_execution(
        ExecutionRecord(
            prompt_id="FINOS-P001",
            subsystem="Auth",
            execution_status=PromptStatus.SUCCESS,
            rework_attempt_number=0,
            files_modified=["backend/a.py"],
            test_results="PASS",
            execution_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    updater.append_execution(
        ExecutionRecord(
            prompt_id="FINOS-P002",
            subsystem="RBAC",
            execution_status=PromptStatus.FAIL,
            rework_attempt_number=1,
            files_modified=["backend/b.py"],
            test_results="FAIL/NOT_RUN",
            failure_reason="boom",
            execution_timestamp=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    return updater


def test_ledger_hash_chain_verify_passes(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    updater = _append_sample_rows(ledger)
    result = updater.verify_hash_chain()
    assert result.ok is True


def test_ledger_hash_chain_verify_fails_on_tamper(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    updater = _append_sample_rows(ledger)
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text.replace("FAIL", "SUCCESS", 1), encoding="utf-8")

    result = updater.verify_hash_chain()
    assert result.ok is False
    assert result.reason is not None


def test_ledger_hash_chain_repair_rebuilds_hashes(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "ledgers" / "PROMPTS_LEDGER.md"
    updater = _append_sample_rows(ledger)
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text.replace("FAIL", "SUCCESS", 1), encoding="utf-8")

    broken = updater.verify_hash_chain()
    assert broken.ok is False

    repair = updater.repair_hash_chain()
    assert repair.ok is True

    repaired = updater.verify_hash_chain()
    assert repaired.ok is True
