from __future__ import annotations

import importlib

import pytest


def test_erp_integration_module_not_importable_after_cleanup() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("financeops.api.v1.erp")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("financeops.modules.erp_integration")
