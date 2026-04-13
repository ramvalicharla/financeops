from __future__ import annotations

import importlib
from pathlib import Path


def test_set_rls_context_not_importable_from_session() -> None:
    """set_rls_context is removed from db.session - use rls module."""
    session_mod = importlib.import_module("financeops.db.session")
    assert not hasattr(session_mod, "set_rls_context")
    assert not hasattr(session_mod, "clear_rls_context")


def test_canonical_rls_functions_importable_from_rls() -> None:
    """set_tenant_context and clear_tenant_context import cleanly."""
    from financeops.db.rls import clear_tenant_context, set_tenant_context

    assert callable(set_tenant_context)
    assert callable(clear_tenant_context)


def test_no_rls_context_calls_in_codebase() -> None:
    """No source file uses the deprecated set_rls_context name."""
    root = Path(__file__).parent.parent / "financeops"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "set_rls_context" in line or "clear_rls_context" in line:
                hits.append(f"{path}:{lineno}: {line}")
    assert not hits, (
        "Deprecated RLS function names still in use:\n"
        + "\n".join(hits)
    )

