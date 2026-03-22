from __future__ import annotations

from financeops.modules.erp_sync.application.publish_service import DATASET_CONSUMPTION_MAP


def test_tds_reconciliation_consumption_includes_26as_and_ais() -> None:
    assert DATASET_CONSUMPTION_MAP["tds_register"] == "tds_reconciliation_register"
    assert DATASET_CONSUMPTION_MAP["form_26as"] == "tds_reconciliation_register"
    assert DATASET_CONSUMPTION_MAP["ais_register"] == "tds_reconciliation_register"
