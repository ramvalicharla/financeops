from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from financeops.prompt_engine import PromptDefinition


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
            columns = [cell.strip().lower() for cell in line.strip().strip("|").split("|")]
            required = {"prompt id", "subsystem", "dependencies", "prompt text"}
            if required.issubset(set(columns)):
                header_idx = idx
                col_map = {name: columns.index(name) for name in required}
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

            prompt_id = cells[col_map["prompt id"]]
            subsystem = cells[col_map["subsystem"]]
            dependencies = self._parse_dependencies(cells[col_map["dependencies"]])
            prompt_text = cells[col_map["prompt text"]].replace("<br>", "\n").strip()
            if not prompt_id or not subsystem:
                continue

            prompts.append(
                PromptDefinition(
                    prompt_id=prompt_id,
                    subsystem=subsystem,
                    dependencies=dependencies,
                    prompt_text=prompt_text,
                )
            )

        return prompts

    def _parse_structured_blocks(self, content: str) -> list[PromptDefinition]:
        pattern = re.compile(
            r"(?:^|\n)\s*(?:PROMPT[_ ]ID|Prompt ID):\s*(?P<prompt_id>[^\n]+)\n"
            r"\s*(?:SUBSYSTEM|Subsystem):\s*(?P<subsystem>[^\n]+)\n"
            r"\s*(?:DEPENDENCIES|Dependencies):\s*(?P<dependencies>[^\n]*)\n"
            r"(?:\s*\n)*\s*(?:PROMPT_TEXT|Prompt Text):\s*(?P<prompt_text>.*?)"
            r"(?=\n\s*(?:PROMPT[_ ]ID|Prompt ID):|\Z)",
            re.DOTALL | re.IGNORECASE | re.MULTILINE,
        )
        prompts: list[PromptDefinition] = []
        for match in pattern.finditer(content):
            prompts.append(
                PromptDefinition(
                    prompt_id=match.group("prompt_id").strip(),
                    subsystem=match.group("subsystem").strip(),
                    dependencies=self._parse_dependencies(match.group("dependencies")),
                    prompt_text=match.group("prompt_text").strip(),
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
