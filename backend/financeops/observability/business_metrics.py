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
