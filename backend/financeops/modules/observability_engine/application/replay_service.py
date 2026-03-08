from __future__ import annotations

from financeops.modules.cash_flow_engine.domain.value_objects import CashFlowRunTokenInput
from financeops.modules.cash_flow_engine.infrastructure.token_builder import build_cash_flow_run_token
from financeops.modules.equity_engine.domain.value_objects import EquityRunTokenInput
from financeops.modules.equity_engine.infrastructure.token_builder import build_equity_run_token


class ReplayService:
    def recompute_run_token(self, *, module_code: str, row: object) -> str:
        if module_code == "equity_engine":
            return build_equity_run_token(
                EquityRunTokenInput(
                    tenant_id=row.tenant_id,
                    organisation_id=row.organisation_id,
                    reporting_period=row.reporting_period,
                    statement_definition_version_token=row.statement_definition_version_token,
                    line_definition_version_token=row.line_definition_version_token,
                    rollforward_rule_version_token=row.rollforward_rule_version_token,
                    source_mapping_version_token=row.source_mapping_version_token,
                    consolidation_run_ref_nullable=str(row.consolidation_run_ref_nullable)
                    if row.consolidation_run_ref_nullable
                    else None,
                    fx_translation_run_ref_nullable=str(row.fx_translation_run_ref_nullable)
                    if row.fx_translation_run_ref_nullable
                    else None,
                    ownership_consolidation_run_ref_nullable=str(row.ownership_consolidation_run_ref_nullable)
                    if row.ownership_consolidation_run_ref_nullable
                    else None,
                    run_status=str(row.run_status),
                )
            )
        if module_code == "cash_flow_engine":
            return build_cash_flow_run_token(
                CashFlowRunTokenInput(
                    tenant_id=row.tenant_id,
                    organisation_id=row.organisation_id,
                    reporting_period=row.reporting_period,
                    statement_definition_version_token=row.statement_definition_version_token,
                    line_mapping_version_token=row.line_mapping_version_token,
                    bridge_rule_version_token=row.bridge_rule_version_token,
                    source_consolidation_run_ref=str(row.source_consolidation_run_ref),
                    source_fx_translation_run_ref_nullable=str(row.source_fx_translation_run_ref_nullable)
                    if row.source_fx_translation_run_ref_nullable
                    else None,
                    source_ownership_consolidation_run_ref_nullable=str(
                        row.source_ownership_consolidation_run_ref_nullable
                    )
                    if row.source_ownership_consolidation_run_ref_nullable
                    else None,
                    run_status=str(row.run_status),
                )
            )
        raise ValueError(f"replay validation is not supported for module {module_code}")
