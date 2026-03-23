from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.audit import AuditTrail
from financeops.db.models.users import IamSession, IamUser
from financeops.modules.closing_checklist.models import ChecklistRunTask
from financeops.modules.compliance.gdpr_models import (
    GDPRBreachRecord,
    GDPRConsentRecord,
    GDPRDataRequest,
)
from financeops.modules.compliance.models import ComplianceEvent, ErasureLog
from financeops.modules.expense_management.models import ExpenseClaim
from financeops.tasks.celery_app import celery_app

CONSENT_TYPES = (
    "analytics",
    "marketing",
    "ai_processing",
    "data_sharing",
    "performance_monitoring",
)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def export_user_data(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> dict[str, Any]:
    user = (
        await session.execute(
            select(IamUser).where(IamUser.id == user_id, IamUser.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")

    claims = (
        await session.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.tenant_id == tenant_id,
                ExpenseClaim.submitted_by == user_id,
            )
        )
    ).scalars().all()
    checklist_tasks = (
        await session.execute(
            select(ChecklistRunTask).where(
                ChecklistRunTask.tenant_id == tenant_id,
                ChecklistRunTask.assigned_to == user_id,
            )
        )
    ).scalars().all()
    compliance_events = (
        await session.execute(
            select(ComplianceEvent).where(ComplianceEvent.tenant_id == tenant_id)
        )
    ).scalars().all()
    consent_records = (
        await session.execute(
            select(GDPRConsentRecord).where(
                GDPRConsentRecord.tenant_id == tenant_id,
                GDPRConsentRecord.user_id == user_id,
            )
        )
    ).scalars().all()
    erasure_logs = (
        await session.execute(
            select(ErasureLog).where(
                ErasureLog.tenant_id == tenant_id,
                ErasureLog.requested_by == user_id,
            )
        )
    ).scalars().all()

    payload = {
        "requested_at": datetime.now(UTC).isoformat(),
        "user": {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
            "mfa_enabled": user.mfa_enabled,
            # Intentionally exclude hashed_password and totp_secret_encrypted.
        },
        "expense_claims": [
            {
                "id": str(row.id),
                "claim_date": row.claim_date.isoformat(),
                "category": row.category,
                "amount": format(row.amount, "f"),
                "status": row.status,
            }
            for row in claims
        ],
        "checklist_tasks": [
            {
                "id": str(row.id),
                "task_name": row.task_name,
                "status": row.status,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in checklist_tasks
        ],
        "compliance_events": [
            {
                "id": str(row.id),
                "framework": row.framework,
                "control_id": row.control_id,
                "event_type": row.event_type,
                "new_status": row.new_status,
                "created_at": row.created_at.isoformat(),
            }
            for row in compliance_events
        ],
        "consent_records": [
            {
                "consent_type": row.consent_type,
                "granted": row.granted,
                "granted_at": row.granted_at.isoformat() if row.granted_at else None,
                "withdrawn_at": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
                "lawful_basis": row.lawful_basis,
            }
            for row in consent_records
        ],
        "erasure_log": [
            {
                "status": row.status,
                "user_id_hash": row.user_id_hash,
                "request_method": row.request_method,
                "created_at": row.created_at.isoformat(),
            }
            for row in erasure_logs
        ],
    }

    request = GDPRDataRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        request_type="portability",
        status="completed",
        completed_at=datetime.now(UTC),
        export_url=None,
    )
    session.add(request)
    await session.flush()
    payload["request_id"] = str(request.id)
    return payload


async def record_consent(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    consent_type: str,
    granted: bool,
    ip_address: str | None = None,
    lawful_basis: str = "consent",
) -> GDPRConsentRecord:
    existing = (
        await session.execute(
            select(GDPRConsentRecord).where(
                GDPRConsentRecord.tenant_id == tenant_id,
                GDPRConsentRecord.user_id == user_id,
                GDPRConsentRecord.consent_type == consent_type,
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is None:
        existing = GDPRConsentRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            lawful_basis=lawful_basis,
            ip_address=ip_address,
            granted_at=now if granted else None,
            withdrawn_at=now if not granted else None,
        )
        session.add(existing)
    else:
        existing.granted = granted
        existing.lawful_basis = lawful_basis
        existing.ip_address = ip_address
        existing.updated_at = now
        if granted:
            existing.granted_at = now
            existing.withdrawn_at = None
        else:
            existing.withdrawn_at = now
    await session.flush()
    return existing


async def get_consent_summary(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    total_users = (
        await session.execute(
            select(func.count()).select_from(IamUser).where(IamUser.tenant_id == tenant_id)
        )
    ).scalar_one()
    total = int(total_users or 0)
    coverage: list[dict[str, Any]] = []
    for consent_type in CONSENT_TYPES:
        granted_count = (
            await session.execute(
                select(func.count()).select_from(GDPRConsentRecord).where(
                    GDPRConsentRecord.tenant_id == tenant_id,
                    GDPRConsentRecord.consent_type == consent_type,
                    GDPRConsentRecord.granted.is_(True),
                )
            )
        ).scalar_one()
        withdrawn_count = (
            await session.execute(
                select(func.count()).select_from(GDPRConsentRecord).where(
                    GDPRConsentRecord.tenant_id == tenant_id,
                    GDPRConsentRecord.consent_type == consent_type,
                    GDPRConsentRecord.granted.is_(False),
                )
            )
        ).scalar_one()
        pct = Decimal("0")
        if total > 0:
            pct = _q4(Decimal(str(granted_count or 0)) / Decimal(str(total)))
        coverage.append(
            {
                "consent_type": consent_type,
                "granted_count": int(granted_count or 0),
                "withdrawn_count": int(withdrawn_count or 0),
                "coverage_pct": pct,
            }
        )
    return {"total_users": total, "consent": coverage}


async def record_breach(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    breach_data: dict[str, Any],
    created_by: uuid.UUID,
) -> GDPRBreachRecord:
    record = GDPRBreachRecord(
        tenant_id=tenant_id,
        breach_type=str(breach_data["breach_type"]),
        description=str(breach_data["description"]),
        affected_user_count=int(breach_data.get("affected_user_count", 0)),
        affected_data_types=list(breach_data.get("affected_data_types", [])),
        discovered_at=breach_data["discovered_at"],
        reported_to_dpa_at=breach_data.get("reported_to_dpa_at"),
        notified_users_at=breach_data.get("notified_users_at"),
        severity=str(breach_data["severity"]),
        status=str(breach_data.get("status", "open")),
        remediation_notes=breach_data.get("remediation_notes"),
        created_by=created_by,
    )
    session.add(record)
    await session.flush()

    if record.severity in {"high", "critical"} and record.affected_user_count > 0:
        celery_app.send_task(
            "gdpr.notify_dpa_reminder",
            kwargs={"tenant_id": str(tenant_id), "breach_id": str(record.id)},
            countdown=72 * 3600,
        )
    return record


async def run_retention_check(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    old_sessions = (
        await session.execute(
            select(IamSession.id).where(
                IamSession.tenant_id == tenant_id,
                IamSession.created_at < cutoff,
            )
        )
    ).scalars().all()
    purged_count = len(old_sessions)
    if purged_count:
        await session.execute(
            delete(IamSession).where(IamSession.id.in_(old_sessions))
        )

    approaching_limit = (
        await session.execute(
            select(func.count()).select_from(AuditTrail).where(
                AuditTrail.tenant_id == tenant_id,
                AuditTrail.created_at <= (now - timedelta(days=365 * 6 + 300)),
            )
        )
    ).scalar_one()
    return {
        "sessions_purged": purged_count,
        "audit_records_approaching_retention_limit": int(approaching_limit or 0),
    }


__all__ = [
    "export_user_data",
    "get_consent_summary",
    "record_breach",
    "record_consent",
    "run_retention_check",
]
