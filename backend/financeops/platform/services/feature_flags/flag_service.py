from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.platform.db.models.feature_flags import CpModuleFeatureFlag
from financeops.services.audit_writer import AuditEvent, AuditWriter


_SCOPE_PRECEDENCE: dict[str, int] = {
    "entity": 0,
    "user": 1,
    "canary": 2,
    "tenant": 3,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _canary_hit(request_fingerprint: str, traffic_percent: float | None) -> bool:
    if traffic_percent is None:
        return False
    digest = hashlib.sha256(request_fingerprint.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    threshold = int(round(traffic_percent * 100))
    return bucket < threshold


async def create_feature_flag(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_id: uuid.UUID,
    flag_key: str,
    flag_value: dict,
    rollout_mode: str,
    compute_enabled: bool,
    write_enabled: bool,
    visibility_enabled: bool,
    target_scope_type: str,
    target_scope_id: uuid.UUID | None,
    traffic_percent: float | None,
    effective_from: datetime,
    effective_to: datetime | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpModuleFeatureFlag:
    target_scope_filter = (
        CpModuleFeatureFlag.target_scope_id.is_(None)
        if target_scope_id is None
        else CpModuleFeatureFlag.target_scope_id == target_scope_id
    )
    overlap_result = await session.execute(
        select(CpModuleFeatureFlag).where(
            CpModuleFeatureFlag.tenant_id == tenant_id,
            CpModuleFeatureFlag.module_id == module_id,
            CpModuleFeatureFlag.flag_key == flag_key,
            CpModuleFeatureFlag.target_scope_type == target_scope_type,
            target_scope_filter,
            or_(
                and_(CpModuleFeatureFlag.effective_to.is_(None), CpModuleFeatureFlag.effective_from < (effective_to or datetime.max.replace(tzinfo=UTC))),
                and_(CpModuleFeatureFlag.effective_to.is_not(None), CpModuleFeatureFlag.effective_to > effective_from),
            ),
        )
    )
    if overlap_result.scalars().first() is not None:
        raise ValidationError("Overlapping feature flag effective window for scope")

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpModuleFeatureFlag,
        tenant_id=tenant_id,
        record_data={
            "module_id": str(module_id),
            "flag_key": flag_key,
            "rollout_mode": rollout_mode,
            "target_scope_type": target_scope_type,
            "effective_from": effective_from.isoformat(),
        },
        values={
            "module_id": module_id,
            "flag_key": flag_key,
            "flag_value": flag_value,
            "rollout_mode": rollout_mode,
            "compute_enabled": compute_enabled,
            "write_enabled": write_enabled,
            "visibility_enabled": visibility_enabled,
            "target_scope_type": target_scope_type,
            "target_scope_id": target_scope_id,
            "traffic_percent": traffic_percent,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.feature_flag.created",
            resource_type="cp_module_feature_flag",
            new_value={"flag_key": flag_key, "rollout_mode": rollout_mode},
        ),
    )


async def evaluate_feature_flag(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_id: uuid.UUID,
    flag_key: str,
    request_fingerprint: str,
    user_id: uuid.UUID | None,
    entity_id: uuid.UUID | None,
    as_of: datetime | None = None,
) -> dict:
    check_time = as_of or _now()
    result = await session.execute(
        select(CpModuleFeatureFlag)
        .where(
            CpModuleFeatureFlag.tenant_id == tenant_id,
            CpModuleFeatureFlag.module_id == module_id,
            CpModuleFeatureFlag.flag_key == flag_key,
            CpModuleFeatureFlag.effective_from <= check_time,
            (CpModuleFeatureFlag.effective_to.is_(None) | (CpModuleFeatureFlag.effective_to > check_time)),
        )
        .order_by(CpModuleFeatureFlag.effective_from.desc())
    )
    candidates = list(result.scalars().all())

    applicable: list[CpModuleFeatureFlag] = []
    for row in candidates:
        if row.target_scope_type == "entity" and entity_id is not None and row.target_scope_id == entity_id:
            applicable.append(row)
        elif row.target_scope_type == "user" and user_id is not None and row.target_scope_id == user_id:
            applicable.append(row)
        elif row.target_scope_type == "tenant":
            applicable.append(row)
        elif row.target_scope_type == "canary" and _canary_hit(request_fingerprint, float(row.traffic_percent or 0.0)):
            applicable.append(row)

    if not applicable:
        return {
            "enabled": False,
            "compute_enabled": False,
            "write_enabled": False,
            "visibility_enabled": False,
            "selected_flag_id": None,
            "rollout_mode": "off",
        }

    applicable.sort(key=lambda item: (_SCOPE_PRECEDENCE.get(item.target_scope_type, 999), -int(item.effective_from.timestamp())))
    selected = applicable[0]
    enabled = selected.rollout_mode != "off"
    return {
        "enabled": enabled,
        "compute_enabled": bool(selected.compute_enabled and enabled),
        "write_enabled": bool(selected.write_enabled and enabled),
        "visibility_enabled": bool(selected.visibility_enabled and enabled),
        "selected_flag_id": str(selected.id),
        "rollout_mode": selected.rollout_mode,
    }
