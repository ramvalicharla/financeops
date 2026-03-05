from __future__ import annotations

from pathlib import Path

import pytest

from financeops.prompt_engine.prompt_loader import PromptLoader


def test_prompt_loader_parses_markdown_table(tmp_path: Path) -> None:
    catalog = tmp_path / "PROMPTS_CATALOG.md"
    catalog.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text |",
                "|---|---|---|---|",
                "| FINOS-P001 | Auth | None | Build auth |",
                "| FINOS-P002 | RBAC | FINOS-P001 | Build rbac |",
            ]
        ),
        encoding="utf-8",
    )

    loaded = PromptLoader(catalog).load()
    assert len(loaded.prompts) == 2
    assert loaded.prompts[0].prompt_id == "FINOS-P001"
    assert loaded.prompts[0].dependencies == []
    assert loaded.prompts[1].dependencies == ["FINOS-P001"]


def test_prompt_loader_rejects_duplicate_prompt_ids(tmp_path: Path) -> None:
    catalog = tmp_path / "PROMPTS_CATALOG.md"
    catalog.write_text(
        "\n".join(
            [
                "| Prompt ID | Subsystem | Dependencies | Prompt Text |",
                "|---|---|---|---|",
                "| FINOS-P001 | Auth | None | Build auth |",
                "| FINOS-P001 | Auth2 | None | Build auth2 |",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate Prompt ID"):
        PromptLoader(catalog).load()


def test_prompt_loader_parses_structured_catalog_blocks(tmp_path: Path) -> None:
    catalog = tmp_path / "PROMPTS_CATALOG.md"
    catalog.write_text(
        "\n".join(
            [
                "# FINOS Prompt Catalog",
                "",
                "PROMPT_ID: FINOS-P001",
                "SUBSYSTEM: Auth",
                "DEPENDENCIES: None",
                "",
                "PROMPT_TEXT:",
                "Placeholder prompt for initial pipeline validation.",
                "",
                "PROMPT_ID: FINOS-P002",
                "SUBSYSTEM: Multi-Tenant",
                "DEPENDENCIES: FINOS-P001",
                "",
                "PROMPT_TEXT:",
                "Placeholder prompt for tenant isolation implementation.",
            ]
        ),
        encoding="utf-8",
    )

    loaded = PromptLoader(catalog).load()
    assert len(loaded.prompts) == 2
    assert loaded.prompts[0].prompt_id == "FINOS-P001"
    assert loaded.prompts[0].subsystem == "Auth"
    assert loaded.prompts[0].dependencies == []
    assert loaded.prompts[1].prompt_id == "FINOS-P002"
    assert loaded.prompts[1].dependencies == ["FINOS-P001"]
