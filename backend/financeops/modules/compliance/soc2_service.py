from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.compliance.models import ComplianceControl, ComplianceEvent
from financeops.modules.compliance.soc2_controls import SOC2_CONTROLS, SOC2Control


VALID_CONTROL_STATUSES = {"not_evaluated", "pass", "fail", "partial", "not_applicable"}
STATUS_TO_RAG = {
    "pass": "green",
    "partial": "amber",
    "fail": "red",
    "not_evaluated": "grey",
    "not_applicable": "grey",
}


def _overall_rag(summary: dict[str, int]) -> str:
    if summary["red"] > 0:
        return "red"
    if summary["amber"] > 0:
        return "amber"
    if summary["green"] == summary["total"] and summary["total"] > 0:
        return "green"
    return "grey"


async def ensure_framework_controls_seeded(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    framework: str,
    definitions: list[SOC2Control] | list[dict[str, Any]],
) -> None:
    existing_ids = set(
        (
            await session.execute(
                select(ComplianceControl.control_id).where(
                    ComplianceControl.tenant_id == tenant_id,
                    ComplianceControl.framework == framework,
                )
            )
        ).scalars().all()
    )
    for definition in definitions:
        control_id = str(definition["control_id"])
        if control_id in existing_ids:
            continue
        session.add(
            ComplianceControl(
                tenant_id=tenant_id,
                framework=framework,
                control_id=control_id,
                control_name=str(definition["control_name"]),
                control_description=str(definition["control_description"]),
                category=str(definition["category"]),
                status="not_evaluated",
                rag_status="grey",
                auto_evaluable=bool(definition["auto_evaluable"]),
            )
        )
    await session.flush()


async def _record_event(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    framework: str,
    control_id: str,
    event_type: str,
    previous_status: str | None,
    new_status: str,
    triggered_by: str,
    notes: str | None = None,
    evidence_snapshot: dict[str, Any] | None = None,
) -> ComplianceEvent:
    event = ComplianceEvent(
        tenant_id=tenant_id,
        framework=framework,
        control_id=control_id,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        evidence_snapshot=evidence_snapshot,
        triggered_by=triggered_by,
        notes=notes,
    )
    session.add(event)
    await session.flush()
    return event


async def set_control_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    framework: str,
    control_id: str,
    new_status: str,
    *,
    triggered_by: str,
    notes: str | None = None,
    evidence_snapshot: dict[str, Any] | None = None,
) -> ComplianceControl:
    if new_status not in VALID_CONTROL_STATUSES:
        raise ValueError("Invalid control status")
    control = (
        await session.execute(
            select(ComplianceControl).where(
                ComplianceControl.tenant_id == tenant_id,
                ComplianceControl.framework == framework,
                ComplianceControl.control_id == control_id,
            )
        )
    ).scalar_one_or_none()
    if control is None:
        raise ValueError("Control not found")

    previous_status = control.status
    control.status = new_status
    control.rag_status = STATUS_TO_RAG[new_status]
    control.last_evaluated_at = datetime.now(UTC)
    control.updated_at = datetime.now(UTC)
    if notes:
        control.evidence_summary = notes

    event_type = "status_changed"
    if triggered_by.startswith("manual"):
        event_type = "manual_pass" if new_status == "pass" else "manual_fail"
    await _record_event(
        session,
        tenant_id,
        framework,
        control_id,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        triggered_by=triggered_by,
        notes=notes,
        evidence_snapshot=evidence_snapshot,
    )
    await session.flush()
    return control


async def check_cc6_1_rls(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del tenant_id
    count = (
        await session.execute(
            text(
                """
                SELECT count(*)
                FROM pg_policies
                WHERE policyname = 'tenant_isolation'
                """
            )
        )
    ).scalar_one()
    ok = int(count or 0) > 0
    return ok, "RLS tenant_isolation policies found" if ok else "No tenant_isolation policy found"


async def check_cc6_2_offboarding(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    try:
        from financeops.services.user_service import offboard_user  # noqa: F401

        return True, "offboard_user importable"
    except Exception as exc:
        return False, f"offboard_user import failed: {exc}"


async def check_cc6_6_mfa(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    missing = (
        await session.execute(
            select(func.count()).select_from(IamUser).where(
                IamUser.tenant_id == tenant_id,
                IamUser.role == UserRole.finance_leader,
                IamUser.is_active.is_(True),
                IamUser.mfa_enabled.is_(False),
            )
        )
    ).scalar_one()
    ok = int(missing or 0) == 0
    return ok, "All finance leaders have MFA enabled" if ok else f"{missing} finance leader(s) missing MFA"


async def check_cc7_1_clamav(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    ok = bool(settings.CLAMAV_REQUIRED)
    return ok, "CLAMAV_REQUIRED is true" if ok else "CLAMAV_REQUIRED is false"


async def check_cc8_1_migrations(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del tenant_id
    alembic_cfg = Config("alembic.ini")
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script_dir.get_current_head()
    current_head = (await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))).scalar_one_or_none()
    ok = current_head == expected_head
    return ok, f"alembic head={current_head} expected={expected_head}"


async def check_a1_1_health(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    from financeops.main import app

    has_health_route = any(str(route.path) == "/health" for route in app.routes)
    return has_health_route, "Health route registered" if has_health_route else "/health route missing"


async def check_c1_2_erasure(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del tenant_id
    try:
        from financeops.modules.compliance.erasure_service import erase_user_pii  # noqa: F401
    except Exception as exc:
        return False, f"erase_user_pii import failed: {exc}"
    exists = (
        await session.execute(text("SELECT to_regclass('public.erasure_log')"))
    ).scalar_one_or_none()
    ok = exists is not None
    return ok, "erasure service and table present" if ok else "erasure_log table missing"


AUTO_CHECKS = {
    "check_cc6_1_rls": check_cc6_1_rls,
    "check_cc6_2_offboarding": check_cc6_2_offboarding,
    "check_cc6_6_mfa": check_cc6_6_mfa,
    "check_cc7_1_clamav": check_cc7_1_clamav,
    "check_cc8_1_migrations": check_cc8_1_migrations,
    "check_a1_1_health": check_a1_1_health,
    "check_c1_2_erasure": check_c1_2_erasure,
}


async def run_auto_evaluation(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
    await ensure_framework_controls_seeded(session, tenant_id, "SOC2", SOC2_CONTROLS)
    passed = 0
    failed = 0
    evaluated = 0
    now = datetime.now(UTC)

    for definition in SOC2_CONTROLS:
        check_name = definition.get("auto_check_function")
        if not check_name:
            continue
        evaluated += 1
        check_fn = AUTO_CHECKS[check_name]
        ok, note = await check_fn(session, tenant_id)
        status = "pass" if ok else "fail"
        rag = "green" if ok else "red"
        control = (
            await session.execute(
                select(ComplianceControl).where(
                    ComplianceControl.tenant_id == tenant_id,
                    ComplianceControl.framework == "SOC2",
                    ComplianceControl.control_id == definition["control_id"],
                )
            )
        ).scalar_one()
        previous_status = control.status
        control.status = status
        control.rag_status = rag
        control.last_evaluated_at = now
        control.next_evaluation_due = now
        control.evidence_summary = note
        control.updated_at = now
        await _record_event(
            session,
            tenant_id=tenant_id,
            framework="SOC2",
            control_id=control.control_id,
            event_type="auto_pass" if ok else "auto_fail",
            previous_status=previous_status,
            new_status=status,
            triggered_by="auto_evaluation",
            notes=note,
            evidence_snapshot={"check": check_name, "result": "pass" if ok else "fail"},
        )
        if ok:
            passed += 1
        else:
            failed += 1

    await _record_event(
        session,
        tenant_id=tenant_id,
        framework="SOC2",
        control_id="SOC2_EVALUATION",
        event_type="evaluation_run",
        previous_status=None,
        new_status="pass" if failed == 0 else "partial",
        triggered_by="auto_evaluation",
        notes=f"evaluated={evaluated} passed={passed} failed={failed}",
    )
    await session.flush()
    return {"total": evaluated, "passed": passed, "failed": failed}


async def get_soc2_dashboard(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    await ensure_framework_controls_seeded(session, tenant_id, "SOC2", SOC2_CONTROLS)
    controls = (
        await session.execute(
            select(ComplianceControl)
            .where(
                ComplianceControl.tenant_id == tenant_id,
                ComplianceControl.framework == "SOC2",
            )
            .order_by(ComplianceControl.category, ComplianceControl.control_id)
        )
    ).scalars().all()

    summary = {"green": 0, "amber": 0, "red": 0, "grey": 0, "total": len(controls)}
    controls_by_category: dict[str, list[dict[str, Any]]] = {}
    last_evaluated: datetime | None = None

    for control in controls:
        summary[control.rag_status] += 1
        controls_by_category.setdefault(control.category, []).append(
            {
                "control_id": control.control_id,
                "control_name": control.control_name,
                "status": control.status,
                "rag_status": control.rag_status,
                "auto_evaluable": control.auto_evaluable,
                "last_evaluated_at": control.last_evaluated_at,
                "evidence_summary": control.evidence_summary,
            }
        )
        if control.last_evaluated_at and (last_evaluated is None or control.last_evaluated_at > last_evaluated):
            last_evaluated = control.last_evaluated_at

    recently_failed = [
        {
            "control_id": c.control_id,
            "control_name": c.control_name,
            "last_evaluated_at": c.last_evaluated_at,
            "evidence_summary": c.evidence_summary,
        }
        for c in controls
        if c.rag_status == "red"
    ][:5]
    upcoming = [
        {
            "control_id": c.control_id,
            "control_name": c.control_name,
            "next_evaluation_due": c.next_evaluation_due,
        }
        for c in controls
        if c.next_evaluation_due is not None
    ][:10]

    return {
        "overall_rag": _overall_rag(summary),
        "last_evaluated": last_evaluated,
        "summary": summary,
        "controls_by_category": controls_by_category,
        "recently_failed": recently_failed,
        "upcoming_evaluations": upcoming,
    }


async def get_soc2_evidence_package(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    dashboard = await get_soc2_dashboard(session, tenant_id)
    controls = (
        await session.execute(
            select(ComplianceControl)
            .where(
                ComplianceControl.tenant_id == tenant_id,
                ComplianceControl.framework == "SOC2",
            )
            .order_by(ComplianceControl.control_id)
        )
    ).scalars().all()
    tenant_hash = hashlib.sha256(str(tenant_id).encode()).hexdigest()
    evidence_controls: list[dict[str, Any]] = []
    for control in controls:
        evidence_controls.append(
            {
                "control_id": control.control_id,
                "control_name": control.control_name,
                "category": control.category,
                "status": control.status,
                "rag_status": control.rag_status,
                "last_evaluated_at": control.last_evaluated_at.isoformat() if control.last_evaluated_at else None,
                "evidence_summary": control.evidence_summary,
                "tenant_hash": tenant_hash,
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "framework": "SOC2",
        "tenant_hash": tenant_hash,
        "controls": evidence_controls,
        "summary": {
            "total": dashboard["summary"]["total"],
            "green": dashboard["summary"]["green"],
            "amber": dashboard["summary"]["amber"],
            "red": dashboard["summary"]["red"],
            "grey": dashboard["summary"]["grey"],
            "overall_rag": dashboard["overall_rag"],
        },
    }

