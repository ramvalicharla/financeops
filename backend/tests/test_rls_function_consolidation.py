from __future__ import annotations

import importlib
import subprocess


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
    result = subprocess.run(
        ["rg", "-n", "set_rls_context|clear_rls_context", "financeops/"],
        capture_output=True,
        text=True,
        cwd=".",
        check=False,
    )
    assert result.stdout == "", (
        "Deprecated RLS function names still in use:\n"
        f"{result.stdout}"
    )

