from __future__ import annotations

import argparse
import asyncio
import cProfile
import io
import json
import os
import pstats
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.append(str(Path(__file__).resolve().parents[1]))

from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    seed_active_anomaly_configuration,
    seed_upstream_for_anomaly,
)
from tests.integration.board_pack_phase1f7_helpers import (
    build_board_pack_service,
    seed_active_board_pack_configuration,
    seed_upstream_for_board_pack,
)
from tests.integration.financial_risk_phase1f5_helpers import (
    build_financial_risk_service,
    seed_active_risk_configuration,
    seed_upstream_ratio_run,
)
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    seed_finalized_normalization_pair,
)
from tests.integration.ratio_variance_phase1f4_helpers import (
    build_ratio_variance_service,
    seed_active_definition_set,
)


DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/finos_test"


@dataclass
class QueryCounter:
    count: int = 0
    db_time_ms: float = 0.0
    statement_counts: dict[str, int] | None = None
    statement_time_ms: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.statement_counts is None:
            self.statement_counts = {}
        if self.statement_time_ms is None:
            self.statement_time_ms = {}

    def before(self, conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        context._perf_query_start = time.perf_counter()

    def after(self, conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        start = getattr(context, "_perf_query_start", None)
        elapsed_ms = 0.0
        if start is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.db_time_ms += elapsed_ms
        self.count += 1
        fingerprint = " ".join(statement.split())
        if len(fingerprint) > 160:
            fingerprint = f"{fingerprint[:160]}..."
        self.statement_counts[fingerprint] = self.statement_counts.get(fingerprint, 0) + 1
        self.statement_time_ms[fingerprint] = self.statement_time_ms.get(fingerprint, 0.0) + elapsed_ms

    def top_statements(self, limit: int = 10) -> list[dict[str, Any]]:
        keys = sorted(
            self.statement_counts.keys(),
            key=lambda key: (
                -self.statement_counts.get(key, 0),
                -self.statement_time_ms.get(key, 0.0),
                key,
            ),
        )[:limit]
        return [
            {
                "statement": key,
                "count": self.statement_counts.get(key, 0),
                "db_time_ms": round(self.statement_time_ms.get(key, 0.0), 3),
            }
            for key in keys
        ]


def _profile_hotspots(label: str, fn: Callable[[], Any]) -> list[str]:
    profile = cProfile.Profile()
    profile.enable()
    fn()
    profile.disable()
    out = io.StringIO()
    stats = pstats.Stats(profile, stream=out).sort_stats("cumulative")
    stats.print_stats(20)
    lines = [line.rstrip() for line in out.getvalue().splitlines()]
    # Keep only the non-empty tail lines with function stats.
    filtered = [line for line in lines if line.strip()]
    return filtered[-20:]


@contextmanager
def _attach_query_counter(engine, counter: QueryCounter):  # noqa: ANN001
    event.listen(engine.sync_engine, "before_cursor_execute", counter.before)
    event.listen(engine.sync_engine, "after_cursor_execute", counter.after)
    try:
        yield
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", counter.before)
        event.remove(engine.sync_engine, "after_cursor_execute", counter.after)


async def _ratio_flow(session: AsyncSession) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    org_id = tenant_id
    created_by = tenant_id
    from financeops.db.rls import set_tenant_context

    await set_tenant_context(session, tenant_id)
    pair = await seed_finalized_normalization_pair(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_definition_set(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        effective_from=date(2026, 1, 1),
    )
    service = build_ratio_variance_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=created_by,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    run_id = uuid.UUID(executed["run_id"])
    summary = await service.summary(tenant_id=tenant_id, run_id=run_id)
    return {"run_id": str(run_id), "summary": summary}


async def _risk_flow(session: AsyncSession) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    org_id = tenant_id
    created_by = tenant_id
    from financeops.db.rls import set_tenant_context

    await set_tenant_context(session, tenant_id)
    ratio = await seed_upstream_ratio_run(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_risk_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        effective_from=date(2026, 1, 1),
    )
    service = build_financial_risk_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=created_by,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    run_id = uuid.UUID(executed["run_id"])
    summary = await service.summary(tenant_id=tenant_id, run_id=run_id)
    return {"run_id": str(run_id), "summary": summary}


async def _anomaly_flow(session: AsyncSession) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    org_id = tenant_id
    created_by = tenant_id
    from financeops.db.rls import set_tenant_context

    await set_tenant_context(session, tenant_id)
    upstream = await seed_upstream_for_anomaly(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_anomaly_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        effective_from=date(2026, 1, 1),
    )
    service = build_anomaly_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=created_by,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    run_id = uuid.UUID(executed["run_id"])
    summary = await service.summary(tenant_id=tenant_id, run_id=run_id)
    return {"run_id": str(run_id), "summary": summary}


async def _board_pack_flow(session: AsyncSession) -> dict[str, Any]:
    tenant_id = uuid.uuid4()
    org_id = tenant_id
    created_by = tenant_id
    from financeops.db.rls import set_tenant_context

    await set_tenant_context(session, tenant_id)
    upstream = await seed_upstream_for_board_pack(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=org_id,
        created_by=created_by,
        effective_from=date(2026, 1, 1),
    )
    service = build_board_pack_service(session)
    created = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
        created_by=created_by,
    )
    executed = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    run_id = uuid.UUID(executed["run_id"])
    summary = await service.summary(tenant_id=tenant_id, run_id=run_id)
    return {"run_id": str(run_id), "summary": summary}


async def _run_flow(
    name: str,
    session_factory: async_sessionmaker[AsyncSession],
    engine,
    flow: Callable[[AsyncSession], Any],
) -> dict[str, Any]:
    counter = QueryCounter()
    with _attach_query_counter(engine, counter):
        started = time.perf_counter()
        async with session_factory() as session:
            await session.begin()
            try:
                payload = await flow(session)
            finally:
                await session.rollback()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "name": name,
        "elapsed_ms": round(elapsed_ms, 3),
        "query_count": counter.count,
        "db_time_ms": round(counter.db_time_ms, 3),
        "top_statements": counter.top_statements(limit=8),
        "payload": payload,
    }


async def _run_hotspot_flow(*, database_url: str, flow_name: str) -> None:
    flow_map = {
        "ratio": _ratio_flow,
        "risk": _risk_flow,
        "anomaly": _anomaly_flow,
        "board_pack": _board_pack_flow,
    }
    flow = flow_map[flow_name]
    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.begin()
            try:
                await flow(session)
            finally:
                await session.rollback()
    finally:
        await engine.dispose()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, choices=["baseline", "after"])
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        flows = {
            "ratio": _ratio_flow,
            "risk": _risk_flow,
            "anomaly": _anomaly_flow,
            "board_pack": _board_pack_flow,
        }
        results: dict[str, Any] = {}
        for name, flow in flows.items():
            results[name] = await _run_flow(name, session_factory, engine, flow)

        # CPU hotspots on two heaviest flows via cProfile.
        hotspot_data: dict[str, list[str]] = {}
        for hot_name in ("anomaly", "board_pack"):
            try:
                hotspot_data[hot_name] = await asyncio.to_thread(
                    _profile_hotspots,
                    hot_name,
                    lambda name=hot_name, db=database_url: asyncio.run(  # noqa: B023
                        _run_hotspot_flow(database_url=db, flow_name=name)
                    ),
                )
            except Exception as exc:  # pragma: no cover - profiling fallback
                hotspot_data[hot_name] = [f"hotspot capture failed: {exc}"]

        output = {
            "label": args.label,
            "captured_at": datetime.now(UTC).isoformat(),
            "database_url": database_url,
            "flows": results,
            "python_hotspots": hotspot_data,
        }
        output_path = Path(__file__).resolve().parents[2] / "docs" / f"phase_2_2_profile_{args.label}.json"
        output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"output": str(output_path)}, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
