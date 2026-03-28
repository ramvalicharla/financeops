from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx

from financeops.modules.erp_push.domain.schemas import PushJournalPacket, PushResult
from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import (
    RateLimitError,
    TransientError,
    with_backoff,
)

QBO_API_BASE = "https://quickbooks.api.intuit.com"
QBO_MINOR_VERSION = "75"

QBO_AUTH_INVALID_TOKEN = "QBO_AUTH_INVALID_TOKEN"
QBO_RATE_LIMIT = "QBO_RATE_LIMIT"
QBO_NETWORK = "QBO_NETWORK"
QBO_PAYLOAD_INVALID = "QBO_PAYLOAD_INVALID"
QBO_NOT_FOUND = "QBO_NOT_FOUND"


def _decimal_to_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _build_qbo_auth_header(access_token: str) -> str:
    return f"Bearer {access_token}"


def _build_qbo_journal_payload(packet: PushJournalPacket) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for idx, line in enumerate(packet.lines, start=1):
        lines.append(
            {
                "Id": str(idx),
                "LineNum": idx,
                "Description": line.narration or "",
                "Amount": _decimal_to_str(line.amount),
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit" if line.entry_type == "DEBIT" else "Credit",
                    "AccountRef": {"value": line.external_account_id},
                },
            }
        )
    return {
        "TxnDate": packet.period_date,
        "DocNumber": packet.jv_number,
        "PrivateNote": packet.description or "",
        "Line": lines,
        "CurrencyRef": {"value": packet.currency},
    }


async def push_journal_to_qbo(
    packet: PushJournalPacket,
    *,
    access_token: str,
    realm_id: str,
    simulation: bool = False,
) -> PushResult:
    payload = _build_qbo_journal_payload(packet)
    if simulation:
        return PushResult(
            success=True,
            external_journal_id=f"SIM-QBO-{packet.jv_number}",
            raw_response={"simulation": True, "payload": payload},
        )

    url = (
        f"{QBO_API_BASE}/v3/company/{realm_id}/journalentry"
        f"?minorversion={QBO_MINOR_VERSION}"
    )
    headers = {
        "Authorization": _build_qbo_auth_header(access_token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await with_backoff(
                lambda: client.post(url, headers=headers, content=json.dumps(payload)),
                context=f"QBO:push_journal:{packet.jv_id}",
            )
    except RateLimitError as exc:
        return PushResult(
            success=False,
            error_code=QBO_RATE_LIMIT,
            error_message=str(exc),
            error_category="SOFT",
        )
    except (TransientError, httpx.RequestError, httpx.TimeoutException) as exc:
        return PushResult(
            success=False,
            error_code=QBO_NETWORK,
            error_message=str(exc),
            error_category="SOFT",
        )

    if response.status_code == 401:
        return PushResult(
            success=False,
            error_code=QBO_AUTH_INVALID_TOKEN,
            error_message="QBO access token invalid",
            error_category="HARD",
        )
    if response.status_code == 404:
        return PushResult(
            success=False,
            error_code=QBO_NOT_FOUND,
            error_message=f"QBO resource not found: {response.text[:200]}",
            error_category="HARD",
        )
    if response.status_code in (400, 422):
        return PushResult(
            success=False,
            error_code=QBO_PAYLOAD_INVALID,
            error_message=f"QBO rejected payload: {response.text[:300]}",
            error_category="HARD",
        )
    if response.status_code not in (200, 201):
        return PushResult(
            success=False,
            error_code=QBO_NETWORK,
            error_message=f"Unexpected status {response.status_code}",
            error_category="SOFT",
        )

    data = response.json()
    journal = data.get("JournalEntry", {}) if isinstance(data, dict) else {}
    journal_id = journal.get("Id", "")
    return PushResult(
        success=True,
        external_journal_id=str(journal_id),
        raw_response=data if isinstance(data, dict) else {},
    )


async def get_qbo_journal_status(
    external_journal_id: str,
    *,
    access_token: str,
    realm_id: str,
) -> dict[str, Any]:
    url = (
        f"{QBO_API_BASE}/v3/company/{realm_id}/journalentry/{external_journal_id}"
        f"?minorversion={QBO_MINOR_VERSION}"
    )
    headers = {
        "Authorization": _build_qbo_auth_header(access_token),
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await with_backoff(
            lambda: client.get(url, headers=headers),
            context=f"QBO:get_journal_status:{external_journal_id}",
            max_retries=3,
        )
    return {
        "found": response.status_code == 200,
        "status_code": response.status_code,
        "data": response.json() if response.status_code == 200 else {},
    }
