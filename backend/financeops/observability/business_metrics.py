from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Tenant metrics
active_tenants_gauge = Gauge(
    "financeops_active_tenants_total",
    "Number of tenants with at least one active session",
)

tenant_registrations_counter = Counter(
    "financeops_tenant_registrations_total",
    "Total tenant registrations",
    ["tenant_type"],
)

# Credit metrics
credits_consumed_counter = Counter(
    "financeops_credits_consumed_total_events",
    "Total credits consumed",
    ["task_type", "tenant_type"],
)

credits_reserved_gauge = Gauge(
    "financeops_credits_reserved_current",
    "Credits currently reserved (not yet confirmed or released)",
)

# AI cost metrics
ai_cost_counter = Counter(
    "financeops_ai_cost_usd_total_events",
    "Total AI cost in USD",
    ["provider", "model", "task_type"],
)

ai_tokens_counter = Counter(
    "financeops_ai_tokens_total",
    "Total AI tokens consumed",
    ["provider", "model", "token_type"],
)

ai_pipeline_duration_histogram = Histogram(
    "financeops_ai_pipeline_duration_ms",
    "AI pipeline end-to-end duration in milliseconds",
    ["task_type", "stage_4_triggered"],
    buckets=[100, 500, 1000, 2000, 5000, 10000, 30000],
)

ai_fallback_counter = Counter(
    "financeops_ai_fallback_total",
    "AI fallback events (primary model unavailable)",
    ["from_provider", "to_provider", "reason"],
)

ai_cache_hit_counter = Counter(
    "financeops_ai_cache_hits_total",
    "AI response cache hits",
    ["task_type"],
)

# Task metrics
task_queue_depth_gauge = Gauge(
    "financeops_celery_queue_depth",
    "Current Celery queue depth",
    ["queue_name"],
)

task_duration_histogram = Histogram(
    "financeops_task_duration_ms",
    "Celery task duration",
    ["task_name", "status"],
    buckets=[100, 500, 1000, 5000, 15000, 60000, 300000],
)

# ERP sync metrics
erp_sync_counter = Counter(
    "financeops_erp_sync_total",
    "ERP sync runs",
    ["connector_type", "status"],
)

erp_sync_records_counter = Counter(
    "financeops_erp_sync_records_total",
    "Records synced from ERP connectors",
    ["connector_type"],
)

# Workflow metrics
workflow_started_counter = Counter(
    "financeops_workflow_started_total",
    "Temporal workflows started",
    ["workflow_type"],
)

workflow_completed_counter = Counter(
    "financeops_workflow_completed_total",
    "Temporal workflows completed",
    ["workflow_type", "status"],
)

# API observability metrics
api_request_counter = Counter(
    "financeops_api_requests_total",
    "Total API requests",
    ["method", "path", "status_code"],
)

api_error_counter = Counter(
    "financeops_api_errors_total",
    "Total API error responses",
    ["method", "path", "status_code"],
)

api_request_latency_ms = Histogram(
    "financeops_api_request_latency_ms",
    "API request latency in milliseconds",
    ["method", "path"],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

# Finance workflow timings/signals (p50/p95/p99 derived by Prometheus over histogram)
finance_workflow_duration_ms = Histogram(
    "financeops_finance_workflow_duration_ms",
    "Finance workflow duration in milliseconds",
    ["workflow", "status"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
)

finance_workflow_counter = Counter(
    "financeops_finance_workflow_total",
    "Finance workflow run count",
    ["workflow", "status"],
)

# ERP sync observability
erp_sync_duration_ms = Histogram(
    "financeops_erp_sync_duration_ms",
    "ERP sync request duration in milliseconds",
    ["operation", "status"],
    buckets=[25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
)

# Governance observability
governance_operation_counter = Counter(
    "financeops_governance_operations_total",
    "Governance operation count",
    ["operation", "status"],
)

close_readiness_failures_counter = Counter(
    "financeops_close_readiness_failures_total",
    "Close readiness failures",
    ["reason"],
)

close_checklist_blockers_gauge = Gauge(
    "financeops_close_checklist_blockers_current",
    "Current checklist blockers count",
    ["tenant_id", "entity_id"],
)

# AI observability
ai_anomaly_generation_counter = Counter(
    "financeops_ai_anomaly_generation_total",
    "AI anomaly generation events",
    ["status"],
)

ai_narrative_duration_ms = Histogram(
    "financeops_ai_narrative_duration_ms",
    "AI narrative generation duration in milliseconds",
    ["status"],
    buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
)

ai_recommendation_failures_counter = Counter(
    "financeops_ai_recommendation_failures_total",
    "AI recommendation generation failures",
    ["reason"],
)

# Alert-ready counters
auth_failure_counter = Counter(
    "financeops_auth_failures_total",
    "Authentication/authorization failures",
    ["failure_type"],
)

upload_validation_failure_counter = Counter(
    "financeops_upload_validation_failures_total",
    "Upload validation failures",
    ["module"],
)

job_success_count = Counter(
    "financeops_job_success_count",
    "Successful governed job executions",
)

job_failure_count = Counter(
    "financeops_job_failure_count",
    "Failed governed job executions",
)

airlock_failure_count = Counter(
    "financeops_airlock_failure_count",
    "Airlock validation or admission failures",
)

job_duration_ms = Histogram(
    "financeops_job_duration_ms",
    "Governed job execution duration in milliseconds",
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
)
