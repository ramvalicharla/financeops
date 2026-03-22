from __future__ import annotations


def test_erp_sync_module_importable() -> None:
    from financeops.modules.erp_sync.api.router import router

    assert router is not None
