from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import yaml

from prometheus_client import REGISTRY

from financeops.observability.business_metrics import (
    ai_cost_counter,
    ai_tokens_counter,
    credits_consumed_counter,
    task_queue_depth_gauge,
    workflow_completed_counter,
    workflow_started_counter,
)


def _metric_names() -> list[str]:
    return [metric.name for metric in REGISTRY.collect()]


def _counter_total(prefix: str) -> float:
    total = 0.0
    for metric in REGISTRY.collect():
        if metric.name.startswith(prefix):
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    total += float(sample.value)
    return total


def test_business_metrics_are_registered() -> None:
    """All required business metric families are registered."""
    metric_names = _metric_names()
    required = [
        "financeops_active_tenants",
        "financeops_credits_consumed",
        "financeops_ai_cost_usd",
        "financeops_ai_tokens",
        "financeops_celery_queue_depth",
        "financeops_erp_sync",
    ]
    for name in required:
        assert any(name in metric for metric in metric_names), f"Metric {name} not registered"


def test_credits_consumed_increments_counter() -> None:
    """Credits consumed metric increments."""
    before = _counter_total("financeops_credits_consumed")
    credits_consumed_counter.labels(task_type="test", tenant_type="sme").inc(5)
    after = _counter_total("financeops_credits_consumed")
    assert after > before


def test_ai_cost_counter_uses_decimal_labels() -> None:
    """AI cost metric accepts Decimal-derived increments."""
    before = _counter_total("financeops_ai_cost_usd")
    ai_cost_counter.labels(
        provider="openai",
        model="gpt-4o-mini",
        task_type="classification",
    ).inc(float(Decimal("0.000450")))
    after = _counter_total("financeops_ai_cost_usd")
    assert after > before


def test_ai_tokens_counter_increments() -> None:
    """AI token metric increments for prompt/completion labels."""
    before = _counter_total("financeops_ai_tokens")
    ai_tokens_counter.labels(provider="openai", model="gpt-4o-mini", token_type="prompt").inc(3)
    ai_tokens_counter.labels(provider="openai", model="gpt-4o-mini", token_type="completion").inc(2)
    after = _counter_total("financeops_ai_tokens")
    assert after >= before + 5


def test_queue_depth_gauge_settable() -> None:
    """Queue depth gauge can be updated per queue."""
    task_queue_depth_gauge.labels(queue_name="erp_sync").set(7)
    metric_names = _metric_names()
    assert any("financeops_celery_queue_depth" in metric for metric in metric_names)


def test_workflow_counters_increment() -> None:
    """Workflow start/complete counters are incrementable."""
    before = _counter_total("financeops_workflow_started")
    workflow_started_counter.labels(workflow_type="month_end_close").inc()
    workflow_completed_counter.labels(workflow_type="month_end_close", status="completed").inc()
    after = _counter_total("financeops_workflow_started")
    assert after > before


def test_grafana_dashboard_files_exist() -> None:
    """All five dashboard JSON files exist and are valid JSON."""
    repo_root = Path(__file__).resolve().parents[2]
    dashboard_dir = repo_root / "infra" / "grafana" / "dashboards"
    required_files = [
        "infrastructure.json",
        "application.json",
        "database.json",
        "ai_pipeline.json",
        "business.json",
    ]
    for filename in required_files:
        path = dashboard_dir / filename
        assert path.exists(), f"Missing dashboard: {filename}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "panels" in data
        assert "uid" in data


def test_grafana_dashboards_reference_financeops_latency_metrics() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    dashboard_dir = repo_root / "infra" / "grafana" / "dashboards"
    dashboard_files = [
        dashboard_dir / "infrastructure.json",
        dashboard_dir / "application.json",
        dashboard_dir / "business.json",
    ]

    financeops_latency_refs = 0
    p99_refs = 0
    for path in dashboard_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for panel in data.get("panels", []):
            for target in panel.get("targets", []):
                expr = str(target.get("expr", ""))
                if "financeops_" in expr and "_duration_ms_bucket" in expr or "financeops_api_request_latency_ms_bucket" in expr:
                    financeops_latency_refs += 1
                if "histogram_quantile(0.99" in expr:
                    p99_refs += 1

    assert financeops_latency_refs >= 4
    assert p99_refs >= 1


def test_prometheus_latency_alert_rules_exist_and_are_valid_yaml() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    rules_path = repo_root / "infra" / "prometheus" / "alerts" / "financeops-latency-alerts.yaml"
    assert rules_path.exists(), "Missing latency alert rules file"
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    groups = data.get("groups")
    assert isinstance(groups, list) and groups
    rules = groups[0].get("rules")
    assert isinstance(rules, list) and rules
    assert any("financeops_api_request_latency_ms_bucket" in str(rule.get("expr", "")) for rule in rules)


def test_provisioning_yaml_files_exist() -> None:
    """Grafana provisioning YAML files are present."""
    repo_root = Path(__file__).resolve().parents[2]
    files = [
        repo_root / "infra" / "grafana" / "provisioning" / "datasources" / "prometheus.yaml",
        repo_root / "infra" / "grafana" / "provisioning" / "datasources" / "loki.yaml",
        repo_root / "infra" / "grafana" / "provisioning" / "dashboards" / "dashboard.yaml",
    ]
    for file_path in files:
        assert file_path.exists(), f"Missing provisioning file: {file_path}"
