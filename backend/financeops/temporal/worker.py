from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from financeops.config import settings
from financeops.temporal.client import get_temporal_client
from financeops.temporal.fx_activities import (
    fx_fetch_activity,
    fx_month_end_apply_activity,
)
from financeops.temporal.fx_workflows import FxFetchWorkflow, FxMonthEndApplyWorkflow
from financeops.temporal.fixed_assets_activities import (
    fixed_assets_apply_impairment_disposal_activity,
    fixed_assets_build_journal_preview_activity,
    fixed_assets_finalize_activity,
    fixed_assets_generate_depreciation_schedule_activity,
    fixed_assets_load_assets_activity,
    fixed_assets_mark_running_activity,
    fixed_assets_validate_lineage_activity,
)
from financeops.temporal.fixed_assets_workflows import FixedAssetsWorkflow
from financeops.temporal.lease_activities import (
    lease_build_journal_preview_activity,
    lease_build_payment_timeline_activity,
    lease_calculate_present_value_activity,
    lease_finalize_activity,
    lease_generate_liability_schedule_activity,
    lease_generate_rou_schedule_activity,
    lease_load_leases_and_payments_activity,
    lease_mark_running_activity,
    lease_validate_lineage_activity,
)
from financeops.temporal.lease_workflows import LeaseAccountingWorkflow
from financeops.temporal.prepaid_activities import (
    prepaid_build_journal_preview_activity,
    prepaid_finalize_activity,
    prepaid_generate_amortization_schedule_activity,
    prepaid_load_prepaids_activity,
    prepaid_mark_running_activity,
    prepaid_resolve_amortization_pattern_activity,
    prepaid_validate_lineage_activity,
)
from financeops.temporal.prepaid_workflows import PrepaidAmortizationWorkflow
from financeops.temporal.revenue_activities import (
    revenue_allocate_contract_value_activity,
    revenue_build_journal_preview_activity,
    revenue_finalize_activity,
    revenue_generate_revenue_schedule_activity,
    revenue_load_contracts_and_obligations_activity,
    revenue_mark_running_activity,
    revenue_validate_lineage_activity,
)
from financeops.temporal.revenue_workflows import RevenueRecognitionWorkflow
from financeops.platform.temporal.tenant_migration_activities import (
    tenant_migration_finalize_activity,
    tenant_migration_mark_running_activity,
)
from financeops.platform.temporal.tenant_migration_workflows import TenantMigrationWorkflow
from financeops.platform.temporal.tenant_onboarding_activities import (
    tenant_onboarding_finalize_activity,
    tenant_onboarding_validate_activity,
)
from financeops.platform.temporal.tenant_onboarding_workflows import (
    TenantOnboardingWorkflow,
)
from financeops.temporal.consolidation_activities import (
    consolidation_aggregate_results_activity,
    consolidation_apply_fx_activity,
    consolidation_compute_eliminations_activity,
    consolidation_finalize_activity,
    consolidation_mark_running_activity,
    consolidation_match_ic_activity,
    consolidation_prepare_entities_activity,
)
from financeops.temporal.consolidation_workflows import ConsolidationWorkflow
from financeops.temporal.workflows import RuntimeProbeWorkflow

log = logging.getLogger(__name__)


async def run_temporal_worker() -> None:
    """
    Start the base Temporal worker for FinanceOps runtime workflows.
    """
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[
            RuntimeProbeWorkflow,
            FxFetchWorkflow,
            FxMonthEndApplyWorkflow,
            ConsolidationWorkflow,
            RevenueRecognitionWorkflow,
            LeaseAccountingWorkflow,
            PrepaidAmortizationWorkflow,
            FixedAssetsWorkflow,
            TenantOnboardingWorkflow,
            TenantMigrationWorkflow,
        ],
        activities=[
            fx_fetch_activity,
            fx_month_end_apply_activity,
            consolidation_mark_running_activity,
            consolidation_prepare_entities_activity,
            consolidation_apply_fx_activity,
            consolidation_match_ic_activity,
            consolidation_compute_eliminations_activity,
            consolidation_aggregate_results_activity,
            consolidation_finalize_activity,
            revenue_mark_running_activity,
            revenue_load_contracts_and_obligations_activity,
            revenue_allocate_contract_value_activity,
            revenue_generate_revenue_schedule_activity,
            revenue_build_journal_preview_activity,
            revenue_validate_lineage_activity,
            revenue_finalize_activity,
            lease_mark_running_activity,
            lease_load_leases_and_payments_activity,
            lease_build_payment_timeline_activity,
            lease_calculate_present_value_activity,
            lease_generate_liability_schedule_activity,
            lease_generate_rou_schedule_activity,
            lease_build_journal_preview_activity,
            lease_validate_lineage_activity,
            lease_finalize_activity,
            prepaid_mark_running_activity,
            prepaid_load_prepaids_activity,
            prepaid_resolve_amortization_pattern_activity,
            prepaid_generate_amortization_schedule_activity,
            prepaid_build_journal_preview_activity,
            prepaid_validate_lineage_activity,
            prepaid_finalize_activity,
            fixed_assets_mark_running_activity,
            fixed_assets_load_assets_activity,
            fixed_assets_generate_depreciation_schedule_activity,
            fixed_assets_apply_impairment_disposal_activity,
            fixed_assets_build_journal_preview_activity,
            fixed_assets_validate_lineage_activity,
            fixed_assets_finalize_activity,
            tenant_onboarding_validate_activity,
            tenant_onboarding_finalize_activity,
            tenant_migration_mark_running_activity,
            tenant_migration_finalize_activity,
        ],
    )
    log.info(
        "Temporal worker started: address=%s namespace=%s task_queue=%s",
        settings.TEMPORAL_ADDRESS,
        settings.TEMPORAL_NAMESPACE,
        settings.TEMPORAL_TASK_QUEUE,
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_temporal_worker())


if __name__ == "__main__":
    main()
