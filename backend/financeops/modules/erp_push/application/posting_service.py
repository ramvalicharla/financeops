from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.accounting_jv import AccountingJVAggregate
from financeops.db.models.erp_push import (
    ErpPushEvent,
    ErpPushIdempotencyKey,
    ErpPushRun,
    ErrorCategory,
    PushEventType,
    PushStatus,
)
from financeops.db.models.erp_sync import ErpAccountExternalRef, ExternalConnection
from financeops.modules.accounting_layer.application.push_gate import (
    GateFailure,
    run_all_push_gates,
)
from financeops.modules.erp_push.domain.schemas import (
    PushJournalLine,
    PushJournalPacket,
    PushResult,
)


class SoftPushError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(previous_hash: str | None, content: str) -> str:
    payload = f"{previous_hash or ''}:{content}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def _next_chain(
    db: AsyncSession,
    *,
    model: type[ErpPushRun] | type[ErpPushEvent] | type[ErpPushIdempotencyKey],
    tenant_id: uuid.UUID,
    content: str,
) -> tuple[str, str]:
    result = await db.execute(
        select(model.chain_hash)
        .where(model.tenant_id == tenant_id)
        .order_by(model.created_at.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none() or ""
    return _hash(previous, content), previous


def compute_idempotency_key(packet: PushJournalPacket) -> str:
    canonical = json.dumps(
        {
            "jv_id": str(packet.jv_id),
            "jv_version": packet.jv_version,
            "connector_type": packet.connector_type,
            "jv_number": packet.jv_number,
            "lines": [
                {
                    "account_code": line.account_code,
                    "entry_type": line.entry_type,
                    "amount": str(line.amount),
                }
                for line in packet.lines
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _resolve_account_mappings(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector_type: str,
    account_codes: list[str],
) -> dict[str, str]:
    normalized_connector = connector_type.lower()
    result = await db.execute(
        select(ErpAccountExternalRef).where(
            ErpAccountExternalRef.tenant_id == tenant_id,
            func.lower(ErpAccountExternalRef.connector_type) == normalized_connector,
            ErpAccountExternalRef.internal_account_code.in_(account_codes),
            ErpAccountExternalRef.is_active.is_(True),
            ErpAccountExternalRef.is_stale.is_(False),
        )
    )
    rows = result.scalars().all()
    mapping = {row.internal_account_code: row.external_account_id for row in rows}
    missing = sorted(set(account_codes) - set(mapping.keys()))
    if missing:
        raise ValidationError(
            "Cannot push JV: account codes have no active ERP mapping for "
            f"connector '{normalized_connector}': {missing}"
        )
    return mapping


async def build_push_packet(
    db: AsyncSession,
    *,
    jv: AccountingJVAggregate,
    connector_type: str,
    tenant_id: uuid.UUID,
) -> PushJournalPacket:
    active_lines = [line for line in jv.lines if line.jv_version == jv.version]
    account_codes = sorted({line.account_code for line in active_lines})
    mapping = await _resolve_account_mappings(
        db,
        tenant_id=tenant_id,
        connector_type=connector_type,
        account_codes=account_codes,
    )
    lines = [
        PushJournalLine(
            account_code=line.account_code,
            external_account_id=mapping[line.account_code],
            entry_type=line.entry_type,
            amount=line.amount,
            currency=line.currency,
            narration=line.narration,
            tax_code=line.tax_code,
        )
        for line in active_lines
    ]

    packet = PushJournalPacket(
        jv_id=jv.id,
        jv_number=jv.jv_number,
        jv_version=jv.version,
        period_date=jv.period_date.isoformat(),
        description=jv.description,
        reference=jv.reference,
        currency=jv.currency,
        lines=lines,
        entity_id=jv.entity_id,
        connector_type=connector_type.lower(),
    )
    return packet.model_copy(update={"idempotency_key": compute_idempotency_key(packet)})


async def _append_push_event(
    db: AsyncSession,
    *,
    push_run_id: uuid.UUID,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> ErpPushEvent:
    chain_hash, previous_hash = await _next_chain(
        db,
        model=ErpPushEvent,
        tenant_id=tenant_id,
        content=f"{push_run_id}:{event_type}:{_utcnow().isoformat()}",
    )
    event = ErpPushEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
        push_run_id=push_run_id,
        jv_id=jv_id,
        event_type=event_type,
        event_data=event_data,
        occurred_at=_utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


async def _append_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv_id: uuid.UUID,
    jv_version: int,
    connection_id: uuid.UUID,
    connector_type: str,
    idempotency_key: str,
    status: str,
    attempt_number: int,
    external_journal_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    error_category: str | None = None,
    erp_response: dict[str, Any] | None = None,
    pushed_at: datetime | None = None,
) -> ErpPushRun:
    chain_hash, previous_hash = await _next_chain(
        db,
        model=ErpPushRun,
        tenant_id=tenant_id,
        content=(
            f"{jv_id}:{status}:{attempt_number}:{idempotency_key}:"
            f"{external_journal_id or ''}:{_utcnow().isoformat()}"
        ),
    )
    run = ErpPushRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
        jv_id=jv_id,
        jv_version=jv_version,
        connection_id=connection_id,
        connector_type=connector_type.lower(),
        idempotency_key=idempotency_key,
        status=status,
        external_journal_id=external_journal_id,
        error_code=error_code,
        error_message=error_message,
        error_category=error_category,
        attempt_number=attempt_number,
        erp_response=erp_response,
        pushed_at=pushed_at,
    )
    db.add(run)
    await db.flush()
    return run


async def _append_idempotency(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    jv_id: uuid.UUID,
    idempotency_key: str,
    status: str,
    push_run_id: uuid.UUID | None,
    external_journal_id: str | None = None,
) -> ErpPushIdempotencyKey:
    chain_hash, previous_hash = await _next_chain(
        db,
        model=ErpPushIdempotencyKey,
        tenant_id=tenant_id,
        content=f"{idempotency_key}:{status}:{push_run_id}:{_utcnow().isoformat()}",
    )
    row = ErpPushIdempotencyKey(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
        idempotency_key=idempotency_key,
        jv_id=jv_id,
        push_run_id=push_run_id,
        status=status,
        external_journal_id=external_journal_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _dispatch_to_connector(
    db: AsyncSession,
    *,
    packet: PushJournalPacket,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    connector_type: str,
    simulation: bool,
) -> PushResult:
    from financeops.modules.erp_sync.application.oauth_service import get_decrypted_access_token
    from financeops.modules.erp_sync.infrastructure.secret_store import secret_store

    connection = (
        await db.execute(
            select(ExternalConnection).where(
                ExternalConnection.id == connection_id,
                ExternalConnection.organisation_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise NotFoundError(f"Connection {connection_id} not found")

    creds = await secret_store.get_secret(str(connection.secret_ref or ""))
    normalized = connector_type.lower()

    if normalized == "zoho":
        from financeops.modules.erp_push.infrastructure.clients.zoho import push_journal_to_zoho

        token = await get_decrypted_access_token(
            db,
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        organization_id = str(creds.get("organization_id") or "").strip()
        return await push_journal_to_zoho(
            packet,
            access_token=token,
            organization_id=organization_id,
            simulation=simulation,
        )

    if normalized in {"qbo", "quickbooks"}:
        from financeops.modules.erp_push.infrastructure.clients.qbo import push_journal_to_qbo

        token = await get_decrypted_access_token(
            db,
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        realm_id = str(creds.get("realm_id") or "").strip()
        return await push_journal_to_qbo(
            packet,
            access_token=token,
            realm_id=realm_id,
            simulation=simulation,
        )

    if normalized == "tally":
        from financeops.modules.erp_push.infrastructure.clients.tally import push_journal_to_tally

        return await push_journal_to_tally(
            packet,
            tally_host=str(creds.get("tally_host") or "localhost"),
            tally_port=int(creds.get("tally_port") or 9000),
            simulation=simulation,
        )

    return PushResult(
        success=False,
        error_code="UNSUPPORTED_CONNECTOR",
        error_message=f"Connector '{connector_type}' does not support push",
        error_category=ErrorCategory.HARD,
    )


async def _poll_erp_for_status(
    db: AsyncSession,
    *,
    connector_type: str,
    external_journal_id: str | None,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> dict[str, Any]:
    if not external_journal_id:
        return {"found": False, "status_code": 0, "data": {}}

    from financeops.modules.erp_sync.application.oauth_service import get_decrypted_access_token
    from financeops.modules.erp_sync.infrastructure.secret_store import secret_store

    connection = (
        await db.execute(
            select(ExternalConnection).where(
                ExternalConnection.id == connection_id,
                ExternalConnection.organisation_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        return {"found": False, "status_code": 404, "data": {}}

    creds = await secret_store.get_secret(str(connection.secret_ref or ""))
    normalized = connector_type.lower()

    if normalized == "zoho":
        from financeops.modules.erp_push.infrastructure.clients.zoho import get_zoho_journal_status

        token = await get_decrypted_access_token(
            db,
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        return await get_zoho_journal_status(
            external_journal_id,
            access_token=token,
            organization_id=str(creds.get("organization_id") or "").strip(),
        )

    if normalized in {"qbo", "quickbooks"}:
        from financeops.modules.erp_push.infrastructure.clients.qbo import get_qbo_journal_status

        token = await get_decrypted_access_token(
            db,
            tenant_id=tenant_id,
            connection_id=connection_id,
        )
        return await get_qbo_journal_status(
            external_journal_id,
            access_token=token,
            realm_id=str(creds.get("realm_id") or "").strip(),
        )

    return {"found": False, "status_code": 0, "data": {}}


async def execute_push(
    db: AsyncSession,
    *,
    jv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    connector_type: str,
    simulation: bool = False,
) -> ErpPushRun:
    jv = (
        await db.execute(
            select(AccountingJVAggregate)
            .options(selectinload(AccountingJVAggregate.lines))
            .where(
                AccountingJVAggregate.id == jv_id,
                AccountingJVAggregate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if jv is None:
        raise NotFoundError(f"JV {jv_id} not found")

    try:
        await run_all_push_gates(
            db,
            jv=jv,
            connector_type=connector_type,
            tenant_id=tenant_id,
        )
    except GateFailure as exc:
        raise ValidationError(f"Pre-push gate failed [{exc.gate}]: {exc.reason}")

    packet = await build_push_packet(
        db,
        jv=jv,
        connector_type=connector_type,
        tenant_id=tenant_id,
    )

    existing_run = (
        await db.execute(
            select(ErpPushRun)
            .where(
                ErpPushRun.tenant_id == tenant_id,
                ErpPushRun.idempotency_key == packet.idempotency_key,
            )
            .order_by(ErpPushRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing_run is not None:
        if existing_run.status == PushStatus.PUSHED:
            return existing_run
        if existing_run.status == PushStatus.PUSH_IN_PROGRESS:
            poll = await _poll_erp_for_status(
                db,
                connector_type=connector_type,
                external_journal_id=existing_run.external_journal_id,
                tenant_id=tenant_id,
                connection_id=connection_id,
            )
            if poll.get("found"):
                recovered = await _append_run(
                    db,
                    tenant_id=tenant_id,
                    jv_id=jv.id,
                    jv_version=jv.version,
                    connection_id=connection_id,
                    connector_type=connector_type,
                    idempotency_key=packet.idempotency_key,
                    status=PushStatus.PUSHED,
                    attempt_number=existing_run.attempt_number + 1,
                    external_journal_id=existing_run.external_journal_id,
                    erp_response=poll.get("data", {}),
                    pushed_at=_utcnow(),
                )
                await _append_idempotency(
                    db,
                    tenant_id=tenant_id,
                    jv_id=jv.id,
                    idempotency_key=packet.idempotency_key,
                    status=PushStatus.PUSHED,
                    push_run_id=recovered.id,
                    external_journal_id=existing_run.external_journal_id,
                )
                await _append_push_event(
                    db,
                    push_run_id=recovered.id,
                    jv_id=jv.id,
                    tenant_id=tenant_id,
                    event_type=PushEventType.STATUS_POLLED,
                    event_data={"status_code": poll.get("status_code")},
                )
                await db.commit()
                return recovered

    in_progress = await _append_run(
        db,
        tenant_id=tenant_id,
        jv_id=jv.id,
        jv_version=jv.version,
        connection_id=connection_id,
        connector_type=connector_type,
        idempotency_key=packet.idempotency_key,
        status=PushStatus.PUSH_IN_PROGRESS,
        attempt_number=(existing_run.attempt_number + 1) if existing_run else 1,
    )
    await _append_idempotency(
        db,
        tenant_id=tenant_id,
        jv_id=jv.id,
        idempotency_key=packet.idempotency_key,
        status=PushStatus.PUSH_IN_PROGRESS,
        push_run_id=in_progress.id,
    )
    await _append_push_event(
        db,
        push_run_id=in_progress.id,
        jv_id=jv.id,
        tenant_id=tenant_id,
        event_type=PushEventType.PUSH_INITIATED,
        event_data={"connector_type": connector_type.lower(), "simulation": simulation},
    )
    await db.commit()

    result = await _dispatch_to_connector(
        db,
        packet=packet,
        tenant_id=tenant_id,
        connection_id=connection_id,
        connector_type=connector_type,
        simulation=simulation,
    )

    terminal_status = PushStatus.PUSHED if result.success else PushStatus.PUSH_FAILED
    terminal_run = await _append_run(
        db,
        tenant_id=tenant_id,
        jv_id=jv.id,
        jv_version=jv.version,
        connection_id=connection_id,
        connector_type=connector_type,
        idempotency_key=packet.idempotency_key,
        status=terminal_status,
        attempt_number=in_progress.attempt_number + 1,
        external_journal_id=result.external_journal_id,
        error_code=result.error_code,
        error_message=result.error_message,
        error_category=result.error_category,
        erp_response=result.raw_response,
        pushed_at=_utcnow() if result.success else None,
    )
    await _append_idempotency(
        db,
        tenant_id=tenant_id,
        jv_id=jv.id,
        idempotency_key=packet.idempotency_key,
        status=terminal_status,
        push_run_id=terminal_run.id,
        external_journal_id=result.external_journal_id,
    )
    await _append_push_event(
        db,
        push_run_id=terminal_run.id,
        jv_id=jv.id,
        tenant_id=tenant_id,
        event_type=(
            PushEventType.ERP_API_SUCCEEDED if result.success else PushEventType.ERP_API_FAILED
        ),
        event_data={
            "external_journal_id": result.external_journal_id,
            "error_code": result.error_code,
            "error_category": result.error_category,
        },
    )

    if result.success:
        await db.commit()
        return terminal_run

    if result.error_category == ErrorCategory.HARD:
        dead_letter = await _append_run(
            db,
            tenant_id=tenant_id,
            jv_id=jv.id,
            jv_version=jv.version,
            connection_id=connection_id,
            connector_type=connector_type,
            idempotency_key=packet.idempotency_key,
            status=PushStatus.DEAD_LETTER,
            attempt_number=terminal_run.attempt_number + 1,
            external_journal_id=result.external_journal_id,
            error_code=result.error_code,
            error_message=result.error_message,
            error_category=ErrorCategory.HARD,
            erp_response=result.raw_response,
        )
        await _append_idempotency(
            db,
            tenant_id=tenant_id,
            jv_id=jv.id,
            idempotency_key=packet.idempotency_key,
            status=PushStatus.DEAD_LETTER,
            push_run_id=dead_letter.id,
            external_journal_id=result.external_journal_id,
        )
        await _append_push_event(
            db,
            push_run_id=dead_letter.id,
            jv_id=jv.id,
            tenant_id=tenant_id,
            event_type=PushEventType.DEAD_LETTERED,
            event_data={"error_code": result.error_code},
        )
        await db.commit()
        return dead_letter

    await _append_push_event(
        db,
        push_run_id=terminal_run.id,
        jv_id=jv.id,
        tenant_id=tenant_id,
        event_type=PushEventType.RETRY_SCHEDULED,
        event_data={"error_code": result.error_code},
    )
    await db.commit()
    raise SoftPushError(result.error_message or "Push failed with retryable error")
