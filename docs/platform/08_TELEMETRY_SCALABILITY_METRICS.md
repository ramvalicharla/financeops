# FinanceOps Platform â€” Telemetry, Scalability & Platform Metrics
> Version 1.0 | Status: Locked
> The nervous system of the platform. Without this you are flying blind.

---

## Table of Contents
1. [Philosophy & Architecture](#1-philosophy--architecture)
2. [Telemetry Pipeline](#2-telemetry-pipeline)
3. [Infrastructure Metrics](#3-infrastructure-metrics)
4. [Application Metrics](#4-application-metrics)
5. [Database Health Metrics](#5-database-health-metrics)
6. [AI Pipeline Telemetry](#6-ai-pipeline-telemetry)
7. [Business Metrics](#7-business-metrics)
8. [Product Analytics](#8-product-analytics)
9. [Security Telemetry](#9-security-telemetry)
10. [Tenant Health Scoring](#10-tenant-health-scoring)
11. [SLA Tracking](#11-sla-tracking)
12. [Scalability Architecture](#12-scalability-architecture)
13. [Capacity Planning](#13-capacity-planning)
14. [Cost Attribution](#14-cost-attribution)
15. [Data Pipeline Observability](#15-data-pipeline-observability)
16. [Alerting Hierarchy](#16-alerting-hierarchy)
17. [Vector Memory Telemetry](#17-vector-memory-telemetry)
18. [Dashboard Specifications](#18-dashboard-specifications)
19. [Implementation in Claude Code](#19-implementation-in-claude-code)

---

## 1. Philosophy & Architecture

### Core Principle
```
Measure everything. Store efficiently. Alert intelligently. Act proactively.

The platform must tell you:
â”œâ”€â”€ What is happening RIGHT NOW (real-time)
â”œâ”€â”€ What WILL happen if current trends continue (predictive)
â”œâ”€â”€ What SHOULD you do about it (prescriptive)
â””â”€â”€ What HAPPENED and why (historical/forensic)
```

### Three Audiences for Metrics
```
FOUNDER / CTO:
  Business health, platform health, cost vs revenue, tenant risk
  Cadence: Real-time dashboard + daily digest email

ENGINEERING TEAM:
  Service health, error rates, query performance, queue depths
  Cadence: Real-time alerts + weekly report

TENANTS (Finance Leaders):
  Their own platform usage, credits consumed, task history, SLA
  Cadence: In-app dashboard + monthly usage report
```

### Telemetry Stack
```
COLLECTION:
  OpenTelemetry SDK (Python + TypeScript) â€” unified collection layer
  Instruments: traces, metrics, logs from every service automatically

TRANSPORT:
  OpenTelemetry Collector (aggregates, batches, routes)
  â†’ Prometheus (metrics)
  â†’ Loki (logs)
  â†’ Tempo (traces)

STORAGE:
  Prometheus + Thanos (long-term metrics storage, 1 year retention)
  Loki (logs, 90 day retention hot, 1 year cold in R2)
  Tempo (traces, 30 day retention)
  TimescaleDB (business metrics, permanent retention)
  ClickHouse (product analytics events, permanent retention)

VISUALISATION:
  Grafana (infrastructure + application + AI metrics)
  Custom React dashboards (business metrics, tenant health)
  Metabase (self-serve analytics for founder + team)

ALERTING:
  Grafana Alerting â†’ PagerDuty (P0/P1) â†’ Slack (P2/P3) â†’ Email (P4)
```

---

## 2. Telemetry Pipeline

### Every Event Flows Through This Pipeline
```
EVENT SOURCES:
â”œâ”€â”€ FastAPI requests (every HTTP request)
â”œâ”€â”€ Celery tasks (every task start/complete/fail)
â”œâ”€â”€ Temporal workflows (every workflow state change)
â”œâ”€â”€ Database queries (slow query log, deadlocks)
â”œâ”€â”€ AI Gateway calls (every LLM call, every stage)
â”œâ”€â”€ File processing (upload, scan, parse, complete)
â”œâ”€â”€ Authentication events (login, logout, MFA, failure)
â”œâ”€â”€ Credit transactions (reserve, deduct, release)
â”œâ”€â”€ Payment events (via gateway webhooks)
â”œâ”€â”€ ERP sync events (start, complete, records synced)
â””â”€â”€ User actions (button clicks, form submits, module opens)

PIPELINE FLOW:
Service â†’ OpenTelemetry SDK â†’ OTel Collector
                                    â”œâ”€â”€ Metrics â†’ Prometheus
                                    â”œâ”€â”€ Logs â†’ Loki
                                    â”œâ”€â”€ Traces â†’ Tempo
                                    â””â”€â”€ Business Events â†’ TimescaleDB

INSTRUMENTATION RULES:
Every span must include:
  â”œâ”€â”€ correlation_id (from request middleware)
  â”œâ”€â”€ tenant_id (hashed for privacy in telemetry)
  â”œâ”€â”€ service_name
  â”œâ”€â”€ operation_name
  â”œâ”€â”€ duration_ms
  â”œâ”€â”€ status (success/failure/timeout)
  â””â”€â”€ error_type (if failure)
```

### OpenTelemetry Setup (Backend)
```python
# backend/telemetry/setup.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor

def setup_telemetry(app):
    # Traces
    tracer_provider = TracerProvider(
        resource=Resource(attributes={
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        })
    )
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    meter_provider = MeterProvider(
        metric_readers=[PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=settings.OTEL_ENDPOINT),
            export_interval_millis=10000
        )]
    )
    metrics.set_meter_provider(meter_provider)

    # Auto-instrument everything
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
```

---

## 3. Infrastructure Metrics

### What to Track Per Service
```
CPU:
  â”œâ”€â”€ cpu_usage_percent (per service, per container)
  â”œâ”€â”€ cpu_throttle_percent (are containers being throttled?)
  â””â”€â”€ Alert: >80% sustained for >5 minutes

MEMORY:
  â”œâ”€â”€ memory_usage_bytes (per service)
  â”œâ”€â”€ memory_usage_percent (vs limit)
  â”œâ”€â”€ memory_oom_kills_total (out of memory kills â€” critical)
  â””â”€â”€ Alert: >85% for >5 minutes, OOM kill = immediate P1

NETWORK:
  â”œâ”€â”€ network_bytes_in / network_bytes_out (per service)
  â”œâ”€â”€ network_errors_total
  â””â”€â”€ Alert: error rate >0.1%

DISK:
  â”œâ”€â”€ disk_usage_percent (per volume)
  â”œâ”€â”€ disk_iops (reads and writes)
  â”œâ”€â”€ disk_latency_ms
  â””â”€â”€ Alert: >80% usage, >50ms latency

CONTAINER HEALTH:
  â”œâ”€â”€ container_restarts_total (per service)
  â”œâ”€â”€ container_uptime_seconds
  â””â”€â”€ Alert: >2 restarts in 10 minutes = P1

RAILWAY / AWS METRICS:
  â”œâ”€â”€ Replicas running vs desired
  â”œâ”€â”€ Deployment success/failure
  â””â”€â”€ Alert: desired != running for >2 minutes
```

### Infrastructure Prometheus Metrics (Custom)
```python
# backend/telemetry/metrics.py
from opentelemetry import metrics

meter = metrics.get_meter("financeops.infrastructure")

# Request metrics
request_counter = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
    unit="1"
)

request_duration = meter.create_histogram(
    "http_request_duration_ms",
    description="HTTP request duration",
    unit="ms"
)

# Worker metrics
worker_task_counter = meter.create_counter(
    "celery_tasks_total",
    description="Total Celery tasks by status"
)

worker_task_duration = meter.create_histogram(
    "celery_task_duration_ms",
    description="Celery task duration"
)

queue_depth = meter.create_observable_gauge(
    "celery_queue_depth",
    callbacks=[get_queue_depths],
    description="Current queue depth per queue"
)

# File processing metrics
file_scan_duration = meter.create_histogram(
    "file_scan_duration_ms",
    description="ClamAV scan duration"
)

file_parse_duration = meter.create_histogram(
    "file_parse_duration_ms",
    description="Document parse duration"
)
```

---

## 4. Application Metrics

### API Performance Metrics
```
Per Endpoint:
  â”œâ”€â”€ request_rate (requests/second)
  â”œâ”€â”€ error_rate (4xx and 5xx separately)
  â”œâ”€â”€ latency_p50, latency_p95, latency_p99
  â”œâ”€â”€ timeout_rate
  â””â”€â”€ Alerts:
        p99 > 3s = P2 alert
        p99 > 10s = P1 alert
        error_rate > 1% = P2 alert
        error_rate > 5% = P1 alert

Per Tenant (aggregated):
  â”œâ”€â”€ requests_per_minute
  â”œâ”€â”€ error_rate
  â””â”€â”€ Alert if single tenant consuming >30% of platform capacity

GOLDEN SIGNALS (track always):
  Latency:    How long requests take
  Traffic:    How many requests per second
  Errors:     Rate of failing requests
  Saturation: How full your services are (CPU, memory, queue)
```

### Task Processing Metrics
```
Per Queue:
  â”œâ”€â”€ queue_depth (messages waiting)
  â”œâ”€â”€ consumer_count (workers processing)
  â”œâ”€â”€ processing_rate (tasks/minute)
  â”œâ”€â”€ p50/p95/p99 task duration
  â”œâ”€â”€ failure_rate
  â”œâ”€â”€ retry_rate
  â””â”€â”€ dead_letter_count

Per Task Type:
  â”œâ”€â”€ success_rate (lifetime and 24h window)
  â”œâ”€â”€ avg_duration_ms
  â”œâ”€â”€ credit_deduction_rate (are credits being deducted correctly?)
  â””â”€â”€ cancellation_rate

Alert thresholds:
  Queue depth > 100 for >5 minutes = P2
  Queue depth > 500 for >2 minutes = P1
  Task failure rate > 5% = P2
  Task failure rate > 20% = P1
  Dead letter queue > 0 = P3 (investigate)
  Dead letter queue > 10 = P2
```

### Temporal Workflow Metrics
```
â”œâ”€â”€ workflows_running (currently active)
â”œâ”€â”€ workflows_completed_total
â”œâ”€â”€ workflows_failed_total
â”œâ”€â”€ workflow_duration_p50/p95/p99 (per workflow type)
â”œâ”€â”€ activity_timeout_total (per activity)
â”œâ”€â”€ workflows_stuck_total (running > expected max duration)

Alert:
  Stuck workflows > 0 = P2 (investigate immediately)
  Workflow failure rate > 2% = P2
  Activity timeout rate > 1% = P2
```

---

## 5. Database Health Metrics

### PostgreSQL Metrics (Critical â€” Most Failures Start Here)
```
CONNECTION POOL:
  â”œâ”€â”€ pg_connections_active
  â”œâ”€â”€ pg_connections_idle
  â”œâ”€â”€ pg_connections_waiting (waiting for connection = danger)
  â”œâ”€â”€ pg_connections_max
  â””â”€â”€ Alert: waiting > 0 for >30 seconds = P1

QUERY PERFORMANCE:
  â”œâ”€â”€ pg_slow_queries_total (queries >1s)
  â”œâ”€â”€ pg_query_duration_p50/p95/p99
  â”œâ”€â”€ pg_deadlocks_total
  â”œâ”€â”€ pg_lock_waits_total
  â””â”€â”€ Alerts:
        slow queries > 10/minute = P2
        deadlock detected = P2
        any query >5s = P2 (log the query)
        any query >30s = P1 (kill + alert)

INDEX HEALTH:
  â”œâ”€â”€ pg_index_bloat_ratio (per table)
  â”œâ”€â”€ pg_table_bloat_ratio
  â”œâ”€â”€ pg_seq_scans_total (sequential scans on large tables = missing index)
  â””â”€â”€ Alert: seq scan on table >10K rows = P3 (add index)

REPLICATION (when replica added):
  â”œâ”€â”€ pg_replication_lag_bytes
  â”œâ”€â”€ pg_replication_lag_seconds
  â””â”€â”€ Alert: lag > 30 seconds = P1

STORAGE:
  â”œâ”€â”€ pg_database_size_bytes (per database)
  â”œâ”€â”€ pg_table_size_bytes (top 20 largest tables)
  â”œâ”€â”€ pg_index_size_bytes
  â””â”€â”€ Alert: database size >80% of allocated = P2

pgvector SPECIFIC:
  â”œâ”€â”€ vector_index_size_bytes (per tenant)
  â”œâ”€â”€ vector_query_duration_ms (similarity search latency)
  â”œâ”€â”€ vector_count_per_tenant (memory usage indicator)
  â””â”€â”€ Alert: vector query p99 > 500ms = P2 (rebuild index)
```

### Redis Metrics
```
â”œâ”€â”€ redis_memory_used_bytes vs maxmemory
â”œâ”€â”€ redis_connected_clients
â”œâ”€â”€ redis_commands_per_second
â”œâ”€â”€ redis_keyspace_hits vs misses (cache hit rate)
â”œâ”€â”€ redis_evicted_keys_total (eviction = memory pressure)
â”œâ”€â”€ redis_blocked_clients (BLPOP waiting)
â””â”€â”€ Alerts:
      memory > 85% = P1
      evictions > 0/minute = P2 (increase memory or fix caching)
      cache hit rate < 60% = P3 (review cache strategy)
```

---

## 6. AI Pipeline Telemetry

### Per Pipeline Run (Every LLM Call Tracked)
```python
# Stored in: ai_pipeline_runs table (TimescaleDB for time-series)
{
    "pipeline_run_id": "uuid",
    "tenant_id_hash": "sha256",        # privacy-safe
    "task_type": "variance_analysis",
    "module": "reporting",

    # Stage timings
    "stage1_duration_ms": 412,          # Preparation (local)
    "stage2_duration_ms": 1840,         # Execution
    "stage3_duration_ms": 1620,         # Validation
    "stage4_duration_ms": null,         # Correction (null if not triggered)
    "stage5_duration_ms": 290,          # Formatting
    "total_duration_ms": 4162,

    # Models used
    "stage1_model": "phi3:mini",
    "stage2_model": "claude-sonnet-4-5",
    "stage3_model": "gpt-4o-mini",
    "stage4_model": null,

    # Quality
    "validation_score": 0.97,           # Stage 3 agreement score
    "stage4_triggered": false,
    "human_feedback": "positive",       # positive / negative / null
    "human_corrected": false,

    # Cost
    "stage2_tokens_in": 1240,
    "stage2_tokens_out": 890,
    "stage2_cost_usd": 0.0032,
    "stage3_tokens_in": 980,
    "stage3_tokens_out": 340,
    "stage3_cost_usd": 0.0008,
    "total_ai_cost_usd": 0.0040,

    # Cache
    "cache_hit": false,                 # true if served from Redis cache

    # Context
    "from_vector_memory": true,         # was memory retrieved?
    "memory_chunks_retrieved": 3,

    "created_at": "2025-03-31T22:14:03Z"
}
```

### AI Metrics Dashboard (Grafana)
```
PIPELINE HEALTH (real-time):
  â”œâ”€â”€ Avg total pipeline duration (target: <5s)
  â”œâ”€â”€ Stage 4 trigger rate (target: <5%)
  â”œâ”€â”€ Validation agreement score avg (target: >95%)
  â”œâ”€â”€ Human acceptance rate (target: >90%)
  â”œâ”€â”€ Human correction rate (inverse of acceptance)
  â””â”€â”€ Cache hit rate (target: >40% for repeated queries)

COST TRACKING (daily/monthly):
  â”œâ”€â”€ Total AI cost today / this month
  â”œâ”€â”€ Cost by model (Claude / GPT / DeepSeek / Local)
  â”œâ”€â”€ Cost by task type (which tasks are most expensive)
  â”œâ”€â”€ Cost by tenant (top 10 most expensive tenants)
  â”œâ”€â”€ Local vs cloud ratio (target: >65% local)
  â””â”€â”€ Cost per credit (should be <$0.03 per credit)

MODEL PERFORMANCE OVER TIME:
  â”œâ”€â”€ Accuracy trend (human acceptance rate, 30-day rolling)
  â”œâ”€â”€ Latency trend (p95 per model, 30-day rolling)
  â”œâ”€â”€ Stage 4 trigger rate trend (should decrease as learning improves)
  â””â”€â”€ Model availability (uptime per API)

LEARNING EFFECTIVENESS:
  â”œâ”€â”€ Correction rate trend per tenant (should decrease month-over-month)
  â”œâ”€â”€ Signals captured this month (per tenant, per module)
  â”œâ”€â”€ Vector memory size growth (per tenant)
  â””â”€â”€ Classification accuracy improvement (monthly comparison)
```

### AI Cost Anomaly Detection
```python
# Celery Beat job â€” runs hourly
def detect_ai_cost_anomaly():
    """
    Alert if any tenant's AI cost is 3x their 30-day average.
    Could indicate: runaway loop, abuse, or inefficient prompting.
    """
    for tenant in get_active_tenants():
        hourly_cost = get_ai_cost_last_hour(tenant.id)
        avg_hourly_cost = get_avg_hourly_ai_cost_30d(tenant.id)

        if hourly_cost > avg_hourly_cost * 3:
            send_alert(
                severity="P2",
                title=f"AI cost anomaly: {tenant.name}",
                detail=f"Hourly cost ${hourly_cost:.2f} vs avg ${avg_hourly_cost:.2f}",
                action="Investigate and throttle if necessary"
            )
```

---

## 7. Business Metrics

### The Metrics That Tell You If You Have a Real Business

All stored in TimescaleDB (time-series) for historical trending.

```
REVENUE METRICS (computed daily):
  â”œâ”€â”€ MRR (Monthly Recurring Revenue)
  â”‚     = sum of active subscription monthly values
  â”œâ”€â”€ ARR (Annual Recurring Revenue) = MRR Ã— 12
  â”œâ”€â”€ New MRR (from new subscriptions this month)
  â”œâ”€â”€ Expansion MRR (upgrades + top-ups from existing tenants)
  â”œâ”€â”€ Contraction MRR (downgrades from existing tenants)
  â”œâ”€â”€ Churned MRR (from cancelled subscriptions)
  â””â”€â”€ Net New MRR = New + Expansion - Contraction - Churned

RETENTION METRICS:
  â”œâ”€â”€ NRR (Net Revenue Retention)
  â”‚     = (MRR end of month from cohort / MRR start of month from cohort) Ã— 100
  â”‚     Target: >110%
  â”œâ”€â”€ GRR (Gross Revenue Retention)
  â”‚     = (MRR end of month excluding expansion / MRR start) Ã— 100
  â”‚     Target: >90%
  â”œâ”€â”€ Logo Churn Rate = customers lost / customers start of month
  â”‚     Target: <2% monthly
  â””â”€â”€ Revenue Churn Rate = MRR lost / MRR start of month
        Target: <1.5% monthly

CUSTOMER METRICS:
  â”œâ”€â”€ Total active tenants
  â”œâ”€â”€ New tenants this month
  â”œâ”€â”€ Churned tenants this month
  â”œâ”€â”€ Tenants by tier (Starter/Pro/Business/Enterprise)
  â”œâ”€â”€ Tenants by geography (IN/AE/SG/AU/US/other)
  â””â”€â”€ Tenants by type (Corporate/CA Firm/SME)

UNIT ECONOMICS:
  â”œâ”€â”€ LTV (Lifetime Value) = ARPU / Monthly Churn Rate
  â”œâ”€â”€ CAC (Customer Acquisition Cost) = Sales+Marketing spend / New customers
  â”œâ”€â”€ LTV:CAC Ratio (target: >3x)
  â”œâ”€â”€ Payback Period = CAC / (ARPU Ã— Gross Margin %)
  â”‚     Target: <12 months
  â””â”€â”€ ARPU (Average Revenue Per Unit) = MRR / Active Tenants

CREDIT METRICS:
  â”œâ”€â”€ Credits sold this month (subscription + top-up)
  â”œâ”€â”€ Credits consumed this month
  â”œâ”€â”€ Credits expired this month
  â”œâ”€â”€ Top-up revenue as % of total revenue
  â”œâ”€â”€ Average top-up frequency per tenant
  â””â”€â”€ Credits consumed per tenant (identify heavy and light users)

ONBOARDING & SERVICES REVENUE:
  â”œâ”€â”€ Onboarding fees collected this month
  â”œâ”€â”€ Template design revenue this month
  â”œâ”€â”€ Marketplace revenue (platform's share)
  â””â”€â”€ Total services revenue as % of total revenue
```

### Business Metrics Computation (Celery Beat)
```python
# backend/telemetry/business_metrics.py
# Runs nightly at 00:05 UTC

@celery.task
def compute_daily_business_metrics():
    date = datetime.utcnow().date() - timedelta(days=1)

    metrics = {
        "date": date,
        "mrr": compute_mrr(),
        "arr": compute_mrr() * 12,
        "new_mrr": compute_new_mrr(date),
        "expansion_mrr": compute_expansion_mrr(date),
        "churned_mrr": compute_churned_mrr(date),
        "active_tenants": count_active_tenants(),
        "new_tenants": count_new_tenants(date),
        "churned_tenants": count_churned_tenants(date),
        "nrr": compute_nrr(date),
        "grr": compute_grr(date),
        "arpu": compute_arpu(),
        "credits_sold": sum_credits_sold(date),
        "credits_consumed": sum_credits_consumed(date),
        "credits_expired": sum_credits_expired(date),
        "ai_cost_total": sum_ai_cost(date),
        "compute_cost_total": estimate_compute_cost(date),
        "gross_margin_pct": compute_gross_margin(date),
    }

    # Store in TimescaleDB (append-only)
    insert_business_metrics(metrics)

    # Send daily digest to founder
    send_daily_digest_email(metrics)
```

### Daily Digest Email (Founder)
```
Subject: FinanceOps Daily â€” {date} | MRR: $X | NRR: X% | {emoji health indicator}

YESTERDAY'S HIGHLIGHTS:
  New tenants:        +3  (Total: 127)
  Churned tenants:    0
  New MRR added:      +$447
  Credits consumed:   18,430
  AI cost:            $184.30
  Gross margin:       79.4%

RUNNING TOTALS:
  MRR:                $24,890  (â†‘ 2.1% vs last month)
  ARR:                $298,680
  NRR (30d):          114%     âœ…
  Logo churn (30d):   0.8%     âœ…

ACTION REQUIRED:
  âš ï¸  Tenant "ABC Group" has not logged in for 18 days (churn risk)
  âš ï¸  3 tenants on Starter for >6 months (upgrade opportunity)
  âœ…  No P0/P1 incidents yesterday
```

---

## 8. Product Analytics

### What Users Actually Do (Behaviour Tracking)

```
EVENTS TO TRACK (frontend + backend):
Every event includes: tenant_id_hash, user_role, session_id, timestamp

ACTIVATION EVENTS (did they get value?):
  â”œâ”€â”€ first_mis_upload
  â”œâ”€â”€ first_reconciliation_run
  â”œâ”€â”€ first_consolidation_run
  â”œâ”€â”€ first_ai_query
  â”œâ”€â”€ first_report_generated
  â””â”€â”€ first_approval_workflow_complete
  Target: all 6 within 14 days of onboarding = "activated"

ENGAGEMENT EVENTS (are they using it?):
  â”œâ”€â”€ module_opened (which module, how often)
  â”œâ”€â”€ task_run (which task, credits used)
  â”œâ”€â”€ ai_query_submitted
  â”œâ”€â”€ report_downloaded
  â”œâ”€â”€ erp_sync_triggered
  â””â”€â”€ dashboard_viewed

FEATURE ADOPTION (which features are used):
  â”œâ”€â”€ features_enabled_per_tenant (% of available modules used)
  â”œâ”€â”€ ai_usage_rate (% of tenants using AI chat)
  â”œâ”€â”€ fdd_usage_rate (% of eligible tenants running FDD)
  â””â”€â”€ mobile_pwa_installs

FRICTION EVENTS (where users struggle):
  â”œâ”€â”€ upload_failed (type of failure)
  â”œâ”€â”€ task_cancelled (which task, how far through)
  â”œâ”€â”€ form_abandoned (which form, which field)
  â”œâ”€â”€ error_encountered (which error, which screen)
  â””â”€â”€ help_tooltip_opened (which screen â€” indicates confusion)

STORAGE:
  All events â†’ ClickHouse (columnar, fast aggregation)
  Retention: permanent (anonymised, hashed tenant IDs)
```

### Activation Funnel
```
Signup
  â†“ [Track: time to complete onboarding wizard]
First login
  â†“ [Track: time to first MIS upload]
First data upload
  â†“ [Track: time to first task run]
First AI query
  â†“ [Track: time to first report generated]
ACTIVATED â† (target: within 14 days)
  â†“ [Track: weekly active usage]
RETAINED â† (target: active in week 4 AND week 8)
  â†“ [Track: expansion signals]
EXPANDED â† (top-up credits or plan upgrade)
```

### Cohort Analysis (Monthly)
```
For each monthly cohort of new tenants, track at 30/60/90/180/365 days:
  â”œâ”€â”€ % still active
  â”œâ”€â”€ Average credits consumed
  â”œâ”€â”€ % who upgraded tier
  â”œâ”€â”€ % who ran FDD/PPA (premium module adoption)
  â””â”€â”€ Average ARPU vs initial ARPU

This tells you:
  Which cohorts have best retention (â†’ which acquisition channel works)
  When churn happens (â†’ where to invest in product)
  Which features drive expansion (â†’ what to build next)
```

---

## 9. Security Telemetry

### What to Monitor for Security Events
```
AUTHENTICATION ANOMALIES:
  â”œâ”€â”€ login_failure_rate per user (>5 failures in 10 min = lockout + alert)
  â”œâ”€â”€ login_from_new_country (alert user + log)
  â”œâ”€â”€ login_from_new_device (alert user + log)
  â”œâ”€â”€ mfa_bypass_attempts
  â”œâ”€â”€ concurrent_sessions_per_user (>3 = alert)
  â””â”€â”€ token_reuse_attempts (replayed JWT = immediate P1)

ACCESS PATTERN ANOMALIES:
  â”œâ”€â”€ api_calls_per_minute per tenant (>10x normal = alert)
  â”œâ”€â”€ bulk_data_export (large data download = log + alert)
  â”œâ”€â”€ off_hours_access (access at unusual hours for that user)
  â”œâ”€â”€ cross_tenant_access_attempt (RLS violation attempt = P0)
  â””â”€â”€ admin_endpoint_access (every platform admin call logged)

AI SECURITY EVENTS:
  â”œâ”€â”€ prompt_injection_detected (count per tenant per day)
  â”œâ”€â”€ pii_detected_in_query (masked, but count tracked)
  â”œâ”€â”€ jailbreak_attempt (immediate alert + log)
  â”œâ”€â”€ output_validation_failure (LLM output didn't match DB)
  â””â”€â”€ system_prompt_override_attempt

FILE SECURITY EVENTS:
  â”œâ”€â”€ malware_detected (quarantine + alert + investigation)
  â”œâ”€â”€ suspicious_file_type (wrong extension or magic bytes)
  â”œâ”€â”€ oversized_upload_attempt (>50MB blocked)
  â””â”€â”€ macro_detected_in_office_file

INFRASTRUCTURE SECURITY:
  â”œâ”€â”€ failed_db_connection_attempts
  â”œâ”€â”€ unusual_query_patterns (potential SQL injection despite parameterisation)
  â”œâ”€â”€ secrets_access_anomaly (unusual Doppler access)
  â””â”€â”€ container_privilege_escalation_attempt
```

### Security Score Dashboard
```
PLATFORM SECURITY SCORE: 94/100

Authentication:        âœ… 20/20
  MFA enforced for Manager+: âœ…
  JWT rotation working: âœ…
  Brute force protection: âœ…
  No failed logins >5 in 24h: âœ…

Data Protection:       âœ… 19/20
  Encryption at rest: âœ…
  TLS 1.3 in transit: âœ…
  PII masking in AI: âœ…
  RLS active on all tables: âœ…
  Field-level encryption (PII): âš ï¸ Partial

AI Security:           âœ… 15/15
  Injection detection: âœ…
  Output validation: âœ…
  Jailbreak logging: âœ…

File Security:         âœ… 20/20
  ClamAV scanning: âœ…
  Magic byte validation: âœ…
  Macro detection: âœ…

Infrastructure:        âœ… 20/25
  Cloudflare WAF: âœ…
  DDoS protection: âœ…
  Secret management: âœ…
  Container isolation: âœ…
  Network segmentation: âš ï¸ Planned
```

---

## 10. Tenant Health Scoring

### Churn Prediction (Computed Weekly Per Tenant)
```python
# backend/telemetry/tenant_health.py

def compute_tenant_health_score(tenant_id: str) -> TenantHealthScore:
    """
    Score 0-100. Below 40 = at risk. Below 20 = critical churn risk.
    Computed weekly via Celery Beat.
    """

    score = 100
    risk_factors = []
    positive_factors = []

    # NEGATIVE SIGNALS (reduce score)

    days_since_last_login = get_days_since_last_login(tenant_id)
    if days_since_last_login > 30:
        score -= 30
        risk_factors.append(f"No login in {days_since_last_login} days")
    elif days_since_last_login > 14:
        score -= 15
        risk_factors.append(f"No login in {days_since_last_login} days")

    credits_usage_rate = get_credit_usage_vs_allocation(tenant_id)
    if credits_usage_rate < 0.2:  # using <20% of allocated credits
        score -= 20
        risk_factors.append("Using <20% of allocated credits (low adoption)")

    modules_used = get_modules_used_count(tenant_id)
    modules_available = get_modules_available_count(tenant_id)
    if modules_used / modules_available < 0.3:
        score -= 15
        risk_factors.append("Using <30% of available modules")

    support_tickets_open = get_open_support_tickets(tenant_id)
    if support_tickets_open > 2:
        score -= 10
        risk_factors.append(f"{support_tickets_open} unresolved support issues")

    # POSITIVE SIGNALS (restore score)

    if get_has_completed_onboarding(tenant_id):
        positive_factors.append("Onboarding complete")
    else:
        score -= 10
        risk_factors.append("Onboarding not completed")

    if get_has_run_month_end_report(tenant_id):
        score = min(100, score + 5)
        positive_factors.append("Has generated month-end report")

    if get_nps_score(tenant_id) and get_nps_score(tenant_id) >= 8:
        score = min(100, score + 10)
        positive_factors.append("NPS promoter")

    if get_has_invited_team_members(tenant_id, min_count=3):
        score = min(100, score + 5)
        positive_factors.append("Team actively using platform (3+ users)")

    if get_used_ai_this_week(tenant_id):
        score = min(100, score + 5)
        positive_factors.append("Active AI usage this week")

    return TenantHealthScore(
        tenant_id=tenant_id,
        score=score,
        risk_level="critical" if score < 20 else "at_risk" if score < 40 else "healthy",
        risk_factors=risk_factors,
        positive_factors=positive_factors,
        recommended_action=get_recommended_action(score, risk_factors),
        computed_at=datetime.utcnow()
    )
```

### Tenant Health Dashboard (Founder View)
```
TENANT HEALTH OVERVIEW

ðŸŸ¢ Healthy (score 70-100):      89 tenants   (70%)
ðŸŸ¡ At Risk (score 40-69):       27 tenants   (21%)
ðŸ”´ Critical (score <40):        11 tenants   (9%)

CRITICAL TENANTS â€” ACTION REQUIRED:
  ABC Consulting      Score: 18  Last login: 34 days ago  â†’ Personal outreach today
  XYZ Group           Score: 22  Credits used: 8%         â†’ Onboarding call needed
  PQR CA Firm         Score: 31  0 reports generated      â†’ Demo offer sent?

AT RISK TENANTS â€” MONITOR:
  [list of 27 tenants with scores and top risk factor]

RECOMMENDED ACTIONS:
  11 tenants need personal outreach (founder/CS call)
  8 tenants need onboarding completion assistance
  5 tenants are candidates for upgrade conversation (high usage on Starter)
```

---

## 11. SLA Tracking

### SLA Definitions Per Tier
```
STARTER ($49/month):
  Uptime SLA:         99.5% monthly  (3.6 hours downtime allowed)
  Support response:   48 hours
  No credits for SLA breach (terms of service)

PROFESSIONAL ($149/month):
  Uptime SLA:         99.9% monthly  (43 minutes downtime allowed)
  Task completion:    95% of tasks complete within 2x expected duration
  Support response:   24 hours
  Credits for breach: 10% monthly subscription credit per 1% below SLA

BUSINESS ($449/month):
  Uptime SLA:         99.9% monthly
  Task completion:    99% within expected duration
  Support response:   8 hours
  AI pipeline SLA:    p95 < 8 seconds
  Credits for breach: 20% monthly credit per 1% below SLA

ENTERPRISE (Custom):
  Uptime SLA:         99.95% monthly (22 minutes downtime allowed)
  Task completion:    99.5% within expected duration
  Support response:   4 hours (business hours), 8 hours (off hours)
  AI pipeline SLA:    p95 < 5 seconds
  Dedicated SLA:      Custom in contract
```

### SLA Tracking Implementation
```python
# backend/telemetry/sla_tracker.py

class SLATracker:
    def record_downtime(self, start: datetime, end: datetime, affected_services: list):
        """Record an incident. Compute which tenants affected and SLA impact."""
        duration_minutes = (end - start).total_seconds() / 60
        affected_tenants = get_active_tenants_during(start, end)

        for tenant in affected_tenants:
            current_uptime = get_monthly_uptime_pct(tenant.id)
            if current_uptime < get_sla_threshold(tenant.subscription_tier):
                breach_amount = get_sla_threshold(tenant.tier) - current_uptime
                credits_owed = compute_sla_credit(tenant, breach_amount)
                issue_sla_credit(tenant.id, credits_owed, reason=f"SLA breach {breach_amount:.2f}%")
                notify_tenant_of_sla_credit(tenant, credits_owed)

    def get_monthly_report(self, tenant_id: str, month: date) -> SLAReport:
        return SLAReport(
            tenant_id=tenant_id,
            month=month,
            total_minutes=get_total_minutes_in_month(month),
            downtime_minutes=get_downtime_minutes(tenant_id, month),
            uptime_pct=compute_uptime_pct(tenant_id, month),
            sla_threshold=get_sla_threshold(tenant_id),
            sla_met=compute_uptime_pct(tenant_id, month) >= get_sla_threshold(tenant_id),
            credits_issued=get_sla_credits_issued(tenant_id, month),
            incidents=get_incidents(tenant_id, month)
        )
```

---

## 12. Scalability Architecture

### How Platform Scales Without Breaking

```
STATELESS EVERYTHING:
  Every FastAPI worker is identical and interchangeable.
  Any worker can handle any request.
  Scale horizontally: add more workers = more capacity.
  Zero shared in-process state.

SCALE TRIGGERS (automatic):
  CPU > 70% sustained 3 minutes â†’ add worker instance
  Queue depth > 50 tasks        â†’ add Celery worker
  p95 latency > 2s              â†’ add API worker
  Memory > 80%                  â†’ add worker instance

SCALE LIMITS (to prevent runaway costs):
  Max API workers:      10 (Railway config)
  Max Celery workers:   20 (per queue type)
  Max DB connections:   100 (via PgBouncer)
  Alert when hitting:   80% of any limit

SCALE STAGES:
Stage 1 (0-50 tenants):
  Railway single region, 2 API workers, 4 Celery workers
  PostgreSQL: Railway managed, 2 vCPU / 4GB RAM
  Redis: Upstash free tier

Stage 2 (50-200 tenants):
  Railway multi-worker, 4 API workers, 8 Celery workers
  PostgreSQL: Railway Pro or Supabase Pro
  Redis: Upstash Pro

Stage 3 (200-1,000 tenants):
  Migrate to AWS ECS (Fargate) for API + workers
  AWS RDS PostgreSQL (Multi-AZ for HA)
  AWS ElastiCache Redis
  Cloudflare load balancing

Stage 4 (1,000+ tenants):
  Multi-region deployment (India + UAE + Singapore)
  Read replicas per region
  Global CDN for static assets
  Tenant data residency enforcement (data stays in region)
```

### Database Scalability Path
```
NOW (0-200 tenants):
  Single PostgreSQL instance
  pgvector on same instance
  All data one database, RLS for isolation

200-500 tenants:
  Read replica added (reporting queries â†’ replica)
  pgvector moved to dedicated instance (vector search heavy)
  TimescaleDB for metrics (separate from app DB)

500-2,000 tenants:
  Connection pooling via PgBouncer (mandatory at this scale)
  Partition large tables by tenant_id + created_at
  Archival: move data >2 years to cold storage (Cloudflare R2)

2,000+ tenants:
  Evaluate: tenant sharding (each large tenant gets own schema/DB)
  Citus (distributed PostgreSQL) for horizontal scaling
  Separate OLAP (ClickHouse) from OLTP (PostgreSQL)
```

### Multi-Region Data Residency
```
INDIA TENANTS:
  Data stored in: AWS ap-south-1 (Mumbai)
  AI calls: local Ollama OR Anthropic API (data processed in India region)
  Backups: AWS ap-south-1 (never leaves India)
  Required by: DPDP Act (India Digital Personal Data Protection)

UAE TENANTS:
  Data stored in: AWS me-south-1 (Bahrain) or me-central-1 (UAE)
  Required by: UAE Data Protection Law (Federal Law No. 45 of 2021)

SINGAPORE TENANTS:
  Data stored in: AWS ap-southeast-1 (Singapore)
  Required by: PDPA (Personal Data Protection Act)

ROUTING:
  Cloudflare Workers at edge: detect tenant country from JWT
  Route API requests to correct regional deployment
  Tenant data NEVER crosses regional boundaries
```

---

## 13. Capacity Planning

### When to Scale â€” Proactive Triggers
```
COMPUTE:
  Current: 2 API workers
  Scale at: p95 API latency >1s for 10 minutes
  Scale to: add 2 workers
  Max before architecture change: 10 workers on Railway

DATABASE:
  Current: 2 vCPU / 4GB RAM PostgreSQL
  Scale at: CPU >70% or memory >80% or connections >80% of pool
  Scale to: 4 vCPU / 8GB RAM
  Trigger for read replica: query volume >500 queries/second

AI GATEWAY:
  Current: local Ollama + Claude API + GPT-4o
  Scale at: API rate limits hit >5 times/hour
  Scale to: add Groq API (fast inference) as additional model
  Cost review: monthly if AI cost >15% of revenue

STORAGE:
  Current: Cloudflare R2 (virtually unlimited, cheap)
  Review at: $200/month R2 cost (indicates significant volume)
  Action: implement file archival for files >6 months old

VECTOR MEMORY:
  Current: pgvector on main PostgreSQL
  Scale at: vector index size >10GB or search p99 >500ms
  Scale to: dedicated pgvector instance or Qdrant
```

### Capacity Forecast (Celery Beat â€” Weekly)
```python
# Runs every Monday morning â€” projects capacity needs 4 weeks out
def generate_capacity_forecast():
    trends = {
        "tenants_growth_rate": compute_weekly_tenant_growth_rate(),
        "api_request_growth": compute_weekly_api_growth_rate(),
        "storage_growth": compute_weekly_storage_growth_rate(),
        "ai_cost_growth": compute_weekly_ai_cost_growth(),
    }

    projections = {}
    for metric, rate in trends.items():
        current = get_current_value(metric)
        projections[metric] = {
            "week_2": current * (1 + rate) ** 2,
            "week_4": current * (1 + rate) ** 4,
            "week_8": current * (1 + rate) ** 8,
        }

    # Check if any projection breaches a threshold
    alerts = check_capacity_thresholds(projections)
    if alerts:
        send_capacity_planning_alert(alerts, projections)
```

---

## 14. Cost Attribution

### Exact Cost Per Tenant Per Month
```
COMPUTE COST ATTRIBUTION:
  Method: time-weighted API request share
  Tenant A made 15% of all API requests this month
  â†’ Tenant A attributed 15% of compute cost

AI COST ATTRIBUTION:
  Exact: every AI Gateway call logs cost per tenant
  Direct attribution: no estimation needed

STORAGE COST ATTRIBUTION:
  Exact: R2 storage and egress metered per tenant folder
  /data/{tenant_id_hash}/ â†’ exact bytes stored and served

DATABASE COST ATTRIBUTION:
  Estimated: by row count per tenant across all tables
  More precise: by query execution time per tenant (pg_stat_statements)

EMAIL COST ATTRIBUTION:
  Exact: SendGrid tracks sends per tenant (from API)

TOTAL COST PER TENANT:
  tenant_cost = compute_cost + ai_cost + storage_cost +
                db_cost_share + email_cost + payment_fee

MARGIN PER TENANT:
  tenant_margin = (tenant_revenue - tenant_cost) / tenant_revenue

FLAG: if tenant_margin < 65% â†’ investigate
      if tenant_margin < 50% â†’ immediate action (reprice or throttle)
```

### Cost Attribution Table (Founder Dashboard)
```
TENANT COST ATTRIBUTION â€” MARCH 2025

Tenant           Revenue    AI Cost  Compute  Storage  Total Cost  Margin
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ABC Group        $449       $48      $22      $8       $78         82.6% âœ…
XYZ CA Firm      $149       $12      $8       $3       $23         84.6% âœ…
PQR Corp         $449       $89      $31      $15      $135        69.9% âš ï¸
Heavy User Co    $149       $67      $28      $12      $107        28.2% ðŸ”´

ACTION: Heavy User Co â€” consuming 3x expected AI for Professional tier.
  Option 1: Upgrade conversation (they need Business tier)
  Option 2: Apply AI usage cap until upgrade
  Option 3: Reprice credits for their usage pattern
```

---

## 15. Data Pipeline Observability

### ERP Sync Monitoring
```
Per ERP connector, per tenant, per sync run:
  â”œâ”€â”€ sync_id (uuid)
  â”œâ”€â”€ connector_type (tally/zoho/qbo/etc)
  â”œâ”€â”€ tenant_id
  â”œâ”€â”€ sync_type (scheduled/manual)
  â”œâ”€â”€ started_at
  â”œâ”€â”€ completed_at
  â”œâ”€â”€ duration_ms
  â”œâ”€â”€ records_fetched (TB rows, GL entries)
  â”œâ”€â”€ records_inserted (new data)
  â”œâ”€â”€ records_updated (changed data)
  â”œâ”€â”€ records_skipped (duplicates)
  â”œâ”€â”€ errors (list of any parsing errors)
  â”œâ”€â”€ status (success/partial/failed)
  â””â”€â”€ next_sync_scheduled_at

Alerts:
  Sync failed: P2 (retry 3x, then alert Finance Leader)
  Sync partial (>5% records errored): P3 (log + notify)
  Sync overdue (>2x expected duration): P3
  No sync in 48h (for daily sync tenants): P3
```

### File Processing Pipeline Monitoring
```
Per file, from upload to completion:
  â”œâ”€â”€ file_id
  â”œâ”€â”€ tenant_id
  â”œâ”€â”€ file_type (mis/tb/gl/paysheet/contract/pdf)
  â”œâ”€â”€ file_size_bytes
  â”œâ”€â”€ upload_completed_at
  â”œâ”€â”€ scan_started_at
  â”œâ”€â”€ scan_completed_at
  â”œâ”€â”€ scan_result (clean/infected/error)
  â”œâ”€â”€ parse_started_at
  â”œâ”€â”€ parse_completed_at
  â”œâ”€â”€ parse_result (success/partial/failed)
  â”œâ”€â”€ rows_extracted
  â”œâ”€â”€ rows_failed
  â”œâ”€â”€ ai_classification_started_at (if applicable)
  â”œâ”€â”€ ai_classification_completed_at
  â”œâ”€â”€ total_pipeline_duration_ms
  â””â”€â”€ final_status

SLA: file processing complete within 5 minutes of upload
Alert: any file >10 minutes in pipeline = P2
Alert: scan failure (ClamAV down) = P1
Alert: parse failure rate >5% in 1 hour = P2
```

---

## 16. Alerting Hierarchy

### Severity Definitions
```
P0 â€” CRITICAL (wake up now, any time):
  â”œâ”€â”€ Complete platform unavailability (>5 minutes)
  â”œâ”€â”€ Data breach confirmed or suspected
  â”œâ”€â”€ Cross-tenant data leakage (RLS failure)
  â”œâ”€â”€ Payment processing down (all gateways)
  â”œâ”€â”€ Database down or unrecoverable
  â””â”€â”€ Security incident (active attack in progress)
  Response: Immediate. Page on-call. All hands.
  SLA: Acknowledge in 5 minutes, resolve in 60 minutes

P1 â€” HIGH (fix within 1 hour, business hours override):
  â”œâ”€â”€ Significant service degradation (>20% error rate)
  â”œâ”€â”€ AI Gateway all models unavailable
  â”œâ”€â”€ File upload/processing completely broken
  â”œâ”€â”€ Authentication broken (users cannot log in)
  â”œâ”€â”€ Any OOM (out of memory) kill
  â””â”€â”€ Replication lag >60 seconds
  Response: Immediate during business hours.
  SLA: Acknowledge in 15 minutes, resolve in 4 hours

P2 â€” MEDIUM (fix within 4 hours):
  â”œâ”€â”€ Single service degraded (elevated error rate >5%)
  â”œâ”€â”€ API p99 >10 seconds
  â”œâ”€â”€ Queue depth >500 for >5 minutes
  â”œâ”€â”€ AI cost anomaly (3x normal)
  â”œâ”€â”€ Single tenant data access issue
  â””â”€â”€ ERP sync failing repeatedly
  Response: During business hours, same day.
  SLA: Acknowledge in 1 hour, resolve in 8 hours

P3 â€” LOW (fix within 24 hours):
  â”œâ”€â”€ Single endpoint slow (not platform-wide)
  â”œâ”€â”€ Dead letter queue items
  â”œâ”€â”€ Cache hit rate degraded
  â”œâ”€â”€ Non-critical background job failing
  â””â”€â”€ Log volume spike
  Response: Next business day if raised after hours.

P4 â€” INFO (no immediate action):
  â”œâ”€â”€ Successful deployments
  â”œâ”€â”€ Tenant health score changes
  â”œâ”€â”€ Scheduled maintenance reminders
  â””â”€â”€ Capacity forecast warnings (>4 weeks out)
```

### Alert Routing
```
P0: PagerDuty â†’ Founder's phone (call + SMS) + all engineers
P1: PagerDuty â†’ Founder's phone + on-call engineer
P2: Slack #platform-alerts + email to on-call
P3: Slack #platform-alerts
P4: Slack #platform-info (digest, not real-time)

ESCALATION:
  P1 not acknowledged in 15 minutes â†’ escalate to P0 treatment
  P2 not acknowledged in 1 hour â†’ escalate to P1 treatment
```

---

## 17. Vector Memory Telemetry

### Track Memory Effectiveness
```
Per tenant, per module, per week:
  â”œâ”€â”€ memory_chunks_stored (total vectors in tenant memory)
  â”œâ”€â”€ memory_retrievals_per_query (avg vectors retrieved)
  â”œâ”€â”€ memory_hit_rate (% of queries that found relevant memory)
  â”œâ”€â”€ accuracy_with_memory vs accuracy_without_memory
  â”œâ”€â”€ stage4_trigger_rate_trend (should decrease as memory builds)
  â””â”€â”€ human_correction_rate_trend (should decrease as memory builds)

LEARNING EFFECTIVENESS METRICS:
  â”œâ”€â”€ classification_accuracy_month1 vs month3 vs month6
  â”œâ”€â”€ commentary_edit_rate (how much Finance Leader edits AI drafts)
  â”œâ”€â”€ assumption_override_rate (how often Finance Leader changes AI assumptions)
  â””â”€â”€ query_first_attempt_success_rate (did NLQ answer correctly first try?)

VECTOR INDEX HEALTH:
  â”œâ”€â”€ vector_index_size_bytes per tenant
  â”œâ”€â”€ vector_search_latency_p99
  â”œâ”€â”€ embedding_generation_latency
  â””â”€â”€ Alert: index fragmentation >30% â†’ VACUUM + REINDEX
```

---

## 18. Dashboard Specifications

### Founder Master Dashboard â€” Real-Time

```
LAYOUT: 4-column grid, dark theme, auto-refresh every 10 seconds

ROW 1 â€” BUSINESS HEALTH (large KPI cards):
  MRR         ARR         NRR         Active Tenants
  $24,890     $298,680    114%        127
  â†‘2.1%       â†‘2.1%       âœ…          â†‘3 this week

ROW 2 â€” PLATFORM HEALTH (RAG status):
  API         Workers     Database    AI Gateway    Queue
  âœ… Healthy  âœ… Healthy  âœ… Healthy  âœ… Healthy    âœ… 12 jobs

ROW 3 â€” PERFORMANCE (sparklines):
  API p95 latency (24h)        Error rate (24h)
  AI pipeline avg (24h)        Queue depth (24h)

ROW 4 â€” AI & COST:
  AI cost today   Local %    Avg pipeline time   Stage 4 rate
  $184            68%        3.8s                2.9%

ROW 5 â€” TENANT HEALTH:
  ðŸŸ¢ 89 Healthy    ðŸŸ¡ 27 At Risk    ðŸ”´ 11 Critical
  [View All Tenants]

ROW 6 â€” RECENT ALERTS:
  Last 5 alerts with severity, time, status (resolved/open)
```

### Engineering Dashboard â€” Grafana

```
PANELS:
1. Request rate + error rate (time series, 24h)
2. API latency p50/p95/p99 per endpoint (heatmap)
3. Worker queue depths (all queues, real-time gauge)
4. Database connection pool utilisation
5. Redis memory + hit rate
6. AI pipeline stage timing breakdown (stacked bar)
7. Container CPU + memory per service
8. Deployment history (annotations on all graphs)
9. Error log stream (live tail from Loki)
10. Top 10 slowest queries (table, updated every 5 minutes)
```

---

## 19. Implementation in Claude Code

### Claude Code Prompt — Telemetry & Metrics

This prompt must be generated using `FINOS_EXEC_PROMPT_TEMPLATE v1.1`
(defined in `docs/platform/02_IMPLEMENTATION_PLAN.md`), including sections 7A and 9A.

```
Add to Phase 6 implementation:

TELEMETRY & METRICS IMPLEMENTATION

1. OPENTELEMETRY SETUP (backend/telemetry/setup.py)
   - Install: opentelemetry-sdk, opentelemetry-instrumentation-fastapi,
     opentelemetry-instrumentation-sqlalchemy, opentelemetry-instrumentation-redis,
     opentelemetry-instrumentation-celery, opentelemetry-exporter-otlp
   - Auto-instrument FastAPI, SQLAlchemy, Redis, Celery
   - Custom metrics: request counters, task counters, queue gauges
   - All spans include: correlation_id, tenant_id_hash, service_name

2. BUSINESS METRICS ENGINE (backend/telemetry/business_metrics.py)
   - Celery Beat job: compute_daily_business_metrics() at 00:05 UTC daily
   - Store in TimescaleDB hypertable: business_metrics_daily
   - Compute: MRR, ARR, NRR, GRR, new/churned/expansion MRR, ARPU, LTV
   - Trigger: send_daily_digest_email() after computation

3. AI PIPELINE TELEMETRY (backend/ai_gateway/telemetry.py)
   - Log every pipeline run to ai_pipeline_runs table
   - Fields: all stage timings, models used, costs, validation score,
     cache_hit, human_feedback, tokens per stage
   - Prometheus metrics: pipeline duration histogram, stage4 rate counter,
     ai_cost_gauge per model per tenant

4. TENANT HEALTH SCORING (backend/telemetry/tenant_health.py)
   - Celery Beat job: compute_all_tenant_health_scores() weekly (Monday 06:00)
   - Score 0-100 based on: login recency, credit usage %, modules used,
     report generation, team size, NPS if available
   - Store in tenant_health_scores table (history kept)
   - Trigger alerts for critical tenants (<20) to founder Slack

5. COST ATTRIBUTION (backend/telemetry/cost_attribution.py)
   - Celery Beat job: compute_tenant_cost_attribution() monthly (1st at 01:00)
   - Compute per tenant: AI cost (exact), compute cost (proportional),
     storage cost (exact from R2 API), email cost (exact from SendGrid API)
   - Store in tenant_cost_attribution table
   - Alert: if any tenant margin < 65%

6. SLA TRACKER (backend/telemetry/sla_tracker.py)
   - Incident recording: record_incident(start, end, services, tenants_affected)
   - Monthly SLA computation per tenant
   - Auto-issue SLA credits where applicable
   - SLA breach notification to tenant Finance Leader

7. PRODUCT ANALYTICS (backend/telemetry/product_events.py)
   - Event tracking endpoint: POST /api/v1/telemetry/event
   - Store in ClickHouse (or TimescaleDB initially)
   - Events: activation funnel, feature usage, friction events
   - Frontend: call tracking endpoint on key user actions

8. SECURITY TELEMETRY (backend/telemetry/security.py)
   - Middleware: detect and log anomalous access patterns
   - Login anomaly detection (new country, new device, rate)
   - Prompt injection logging with tenant context
   - Daily security score computation

9. GRAFANA DASHBOARDS (infra/grafana/dashboards/)
   - infrastructure.json (CPU, memory, network per service)
   - application.json (API latency, error rates, queue depths)
   - ai_pipeline.json (stage timings, costs, accuracy)
   - database.json (connections, query performance, index health)
   - business.json (MRR, NRR, tenant health, cost attribution)

10. FOUNDER REAL-TIME DASHBOARD (apps/web/app/platform/dashboard/)
    - WebSocket: push updates every 10 seconds
    - Panels: business KPIs, platform health, AI metrics, tenant health,
      recent alerts, cost attribution
    - Dark theme, responsive, mobile-accessible
    - Export: daily digest PDF on demand

DOCKER COMPOSE additions for local dev:
  - Prometheus (port 9090)
  - Grafana (port 3001) with all dashboards pre-loaded
  - Loki (port 3100)
  - Tempo (port 3200)
  - ClickHouse (port 8123) for product analytics
  - OTel Collector (port 4317)

All telemetry services: health checks, persistent volumes,
auto-restart on failure.
```

### Definition of Done â€” Telemetry
```
[ ] API request traced end-to-end (request â†’ DB â†’ response visible in Tempo)
[ ] Error in any service: visible in Grafana within 30 seconds
[ ] Business metrics computed: MRR + NRR correct for test data
[ ] Daily digest email received with correct metrics
[ ] Tenant health score computed and critical tenants flagged
[ ] AI pipeline run: all stage timings and costs logged correctly
[ ] Cost attribution: per-tenant cost computed within 5% accuracy
[ ] Founder dashboard: all panels load, WebSocket updates every 10s
[ ] P1 alert triggered: notification received in Slack within 2 minutes
[ ] SLA breach: credits auto-issued and tenant notified
```

---

*End of Telemetry, Scalability & Platform Metrics v1.0*
*Update this document when new services are added or alert thresholds are adjusted*

---

## 18. Partner Program Metrics

```
TRACK IN BUSINESS METRICS ENGINE (nightly computation):

PARTNER METRICS:
  â”œâ”€â”€ active_referral_partners         (count)
  â”œâ”€â”€ active_reseller_partners         (count)
  â”œâ”€â”€ referrals_this_month             (count)
  â”œâ”€â”€ referral_conversion_rate         (% referred â†’ paying)
  â”œâ”€â”€ partner_sourced_mrr              (â‚¹ MRR from partner channel)
  â”œâ”€â”€ partner_sourced_mrr_pct          (% of total MRR from partners)
  â”œâ”€â”€ avg_time_to_convert_referral     (days from referral â†’ first payment)
  â”œâ”€â”€ commission_paid_this_month       (â‚¹ total)
  â”œâ”€â”€ top_5_partners_by_revenue        (ranked list)
  â””â”€â”€ reseller_tenant_count            (tenants managed by resellers)

PARTNER HEALTH DASHBOARD (Grafana â€” business dashboard addition):
  â”œâ”€â”€ Partner channel MRR trend (30/60/90 days)
  â”œâ”€â”€ Conversion funnel (referred â†’ trial â†’ paid)
  â”œâ”€â”€ Top performing partners (by revenue contributed)
  â””â”€â”€ Commission liability (what we owe partners this month)

ALERT:
  If partner conversion rate drops below 15% for 30 days â†’ investigate
  (Either partner quality declining or onboarding broken)
```

---

## 19. Model Drift Detection

```
WHAT IS MODEL DRIFT:
  The AI model's output distribution shifts over time.
  Cause: underlying data patterns change (new industries, new GL formats)
  Effect: classification accuracy degrades slowly â€” hard to notice
  
  Detection: compare output distribution this month vs baseline month.

DRIFT METRICS TO TRACK (monthly):

1. CLASSIFICATION DISTRIBUTION:
   Track: % of GL accounts mapped to each MIS category
   Baseline: established from first 3 months of production
   Alert: if any category shifts >15% from baseline distribution
   
   Example: "Employee Cost" was 28% of all classifications.
            Now it's 41%. Something changed â€” investigate.

2. CONFIDENCE SCORE DISTRIBUTION:
   Track: histogram of Stage 2 confidence scores
   Baseline: p50/p75/p90 of confidence scores
   Alert: if p50 confidence drops >10% â†’ model becoming uncertain

3. STAGE 4 TRIGGER RATE BY CATEGORY:
   Track: which task types trigger Stage 4 most
   Baseline: 30-day rolling average per task type
   Alert: if any task type Stage 4 rate increases >3% month-over-month

4. HUMAN CORRECTION PATTERNS:
   Track: what corrections humans make (which fields, which categories)
   Analysis: if same correction made >20 times â†’ systematic error
              â†’ update training data or prompt for that pattern

DRIFT DETECTION JOB (Celery Beat â€” monthly, 5th of month):
  def detect_model_drift():
      current_distribution = compute_output_distribution(last_30_days)
      baseline = load_baseline_distribution()
      drift_score = compute_kl_divergence(current, baseline)
      
      if drift_score > DRIFT_THRESHOLD:
          send_alert(severity="P3",
              message=f"Model drift detected. Score: {drift_score:.3f}")
      
      # Update baseline every 6 months
      if months_since_baseline > 6:
          update_baseline(current_distribution)
```

---

## 20. Tenant Health Score â€” Payment Health Factor

```
ADDITION TO SECTION 10 (Tenant Health Scoring):

PAYMENT HEALTH FACTOR (add to health score algorithm):

NEGATIVE SIGNALS (payment-related):
  Failed payment in last 30 days:          -20 points
  Currently in grace period (Day 3-7):     -30 points
  Account was suspended in last 90 days:   -15 points
  Downgraded plan in last 60 days:         -10 points

POSITIVE SIGNALS (payment-related):
  Annual plan (paid upfront):              +10 points
  On-time payments 12+ consecutive months: +5 points
  Upgraded plan in last 60 days:           +5 points

PAYMENT HEALTH DASHBOARD:
  Add to existing tenant health dashboard:
  â”œâ”€â”€ Tenants in grace period (count + list)
  â”œâ”€â”€ Tenants with failed payment this month
  â”œâ”€â”€ MRR at risk (sum of MRR for grace period tenants)
  â””â”€â”€ Payment health trend (% of tenants with clean payment history)

ALERT:
  MRR at risk >10% of total MRR â†’ P2 alert to founder
  (Means too many tenants in payment trouble simultaneously)
```

---

## 21. Telemetry Retention vs Privacy â€” Reconciliation

```
CONFLICT IDENTIFIED: "permanent retention" vs GDPR/DPDP compliance.

RESOLVED POLICY:

PERMANENT RETENTION (non-PII identifiers only):
  â”œâ”€â”€ Chain hash ledger:  stores record hashes only (no PII)
  â”œâ”€â”€ AI pipeline runs:   tenant_id_hash + metrics (no PII)
  â”œâ”€â”€ Business metrics:   aggregated numbers only (no PII)
  â””â”€â”€ Security events:    hashed IDs + event type (no PII)

CONFIGURABLE RETENTION (may contain PII):
  â”œâ”€â”€ Application logs (Loki):
  â”‚     Default: 90 days hot, 1 year cold
  â”‚     On GDPR erasure request: search and redact PII from logs
  â”‚     Tenant-configurable: minimum 30 days, maximum 2 years
  â”œâ”€â”€ Product analytics (ClickHouse):
  â”‚     User IDs: SHA256 hashed before storage (not reversible)
  â”‚     On erasure request: delete all rows for that user_id_hash
  â”‚     Retention: 3 years (as defined in schema TTL)
  â””â”€â”€ Audit trail:
        Retained permanently BUT on erasure request:
        Name fields anonymised â†’ "Employee [hashed_id]"
        Financial amounts retained (legal requirement)
        Action type retained (legal requirement)

PII REDACTION PROCEDURE (on GDPR/DPDP erasure request):
  1. Delete HR personal data (name, contact, salary â€” encrypted fields)
  2. Anonymise audit trail (replace name with hashed ID)
  3. Delete product analytics rows for that user_id_hash
  4. Search and redact logs (Loki label-based deletion for user_id)
  5. Retain: financial transactions (anonymised), audit trail (anonymised)
  6. Log: erasure request completion with timestamp (ironic but required)
  
  This satisfies both:
  â”œâ”€â”€ GDPR/DPDP: right to erasure âœ…
  â””â”€â”€ Audit integrity: financial records intact âœ…
```


