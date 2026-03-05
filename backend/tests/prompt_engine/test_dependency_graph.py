from __future__ import annotations

import pytest

from financeops.prompt_engine import PromptDefinition
from financeops.prompt_engine.dependency_graph import DependencyGraph


def test_dependency_graph_topological_order() -> None:
    prompts = [
        PromptDefinition("FINOS-P002", "RBAC", ["FINOS-P001"], "rbac"),
        PromptDefinition("FINOS-P001", "Auth", [], "auth"),
        PromptDefinition("FINOS-P003", "Audit", ["FINOS-P002"], "audit"),
    ]
    ordered = DependencyGraph(prompts).topological_order()
    assert [item.prompt_id for item in ordered] == [
        "FINOS-P001",
        "FINOS-P002",
        "FINOS-P003",
    ]


def test_dependency_graph_detects_cycles() -> None:
    prompts = [
        PromptDefinition("FINOS-P001", "A", ["FINOS-P002"], "a"),
        PromptDefinition("FINOS-P002", "B", ["FINOS-P001"], "b"),
    ]
    with pytest.raises(ValueError, match="Circular dependency"):
        DependencyGraph(prompts).topological_order()


def test_dependency_graph_detects_missing_dependency() -> None:
    prompts = [PromptDefinition("FINOS-P001", "A", ["FINOS-P404"], "a")]
    with pytest.raises(ValueError, match="Missing dependency"):
        DependencyGraph(prompts).topological_order()

