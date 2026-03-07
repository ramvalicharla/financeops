from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from financeops.prompt_engine import ExecutionRecord, PromptDefinition, PromptStatus

_STATUS_SECTION_HEADER = "## Prompt Execution Status"
_STATUS_TABLE_HEADER = (
    "| Prompt ID | Subsystem | Execution Timestamp | Execution Status | "
    "Rework Attempt Number | Files Modified | Test Results | Failure Reason | Notes | "
    "Prev Hash | Entry Hash |"
)
_STATUS_TABLE_DIVIDER = "|---|---|---|---|---|---|---|---|---|---|---|"
_GENESIS_HASH = "GENESIS"


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
            prev_hash = self._last_entry_hash()
            row = self._format_row(record, prev_hash=prev_hash)
            with self.ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(row + "\n")
            return LedgerUpdateResult(ok=True)
        except Exception as exc:
            return LedgerUpdateResult(ok=False, reason=f"Ledger append failed: {exc}")

    def verify_hash_chain(self) -> LedgerUpdateResult:
        if not self.ledger_path.exists():
            return LedgerUpdateResult(ok=True)
        text = self.ledger_path.read_text(encoding="utf-8")
        section = self._extract_status_section(text)
        if section is None:
            return LedgerUpdateResult(ok=True)

        prev_hash = _GENESIS_HASH
        for line_no, line in enumerate(section, start=1):
            if not line.strip().startswith("|"):
                continue
            if line.strip() == _STATUS_TABLE_HEADER or line.strip() == _STATUS_TABLE_DIVIDER:
                continue
            cells = self._split_row(line)
            if len(cells) < 11:
                return LedgerUpdateResult(
                    ok=False,
                    reason=f"Ledger hash chain missing columns at status row {line_no}",
                )

            prompt_id = cells[0]
            status = cells[3]
            timestamp = cells[2]
            row_prev_hash = cells[9]
            row_entry_hash = cells[10]

            if row_prev_hash != prev_hash:
                return LedgerUpdateResult(
                    ok=False,
                    reason=(
                        "Ledger hash chain prev_hash mismatch at "
                        f"status row {line_no}: expected {prev_hash}, got {row_prev_hash}"
                    ),
                )

            expected_entry = self._compute_entry_hash(
                prompt_id=prompt_id,
                status=status,
                timestamp=timestamp,
                prev_hash=row_prev_hash,
            )
            if row_entry_hash != expected_entry:
                return LedgerUpdateResult(
                    ok=False,
                    reason=(
                        "Ledger hash chain entry_hash mismatch at "
                        f"status row {line_no}"
                    ),
                )
            prev_hash = row_entry_hash

        return LedgerUpdateResult(ok=True)

    def repair_hash_chain(self) -> LedgerUpdateResult:
        if not self.ledger_path.exists():
            return LedgerUpdateResult(ok=True)

        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        located = self._locate_status_section(lines)
        if located is None:
            return LedgerUpdateResult(ok=True)
        start_idx, end_idx = located
        section_lines = lines[start_idx + 1 : end_idx]

        repaired_section: list[str] = []
        prev_hash = _GENESIS_HASH
        header_written = False

        for line in section_lines:
            stripped = line.strip()
            if not stripped:
                repaired_section.append(line)
                continue
            if stripped.startswith("|"):
                if stripped == _STATUS_TABLE_HEADER or stripped.startswith("| Prompt ID |"):
                    repaired_section.append(_STATUS_TABLE_HEADER)
                    header_written = True
                    continue
                if stripped == _STATUS_TABLE_DIVIDER or stripped.startswith("|---|"):
                    repaired_section.append(_STATUS_TABLE_DIVIDER)
                    continue

                cells = self._split_row(line)
                if len(cells) < 9:
                    repaired_section.append(line)
                    continue
                prompt_id = cells[0]
                timestamp = cells[2]
                status = cells[3]
                entry_hash = self._compute_entry_hash(
                    prompt_id=prompt_id,
                    status=status,
                    timestamp=timestamp,
                    prev_hash=prev_hash,
                )
                base_cells = cells[:9]
                base_cells.append(prev_hash)
                base_cells.append(entry_hash)
                repaired_section.append(self._join_cells(base_cells))
                prev_hash = entry_hash
                continue

            repaired_section.append(line)

        if not header_written:
            repaired_section.insert(0, _STATUS_TABLE_HEADER)
            repaired_section.insert(1, _STATUS_TABLE_DIVIDER)

        new_lines = lines[: start_idx + 1] + repaired_section + lines[end_idx:]
        self.ledger_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return LedgerUpdateResult(ok=True)

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
        if _STATUS_SECTION_HEADER not in text:
            with self.ledger_path.open("a", encoding="utf-8") as handle:
                if not text.endswith("\n"):
                    handle.write("\n")
                handle.write("\n" + _STATUS_SECTION_HEADER + "\n\n")
                handle.write(_STATUS_TABLE_HEADER + "\n")
                handle.write(_STATUS_TABLE_DIVIDER + "\n")
            return

        lines = text.splitlines()
        located = self._locate_status_section(lines)
        if located is None:
            return
        start_idx, _ = located
        section_lines = lines[start_idx + 1 :]
        header_pos = None
        divider_pos = None
        for idx, line in enumerate(section_lines, start=start_idx + 1):
            stripped = line.strip()
            if stripped.startswith("| Prompt ID |"):
                header_pos = idx
            elif stripped.startswith("|---|") and header_pos is not None:
                divider_pos = idx
                break
        if header_pos is None or divider_pos is None:
            return
        if lines[header_pos].strip() == _STATUS_TABLE_HEADER and lines[divider_pos].strip() == _STATUS_TABLE_DIVIDER:
            return
        lines[header_pos] = _STATUS_TABLE_HEADER
        lines[divider_pos] = _STATUS_TABLE_DIVIDER
        self.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
    def _format_row(record: ExecutionRecord, *, prev_hash: str) -> str:
        files_modified = ", ".join(record.files_modified) if record.files_modified else "-"
        timestamp = record.execution_timestamp.isoformat()
        entry_hash = PromptLedgerUpdater._compute_entry_hash(
            prompt_id=record.prompt_id,
            status=record.execution_status.value,
            timestamp=timestamp,
            prev_hash=prev_hash,
        )
        return (
            f"| {PromptLedgerUpdater._escape(record.prompt_id)} "
            f"| {PromptLedgerUpdater._escape(record.subsystem)} "
            f"| {PromptLedgerUpdater._escape(timestamp)} "
            f"| {record.execution_status.value} "
            f"| {record.rework_attempt_number} "
            f"| {PromptLedgerUpdater._escape(files_modified)} "
            f"| {PromptLedgerUpdater._escape(record.test_results)} "
            f"| {PromptLedgerUpdater._escape(record.failure_reason or '-')} "
            f"| {PromptLedgerUpdater._escape(record.notes or '-')} "
            f"| {prev_hash} "
            f"| {entry_hash} |"
        )

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ").strip()

    @staticmethod
    def _split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    @staticmethod
    def _join_cells(cells: list[str]) -> str:
        escaped = [PromptLedgerUpdater._escape(cell) for cell in cells]
        return "| " + " | ".join(escaped) + " |"

    def _last_entry_hash(self) -> str:
        if not self.ledger_path.exists():
            return _GENESIS_HASH
        text = self.ledger_path.read_text(encoding="utf-8")
        section = self._extract_status_section(text)
        if section is None:
            return _GENESIS_HASH
        for line in reversed(section):
            if not line.strip().startswith("|"):
                continue
            if line.strip() == _STATUS_TABLE_HEADER or line.strip() == _STATUS_TABLE_DIVIDER:
                continue
            cells = self._split_row(line)
            if len(cells) >= 11:
                return cells[10]
            return _GENESIS_HASH
        return _GENESIS_HASH

    @staticmethod
    def _compute_entry_hash(
        *,
        prompt_id: str,
        status: str,
        timestamp: str,
        prev_hash: str,
    ) -> str:
        payload = f"{prompt_id}|{status}|{timestamp}|{prev_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _locate_status_section(lines: list[str]) -> tuple[int, int] | None:
        start_idx = -1
        end_idx = len(lines)
        for idx, line in enumerate(lines):
            if line.strip() == _STATUS_SECTION_HEADER:
                start_idx = idx
                break
        if start_idx < 0:
            return None
        for idx in range(start_idx + 1, len(lines)):
            if lines[idx].startswith("## "):
                end_idx = idx
                break
        return start_idx, end_idx

    @staticmethod
    def successful_prompts(status_map: dict[str, PromptStatus]) -> set[str]:
        return {prompt_id for prompt_id, status in status_map.items() if status == PromptStatus.SUCCESS}

    @staticmethod
    def has_success(status_map: dict[str, PromptStatus], prompt_id: str) -> bool:
        return status_map.get(prompt_id) == PromptStatus.SUCCESS

    @staticmethod
    def statuses_for(prompts: Iterable[PromptDefinition], status_map: dict[str, PromptStatus]) -> dict[str, PromptStatus]:
        return {prompt.prompt_id: status_map.get(prompt.prompt_id, PromptStatus.PENDING) for prompt in prompts}
