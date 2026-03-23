from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.config import settings
from financeops.modules.compliance.iso27001_controls import ISO27001_CONTROLS
from financeops.modules.compliance.models import ComplianceControl
from financeops.modules.compliance.soc2_service import (
    check_c1_2_erasure,
    check_cc6_2_offboarding,
    check_cc6_6_mfa,
    check_cc7_1_clamav,
    ensure_framework_controls_seeded,
    set_control_status,
)


def _overall_rag(summary: dict[str, int]) -> str:
    if summary["red"] > 0:
        return "red"
    if summary["amber"] > 0:
        return "amber"
    if summary["green"] == summary["total"] and summary["total"] > 0:
        return "green"
    return "grey"


async def check_a10_1_1_encryption(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    try:
        decoded = base64.urlsafe_b64decode(settings.FIELD_ENCRYPTION_KEY + "==")
        ok = len(decoded) == 32
        return ok, "FIELD_ENCRYPTION_KEY decodes to 32 bytes" if ok else "FIELD_ENCRYPTION_KEY invalid length"
    except Exception as exc:
        return False, f"FIELD_ENCRYPTION_KEY decode error: {exc}"


async def check_a10_1_2_key_rotation(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    try:
        from financeops.modules.secret_rotation.service import rotate_tenant_secrets  # noqa: F401

        return True, "secret rotation service importable"
    except Exception as exc:
        return False, f"secret rotation import failed: {exc}"


async def check_a12_3_1_backup(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    required = [
        Path("..") / "scripts" / "backup" / "backup_postgres.sh",
        Path("..") / "scripts" / "backup" / "restore_postgres.sh",
        Path("..") / "scripts" / "backup" / "verify_restore.sh",
        Path("..") / "scripts" / "backup" / "backup_redis.sh",
    ]
    missing = [str(path) for path in required if not path.exists()]
    ok = len(missing) == 0
    return ok, "backup scripts present" if ok else f"missing backup scripts: {', '.join(missing)}"


async def check_a12_4_1_chain_hash(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, str]:
    del session, tenant_id
    try:
        from financeops.utils.chain_hash import verify_chain  # noqa: F401

        return True, "verify_chain importable"
    except Exception as exc:
        return False, f"verify_chain import failed: {exc}"


ISO_AUTO_CHECKS = {
    "check_cc6_2_offboarding": check_cc6_2_offboarding,
    "check_cc6_6_mfa": check_cc6_6_mfa,
    "check_cc7_1_clamav": check_cc7_1_clamav,
    "check_c1_2_erasure": check_c1_2_erasure,
    "check_a10_1_1_encryption": check_a10_1_1_encryption,
    "check_a10_1_2_key_rotation": check_a10_1_2_key_rotation,
    "check_a12_3_1_backup": check_a12_3_1_backup,
    "check_a12_4_1_chain_hash": check_a12_4_1_chain_hash,
}


async def run_auto_evaluation(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
    await ensure_framework_controls_seeded(session, tenant_id, "ISO27001", ISO27001_CONTROLS)
    passed = 0
    failed = 0
    evaluated = 0
    for control in ISO27001_CONTROLS:
        check_name = control.get("auto_check_function")
        if not check_name:
            continue
        evaluated += 1
        check_fn = ISO_AUTO_CHECKS[check_name]
        ok, note = await check_fn(session, tenant_id)
        status = "pass" if ok else "fail"
        await set_control_status(
            session,
            tenant_id=tenant_id,
            framework="ISO27001",
            control_id=str(control["control_id"]),
            new_status=status,
            triggered_by="auto_evaluation",
            notes=note,
            evidence_snapshot={"check": check_name, "result": status},
        )
        if ok:
            passed += 1
        else:
            failed += 1
    return {"total": evaluated, "passed": passed, "failed": failed}


async def get_iso27001_dashboard(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    await ensure_framework_controls_seeded(session, tenant_id, "ISO27001", ISO27001_CONTROLS)
    controls = (
        await session.execute(
            select(ComplianceControl)
            .where(
                ComplianceControl.tenant_id == tenant_id,
                ComplianceControl.framework == "ISO27001",
            )
            .order_by(ComplianceControl.category, ComplianceControl.control_id)
        )
    ).scalars().all()
    summary = {"green": 0, "amber": 0, "red": 0, "grey": 0, "total": len(controls)}
    by_category: dict[str, list[dict[str, Any]]] = {}
    for control in controls:
        summary[control.rag_status] += 1
        by_category.setdefault(control.category, []).append(
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
    last_evaluated = max((c.last_evaluated_at for c in controls if c.last_evaluated_at), default=None)
    return {
        "overall_rag": _overall_rag(summary),
        "last_evaluated": last_evaluated,
        "summary": summary,
        "controls_by_category": by_category,
        "recently_failed": recently_failed,
        "upcoming_evaluations": upcoming,
    }


async def get_iso27001_evidence_package(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    dashboard = await get_iso27001_dashboard(session, tenant_id)
    controls = (
        await session.execute(
            select(ComplianceControl)
            .where(
                ComplianceControl.tenant_id == tenant_id,
                ComplianceControl.framework == "ISO27001",
            )
            .order_by(ComplianceControl.control_id)
        )
    ).scalars().all()
    tenant_hash = hashlib.sha256(str(tenant_id).encode()).hexdigest()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "framework": "ISO27001",
        "tenant_hash": tenant_hash,
        "controls": [
            {
                "control_id": c.control_id,
                "control_name": c.control_name,
                "category": c.category,
                "status": c.status,
                "rag_status": c.rag_status,
                "last_evaluated_at": c.last_evaluated_at.isoformat() if c.last_evaluated_at else None,
                "evidence_summary": c.evidence_summary,
                "tenant_hash": tenant_hash,
            }
            for c in controls
        ],
        "summary": {
            "total": dashboard["summary"]["total"],
            "green": dashboard["summary"]["green"],
            "amber": dashboard["summary"]["amber"],
            "red": dashboard["summary"]["red"],
            "grey": dashboard["summary"]["grey"],
            "overall_rag": dashboard["overall_rag"],
        },
    }


async def _policy_count(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT count(*) FROM pg_policies"))
    return int(result.scalar_one() or 0)


__all__ = [
    "check_a10_1_1_encryption",
    "check_a10_1_2_key_rotation",
    "check_a12_3_1_backup",
    "check_a12_4_1_chain_hash",
    "get_iso27001_dashboard",
    "get_iso27001_evidence_package",
    "run_auto_evaluation",
]

