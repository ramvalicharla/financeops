from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from financeops.prompt_engine import PromptDefinition
from financeops.prompt_engine.prompt_governance import normalize_risk

log = logging.getLogger(__name__)


@dataclass(slots=True)
class PromptCatalog:
    prompts: list[PromptDefinition]


class PromptLoader:
    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path

    def load(self) -> PromptCatalog:
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Prompt catalog not found: {self.catalog_path}")

        content = self.catalog_path.read_text(encoding="utf-8")
        prompts = self._parse_markdown_table(content)
        if not prompts:
            prompts = self._parse_structured_blocks(content)
        if not prompts:
            raise ValueError(
                f"No prompts found in catalog: {self.catalog_path}. "
                "Expected markdown table or structured Prompt ID blocks."
            )

        ids = [p.prompt_id for p in prompts]
        dupes = sorted({item for item in ids if ids.count(item) > 1})
        if dupes:
            raise ValueError(f"Duplicate Prompt ID(s) in catalog: {', '.join(dupes)}")
        return PromptCatalog(prompts=prompts)

    def _parse_markdown_table(self, content: str) -> list[PromptDefinition]:
        lines = content.splitlines()
        prompts: list[PromptDefinition] = []
        header_idx = -1
        col_map: dict[str, int] = {}

        for idx, line in enumerate(lines):
            if "|" not in line:
                continue
            columns = [self._normalize_column_name(cell) for cell in line.strip().strip("|").split("|")]
            required = {"prompt_id", "subsystem", "dependencies", "prompt_text"}
            if required.issubset(set(columns)):
                header_idx = idx
                col_map = {name: columns.index(name) for name in required}
                optional = {
                    "title",
                    "risk",
                    "description",
                    "acceptance_criteria",
                    "files_expected",
                }
                for column_name in optional:
                    if column_name in columns:
                        col_map[column_name] = columns.index(column_name)
                break

        if header_idx < 0 or header_idx + 1 >= len(lines):
            return []

        for row in lines[header_idx + 2 :]:
            text = row.strip()
            if not text.startswith("|") or text.count("|") < 4:
                break
            cells = [cell.strip() for cell in text.strip("|").split("|")]
            max_idx = max(col_map.values())
            if len(cells) <= max_idx:
                continue

            prompt_id = cells[col_map["prompt_id"]]
            subsystem = cells[col_map["subsystem"]]
            dependencies = self._parse_dependencies(cells[col_map["dependencies"]])
            prompt_text = cells[col_map["prompt_text"]].replace("<br>", "\n").strip()
            title = self._optional_cell(cells, col_map, "title", subsystem)
            description = self._optional_cell(cells, col_map, "description", "")
            acceptance_criteria = self._optional_cell(cells, col_map, "acceptance_criteria", "")
            files_expected = self._parse_files_expected(
                self._optional_cell(cells, col_map, "files_expected", "")
            )
            risk = normalize_risk(
                prompt_id=prompt_id,
                raw_risk=self._optional_cell(cells, col_map, "risk", None),
                logger=log,
            )
            if not prompt_id or not subsystem:
                continue

            prompts.append(
                PromptDefinition(
                    prompt_id=prompt_id,
                    subsystem=subsystem,
                    dependencies=dependencies,
                    prompt_text=prompt_text,
                    title=title,
                    risk=risk,
                    description=description,
                    acceptance_criteria=acceptance_criteria,
                    files_expected=files_expected,
                )
            )

        return prompts

    def _parse_structured_blocks(self, content: str) -> list[PromptDefinition]:
        prompts: list[PromptDefinition] = []
        block_pattern = re.compile(
            r"(?im)^\s*(?:PROMPT[_ ]ID|Prompt ID):\s*(?P<prompt_id>[^\n]+)\s*$"
        )
        starts = [match.start() for match in block_pattern.finditer(content)]
        if not starts:
            return []

        starts.append(len(content))
        for idx in range(len(starts) - 1):
            block = content[starts[idx] : starts[idx + 1]]
            prompt_id = self._extract_line_field(
                block, ["PROMPT_ID", "Prompt ID"]
            )
            subsystem = self._extract_line_field(
                block, ["SUBSYSTEM", "Subsystem"]
            )
            dependencies = self._parse_dependencies(
                self._extract_line_field(block, ["DEPENDENCIES", "Dependencies"]) or ""
            )
            prompt_text = self._extract_prompt_text(block)
            title = self._extract_line_field(block, ["TITLE", "Title"]) or subsystem or ""
            description = self._extract_line_field(
                block, ["DESCRIPTION", "Description"]
            ) or ""
            acceptance_criteria = self._extract_line_field(
                block,
                ["ACCEPTANCE_CRITERIA", "Acceptance Criteria"],
            ) or ""
            files_expected = self._parse_files_expected(
                self._extract_line_field(block, ["FILES_EXPECTED", "Files Expected"]) or ""
            )
            risk = normalize_risk(
                prompt_id=prompt_id or "UNKNOWN",
                raw_risk=self._extract_line_field(block, ["RISK", "Risk"]),
                logger=log,
            )

            if not prompt_id or not subsystem or not prompt_text:
                continue
            prompts.append(
                PromptDefinition(
                    prompt_id=prompt_id.strip(),
                    subsystem=subsystem.strip(),
                    dependencies=dependencies,
                    prompt_text=prompt_text,
                    title=title.strip(),
                    risk=risk,
                    description=description.strip(),
                    acceptance_criteria=acceptance_criteria.strip(),
                    files_expected=files_expected,
                )
            )
        return prompts

    @staticmethod
    def _parse_dependencies(raw: str) -> list[str]:
        text = raw.strip()
        if not text or text.lower() in {"none", "n/a", "-"}:
            return []
        parts = re.split(r"[;,]", text)
        deps = [part.strip() for part in parts if part.strip()]
        return deps

    @staticmethod
    def _normalize_column_name(raw_name: str) -> str:
        normalized = raw_name.strip().lower().replace(" ", "_")
        normalized = normalized.replace("-", "_")
        return normalized

    @staticmethod
    def _optional_cell(
        cells: list[str], col_map: dict[str, int], key: str, default: str | None
    ) -> str | None:
        index = col_map.get(key)
        if index is None:
            return default
        if index >= len(cells):
            return default
        value = cells[index].strip()
        if not value:
            return default
        return value

    @staticmethod
    def _extract_line_field(block: str, keys: list[str]) -> str | None:
        for key in keys:
            pattern = re.compile(rf"(?im)^\s*{re.escape(key)}:\s*(?P<value>[^\n]*)\s*$")
            match = pattern.search(block)
            if match:
                return match.group("value").strip()
        return None

    @staticmethod
    def _extract_prompt_text(block: str) -> str:
        match = re.search(
            r"(?is)(?:PROMPT_TEXT|Prompt Text):\s*(?P<body>.*)\Z",
            block,
        )
        if not match:
            return ""
        text = match.group("body").strip()
        return text

    @staticmethod
    def _parse_files_expected(raw: str) -> list[str]:
        text = raw.strip()
        if not text:
            return []
        parts = re.split(r"[;,]", text)
        return sorted({part.strip() for part in parts if part.strip()})
