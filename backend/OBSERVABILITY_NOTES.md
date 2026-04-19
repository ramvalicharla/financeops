# FinanceOps Observability Notes (Phase 11B)

## Scope Implemented
- Structured JSON logging with request/tenant correlation context.
- Request and correlation ID propagation via response headers.
- OpenTelemetry instrumentation bootstrap (HTTP, SQLAlchemy, Redis, Celery) behind `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Prometheus-ready API/workflow/governance/integration/AI metrics.
- Health semantics split into liveness/readiness/health:
  - `GET /live`
  - `GET /ready`
  - `GET /health`
  - plus `GET /health/live` and `GET /health/ready`
- Long-running workflow telemetry hooks for:
  - consolidation runs
  - translation runs
  - revaluation runs
  - ERP sync runs
  - close readiness runs

## Structured Log Fields
Each log line now emits JSON fields (when available):
- `timestamp`
- `level`
- `logger`
- `message`
- `event`
- `request_id`
- `correlation_id`
- `tenant_id`
- `org_entity_id`
- `service`
- `module`
- `function`
- `line`

Sensitive keys are masked by key pattern (`password`, `secret`, `token`, `api_key`, `authorization`, `credential`, `dsn`).

## Metrics Exposed
Prometheus endpoint:
- `GET /metrics`

Key metric families added/used:
- API:
  - `financeops_api_requests_total`
  - `financeops_api_errors_total`
  - `financeops_api_request_latency_ms`
- Finance workflows:
  - `financeops_finance_workflow_total`
  - `financeops_finance_workflow_duration_ms`
- ERP:
  - `financeops_erp_sync_duration_ms`
- Governance:
  - `financeops_governance_operations_total`
  - `financeops_close_readiness_failures_total`
  - `financeops_close_checklist_blockers_current`
- AI:
  - `financeops_ai_anomaly_generation_total`
  - `financeops_ai_narrative_duration_ms`
  - `financeops_ai_recommendation_failures_total`
- Alert-ready counters:
  - `financeops_auth_failures_total`
  - `financeops_upload_validation_failures_total`

Percentiles (`p50/p95/p99`) are derived from histogram queries in Prometheus/Grafana.

## Dashboards And Alerts
- Grafana dashboards under `infra/grafana/dashboards` now include FinanceOps-native latency views for:
  - API `p50/p95/p99`
  - Celery task `p95/p99`
  - finance workflow `p95/p99`
  - ERP sync `p95/p99`
  - AI pipeline and AI narrative latency
- Repo-tracked Prometheus alert rules live at:
  - `infra/prometheus/alerts/financeops-latency-alerts.yaml`
- Alert routing, contact points, and notification policies remain environment-specific and are still configured outside application code.

## Tracing
Tracing is additive and disabled unless `OTEL_EXPORTER_OTLP_ENDPOINT` is configured.

When enabled:
- FastAPI inbound request spans
- SQLAlchemy spans
- Redis spans
- Celery spans

No sensitive payloads are intentionally added to spans.

## Health/Readiness/Liveness Semantics
- `/live`: process liveness only.
- `/ready`: dependency-aware readiness (DB + Redis).
- `/health`: broader system summary (`database`, `redis`, `ai`, `queues`, `temporal`, `workers`, migrations summary).

`/ready` returns `503` when critical dependencies are unavailable.

## Failure Diagnosis Playbook
- High API latency:
  - Check `financeops_api_request_latency_ms` by method/path.
  - Correlate with `request_id`/`correlation_id` in logs.
- ERP sync failures:
  - Check `financeops_erp_sync_duration_ms` and ERP sync status logs (`workflow_failed` / `sync_run_*`).
- Consolidation/revaluation/translation failures:
  - Filter logs by `event=workflow_failed` and workflow name.
  - Inspect corresponding workflow duration/counter metrics.
- Close readiness blockers:
  - Use `financeops_close_checklist_blockers_current` and `financeops_close_readiness_failures_total`.

## Remaining Telemetry Risks
- Some legacy modules still emit plain message logs without explicit `event` naming; they remain JSON-formatted but may need richer taxonomy.
- Not every long-running workflow in every module is instrumented with start/complete/fail hooks yet.
- Alert thresholds and routing are not configured in-code (signals are emitted, alerting policy is external).
- Readiness currently checks DB/Redis only; if additional critical dependencies are introduced, readiness checks should be extended.
