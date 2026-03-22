from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.rls import set_tenant_context


async def _insert_run(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    run_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO anomaly_runs (
                id, tenant_id, chain_hash, previous_hash, created_at,
                organisation_id, reporting_period,
                anomaly_definition_version_token, pattern_rule_version_token,
                persistence_rule_version_token, correlation_rule_version_token,
                statistical_rule_version_token,
                source_metric_run_ids_json, source_variance_run_ids_json,
                source_trend_run_ids_json, source_risk_run_ids_json,
                source_reconciliation_session_ids_json,
                run_token, status, validation_summary_json, created_by
            ) VALUES (
                :id, :tenant_id, :chain_hash, :previous_hash, :created_at,
                :organisation_id, :reporting_period,
                :anomaly_definition_version_token, :pattern_rule_version_token,
                :persistence_rule_version_token, :correlation_rule_version_token,
                :statistical_rule_version_token,
                CAST(:source_metric_run_ids_json AS jsonb), CAST(:source_variance_run_ids_json AS jsonb),
                CAST(:source_trend_run_ids_json AS jsonb), CAST(:source_risk_run_ids_json AS jsonb),
                CAST(:source_reconciliation_session_ids_json AS jsonb),
                :run_token, :status, CAST(:validation_summary_json AS jsonb), :created_by
            )
            """
        ),
        {
            "id": str(run_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "0" * 64,
            "previous_hash": "0" * 64,
            "created_at": datetime.now(UTC),
            "organisation_id": str(tenant_id),
            "reporting_period": date(2026, 1, 31),
            "anomaly_definition_version_token": "def-token",
            "pattern_rule_version_token": "pattern-token",
            "persistence_rule_version_token": "persist-token",
            "correlation_rule_version_token": "corr-token",
            "statistical_rule_version_token": "stat-token",
            "source_metric_run_ids_json": f'["{uuid.uuid4()}"]',
            "source_variance_run_ids_json": f'["{uuid.uuid4()}"]',
            "source_trend_run_ids_json": "[]",
            "source_risk_run_ids_json": "[]",
            "source_reconciliation_session_ids_json": "[]",
            "run_token": f"run_{uuid.uuid4().hex}",
            "status": "completed",
            "validation_summary_json": "{}",
            "created_by": str(tenant_id),
        },
    )
    await session.flush()
    return run_id


async def _insert_alert(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    alert_status: str | None = None,
) -> uuid.UUID:
    alert_id = uuid.uuid4()
    params: dict[str, object] = {
        "id": str(alert_id),
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "chain_hash": "1" * 64,
        "previous_hash": "0" * 64,
        "created_at": datetime.now(UTC),
        "line_no": 1,
        "anomaly_code": "ANOM_TEST",
        "anomaly_name": "Anomaly Test",
        "anomaly_domain": "payroll",
        "anomaly_score": "0.850000",
        "z_score": "1.500000",
        "severity": "high",
        "persistence_classification": "first_detected",
        "correlation_flag": True,
        "materiality_elevated": False,
        "risk_elevated": False,
        "board_flag": False,
        "confidence_score": "0.900000",
        "seasonal_adjustment_flag": False,
        "seasonal_normalized_value": None,
        "benchmark_group_id": None,
        "benchmark_baseline_value": None,
        "benchmark_deviation_score": None,
        "source_summary_json": "{}",
        "created_by": str(tenant_id),
    }
    if alert_status is None:
        await session.execute(
            text(
                """
                INSERT INTO anomaly_results (
                    id, tenant_id, run_id, chain_hash, previous_hash, created_at,
                    line_no, anomaly_code, anomaly_name, anomaly_domain, anomaly_score,
                    z_score, severity, persistence_classification, correlation_flag,
                    materiality_elevated, risk_elevated, board_flag, confidence_score,
                    seasonal_adjustment_flag, seasonal_normalized_value, benchmark_group_id,
                    benchmark_baseline_value, benchmark_deviation_score, source_summary_json,
                    created_by
                ) VALUES (
                    :id, :tenant_id, :run_id, :chain_hash, :previous_hash, :created_at,
                    :line_no, :anomaly_code, :anomaly_name, :anomaly_domain, :anomaly_score,
                    :z_score, :severity, :persistence_classification, :correlation_flag,
                    :materiality_elevated, :risk_elevated, :board_flag, :confidence_score,
                    :seasonal_adjustment_flag, :seasonal_normalized_value, :benchmark_group_id,
                    :benchmark_baseline_value, :benchmark_deviation_score, CAST(:source_summary_json AS jsonb),
                    :created_by
                )
                """
            ),
            params,
        )
    else:
        await session.execute(
            text(
                """
                INSERT INTO anomaly_results (
                    id, tenant_id, run_id, chain_hash, previous_hash, created_at,
                    line_no, anomaly_code, anomaly_name, anomaly_domain, anomaly_score,
                    z_score, severity, alert_status, persistence_classification, correlation_flag,
                    materiality_elevated, risk_elevated, board_flag, confidence_score,
                    seasonal_adjustment_flag, seasonal_normalized_value, benchmark_group_id,
                    benchmark_baseline_value, benchmark_deviation_score, source_summary_json,
                    created_by
                ) VALUES (
                    :id, :tenant_id, :run_id, :chain_hash, :previous_hash, :created_at,
                    :line_no, :anomaly_code, :anomaly_name, :anomaly_domain, :anomaly_score,
                    :z_score, :severity, :alert_status, :persistence_classification, :correlation_flag,
                    :materiality_elevated, :risk_elevated, :board_flag, :confidence_score,
                    :seasonal_adjustment_flag, :seasonal_normalized_value, :benchmark_group_id,
                    :benchmark_baseline_value, :benchmark_deviation_score, CAST(:source_summary_json AS jsonb),
                    :created_by
                )
                """
            ),
            {**params, "alert_status": alert_status},
        )
    await session.flush()
    return alert_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_301_anomaly_alert_columns_exist(async_session: AsyncSession) -> None:
    rows = await async_session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='anomaly_results'
            """
        )
    )
    actual = {str(row[0]) for row in rows.all()}
    assert {
        "alert_status",
        "snoozed_until",
        "resolved_at",
        "escalated_at",
        "status_note",
        "status_updated_by",
    }.issubset(actual)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_302_alert_status_check_rejects_invalid_value(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    run_id = await _insert_run(async_session, tenant_id)
    with pytest.raises(IntegrityError):
        await _insert_alert(
            async_session,
            tenant_id=tenant_id,
            run_id=run_id,
            alert_status="INVALID_STATUS",
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_303_alert_status_defaults_to_open(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    run_id = await _insert_run(async_session, tenant_id)
    alert_id = await _insert_alert(async_session, tenant_id=tenant_id, run_id=run_id)
    await async_session.commit()

    await set_tenant_context(async_session, tenant_id)
    status_value = (
        await async_session.execute(
            text("SELECT alert_status FROM anomaly_results WHERE id = CAST(:id AS uuid)"),
            {"id": str(alert_id)},
        )
    ).scalar_one()
    assert status_value == "OPEN"
