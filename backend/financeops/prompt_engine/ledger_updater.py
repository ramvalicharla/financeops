from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from financeops.prompt_engine import ExecutionRecord, PromptDefinition, PromptStatus

_STATUS_SECTION_HEADER = "## Prompt Execution Status"
_STATUS_TABLE_HEADER = (
    "| Prompt ID | Subsystem | Execution Timestamp | Execution Status | "
    "Rework Attempt Number | Files Modified | Test Results | Failure Reason | Notes |"
)
_STATUS_TABLE_DIVIDER = "|---|---|---|---|---|---|---|---|---|"


@dataclass(slots=True)
class LedgerUpdateResult:
    ok: bool
    reason: str | None = None


class PromptLedgerUpdater:
    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path

    def append_running(self, prompt: PromptDefinition) -> LedgerUpdateResult:
        record = ExecutionRecord(
            prompt_id=prompt.prompt_id,
            subsystem=prompt.subsystem,
            execution_status=PromptStatus.RUNNING,
            rework_attempt_number=0,
            files_modified=[],
            test_results="N/A",
            notes="Prompt execution started",
        )
        return self.append_execution(record)

    def append_execution(self, record: ExecutionRecord) -> LedgerUpdateResult:
        try:
            self._ensure_status_section()
            row = self._format_row(record)
            with self.ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(row + "\n")
            return LedgerUpdateResult(ok=True)
        except Exception as exc:
            return LedgerUpdateResult(ok=False, reason=f"Ledger append failed: {exc}")

    def latest_status_map(self) -> dict[str, PromptStatus]:
        if not self.ledger_path.exists():
            return {}
        text = self.ledger_path.read_text(encoding="utf-8")
        section = self._extract_status_section(text)
        if section is None:
            return {}

        statuses: dict[str, PromptStatus] = {}
        for line in section:
            if not line.strip().startswith("|"):
                continue
            if line.strip() == _STATUS_TABLE_HEADER or line.strip() == _STATUS_TABLE_DIVIDER:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            prompt_id = cells[0]
            raw_status = cells[3]
            if not prompt_id:
                continue
            try:
                statuses[prompt_id] = PromptStatus(raw_status)
            except ValueError:
                continue
        return statuses

    def _ensure_status_section(self) -> None:
        if not self.ledger_path.exists():
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self.ledger_path.write_text(
                "# PROMPTS_LEDGER\n\n"
                "Purpose: Track every prompt executed by Codex or AI tools.\n\n"
                "Policy:\n- Append-only entries.\n\n",
                encoding="utf-8",
            )

        text = self.ledger_path.read_text(encoding="utf-8")
        if _STATUS_SECTION_HEADER in text:
            return

        with self.ledger_path.open("a", encoding="utf-8") as handle:
            if not text.endswith("\n"):
                handle.write("\n")
            handle.write("\n" + _STATUS_SECTION_HEADER + "\n\n")
            handle.write(_STATUS_TABLE_HEADER + "\n")
            handle.write(_STATUS_TABLE_DIVIDER + "\n")

    @staticmethod
    def _extract_status_section(text: str) -> list[str] | None:
        lines = text.splitlines()
        start_idx = -1
        for idx, line in enumerate(lines):
            if line.strip() == _STATUS_SECTION_HEADER:
                start_idx = idx
                break
        if start_idx < 0:
            return None

        section_lines: list[str] = []
        for line in lines[start_idx + 1 :]:
            if line.startswith("## "):
                break
            section_lines.append(line)
        return section_lines

    @staticmethod
    def _format_row(record: ExecutionRecord) -> str:
        files_modified = ", ".join(record.files_modified) if record.files_modified else "-"
        timestamp = record.execution_timestamp.isoformat()
        return (
            f"| {PromptLedgerUpdater._escape(record.prompt_id)} "
            f"| {PromptLedgerUpdater._escape(record.subsystem)} "
            f"| {PromptLedgerUpdater._escape(timestamp)} "
            f"| {record.execution_status.value} "
            f"| {record.rework_attempt_number} "
            f"| {PromptLedgerUpdater._escape(files_modified)} "
            f"| {PromptLedgerUpdater._escape(record.test_results)} "
            f"| {PromptLedgerUpdater._escape(record.failure_reason or '-')} "
            f"| {PromptLedgerUpdater._escape(record.notes or '-')} |"
        )

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ").strip()

    @staticmethod
    def successful_prompts(status_map: dict[str, PromptStatus]) -> set[str]:
        return {prompt_id for prompt_id, status in status_map.items() if status == PromptStatus.SUCCESS}

    @staticmethod
    def has_success(status_map: dict[str, PromptStatus], prompt_id: str) -> bool:
        return status_map.get(prompt_id) == PromptStatus.SUCCESS

    @staticmethod
    def statuses_for(prompts: Iterable[PromptDefinition], status_map: dict[str, PromptStatus]) -> dict[str, PromptStatus]:
        return {prompt.prompt_id: status_map.get(prompt.prompt_id, PromptStatus.PENDING) for prompt in prompts}

